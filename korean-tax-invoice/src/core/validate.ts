/**
 * 발행 전 검증. 이 파일이 이 라이브러리의 존재 이유다.
 *
 * 세금계산서는 잘못 발행하면 되돌릴 수 없다. 국세청 수정발행 절차를 밟아야
 * 하고, 수정발행 기록 자체가 남는다. 그래서 필수값이 비었을 때 빈 문자열로
 * 채워 보내는 대신 **발행을 막는다.**
 *
 * 예외를 던지지 않고 사유 배열을 돌려주는 이유
 * --------------------------------------------
 * 차단 사유는 사람이 읽고 고쳐야 하는 정보다("대표자명이 없습니다"). 예외로
 * 던지면 첫 번째 문제만 보이고 나머지는 고친 뒤에야 드러난다. 한 번에 다
 * 보여주면 왕복이 줄고, 승인 카드나 관리자 화면에 그대로 띄울 수 있다.
 */

import type { Buyer, IssueRequest, Supplier } from './types.js'
import { isValidBusinessNumber } from './rules.js'

export type BlockReason =
  | 'missing_supplier_business_number'
  | 'invalid_supplier_business_number'
  | 'missing_supplier_name'
  | 'missing_supplier_representative'
  | 'missing_supplier_contact'
  | 'missing_buyer_business_number'
  | 'invalid_buyer_business_number'
  | 'missing_buyer_name'
  | 'missing_buyer_representative'
  | 'missing_buyer_contact'
  | 'no_items'
  | 'too_many_items'
  | 'invalid_amount'
  | 'not_verified'

export interface ValidationIssue {
  reason: BlockReason
  /** 사람이 읽을 한국어 설명. 승인 화면에 그대로 띄운다. */
  message: string
}

export type ValidationResult =
  | { ok: true }
  | { ok: false; issues: ValidationIssue[] }

/**
 * 품목 개수 상한.
 *
 * 국세청 전자세금계산서 표준이 한 건에 담을 수 있는 품목 수를 제한한다.
 * ASP 마다 조금씩 다르지만 볼타 기준 16개다. 넘으면 계산서를 나눠야 한다.
 */
const MAX_ITEMS = 16

function checkParty(
  party: Supplier | Buyer,
  role: 'supplier' | 'buyer',
  issues: ValidationIssue[],
): void {
  const 역할 = role === 'supplier' ? '공급자' : '공급받는자'
  const p = role === 'supplier' ? 'supplier' : 'buyer'

  if (!party.identificationNumber?.trim()) {
    issues.push({
      reason: `missing_${p}_business_number` as BlockReason,
      message: `${역할} 사업자등록번호가 없습니다.`,
    })
  } else if (!isValidBusinessNumber(party.identificationNumber)) {
    // 체크섬이 틀리면 오타이거나 판독 오류다. ASP 도 거절하지만 그 전에 잡는다.
    issues.push({
      reason: `invalid_${p}_business_number` as BlockReason,
      message: `${역할} 사업자등록번호가 올바르지 않습니다 (${party.identificationNumber}).`,
    })
  }

  if (!party.organizationName?.trim()) {
    issues.push({
      reason: `missing_${p}_name` as BlockReason,
      message: `${역할} 상호가 없습니다.`,
    })
  }

  if (!party.representativeName?.trim()) {
    issues.push({
      reason: `missing_${p}_representative` as BlockReason,
      message: `${역할} 대표자명이 없습니다.`,
    })
  }
}

/**
 * 발행 가능한지 검사한다.
 *
 * @param verified 사람이 거래처 정보를 확인했는가. false 면 차단한다.
 *   자동 판독(OCR·LLM)으로 채운 정보를 사람 확인 없이 발행에 쓰면 안 된다 —
 *   상호를 잘못 읽어도 알 방법이 없다.
 */
export function validateIssueRequest(
  request: IssueRequest,
  options: { verified?: boolean } = {},
): ValidationResult {
  const issues: ValidationIssue[] = []

  checkParty(request.supplier, 'supplier', issues)
  checkParty(request.buyer, 'buyer', issues)

  // 공급자 담당자는 발행 결과를 받을 주체다.
  if (!request.supplier.contact?.email?.trim()) {
    issues.push({
      reason: 'missing_supplier_contact',
      message: '공급자 담당자 이메일이 없습니다.',
    })
  }

  // 공급받는자 담당자가 없으면 계산서를 보낼 곳이 없다.
  //
  // 주의: 사업자등록증에는 이메일이 적혀 있지 않다. 판독으로는 절대 못 채우는
  // 항목이므로, 메일 발신 주소나 별도 입력에서 가져와야 한다. 이걸 놓치면
  // 다른 정보가 다 맞아도 발행이 영원히 막힌다.
  if (!request.buyer.contacts?.length || !request.buyer.contacts[0]?.email?.trim()) {
    issues.push({
      reason: 'missing_buyer_contact',
      message: '세금계산서를 받을 담당자 이메일이 없습니다. 최소 1명이 필요합니다.',
    })
  }

  if (!request.items?.length) {
    issues.push({ reason: 'no_items', message: '품목이 없습니다.' })
  } else if (request.items.length > MAX_ITEMS) {
    issues.push({
      reason: 'too_many_items',
      message: `품목은 최대 ${MAX_ITEMS}개입니다 (현재 ${request.items.length}개). 계산서를 나눠 발행하세요.`,
    })
  } else {
    const total = request.items.reduce((sum, it) => sum + (it.supplyCost ?? 0), 0)
    if (!Number.isFinite(total) || total === 0) {
      issues.push({
        reason: 'invalid_amount',
        message: '공급가액 합계가 0 이거나 올바르지 않습니다.',
      })
    }
  }

  if (options.verified === false) {
    issues.push({
      reason: 'not_verified',
      message: '거래처 정보가 아직 확인되지 않았습니다. 사람이 확인한 뒤 발행하세요.',
    })
  }

  return issues.length === 0 ? { ok: true } : { ok: false, issues }
}

/** 차단 사유를 한 덩어리 문자열로. 로그나 알림에 쓴다. */
export function formatIssues(issues: ValidationIssue[]): string {
  return issues.map((i) => `• ${i.message}`).join('\n')
}
