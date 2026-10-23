import { describe, expect, it } from 'vitest'
import { validateIssueRequest, formatIssues } from '../src/core/validate.js'
import type { IssueRequest } from '../src/core/types.js'

function makeRequest(overrides: Partial<IssueRequest> = {}): IssueRequest {
  return {
    supplier: {
      identificationNumber: '243-13-02906',
      organizationName: '널포인터스튜디오',
      representativeName: '김성구 외 1 명',
      address: '서울특별시 마포구',
      businessType: '정보통신업',
      businessItem: '응용 소프트웨어 개발 및 공급업',
      contact: { email: 'ops@example.com', name: '담당자' },
    },
    buyer: {
      identificationNumber: '220-81-62517',
      organizationName: '고객사',
      representativeName: '홍길동',
      contacts: [{ email: 'tax@client.co.kr' }],
    },
    items: [{ name: '이용료', supplyCost: 100_000 }],
    writeDate: new Date('2026-09-30T00:00:00+09:00'),
    ...overrides,
  }
}

describe('정상 요청', () => {
  it('필수값이 다 있으면 통과한다', () => {
    expect(validateIssueRequest(makeRequest())).toEqual({ ok: true })
  })
})

describe('필수값 누락은 발행을 막는다', () => {
  it('공급받는자 대표자명이 없으면 막는다', () => {
    const r = validateIssueRequest(
      makeRequest({
        buyer: { ...makeRequest().buyer, representativeName: '' },
      }),
    )
    expect(r.ok).toBe(false)
    if (r.ok) return
    expect(r.issues.some((i) => i.reason === 'missing_buyer_representative')).toBe(true)
  })

  it('담당자 이메일이 없으면 막는다', () => {
    // 사업자등록증에는 이메일이 없다. 판독으로 채울 수 없는 항목이라
    // 별도 경로로 넣어야 한다 — 이걸 놓치면 발행이 영원히 막힌다.
    const r = validateIssueRequest(
      makeRequest({ buyer: { ...makeRequest().buyer, contacts: [] } }),
    )
    expect(r.ok).toBe(false)
    if (r.ok) return
    expect(r.issues.some((i) => i.reason === 'missing_buyer_contact')).toBe(true)
  })

  it('공급자 담당자가 없으면 막는다', () => {
    const req = makeRequest()
    const r = validateIssueRequest({
      ...req,
      supplier: { ...req.supplier, contact: { email: '' } },
    })
    expect(r.ok).toBe(false)
  })

  it('사유를 한 번에 다 돌려준다', () => {
    // 예외로 던지면 첫 번째만 보이고 나머지는 고친 뒤에야 드러난다.
    const req = makeRequest()
    const r = validateIssueRequest({
      ...req,
      buyer: {
        identificationNumber: '',
        organizationName: '',
        representativeName: '',
        contacts: [],
      },
    })
    expect(r.ok).toBe(false)
    if (r.ok) return
    expect(r.issues.length).toBeGreaterThanOrEqual(4)
  })
})

describe('체크섬 검증', () => {
  it('사업자등록번호가 틀리면 막는다', () => {
    const req = makeRequest()
    const r = validateIssueRequest({
      ...req,
      buyer: { ...req.buyer, identificationNumber: '220-81-62518' },
    })
    expect(r.ok).toBe(false)
    if (r.ok) return
    expect(r.issues.some((i) => i.reason === 'invalid_buyer_business_number')).toBe(true)
  })

  it('틀린 번호를 메시지에 넣어준다', () => {
    const req = makeRequest()
    const r = validateIssueRequest({
      ...req,
      buyer: { ...req.buyer, identificationNumber: '220-81-62518' },
    })
    if (r.ok) return
    expect(formatIssues(r.issues)).toContain('220-81-62518')
  })
})

describe('품목', () => {
  it('품목이 없으면 막는다', () => {
    const r = validateIssueRequest(makeRequest({ items: [] }))
    expect(r.ok).toBe(false)
  })

  it('16개를 넘으면 막는다', () => {
    const items = Array.from({ length: 17 }, (_, i) => ({
      name: `품목 ${i}`,
      supplyCost: 1000,
    }))
    const r = validateIssueRequest(makeRequest({ items }))
    expect(r.ok).toBe(false)
    if (r.ok) return
    expect(r.issues.some((i) => i.reason === 'too_many_items')).toBe(true)
  })

  it('합계가 0 이면 막는다', () => {
    const r = validateIssueRequest(makeRequest({ items: [{ name: 'x', supplyCost: 0 }] }))
    expect(r.ok).toBe(false)
  })
})

describe('사람 확인', () => {
  it('verified=false 면 막는다', () => {
    // 자동 판독으로 채운 정보를 사람 확인 없이 발행하면 안 된다.
    const r = validateIssueRequest(makeRequest(), { verified: false })
    expect(r.ok).toBe(false)
    if (r.ok) return
    expect(r.issues.some((i) => i.reason === 'not_verified')).toBe(true)
  })

  it('verified 를 주지 않으면 그 항목은 검사하지 않는다', () => {
    // 사람 확인 개념이 없는 시스템도 쓸 수 있어야 한다.
    expect(validateIssueRequest(makeRequest())).toEqual({ ok: true })
  })
})

describe('formatIssues', () => {
  it('사람이 읽을 목록으로 만든다', () => {
    const r = validateIssueRequest(makeRequest({ items: [] }))
    if (r.ok) return
    expect(formatIssues(r.issues)).toMatch(/^• /)
  })
})
