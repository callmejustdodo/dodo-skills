#!/usr/bin/env node
/**
 * 발행 전 사전 점검. 실제 발행은 하지 않는다.
 *
 * Claude 가 사용자를 대신해 돌리는 첫 번째 스크립트다. "발행하기 전에 무엇이
 * 준비됐고 무엇이 비었는지"를 한 번에 보여준다.
 *
 *   node scripts/preflight.mjs
 *
 * 확인하는 것:
 *   - API 키 존재 여부와 테스트/라이브 구분
 *   - 프로바이더 인증이 실제로 되는지 (호출해본다)
 *   - 발급자(공급자) 등록 여부와 공동인증서 만료일
 */

const API_KEY = process.env.BOLTA_API_KEY
const BASE = process.env.BOLTA_API_BASE_URL ?? 'https://xapi.bolta.io'

function line(label, value, ok) {
  const mark = ok === undefined ? ' ' : ok ? '✓' : '✗'
  console.log(`  ${mark} ${label.padEnd(24)} ${value}`)
}

async function main() {
  console.log('=== 전자세금계산서 발행 사전 점검 ===\n')

  if (!API_KEY) {
    line('API 키', 'BOLTA_API_KEY 가 없습니다', false)
    console.log('\n.env 에 키를 넣고 다시 실행하세요.')
    console.log('테스트 키는 볼타 개발자센터 > API 키 에서 만듭니다.')
    process.exit(1)
  }

  const isTest = API_KEY.startsWith('test_')
  line('API 키', `${API_KEY.slice(0, 5)}... (길이 ${API_KEY.length})`, true)
  line('환경', isTest ? '테스트 (가상 발행)' : '라이브 — 실제 국세청 발행', true)

  if (!isTest) {
    console.log('\n  ⚠️  라이브 키입니다. 발행하면 실제로 국세청에 전송됩니다.')
    console.log('     잘못 발행하면 수정발행 절차를 밟아야 하고 기록이 남습니다.')
  }

  // 인증이 실제로 되는지 호출해본다. 키가 있다는 것과 먹힌다는 것은 다르다.
  const auth = `Basic ${Buffer.from(`${API_KEY}:`).toString('base64')}`
  let issuers
  try {
    const res = await fetch(`${BASE}/v1/issuers`, { headers: { Authorization: auth } })
    if (!res.ok) {
      line('인증', `HTTP ${res.status} — 키를 확인하세요`, false)
      process.exit(1)
    }
    issuers = await res.json()
    line('인증', '성공', true)
  } catch (e) {
    line('인증', `연결 실패: ${e.message}`, false)
    process.exit(1)
  }

  console.log()
  if (!Array.isArray(issuers) || issuers.length === 0) {
    line('발급자', '등록된 발급자가 없습니다', false)
    console.log('\n  발급자를 먼저 등록해야 발행할 수 있습니다.')
    console.log('  references/bolta-setup.md 의 "발급자 등록" 절을 보세요.')
    process.exit(1)
  }

  console.log(`발급자 ${issuers.length}곳:\n`)
  const now = Date.now()
  let blocked = false

  for (const it of issuers) {
    console.log(`  ${it.organizationName} (${it.identificationNumber})`)
    console.log(`    대표자: ${it.representativeName}`)

    const cert = it.certificate
    if (!cert) {
      console.log('    인증서: ✗ 미등록 — 발행 불가')
      blocked = true
      continue
    }

    const expires = new Date(cert.expiresAt)
    const daysLeft = Math.floor((expires.getTime() - now) / 86_400_000)
    const mark = daysLeft < 0 ? '✗ 만료됨' : daysLeft < 30 ? '⚠ 곧 만료' : '✓'
    console.log(`    인증서: ${mark} ${expires.toISOString().slice(0, 10)} (${daysLeft}일 남음)`)
    if (daysLeft < 0) blocked = true
  }

  console.log()
  if (blocked) {
    console.log('발행 불가 — 위 항목을 먼저 해결하세요.')
    process.exit(1)
  }
  console.log('발행 준비 완료.')
}

main().catch((e) => {
  console.error('실패:', e.message)
  process.exit(1)
})
