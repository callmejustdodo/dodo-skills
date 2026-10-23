# 볼타 초기 설정

발행하려면 코드 바깥에서 먼저 해둬야 하는 것들이 있다. API 로는 안 되고
콘솔에서만 되는 항목이 섞여 있다.

## 1. 계정과 API 키

https://app.bolta.io → 개발자센터 → API 키

**[API 키 생성]** 에서 테스트/라이브를 고른다. 둘은 완전히 분리된 환경이라
발급자·인증서·웹훅을 각각 등록해야 한다.

- `test_` — 가상 발행. 국세청에 가지 않는다. 개발·검증용
- `live_` — 실제 발행

## 2. 발급자 등록

세금계산서를 발행할 주체(= 공급자, 우리 회사)를 등록한다.

```bash
curl -X POST https://xapi.bolta.io/v1/issuers \
  -u "$BOLTA_API_KEY:" \
  -H 'Content-Type: application/json' \
  -d '{
    "identificationNumber": "2431302906",
    "organizationName": "회사명",
    "representativeName": "홍길동"
  }'
```

이미 등록돼 있으면 목록으로 확인한다.

```bash
curl -s https://xapi.bolta.io/v1/issuers -u "$BOLTA_API_KEY:"
```

### 공동대표는 등록증 표기 그대로

`representativeName` 에 "홍길동 외 1명" 처럼 **사업자등록증에 적힌 그대로**
넣는다. 대표자 한 명만 골라 쓰면 안 된다.

근거: 국세청 예규 부가가치세과-1158(2011.09.27), 부가가치세과-23(2012.01.09) —
"사업자등록증상에 기재된 대표자 명의로" 발급한다.

볼타 API 는 `maxLength: 30` 만 검증하므로 잘못 넣어도 막아주지 않는다.

## 3. 공동인증서 등록

발행에는 사업자용 공동인증서(구 공인인증서)가 필요하다. 등록 URL 을 받아
브라우저에서 진행한다.

```bash
curl -X POST "https://xapi.bolta.io/v1/issuers/{issuerId}/certificates/url" \
  -u "$BOLTA_API_KEY:"
```

- 등록 URL 은 **5분** 유효
- 등록 내역 조회는 등록 후 **30초** 이내에만 가능 (리다이렉트 복귀 직후에 조회)
- 만료되면 URL 을 다시 발급받아야 한다
- 만료일은 `GET /v1/issuers` 응답의 `certificate.expiresAt` 에서 확인

출처: [인증서 등록 연동](https://docs.bolta.io/docs/api-introduction/certificate-registration)

`node scripts/preflight.mjs` 가 만료일과 남은 일수를 보여준다.

## 4. 웹훅 등록

개발자센터 → API 키 → 해당 키 우측 **⋮** → **[수정하기]**

창에 있는 필드 중 **"발행 수신 URL"** 이 웹훅이다. 화면에 "웹훅"이라는 단어가
없어서 못 찾기 쉽다.

```
발행 수신 URL: https://your-app.com/api/webhooks/bolta
```

**API 로는 등록할 수 없다.** 콘솔에서만 된다. 테스트/라이브 각각 따로.

### 등록이 거절될 때

> "정상 접근 가능한 URL만 넣을 수 있습니다"

볼타가 저장 전에 그 주소로 접근해본다. 웹훅 핸들러가 `POST` 만 받으면
`GET` 에 405 가 나가서 거절된다. **`GET` 에 200 을 주도록** 해야 한다.

정보는 노출하지 마라 — 공개된 주소다.

```ts
export function GET() {
  return Response.json({ ok: true })   // 아무것도 알려주지 않는다
}
```

### 웹훅 발송 시간

| 환경 | 소요 |
|---|---|
| 테스트 키 | 10~30초 |
| 라이브 키 | 약 10분 |

출처: [웹훅 - 세금계산서](https://docs.bolta.io/docs/api-introduction/webhook-tax-invoice)

웹훅이 오지 않으면 상태 조회로 확인한다.

## 5. 방화벽

웹훅 발신 IP 는 하나다. 테스트·라이브 공통.

```
43.201.136.252
```

볼타 웹훅에는 **서명이 없다.** 이 IP 가 사실상의 인증이므로, 방화벽이 없는
환경이라면 애플리케이션에서 발신 IP 를 검사해야 한다.

## 확인

```bash
node scripts/preflight.mjs
```

키·인증·발급자·인증서를 한 번에 점검한다.
