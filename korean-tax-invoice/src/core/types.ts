/**
 * 전자세금계산서 발행 프로바이더 인터페이스.
 *
 * 한국의 전자세금계산서는 국세청에 직접 쏘는 게 아니라 ASP 사업자를 거친다.
 * 볼타·팝빌·바로빌 등이 그 자리에 있고, 필드 이름과 응답 모양이 제각각이다.
 * 이 인터페이스는 그 차이를 한 겹 덮어 호출부가 프로바이더를 몰라도 되게 한다.
 *
 * 지금 구현된 것은 볼타뿐이다. 나머지는 이 인터페이스를 채우면 된다 —
 * 구현하지 않은 프로바이더를 있는 척 두지 않는다.
 *
 * 설계에서 양보하지 않은 것 두 가지
 * ---------------------------------
 * 1. 접수와 발행을 구분한다. 대부분의 ASP 는 발행 요청을 *접수*하고 결과는
 *    나중에 웹훅으로 준다. 이 둘을 같은 상태로 두면, 응답을 못 받은 구간에서
 *    재요청이 나가 같은 계산서가 두 장 발행된다.
 *
 * 2. "접수 안 됨"과 "모름"을 구분한다. 4xx 는 거절이라 재요청이 안전하고,
 *    타임아웃은 접수 여부를 알 수 없어 재요청이 위험하다. 이 구분을 놓치면
 *    중복 발행이 난다. 세금계산서 중복 발행은 국세청 수정발행 절차 대상이고
 *    기록이 남는다.
 */

/** 영수(RECEIPT) — 대금을 이미 받음 / 청구(CLAIM) — 앞으로 받을 것 */
export type InvoicePurpose = 'RECEIPT' | 'CLAIM'

/** 과세 / 영세율 / 면세 */
export type TaxType = 'TAXABLE' | 'ZERO_RATE' | 'TAX_FREE'

/** 거래 당사자(공급자·공급받는자 공통). */
export interface Party {
  /** 사업자등록번호. 하이픈 유무는 구현이 알아서 맞춘다. */
  identificationNumber: string
  /** 상호(법인명). */
  organizationName: string
  /**
   * 대표자 성명.
   *
   * 공동대표는 사업자등록증 표기를 그대로 쓴다("홍길동 외 1명").
   * 국세청 예규 부가가치세과-1158(2011.09.27), 부가가치세과-23(2012.01.09):
   * "사업자등록증상에 기재된 대표자 명의로" 발급한다.
   */
  representativeName: string
  address?: string
  /** 업태 (예: 정보통신업) */
  businessType?: string
  /**
   * 종목 (예: 응용 소프트웨어 개발 및 공급업)
   *
   * 업태와 헷갈리기 쉽다. 사업자등록증에서 업태 아래 줄이 종목이다.
   */
  businessItem?: string
}

/** 세금계산서 안내메일을 받을 담당자. */
export interface Contact {
  email: string
  name?: string
  telephone?: string
}

/** 공급자는 담당자가 필수다 — 발행 결과를 받을 주체가 있어야 한다. */
export interface Supplier extends Party {
  contact: Contact
}

/** 공급받는자. 담당자가 여럿일 수 있다(실무자·대표 등). */
export interface Buyer extends Party {
  contacts: Contact[]
}

export interface InvoiceItem {
  name: string
  /** 거래일자. 생략하면 작성일자를 쓴다. */
  date?: Date
  unitPrice?: number
  quantity?: number
  /** 공급가액(세액 제외). */
  supplyCost: number
  /** 세액. 생략하면 taxType 에 따라 계산한다. */
  tax?: number
}

export interface IssueRequest {
  supplier: Supplier
  buyer: Buyer
  items: InvoiceItem[]
  /**
   * 작성일자. 발행일이 아니라 세금계산서에 적히는 날짜다.
   *
   * 반드시 한국 시간 기준으로 만들어라. 서버가 UTC 면 자정 근처에서 하루가
   * 밀리고, 그러면 과세기간이 갈린다. formatKstDate() 를 쓰면 된다.
   */
  writeDate: Date
  purpose?: InvoicePurpose
  taxType?: TaxType
  description?: string
}

/** 접수 성공. 발행이 끝난 게 아니라 "접수됐다"는 뜻이다. */
export interface SubmitResult {
  /** 프로바이더가 이 요청에 매긴 식별자. 상태 조회와 웹훅 대조에 쓴다. */
  issuanceKey: string
}

/** 발행 상태. 프로바이더별 상태값을 이 다섯 가지로 정규화한다. */
export type IssuanceStatus =
  /** 접수됐고 결과를 기다린다. 이 상태에서 재요청하지 않는다. */
  | 'SUBMITTED'
  /** 발행 완료. */
  | 'ISSUED'
  /** 발행 실패. 사유를 확인하고 고쳐서 다시 시도한다. */
  | 'FAILED'
  /** 취소됨. */
  | 'CANCELLED'
  /** 프로바이더가 모르는 요청. */
  | 'UNKNOWN'

export interface StatusResult {
  status: IssuanceStatus
  /** 국세청 승인번호. 발행 완료 후에만 존재한다. */
  ntsConfirmNum?: string
  /** 실패 사유. */
  failureReason?: string
  /** 발행된 세금계산서를 볼 수 있는 주소. */
  invoiceUrl?: string
}

/** 웹훅 페이로드를 정규화한 결과. */
export interface WebhookEvent {
  issuanceKey: string
  status: IssuanceStatus
  ntsConfirmNum?: string
  failureReason?: string
  invoiceUrl?: string
}

/**
 * 프로바이더가 거절했다. 요청이 접수되지 않았으므로 고쳐서 다시 보내도 된다.
 */
export class ProviderRejectedError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
  ) {
    super(message)
    this.name = 'ProviderRejectedError'
  }
}

/**
 * 응답을 받지 못했다. 접수됐는지 알 수 없다.
 *
 * **재요청하지 마라.** 상태 조회로 확인해야 한다. 이 구분이 없으면
 * "실패했으니 다시" 하다가 같은 계산서가 두 장 나간다.
 */
export class ProviderUncertainError extends Error {
  constructor(
    message: string,
    readonly clientReferenceId: string,
    readonly cause?: unknown,
  ) {
    super(message)
    this.name = 'ProviderUncertainError'
  }
}

/**
 * 전자세금계산서 프로바이더.
 *
 * 새 프로바이더를 붙이려면 이 인터페이스를 구현하고
 * src/providers/<이름>/ 아래에 두면 된다.
 */
export interface TaxInvoiceProvider {
  /** 프로바이더 이름. 로그와 오류 메시지에 쓴다. */
  readonly name: string

  /**
   * 테스트 키인지 확인한다.
   *
   * 실제 발행은 되돌릴 수 없으므로, 검증 스크립트는 이걸 먼저 확인하고
   * 라이브 키면 중단해야 한다.
   */
  isTestKey(): boolean

  /**
   * 발행을 접수한다.
   *
   * @param clientReferenceId 멱등성 키. 같은 값으로 다시 보내면 프로바이더가
   *   중복을 막아준다. 재시도할 때도 같은 값을 써야 한다 — 새로 만들면
   *   멱등성이 깨진다.
   * @throws {ProviderRejectedError} 거절됨. 재요청 안전.
   * @throws {ProviderUncertainError} 응답 없음. 재요청 금지.
   */
  submit(request: IssueRequest, clientReferenceId: string): Promise<SubmitResult>

  /** 발행 상태를 조회한다. 웹훅이 오지 않을 때 쓴다. */
  getStatus(issuanceKey: string): Promise<StatusResult>

  /**
   * 웹훅 페이로드를 정규화한다.
   *
   * 우리 이벤트가 아니면 null 을 돌려준다.
   */
  parseWebhook(payload: unknown): WebhookEvent | null

  /**
   * 웹훅 발신자를 검증한다.
   *
   * 서명을 주는 프로바이더도 있고 IP 만 공개하는 곳도 있다. 무엇으로
   * 검증하는지는 구현이 안다.
   */
  verifyWebhookSender(input: WebhookSenderInput): boolean
}

export interface WebhookSenderInput {
  /** 발신 IP. x-forwarded-for 의 맨 앞 값. */
  ip?: string | null
  /** 원문 바디. 서명 검증에 필요하다. */
  rawBody?: string
  headers?: Record<string, string | null | undefined>
}
