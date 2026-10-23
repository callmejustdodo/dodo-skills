/**
 * korean-tax-invoice
 *
 * 한국 전자세금계산서 발행을 안전하게 다루는 라이브러리 + Claude Code 스킬.
 *
 * 이 라이브러리가 막아주는 것
 * ---------------------------
 * 세금계산서는 잘못 발행하면 되돌릴 수 없다. 국세청 수정발행 절차를 밟아야
 * 하고 기록이 남는다. 그래서 세 가지를 강제한다.
 *
 *   1. 필수값이 비면 발행하지 않는다 (빈 문자열로 채워 보내지 않는다)
 *   2. 접수와 발행을 구분한다 (SUBMITTED ≠ ISSUED)
 *   3. "거절됨"과 "모름"을 구분한다 (후자는 재요청 금지)
 *
 * 세 번째가 중복 발행을 막는 핵심이다.
 */

export * from './core/types.js'
export * from './core/rules.js'
export * from './core/validate.js'
export { BoltaProvider, BOLTA_WEBHOOK_IPS, type BoltaOptions } from './providers/bolta/index.js'
