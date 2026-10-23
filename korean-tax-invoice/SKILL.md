---
name: korean-tax-invoice
description: 한국 전자세금계산서(볼타) 발행 시 사용. 중복·오발행을 구조로 막는다.
version: 0.1.0
author: Seonggu Kim (sdkfile)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [세금계산서, 전자세금계산서, 볼타, bolta, 국세청, 부가세, tax-invoice, korea]
---

# 한국 전자세금계산서 발행

한국 사업자가 전자세금계산서를 API 로 발행할 때 쓴다. 발행 요청을 만들고,
검증하고, 접수하고, 결과를 받는 전 과정을 다룬다.

**세금계산서는 잘못 발행하면 되돌릴 수 없다.** 국세청 수정발행 절차를 밟아야
하고 기록이 남는다. 그래서 이 스킬은 "빠르게 발행"이 아니라 "잘못 나가지 않게"
쪽에 무게를 둔다.

지금 구현된 프로바이더는 **볼타(Bolta)** 하나다. 팝빌·바로빌은 인터페이스만
있고 구현이 없다 — 있는 척하지 않는다.

## When to Use

- 한국 사업자에게 세금계산서를 발행해야 할 때
- 발행 자동화를 만들 때 (SaaS 월 청구, 정산 등)
- 발행이 실패했거나 상태가 불분명해 확인이 필요할 때
- 중복 발행 사고를 막는 구조를 짜야 할 때

**쓰지 않을 것:** 현금영수증(별도 API), 해외 인보이스, 세무 신고 자체.

## Prerequisites

```bash
npm install          # 최초 1회
npm run build        # scripts/ 가 dist/ 를 쓴다
```

환경변수 하나면 된다.

```bash
export BOLTA_API_KEY=test_xxxxx    # 볼타 개발자센터 > API 키
```

- `test_` 로 시작 → 가상 발행. 국세청에 가지 않는다.
- `live_` 로 시작 → **실제 발행.** 되돌릴 수 없다.

발급자(공급자) 등록과 공동인증서는 볼타 콘솔에서 먼저 해야 한다.
`references/bolta-setup.md` 참고.

## 발행 절차

발행은 되돌릴 수 없으므로 순서를 지킨다.

### 1. 사전 점검

```
terminal(command="node scripts/preflight.mjs")
```

키·인증·발급자·인증서 만료일을 한 번에 본다. 여기서 막히면 발행해도 실패한다.

**완료 기준:** "발행 준비 완료" 가 출력된다.

### 2. 요청 파일 작성

`examples/request.json` 을 복사해 채운다. 사용자에게 받아야 하는 값:

| 항목 | 어디서 오나 |
|---|---|
| 공급받는자 사업자번호·상호·대표자 | 사업자등록증 |
| **공급받는자 담당자 이메일** | **등록증에 없다.** 메일 발신자나 별도 입력 |
| 품목·금액 | 청구 내역 |
| 작성일자 | 보통 청구 기간 말일. 미래 날짜는 볼타가 거절한다 |

담당자 이메일을 놓치는 사고가 흔하다. 사업자등록증에는 이메일이 적혀 있지
않아서 등록증만 보고 채우면 반드시 빠진다.

### 3. 검증 (발행 안 함)

```
terminal(command="node scripts/issue.mjs <요청파일>")
```

`--confirm` 이 없으면 검증만 하고 무엇을 보낼지 보여준다. **이 출력을 사용자에게
그대로 보여주고 확인받아라.** 금액과 수신처가 맞는지는 사람이 봐야 한다.

**완료 기준:** 차단 사유가 없고, 사용자가 내용을 확인했다.

### 4. 발행

```
terminal(command="node scripts/issue.mjs <요청파일> --confirm")
```

성공하면 `issuanceKey` 와 관리번호가 나온다. **둘 다 기록해라.**

**완료 기준:** "접수 완료" 와 issuanceKey 출력.

### 5. 결과 확인

접수는 발행이 아니다. 볼타가 처리한 뒤 웹훅으로 알려주거나, 조회해야 한다.

```
terminal(command="node scripts/check-status.mjs <issuanceKey>")
```

**완료 기준:** 상태가 `ISSUED` 또는 `FAILED` 로 확정된다.

## 사고를 막는 세 가지 규칙

### 접수와 발행은 다르다

대부분의 ASP 는 발행을 *접수*하고 결과는 나중에 준다. 이 둘을 같은 상태로 두면
응답을 못 받은 구간에서 재요청이 나가 **같은 계산서가 두 장 발행된다.**

```
SUBMITTED  접수됨. 결과 대기 중. 재요청 금지.
ISSUED     발행 완료.
FAILED     실패. 고쳐서 다시 시도 가능.
```

### "거절됨"과 "모름"을 구분한다

```
ProviderRejectedError    4xx. 접수 안 됨.  → 고쳐서 재시도 안전
ProviderUncertainError   타임아웃·5xx.     → 재요청 금지
```

후자에서 재요청하면 중복 발행이다. **반드시 조회부터 한다.**

```
terminal(command="node scripts/check-status.mjs --ref <관리번호>")
```

`SUBMITTED` 면 이미 접수된 것이니 기다린다. `UNKNOWN` 이면 접수되지 않았으니
다시 시도해도 된다.

### 멱등성 키는 재사용한다

같은 청구 건을 재시도할 때 **같은 관리번호**를 써야 프로바이더가 중복을
막아준다. 재시도마다 새로 만들면 멱등성이 아예 동작하지 않는다.

`buildClientReferenceId(prefix, invoiceId)` 가 그래서 시각이나 난수를 섞지
않는다.

## Pitfalls

**작성일자가 하루 밀린다.** 서버가 UTC 면 `getFullYear()` 계열이 KST 자정 근처에서
전날을 준다. 작성일자는 과세기간을 가르는 값이라 월말 발행분이 전월로 넘어가면
부가세 신고가 어긋난다. → `formatKstDate()` 를 써라.

**종목이 조용히 사라진다.** 볼타 필드명은 `businessItem` 이다. `businessClass` 로
보내면 선택 필드라 오류 없이 버려지고, 종목 없는 계산서가 나간다.

**미래 날짜는 거절된다.** 볼타: "작성일자는 현재 날짜와 같거나 이전이어야 합니다."

**공급자 담당자는 필수다.** 문서상 선택처럼 보이지만 없으면 거절된다.

**웹훅에 서명이 없다.** 볼타는 발신 IP(`43.201.136.252`)만 공개한다. 서명 검증을
기대하지 말고 IP + 상태 전이 제한으로 막아라. 웹훅 URL 등록 시 볼타가 그
주소로 접근해보므로 `GET` 에 200 을 줘야 등록된다.

**품목은 16개까지.** 넘으면 계산서를 나눠야 한다.

## 잘못 발행했을 때

이 스킬은 **발행만 한다.** 취소·수정발행 기능은 없다 — 세무 판단이 필요한
영역이라 자동화 대상이 아니다.

이미 나간 계산서는 지울 수 없다. 수정세금계산서를 **추가로** 발행해서
바로잡는다. 사유에 따라 **작성일자와 발급기한이 다르다.**

### 원본 작성일자를 그대로 쓰는 경우

잘못 적은 것을 바로잡는 유형이다. 과세기간이 원본과 같아야 하므로 작성일자를
**원본 그대로** 적는다.

| 상황 | 발급 방법 | 발급기한 |
|---|---|---|
| 기재사항 착오 | 취소분(-) 1장 + 정확한 분(+) 1장 | 착오를 인식한 날 |
| 기재사항 착오 외 | 취소분(-) 1장 + 정확한 분(+) 1장 | 확정신고기한 다음날부터 1년 |
| 착오로 이중발급 | 취소분(-) 1장 | 착오를 인식한 날 |
| 면세 등 발급 대상 아님 | 취소분(-) 1장 | 착오를 인식한 날 |

**신고기한이 지난 뒤 수정하면 부가세 수정신고 대상이다.**

### 새 작성일자를 쓰는 경우

거래 자체가 나중에 변한 유형이다. 사유가 생긴 날이 곧 공급시기라 작성일자를
**사유 발생일**로 적는다. 원본은 건드리지 않는다.

| 상황 | 발급 방법 | 작성일자 | 발급기한 |
|---|---|---|---|
| 공급가액 변동 | 증감분만 (+) 또는 (-) 1장 | 변동사유 발생일 | 다음달 10일 |
| 계약의 해제 | 취소분(-) 1장 | 계약해제일 | 다음달 10일 |
| 환입(반품) | 환입분만 (-) 1장 | 환입된 날 | 다음달 10일 |

이쪽은 **부가세 수정신고 대상이 아니다** — 사유가 생긴 과세기간에 신고한다.

출처: [국세청 - 수정세금계산서 발급방법](https://www.nts.go.kr/nts/cm/cntnts/cntntsView.do?cntntsId=7791&mi=2465)

무엇을 해야 할지 모르겠으면 **발행하지 말고 세무 담당자에게 물어라.**
잘못된 수정발행은 원본보다 정리하기 어렵다.

볼타 콘솔(https://app.bolta.io)에서 수동으로 처리할 수 있다.

## Verification

```
terminal(command="npm run check")
```

타입 검사 + 테스트 47개(핵심 로직 28 + 볼타 19). 네트워크를 타지 않는다 —
볼타 테스트는 `fetch` 를 목으로 바꿔 페이로드와 오류 분기를 확인한다.

실제 발행 흐름은 테스트 키로 확인한다 — 가상 발행이라 국세청에 가지 않는다.

```
terminal(command="node scripts/preflight.mjs")
terminal(command="node scripts/issue.mjs examples/request.json")
```

## 라이브러리로 쓰기

스크립트 대신 코드에서 직접 쓸 수도 있다.

```ts
import { BoltaProvider, validateIssueRequest, buildClientReferenceId } from 'korean-tax-invoice'

const check = validateIssueRequest(request, { verified: company.verifiedAt !== null })
if (!check.ok) return { blocked: check.issues }   // 사유를 사람에게 보여준다

const provider = new BoltaProvider()
const refId = buildClientReferenceId('myapp', invoice.id)

// 프로바이더를 부르기 *전에* 상태를 SUBMITTED 로 잠근다.
// 호출 후에 잠그면 응답 직후 죽는 구간에서 재발송이 난다.
await db.markSubmitted(invoice.id)
const { issuanceKey } = await provider.submit(request, refId)
```

`references/integration.md` 에 웹훅 수신과 상태 전이 설계가 있다.

## 다른 프로바이더 붙이기

`src/core/types.ts` 의 `TaxInvoiceProvider` 를 구현하고
`src/providers/<이름>/` 에 두면 된다. 인터페이스가 요구하는 것:

- `submit()` — 접수. 거절과 불확실을 구분해 던진다
- `getStatus()` — 상태 조회
- `parseWebhook()` — 페이로드 정규화
- `verifyWebhookSender()` — 발신자 검증

핵심 로직(`src/core/`)은 프로바이더와 무관하므로 그대로 쓴다.
