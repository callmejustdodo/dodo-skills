/**
 * 볼타(Bolta) 프로바이더 구현.
 *
 * 문서: https://docs.bolta.io/llms.txt
 *
 * 볼타를 먼저 구현한 이유는 REST + Basic 인증이라 SDK 가 필요 없고, 테스트
 * 키로 실제 발행 흐름을 그대로 돌려볼 수 있어서다.
 *
 * 실측으로 알아낸 것들 (문서만 봐서는 놓치는 것들)
 * ------------------------------------------------
 * - 종목 필드는 `businessItem` 이다. `businessClass` 로 보내면 볼타가 조용히
 *   버린다 — 오류도 없이 종목 없는 계산서가 나간다. 선택 필드라 그렇다.
 * - 공급자 `manager` 는 필수다. 문서에는 선택처럼 보이지만 없으면 거절된다.
 * - 같은 clientReferenceId 로 다른 내용을 보내면 400 이다(멱등성 위반).
 * - 웹훅에 서명이 없다. 발신 IP 로만 검증할 수 있다.
 * - 웹훅 발송 시간: 테스트 키 10~30초, 라이브 키 약 10분.
 */

import {
  ProviderRejectedError,
  ProviderUncertainError,
  type IssueRequest,
  type IssuanceStatus,
  type StatusResult,
  type SubmitResult,
  type TaxInvoiceProvider,
  type WebhookEvent,
  type WebhookSenderInput,
} from '../../core/types.js'
import { calculateTax, formatKstDate, normalizeBusinessNumber } from '../../core/rules.js'

const DEFAULT_BASE_URL = 'https://xapi.bolta.io'

/**
 * 볼타 웹훅 발신 IP. 문서 기준, 테스트·라이브 공통.
 *
 * 볼타 웹훅에는 서명이 없어서 이게 사실상의 인증이다.
 */
export const BOLTA_WEBHOOK_IPS = ['43.201.136.252'] as const

interface BoltaParty {
  identificationNumber: string
  organizationName: string
  representativeName: string
  address?: string
  businessType?: string
  /** 종목. businessClass 가 아니다 — 틀리면 조용히 버려진다. */
  businessItem?: string
}

interface BoltaManager {
  email: string
  name?: string
  telephone?: string
}

interface BoltaIssuePayload {
  supplier: BoltaParty & { manager: BoltaManager }
  supplied: BoltaParty & { managers: BoltaManager[] }
  items: {
    name: string
    date: string
    unitPrice?: number
    quantity?: number
    supplyCost: number
    tax: number | null
  }[]
  date: string
  purpose: string
  taxType: string
  description?: string
}

export interface BoltaOptions {
  apiKey?: string
  baseUrl?: string
  timeoutMs?: number
  /** 테스트에서 주입한다. */
  fetchImpl?: typeof fetch
}

export class BoltaProvider implements TaxInvoiceProvider {
  readonly name = 'bolta'

  private readonly apiKey: string
  private readonly baseUrl: string
  private readonly timeoutMs: number
  private readonly doFetch: typeof fetch

  constructor(options: BoltaOptions = {}) {
    const key = options.apiKey ?? process.env.BOLTA_API_KEY
    if (!key) {
      throw new Error(
        'BOLTA_API_KEY 가 없습니다. 테스트는 test_ 로 시작하는 키를 사용하세요.',
      )
    }
    this.apiKey = key
    this.baseUrl = options.baseUrl ?? process.env.BOLTA_API_BASE_URL ?? DEFAULT_BASE_URL
    this.timeoutMs = options.timeoutMs ?? 30_000
    this.doFetch = options.fetchImpl ?? fetch
  }

  isTestKey(): boolean {
    return this.apiKey.startsWith('test_')
  }

  private authHeader(): string {
    // 볼타는 API 키를 username 으로 쓰고 password 는 빈 값이다.
    return `Basic ${Buffer.from(`${this.apiKey}:`).toString('base64')}`
  }

  private toParty(p: {
    identificationNumber: string
    organizationName: string
    representativeName: string
    address?: string
    businessType?: string
    businessItem?: string
  }): BoltaParty {
    return {
      identificationNumber: normalizeBusinessNumber(p.identificationNumber),
      organizationName: p.organizationName,
      representativeName: p.representativeName,
      ...(p.address ? { address: p.address } : {}),
      ...(p.businessType ? { businessType: p.businessType } : {}),
      ...(p.businessItem ? { businessItem: p.businessItem } : {}),
    }
  }

  private buildPayload(req: IssueRequest): BoltaIssuePayload {
    const writeDate = formatKstDate(req.writeDate)
    const taxType = req.taxType ?? 'TAXABLE'

    return {
      supplier: {
        ...this.toParty(req.supplier),
        // manager 는 필수다. 문서에는 선택처럼 보이지만 없으면 거절된다.
        manager: {
          email: req.supplier.contact.email,
          ...(req.supplier.contact.name ? { name: req.supplier.contact.name } : {}),
          ...(req.supplier.contact.telephone
            ? { telephone: req.supplier.contact.telephone }
            : {}),
        },
      },
      supplied: {
        ...this.toParty(req.buyer),
        managers: req.buyer.contacts.map((c) => ({
          email: c.email,
          ...(c.name ? { name: c.name } : {}),
          ...(c.telephone ? { telephone: c.telephone } : {}),
        })),
      },
      items: req.items.map((it) => ({
        name: it.name,
        date: formatKstDate(it.date ?? req.writeDate),
        ...(it.unitPrice !== undefined ? { unitPrice: it.unitPrice } : {}),
        ...(it.quantity !== undefined ? { quantity: it.quantity } : {}),
        supplyCost: it.supplyCost,
        // TAX_FREE 는 반드시 null 이어야 한다. 0 을 보내면 거절된다.
        tax: taxType === 'TAX_FREE' ? null : (it.tax ?? calculateTax(it.supplyCost, taxType)),
      })),
      date: writeDate,
      purpose: req.purpose ?? 'CLAIM',
      taxType,
      ...(req.description ? { description: req.description } : {}),
    }
  }

  async submit(request: IssueRequest, clientReferenceId: string): Promise<SubmitResult> {
    const payload = this.buildPayload(request)

    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), this.timeoutMs)

    let res: Response
    try {
      res = await this.doFetch(`${this.baseUrl}/v1/taxInvoices/issue`, {
        method: 'POST',
        headers: {
          Authorization: this.authHeader(),
          'Content-Type': 'application/json',
          'Bolta-Client-Reference-Id': clientReferenceId,
        },
        body: JSON.stringify(payload),
        signal: controller.signal,
      })
    } catch (error) {
      // 네트워크 오류·타임아웃: 접수됐는지 알 수 없다.
      // 재요청하면 중복 발행 위험이 있으므로 별도 오류로 구분한다.
      throw new ProviderUncertainError(
        '볼타 응답을 받지 못했습니다. 재요청하지 말고 관리번호로 조회하세요.',
        clientReferenceId,
        error,
      )
    } finally {
      clearTimeout(timer)
    }

    if (!res.ok) {
      const text = await res.text().catch(() => '')
      let message = text.slice(0, 300)
      let code: string | undefined
      try {
        const j = JSON.parse(text) as { message?: string; code?: string }
        message = j.message ?? message
        code = j.code
      } catch {
        // 본문이 JSON 이 아니면 원문을 그대로 쓴다.
      }

      if (res.status >= 500) {
        // 5xx 는 볼타 내부 오류다. 접수됐는지 알 수 없다.
        throw new ProviderUncertainError(
          `볼타 서버 오류(${res.status}). 재요청하지 말고 조회하세요: ${message}`,
          clientReferenceId,
        )
      }

      throw new ProviderRejectedError(message || `볼타 오류 ${res.status}`, res.status, code)
    }

    const body = (await res.json()) as { issuanceKey?: string }
    if (!body.issuanceKey) {
      // 200 인데 키가 없다 — 접수 여부가 불분명하다.
      throw new ProviderUncertainError(
        '볼타가 issuanceKey 를 주지 않았습니다. 조회로 확인하세요.',
        clientReferenceId,
      )
    }

    return { issuanceKey: body.issuanceKey }
  }

  async getStatus(issuanceKey: string): Promise<StatusResult> {
    const res = await this.doFetch(`${this.baseUrl}/v1/taxInvoices/${issuanceKey}`, {
      headers: { Authorization: this.authHeader() },
    })

    if (res.status === 404) return { status: 'UNKNOWN' }
    if (!res.ok) {
      const text = await res.text().catch(() => '')
      throw new ProviderRejectedError(text.slice(0, 300), res.status)
    }

    const body = (await res.json()) as {
      status?: string
      ntsConfirmNum?: string
      taxInvoiceUrl?: string
      cause?: { message?: string; code?: string }
    }

    return {
      status: mapStatus(body.status),
      ...(body.ntsConfirmNum ? { ntsConfirmNum: body.ntsConfirmNum } : {}),
      ...(body.taxInvoiceUrl ? { invoiceUrl: body.taxInvoiceUrl } : {}),
      ...(body.cause?.message ? { failureReason: body.cause.message } : {}),
    }
  }

  /**
   * 관리번호(clientReferenceId)로 처리 상태를 조회한다.
   *
   * **접수 여부가 불분명할 때는 이걸 써라.** getStatus() 가 쓰는
   * `/v1/taxInvoices/{issuanceKey}` 는 "발행 완료된 것"만 돌려주므로,
   * 접수는 됐지만 아직 발행 전인 건은 404 가 난다. 그걸 "접수 안 됨"으로
   * 오해하고 재요청하면 중복 발행이다.
   *
   * ProviderUncertainError 를 받았을 때 issuanceKey 가 없을 수도 있는데,
   * 관리번호는 우리가 만든 값이라 항상 있다. 그래서 이 경로가 필요하다.
   */
  async getStatusByReferenceId(clientReferenceId: string): Promise<StatusResult> {
    // 관리번호는 쿼리 파라미터다. 헤더로 보내면 500 이 온다(실측).
    const url = new URL(`${this.baseUrl}/v1/taxInvoices/issue/status`)
    url.searchParams.set('clientReferenceId', clientReferenceId)

    const res = await this.doFetch(url.toString(), {
      headers: { Authorization: this.authHeader() },
    })

    if (res.status === 404) return { status: 'UNKNOWN' }

    // 없는 관리번호는 400 + INVALID_REQUEST 로 온다(실측). 이건 오류가
    // 아니라 "접수되지 않았다"는 답이다. 예외로 던지면 호출부가 조회 실패로
    // 오해하고, 접수 여부를 모르는 채로 남는다 — 그 상태가 가장 위험하다.
    if (res.status === 400) {
      const text = await res.text().catch(() => '')
      if (text.includes('존재하지 않는') || text.includes('INVALID_REQUEST')) {
        return { status: 'UNKNOWN' }
      }
      throw new ProviderRejectedError(text.slice(0, 300), res.status)
    }

    if (!res.ok) {
      const text = await res.text().catch(() => '')
      throw new ProviderRejectedError(text.slice(0, 300), res.status)
    }
    // 이 엔드포인트의 응답은 발행 조회와 모양이 다르다. 실측(2026-09):
    //
    //   { "clientReferenceId": "...", "issuanceKey": "IssuanceKey_...",
    //     "message": "요청이 처리되었습니다. 성공/실패 여부는 발행된
    //                 세금계산서를 통해 확인해주세요." }
    //
    // message 는 상태값이 아니라 안내문이다. 판정 기준은 issuanceKey 의
    // 존재 여부다 — 있으면 접수된 것이고, 없으면 접수되지 않은 것이다.
    // 발행 성공/실패는 여기서 알 수 없고 getStatus() 나 웹훅으로 확인한다.
    const body = (await res.json()) as {
      issuanceKey?: string
      clientReferenceId?: string
      message?: string
    }

    if (!body.issuanceKey) return { status: 'UNKNOWN' }

    // message 를 failureReason 에 넣지 않는다 — 실패가 아닌데 실패처럼 읽힌다.
    return { status: 'SUBMITTED' }
  }

  parseWebhook(payload: unknown): WebhookEvent | null {
    if (!payload || typeof payload !== 'object') return null
    const p = payload as {
      eventType?: string
      data?: {
        issuanceKey?: string
        taxInvoiceUrl?: string
        cause?: { code?: string; message?: string }
      }
    }

    const key = p.data?.issuanceKey
    if (!key) return null

    if (p.eventType === 'TAX_INVOICE_ISSUANCE_SUCCESS') {
      return {
        issuanceKey: key,
        status: 'ISSUED',
        ...(p.data?.taxInvoiceUrl ? { invoiceUrl: p.data.taxInvoiceUrl } : {}),
      }
    }

    if (p.eventType === 'TAX_INVOICE_ISSUANCE_FAILURE') {
      const cause = p.data?.cause
      return {
        issuanceKey: key,
        status: 'FAILED',
        failureReason: cause
          ? `${cause.message ?? '발행 실패'}${cause.code ? ` (${cause.code})` : ''}`
          : '발행 실패 (사유 없음)',
      }
    }

    // 우리가 모르는 이벤트 타입. 볼타가 나중에 추가할 수 있다.
    return null
  }

  verifyWebhookSender(input: WebhookSenderInput): boolean {
    // 볼타 웹훅에는 서명이 없다(2026-09 문서 확인). IP 로만 검증한다.
    //
    // x-forwarded-for 는 맨 앞만 본다. 뒤쪽은 프록시라 신뢰할 수 없고,
    // 클라이언트가 헤더를 위조해도 대부분의 호스팅이 실제 값을 앞에 덧붙인다.
    const ip = (input.ip ?? '').split(',')[0]?.trim()
    if (!ip) return false
    return (BOLTA_WEBHOOK_IPS as readonly string[]).includes(ip)
  }
}

function mapStatus(raw?: string): IssuanceStatus {
  switch ((raw ?? '').toUpperCase()) {
    case 'ISSUED':
    case 'SUCCESS':
    case 'DONE':
      return 'ISSUED'
    case 'FAILED':
    case 'FAILURE':
    case 'ERROR':
      return 'FAILED'
    case 'CANCELLED':
    case 'CANCELED':
      return 'CANCELLED'
    case 'PENDING':
    case 'SUBMITTED':
    case 'PROCESSING':
      return 'SUBMITTED'
    default:
      return 'UNKNOWN'
  }
}
