import { describe, expect, it, vi } from 'vitest'
import { BoltaProvider } from '../src/providers/bolta/index.js'
import { ProviderRejectedError, ProviderUncertainError } from '../src/core/types.js'
import type { IssueRequest } from '../src/core/types.js'

function makeRequest(overrides: Partial<IssueRequest> = {}): IssueRequest {
  return {
    supplier: {
      identificationNumber: '243-13-02906',
      organizationName: '널포인터스튜디오',
      representativeName: '김성구 외 1 명',
      businessType: '정보통신업',
      businessItem: '응용 소프트웨어 개발 및 공급업',
      contact: { email: 'ops@example.com' },
    },
    buyer: {
      identificationNumber: '220-81-62517',
      organizationName: '고객사',
      representativeName: '홍길동',
      contacts: [{ email: 'tax@client.co.kr' }],
    },
    items: [{ name: '이용료', supplyCost: 100_000 }],
    writeDate: new Date('2026-09-29T15:00:00Z'), // KST 09-30
    ...overrides,
  }
}

function okFetch(body: unknown) {
  return vi.fn(async () => ({
    ok: true,
    status: 200,
    json: async () => body,
    text: async () => JSON.stringify(body),
  })) as unknown as typeof fetch
}

function errFetch(status: number, body: string) {
  return vi.fn(async () => ({
    ok: false,
    status,
    json: async () => JSON.parse(body),
    text: async () => body,
  })) as unknown as typeof fetch
}


/** fetch 목이 실제로 보낸 요청을 꺼낸다. */
function sentRequest(f: typeof fetch): { url: string; init: RequestInit & { headers: Record<string, string>; body: string } } {
  const calls = (f as unknown as { mock: { calls: [string, RequestInit][] } }).mock.calls
  const [url, init] = calls[0]!
  return { url, init: init as never }
}

/** 보낸 본문을 파싱한다. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function sentBody(f: typeof fetch): any {
  return JSON.parse(sentRequest(f).init.body)
}

function makeProvider(fetchImpl: typeof fetch, apiKey = 'test_abc') {
  return new BoltaProvider({ apiKey, fetchImpl })
}

describe('환경 구분', () => {
  it('test_ 키를 테스트로 판정한다', () => {
    expect(makeProvider(okFetch({}), 'test_x').isTestKey()).toBe(true)
  })

  it('live_ 키를 라이브로 판정한다', () => {
    // 이 판정이 틀리면 실제 발행이 테스트인 줄 알고 나간다.
    expect(makeProvider(okFetch({}), 'live_x').isTestKey()).toBe(false)
  })

  it('키가 없으면 생성 자체를 거부한다', () => {
    const saved = process.env.BOLTA_API_KEY
    delete process.env.BOLTA_API_KEY
    expect(() => new BoltaProvider()).toThrow(/BOLTA_API_KEY/)
    if (saved) process.env.BOLTA_API_KEY = saved
  })
})

describe('페이로드', () => {
  it('종목을 businessItem 으로 보낸다', async () => {
    // businessClass 로 보내면 볼타가 조용히 버린다 — 선택 필드라 오류도 없다.
    const f = okFetch({ issuanceKey: 'K' })
    await makeProvider(f).submit(makeRequest(), 'ref-1')

    const body = sentBody(f)
    expect(body.supplier.businessItem).toBe('응용 소프트웨어 개발 및 공급업')
    expect(body.supplier.businessClass).toBeUndefined()
  })

  it('작성일자를 KST 로 만든다', async () => {
    // UTC 로 계산하면 09-29 가 되어 과세기간이 갈린다.
    const f = okFetch({ issuanceKey: 'K' })
    await makeProvider(f).submit(makeRequest(), 'ref-1')

    const body = sentBody(f)
    expect(body.date).toBe('2026-09-30')
  })

  it('공급자 담당자를 manager 로 넣는다', async () => {
    // 문서상 선택처럼 보이지만 없으면 거절된다.
    const f = okFetch({ issuanceKey: 'K' })
    await makeProvider(f).submit(makeRequest(), 'ref-1')

    const body = sentBody(f)
    expect(body.supplier.manager.email).toBe('ops@example.com')
  })

  it('면세는 세액을 null 로 보낸다', async () => {
    // 0 을 보내면 거절된다.
    const f = okFetch({ issuanceKey: 'K' })
    await makeProvider(f).submit(makeRequest({ taxType: 'TAX_FREE' }), 'ref-1')

    const body = sentBody(f)
    expect(body.items[0].tax).toBeNull()
  })

  it('멱등성 키를 헤더로 보낸다', async () => {
    const f = okFetch({ issuanceKey: 'K' })
    await makeProvider(f).submit(makeRequest(), 'ref-abc')

    const { init } = sentRequest(f)
    expect(init.headers['Bolta-Client-Reference-Id']).toBe('ref-abc')
  })
})

describe('오류 구분 — 중복 발행 방지의 핵심', () => {
  it('4xx 는 거절로 던진다 (재요청 안전)', async () => {
    const f = errFetch(400, '{"message":"필수값 누락","code":"INVALID"}')
    await expect(makeProvider(f).submit(makeRequest(), 'ref-1')).rejects.toBeInstanceOf(
      ProviderRejectedError,
    )
  })

  it('5xx 는 불확실로 던진다 (재요청 금지)', async () => {
    // 접수됐는지 알 수 없다. 재요청하면 중복 발행이다.
    const f = errFetch(500, '{"message":"서버 오류"}')
    await expect(makeProvider(f).submit(makeRequest(), 'ref-1')).rejects.toBeInstanceOf(
      ProviderUncertainError,
    )
  })

  it('네트워크 실패는 불확실로 던진다', async () => {
    const f = vi.fn(async () => {
      throw new Error('ECONNRESET')
    }) as unknown as typeof fetch
    await expect(makeProvider(f).submit(makeRequest(), 'ref-1')).rejects.toBeInstanceOf(
      ProviderUncertainError,
    )
  })

  it('200 인데 키가 없으면 불확실로 던진다', async () => {
    const f = okFetch({})
    await expect(makeProvider(f).submit(makeRequest(), 'ref-1')).rejects.toBeInstanceOf(
      ProviderUncertainError,
    )
  })

  it('불확실 오류는 관리번호를 들고 있다', async () => {
    // 조회로 접수 여부를 확인하려면 이 값이 필요하다.
    const f = errFetch(503, '{}')
    await makeProvider(f)
      .submit(makeRequest(), 'ref-xyz')
      .catch((e) => {
        expect((e as ProviderUncertainError).clientReferenceId).toBe('ref-xyz')
      })
  })
})

describe('웹훅', () => {
  const provider = makeProvider(okFetch({}))

  it('성공 이벤트를 ISSUED 로 정규화한다', () => {
    const e = provider.parseWebhook({
      eventType: 'TAX_INVOICE_ISSUANCE_SUCCESS',
      data: { issuanceKey: 'K', taxInvoiceUrl: 'https://x' },
    })
    expect(e).toMatchObject({ issuanceKey: 'K', status: 'ISSUED', invoiceUrl: 'https://x' })
  })

  it('실패 이벤트에 사유를 담는다', () => {
    const e = provider.parseWebhook({
      eventType: 'TAX_INVOICE_ISSUANCE_FAILURE',
      data: {
        issuanceKey: 'K',
        cause: { code: 'NOT_FOUND_CERTIFICATE', message: '공동인증서가 없습니다.' },
      },
    })
    expect(e?.status).toBe('FAILED')
    expect(e?.failureReason).toContain('공동인증서')
    expect(e?.failureReason).toContain('NOT_FOUND_CERTIFICATE')
  })

  it('모르는 이벤트는 null', () => {
    expect(provider.parseWebhook({ eventType: 'NEW', data: { issuanceKey: 'K' } })).toBeNull()
  })

  it('issuanceKey 가 없으면 null', () => {
    expect(provider.parseWebhook({ eventType: 'TAX_INVOICE_ISSUANCE_SUCCESS' })).toBeNull()
  })

  it('볼타 IP 만 통과시킨다', () => {
    // 볼타 웹훅에는 서명이 없다. IP 가 사실상의 인증이다.
    expect(provider.verifyWebhookSender({ ip: '43.201.136.252' })).toBe(true)
    expect(provider.verifyWebhookSender({ ip: '1.2.3.4' })).toBe(false)
    expect(provider.verifyWebhookSender({ ip: null })).toBe(false)
  })

  it('x-forwarded-for 는 맨 앞만 본다', () => {
    // 뒤쪽은 프록시라 신뢰할 수 없다.
    expect(provider.verifyWebhookSender({ ip: '1.2.3.4, 43.201.136.252' })).toBe(false)
    expect(provider.verifyWebhookSender({ ip: '43.201.136.252, 1.2.3.4' })).toBe(true)
  })
})
