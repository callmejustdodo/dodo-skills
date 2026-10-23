# 애플리케이션에 붙이기

스크립트가 아니라 서비스에 넣을 때의 설계. 실제 운영에서 깨졌던 지점들을
기준으로 적었다.

## 상태 전이

```
        사람 승인
PENDING ────────→ SUBMITTED ──웹훅──→ ISSUED
   │                  │
   └→ BLOCKED         └→ FAILED
```

`SUBMITTED` 를 따로 두는 것이 핵심이다. "요청했다"와 "발행됐다"를 같은 값으로
두면, 응답을 못 받은 구간에서 재요청이 나가 중복 발행이 된다.

## 프로바이더를 부르기 전에 잠근다

```ts
// 순서가 중요하다
await db.update(id, { status: 'SUBMITTED', submittedAt: new Date() })
const { issuanceKey } = await provider.submit(request, refId)
await db.update(id, { issuanceKey })
```

호출 후에 잠그면 응답을 받고 DB 쓰기 직전에 프로세스가 죽는 구간이 생긴다.
그 사이 크론이 돌면 `PENDING` 인 같은 건을 또 보낸다. 멱등성 키가 막아주긴
하지만 그건 마지막 방어선이지 설계가 아니다.

## 오류를 상태로 옮기기

```ts
try {
  const r = await provider.submit(request, refId)
  await db.update(id, { issuanceKey: r.issuanceKey })
} catch (e) {
  if (e instanceof ProviderUncertainError) {
    // 접수 여부 불명. SUBMITTED 를 유지해 재요청을 막는다.
    // FAILED 로 떨어뜨리면 사람이 "실패했으니 다시" 하다가 두 장 나간다.
    await db.update(id, { failureReason: `[접수 불명] ${e.message}` })
    alert(`관리번호 ${refId} 접수 여부 확인 필요 — 재요청 금지`)
    return
  }
  if (e instanceof ProviderRejectedError) {
    // 거절 = 접수 안 됨. 되돌려서 고칠 수 있게 한다.
    await db.update(id, { status: 'FAILED', failureReason: e.message, submittedAt: null })
    return
  }
  throw e
}
```

## 웹훅

```ts
export async function POST(req: Request) {
  // 1. 발신자 검증. 볼타는 서명이 없어 IP 로만 판정한다.
  const ip = req.headers.get('x-forwarded-for')?.split(',')[0]?.trim()
  if (!provider.verifyWebhookSender({ ip })) {
    return Response.json({ error: 'forbidden' }, { status: 403 })
  }

  const event = provider.parseWebhook(await req.json())
  if (!event) return Response.json({ ok: false })   // 모르는 이벤트

  // 2. 우리가 아는 건인지 확인
  const row = await db.findByIssuanceKey(event.issuanceKey)
  if (!row) return Response.json({ ok: false })     // 200 — 재전송해도 같다

  // 3. 상태 전이 제한. 이게 가장 중요한 방어다.
  //    IP 가 우회되더라도 이미 ISSUED 인 건을 FAILED 로 뒤집을 수 없다.
  if (row.status !== 'SUBMITTED') return Response.json({ ok: true })

  await db.update(row.id, {
    status: event.status,
    ...(event.status === 'ISSUED' ? { issuedAt: new Date() } : {}),
    ...(event.failureReason ? { failureReason: event.failureReason } : {}),
  })
  return Response.json({ ok: true })
}

// 볼타가 URL 등록 시 접근해본다. 없으면 405 가 나가 등록이 거절된다.
export function GET() {
  return Response.json({ ok: true })
}
```

### 응답 코드가 곧 재전송 정책

| 상황 | 코드 | 이유 |
|---|---|---|
| 모르는 issuanceKey | 200 | 재전송해도 같다 |
| 파싱 불가 | 200 | 재전송해도 같다 |
| DB 장애 | 500 | 재전송이 도움된다 |
| 발신자 불일치 | 403 | 조용히 넘기지 않는다 |

## 크론으로 돌릴 때

```ts
const ready = await db.findMany({ where: { status: 'PENDING' }, take: 10 })
```

`PENDING` 만 집는다. `SUBMITTED` 를 집으면 중복 발행이다.

**한 번에 처리할 건수를 제한해라.** 서버리스는 실행 시간 상한이 있고, 잘린
자리에서 무엇이 처리됐는지 모르는 상태가 최악이다.

**예외를 밖으로 던지지 마라.** 한 건 실패가 나머지를 막으면 안 된다.

## 자동 판독으로 채울 때

사업자등록증을 OCR·LLM 으로 읽어 채운다면 두 가지를 지켜라.

**상호를 그대로 믿지 마라.** 실측에서 "널포인터스튜디오"를 "별오디스튜디오",
"빌포인터스튜디오"로 읽었고 모델 확신도는 0.98~0.99 였다. 확신도는 통과 기준이
될 수 없다. 사업자등록번호는 체크섬이 있으니 그걸 조회 키로 쓰고, 상호는 기존
DB 값과 나란히 보여줘 사람이 비교하게 해라.

**PDF 는 이미지보다 정확하다.** 텍스트 레이어가 있어 OCR 을 거치지 않는다.
다만 OpenAI Vision 은 PDF 를 `image_url` 로 받지 않는다 — `file` 파트를 써야
한다. 잘못 보내면 `400 invalid_image_format` 이다.

**담당자 이메일은 등록증에 없다.** 판독으로는 절대 못 채운다. 메일 발신 주소나
별도 입력에서 가져와야 하고, 이걸 놓치면 다른 정보가 다 맞아도 발행이 영원히
막힌다.

## 사람 승인을 거칠 때

`validateIssueRequest(request, { verified })` 의 `verified` 에 "사람이 확인했다"는
사실을 넘긴다. 자동 판독 값을 사람 확인 없이 발행에 쓰면 안 된다.

승인 UI 에는 차단 사유를 그대로 띄워라. `formatIssues()` 가 사람이 읽을 목록을
만들어 준다.
