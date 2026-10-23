# korean-tax-invoice

한국 전자세금계산서 발행 라이브러리 + Claude Code 스킬.
중복 발행과 잘못된 발행을 **구조로** 막는다.

> npm 에는 아직 올리지 않았다. 지금은 클론해서 쓴다.

```bash
git clone https://github.com/sdkfile/korean-tax-invoice
cd korean-tax-invoice && npm install && npm run build
```

## 왜 이게 필요한가

세금계산서는 잘못 발행하면 되돌릴 수 없다. 국세청 수정발행 절차를 밟아야 하고
기록이 남는다. 그런데 대부분의 연동 코드는 이걸 일반 API 호출처럼 다룬다.

실제로 터지는 지점은 세 군데다.

**타임아웃 후 재시도.** ASP 가 응답을 안 주면 보통 재시도한다. 그런데 요청은
이미 접수됐을 수 있다. 같은 계산서가 두 장 나간다.

**작성일자 하루 밀림.** 서버가 UTC 면 KST 자정 근처에서 전날이 찍힌다. 작성일자는
과세기간을 가르는 값이라 월말 발행분이 전월로 넘어가면 부가세 신고가 어긋난다.

**필수값 누락을 빈 문자열로.** 대표자명이 없다고 `""` 를 보내면 ASP 가 받아주는
경우가 있다. 그대로 국세청에 간다.

이 라이브러리는 세 가지를 강제한다.

```
1. 필수값이 비면 발행하지 않는다        → validateIssueRequest()
2. 접수와 발행을 구분한다               → SUBMITTED ≠ ISSUED
3. "거절됨"과 "모름"을 구분한다          → 후자는 재요청 금지
```

## 빠른 시작

```bash
export BOLTA_API_KEY=test_xxxxx
npm run build

node scripts/preflight.mjs                          # 키·인증서 점검
node scripts/issue.mjs examples/request.json        # 검증만 (발행 안 함)
node scripts/issue.mjs examples/request.json --confirm   # 실제 발행
node scripts/check-status.mjs <issuanceKey>         # 결과 확인
```

`--confirm` 이 없으면 아무것도 발행하지 않는다. 실수로 실행됐을 때 아무 일도
일어나지 않아야 하기 때문이다.

## 코드로 쓰기

```ts
// npm 게시 전이라 클론 후 `npm link` 하거나 상대경로로 import 한다
import {
  BoltaProvider,
  validateIssueRequest,
  buildClientReferenceId,
  ProviderUncertainError,
} from 'korean-tax-invoice'

const check = validateIssueRequest(request, { verified: company.verifiedAt !== null })
if (!check.ok) {
  // 사유는 한국어 배열로 온다. 승인 화면에 그대로 띄울 수 있다.
  return { blocked: check.issues.map((i) => i.message) }
}

const provider = new BoltaProvider()
const refId = buildClientReferenceId('myapp', invoice.id)

// 프로바이더를 부르기 *전에* 잠근다
await db.markSubmitted(invoice.id)

try {
  const { issuanceKey } = await provider.submit(request, refId)
  await db.saveIssuanceKey(invoice.id, issuanceKey)
} catch (e) {
  if (e instanceof ProviderUncertainError) {
    // 접수 여부 불명. 재요청하면 중복 발행이다.
    const status = await provider.getStatusByReferenceId(refId)
    // SUBMITTED → 이미 접수됨 / UNKNOWN → 접수 안 됨
  }
}
```

## 프로바이더

| 프로바이더 | 상태 |
|---|---|
| 볼타 (Bolta) | 구현됨. 실제 발행 검증 완료 |
| 팝빌 | 인터페이스만 |
| 바로빌 | 인터페이스만 |

새 프로바이더는 `src/core/types.ts` 의 `TaxInvoiceProvider` 를 구현하면 된다.
핵심 로직(검증·사업자번호·KST 날짜)은 프로바이더와 무관하다.

## Claude Code 스킬로 쓰기

스킬 디렉터리에 두면 Claude 가 `SKILL.md` 를 읽고 스크립트를 직접 실행한다.
"○○회사 세금계산서 발행해줘" 라고 하면 검증하고, 내용을 보여주고, 확인받은
뒤 발행한다.

### 설치

```bash
# Claude Code
git clone https://github.com/sdkfile/korean-tax-invoice \
  ~/.claude/skills/korean-tax-invoice

# Hermes
git clone https://github.com/sdkfile/korean-tax-invoice \
  ~/.hermes/skills/korean-tax-invoice
```

### 빌드 (최초 1회, 필수)

```bash
cd ~/.claude/skills/korean-tax-invoice
npm install && npm run build
```

스크립트가 `dist/` 를 쓰기 때문에 이걸 건너뛰면 `issue` 와 `check-status` 가
동작하지 않는다. 잊었을 때는 스크립트가 무엇을 해야 하는지 알려준다.

### 키 설정

```bash
export BOLTA_API_KEY=test_xxxxx    # 볼타 개발자센터 > API 키
```

- `test_` — 가상 발행. 국세청에 가지 않는다. 여기서 시작하라
- `live_` — **실제 발행.** 되돌릴 수 없다

`.env` 에 넣어도 된다. 리포의 `.gitignore` 가 `.env` 를 제외한다.

### 확인

```bash
node scripts/preflight.mjs
```

"발행 준비 완료" 가 나오면 끝이다. Claude 에게 이렇게 말하면 된다.

> 볼타로 세금계산서 발행하려는데 준비됐는지 봐줘

### 사용 예

```
사용자: 고객사 주식회사에 9월 이용료 50만원 세금계산서 발행해줘

Claude: (preflight → 요청 파일 작성 → 검증 실행)

        공급받는자  고객사 주식회사 (220-81-62517)
        받는사람    tax@client.co.kr
        공급가액    500,000원
        세액         50,000원
        합계        550,000원
        환경        테스트 (가상)

        이 내용으로 발행할까요?

사용자: 응

Claude: (--confirm 으로 발행 → issuanceKey 확인 → 상태 조회)
```

`--confirm` 없이는 아무것도 발행되지 않는다. 실수로 실행됐을 때 아무 일도
일어나지 않아야 하기 때문이다.

### 라이브로 넘어갈 때

라이브는 테스트와 **완전히 별도 환경**이다. 키만 바꾸면 안 되고 세 가지를
다시 해야 한다 — 발급자 등록, 공동인증서 등록, 웹훅 URL 등록.
`references/bolta-setup.md` 참고.

첫 실전 발행은 **자기 회사끼리 소액**으로 해보길 권한다. 잘못돼도 남에게
가지 않는다.

## 문서

- [`SKILL.md`](SKILL.md) — 발행 절차와 함정
- [`references/bolta-setup.md`](references/bolta-setup.md) — 발급자·인증서·웹훅 등록
- [`references/integration.md`](references/integration.md) — 서비스에 붙일 때의 설계

## 개발

```bash
npm run check     # 타입 검사 + 테스트
```

테스트는 프로바이더를 호출하지 않는다. 실제 발행 흐름은 테스트 키로 확인한다.

## 면책

이 라이브러리는 발행 API 연동을 돕는다. 세무 판단(과세 유형, 작성일자, 수정발행
사유)은 사용자 책임이다. 확실하지 않으면 세무 전문가에게 확인하라.

## License

MIT
