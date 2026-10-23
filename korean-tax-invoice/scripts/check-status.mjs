#!/usr/bin/env node
/**
 * 발행 상태 조회.
 *
 * 웹훅이 오지 않을 때, 또는 접수 여부가 불분명할 때 쓴다. 재요청 대신
 * **반드시 이걸 먼저** 돌려야 한다 — 접수된 건을 다시 보내면 중복 발행이다.
 *
 *   node scripts/check-status.mjs <issuanceKey>
 *   node scripts/check-status.mjs --ref <관리번호>
 *
 * 어느 쪽을 쓸지
 * -------------
 * issuanceKey 조회는 **발행 완료된 것만** 돌려준다. 접수는 됐지만 아직
 * 발행 전이면 404 가 나는데, 그걸 "접수 안 됨"으로 오해하고 재요청하면
 * 중복 발행이다.
 *
 * 접수 여부가 궁금하면 --ref 로 관리번호를 조회해라. 관리번호는 우리가
 * 만든 값이라 응답을 못 받았을 때도 항상 손에 있다.
 */

import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

// dist 가 없으면 import 가 ERR_MODULE_NOT_FOUND 로 죽는다. 스킬로 설치한
// 직후 가장 먼저 밟는 지뢰라, 스택 트레이스 대신 할 일을 알려준다.
const root = join(dirname(fileURLToPath(import.meta.url)), '..')
if (!existsSync(join(root, 'dist'))) {
  console.error('빌드가 필요합니다:\n')
  console.error('  npm install && npm run build\n')
  console.error('(스크립트가 dist/ 를 사용합니다. 최초 1회만 하면 됩니다.)')
  process.exit(1)
}

const { BoltaProvider } = await import('../dist/providers/bolta/index.js')

const args = process.argv.slice(2)
const refMode = args.includes('--ref')
const key = args.find((a) => !a.startsWith('--'))

if (!key) {
  console.error('사용법:')
  console.error('  node scripts/check-status.mjs <issuanceKey>')
  console.error('  node scripts/check-status.mjs --ref <관리번호>')
  process.exit(1)
}

const LABEL = {
  SUBMITTED: '접수됨 — 결과 대기 중 (재요청하지 마세요)',
  ISSUED: '발행 완료',
  FAILED: '발행 실패',
  CANCELLED: '취소됨',
  UNKNOWN: '조회되지 않습니다',
}

async function main() {
  const provider = new BoltaProvider()
  const r = refMode
    ? await provider.getStatusByReferenceId(key)
    : await provider.getStatus(key)

  console.log(`조회 기준: ${refMode ? '관리번호' : 'issuanceKey'} ${key}`)
  console.log(`상태: ${r.status} — ${LABEL[r.status] ?? ''}`)
  if (r.ntsConfirmNum) console.log(`국세청 승인번호: ${r.ntsConfirmNum}`)
  if (r.invoiceUrl) console.log(`세금계산서: ${r.invoiceUrl}`)
  if (r.failureReason) console.log(`실패 사유: ${r.failureReason}`)

  if (r.status === 'UNKNOWN' && !refMode) {
    console.log('\nissuanceKey 조회는 발행 완료된 건만 돌려줍니다.')
    console.log('접수 여부를 확인하려면 관리번호로 조회하세요:')
    console.log('  node scripts/check-status.mjs --ref <관리번호>')
  }
  if (r.status === 'UNKNOWN' && refMode) {
    console.log('\n접수되지 않았습니다. 다시 발행을 시도해도 됩니다.')
  }
  if (r.status === 'ISSUED' && !r.ntsConfirmNum) {
    console.log('\n국세청 승인번호가 없는 것은 테스트 키(가상 발행)이기 때문입니다.')
  }
}

main().catch((e) => {
  console.error('실패:', e.message)
  process.exit(1)
})
