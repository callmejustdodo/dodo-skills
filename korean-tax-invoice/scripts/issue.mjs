#!/usr/bin/env node
/**
 * 세금계산서 발행. 실제로 나간다.
 *
 * Claude 가 이 스크립트를 돌리기 전에 반드시 사용자에게 내용을 보여주고
 * 확인받아야 한다 — 발행은 되돌릴 수 없다.
 *
 *   node scripts/issue.mjs <요청파일.json>
 *   node scripts/issue.mjs <요청파일.json> --confirm    실제 발행
 *
 * --confirm 없이 돌리면 검증만 하고 무엇을 보낼지 보여준다. 이게 기본값인
 * 이유는 명확하다: 실수로 실행됐을 때 아무 일도 일어나지 않아야 한다.
 *
 * 요청 파일 형식은 examples/request.json 을 보라.
 */

import { readFileSync } from 'node:fs'

import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

// dist 가 없으면 import 가 ERR_MODULE_NOT_FOUND 로 죽는다. 스킬로 설치한
// 직후 가장 먼저 밟는 지뢰라, 스택 트레이스 대신 할 일을 알려준다.
// ESM 정적 import 는 코드 실행 전에 해석되므로 동적 import 를 쓴다.
const root = join(dirname(fileURLToPath(import.meta.url)), '..')
if (!existsSync(join(root, 'dist'))) {
  console.error('빌드가 필요합니다:\n')
  console.error('  npm install && npm run build\n')
  console.error('(스크립트가 dist/ 를 사용합니다. 최초 1회만 하면 됩니다.)')
  process.exit(1)
}

const { validateIssueRequest, formatIssues } = await import('../dist/core/validate.js')
const {
  buildClientReferenceId,
  formatBusinessNumber,
  formatKstDate,
} = await import('../dist/core/rules.js')
const { BoltaProvider } = await import('../dist/providers/bolta/index.js')
const { ProviderRejectedError, ProviderUncertainError } = await import('../dist/core/types.js')

const args = process.argv.slice(2)
const file = args.find((a) => !a.startsWith('--'))
const CONFIRM = args.includes('--confirm')

if (!file) {
  console.error('사용법: node scripts/issue.mjs <요청파일.json> [--confirm]')
  process.exit(1)
}

function money(n) {
  return n.toLocaleString('ko-KR')
}

async function main() {
  const raw = JSON.parse(readFileSync(file, 'utf8'))

  // writeDate 는 JSON 에서 문자열로 온다.
  //
  // 생략하면 오늘(KST)로 채운다. 예제 파일에 고정 날짜를 박아두면 시간이
  // 지나 미래 날짜가 되고, 볼타가 "작성일자는 현재 날짜와 같거나 이전이어야
  // 합니다" 로 거절한다 — 예제가 문서의 경고를 그대로 위반하게 된다.
  const request = {
    ...raw,
    writeDate: raw.writeDate ? new Date(raw.writeDate) : new Date(),
    items: (raw.items ?? []).map((it) => ({
      ...it,
      ...(it.date ? { date: new Date(it.date) } : {}),
    })),
  }

  // 1) 검증 — 프로바이더를 부르기 전에 우리가 먼저 막는다.
  const check = validateIssueRequest(request, { verified: raw.verified })
  if (!check.ok) {
    console.log('발행할 수 없습니다:\n')
    console.log(formatIssues(check.issues))
    console.log('\n위 항목을 채운 뒤 다시 실행하세요.')
    process.exit(1)
  }

  const supplyCost = request.items.reduce((s, i) => s + i.supplyCost, 0)
  const tax = request.items.reduce(
    (s, i) => s + (i.tax ?? Math.round(i.supplyCost * 0.1)),
    0,
  )

  console.log('=== 발행 내용 ===\n')
  console.log(`  공급자     ${request.supplier.organizationName} (${formatBusinessNumber(request.supplier.identificationNumber)})`)
  console.log(`  공급받는자 ${request.buyer.organizationName} (${formatBusinessNumber(request.buyer.identificationNumber)})`)
  console.log(`  대표자     ${request.buyer.representativeName}`)
  console.log(`  받는사람   ${request.buyer.contacts.map((c) => c.email).join(', ')}`)
  // 화면에도 KST 로 보여준다. toISOString() 을 쓰면 UTC 라 하루 밀려 보이고,
  // 실제로 보내는 값(볼타 페이로드)과 화면이 어긋난다.
  console.log(`  작성일자   ${formatKstDate(request.writeDate)}`)
  console.log()
  for (const it of request.items) {
    console.log(`  · ${it.name}  ${money(it.supplyCost)}원`)
  }
  console.log()
  console.log(`  공급가액   ${money(supplyCost)}원`)
  console.log(`  세액       ${money(tax)}원`)
  console.log(`  합계       ${money(supplyCost + tax)}원`)

  // 키가 없어도 검증 결과는 끝까지 보여준다. 여기서 BoltaProvider 를 먼저
  // 만들면 생성자가 던져서 "환경" 줄도 못 찍고 중간에 잘린 것처럼 보인다.
  const key = process.env.BOLTA_API_KEY
  const env = !key
    ? '키 없음 — 발행할 수 없습니다'
    : key.startsWith('test_')
      ? '테스트 (가상)'
      : '라이브 — 실제 국세청 발행'
  console.log(`\n  환경       ${env}`)

  if (!CONFIRM) {
    console.log('\n검증만 했습니다. 실제로 발행하려면 --confirm 을 붙이세요.')
    if (!key) {
      console.log('발행하려면 BOLTA_API_KEY 가 필요합니다.')
    }
    return
  }

  const provider = new BoltaProvider()

  // 멱등성 키. 같은 invoiceId 면 항상 같은 값이라 재시도해도 중복되지 않는다.
  const refId = buildClientReferenceId(raw.referencePrefix ?? 'kti', raw.invoiceId)
  console.log(`\n관리번호: ${refId}`)

  try {
    const result = await provider.submit(request, refId)
    console.log(`\n접수 완료: ${result.issuanceKey}`)
    console.log('\n※ "접수"이지 "발행 완료"가 아닙니다.')
    console.log('   결과는 웹훅으로 오거나, 상태 조회로 확인할 수 있습니다:')
    console.log(`   node scripts/check-status.mjs ${result.issuanceKey}`)
  } catch (e) {
    if (e instanceof ProviderUncertainError) {
      // 여기가 중복 발행이 나는 자리다.
      console.error('\n접수 여부를 알 수 없습니다.')
      console.error(`  ${e.message}`)
      console.error('\n  ⚠️  다시 실행하지 마세요. 같은 계산서가 두 장 발행될 수 있습니다.')
      console.error(`  관리번호로 조회해서 접수됐는지 먼저 확인하세요: ${refId}`)
      process.exit(2)
    }
    if (e instanceof ProviderRejectedError) {
      // 거절 = 접수 안 됨. 고쳐서 다시 보내도 된다.
      console.error(`\n거절됨 (HTTP ${e.status}): ${e.message}`)
      console.error('  접수되지 않았으므로 내용을 고쳐 다시 시도할 수 있습니다.')
      process.exit(1)
    }
    throw e
  }
}

main().catch((e) => {
  console.error('실패:', e.message)
  process.exit(1)
})
