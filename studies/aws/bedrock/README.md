# Bedrock 비용 산정 01 — 토큰 과금·프롬프트 캐싱·에이전트 호출 증폭

[AWS 서비스 목차](../README.md)

> 생성형 AI 에이전트의 요청 한 번은 모델을 몇 번 부르며, 그때마다 반복되는 앞부분(시스템 프롬프트·도구 스키마)을 캐싱하면 비용은 언제 줄고 언제 오히려 늘어나는가?

커리큘럼 02. AWS Infrastructure & Pricing의 학습 노트입니다. 실제 프로젝트에서 Amazon Bedrock 기반 에이전트를 운영할 예정이며, 모델은 아직 정하지 않았습니다. 이 문서는 비교용으로 Anthropic Claude Haiku 5.5·Sonnet 5.5와 Amazon Nova Micro·Lite의 서울 리전 공개 요율을 사용합니다. 작업량은 가상 값입니다.

## 1. 과금 단위

On-Demand 추론은 **입력 토큰**과 **출력 토큰**을 따로 계량합니다. 프롬프트 캐싱을 쓰면 입력 토큰이 세 가지 요율로 나뉩니다.

| 입력 토큰 구분 | 적용 요율 |
|---|---|
| 캐시에 쓴 토큰 | 모델의 캐시 쓰기 요율. 모델에 따라 일반 입력 요율보다 비쌉니다. |
| 캐시에서 읽은 토큰 | 모델의 캐시 읽기 요율 |
| 그 밖의 입력 토큰 | 일반 입력 요율 |

Converse API 응답의 `inputTokens`는 캐시와 무관한 입력만 뜻합니다. 전체 입력은 `inputTokens + cacheReadInputTokens + cacheWriteInputTokens`로 계산합니다. 비용 기록을 남길 때 `inputTokens`만 합산하면 캐시 쓰기 비용이 빠집니다.

### 서울 리전 요율 (USD/100만 토큰)

| 모델 | Price List 구분 | 입력 | 출력 | 캐시 쓰기(5분) | 캐시 쓰기(1시간) | 캐시 읽기 |
|---|---|---:|---:|---:|---:|---:|
| Claude Haiku 5.5 | Global, Standard | 0.10 | 0.50 | 0.125 | 0.20 | 0.01 |
| Claude Sonnet 5.5 | Global, Standard | 2.00 | 10.00 | 2.50 | 4.00 | 0.10 |
| Claude Haiku 4.5 | Global | 1.00 | 5.00 | 1.25 | 2.00 | 0.10 |
| Claude Sonnet 4.5 | Global | 3.00 | 15.00 | 3.75 | 6.00 | 0.30 |
| Amazon Nova Micro | 서울 리전 | 0.041 | 0.164 | 항목 없음 | — | 0.01025 |
| Amazon Nova Lite | 서울 리전 | 0.071 | 0.284 | 항목 없음 | — | 0.01775 |

- Claude 모델의 서울 리전 On-Demand 요율은 Price List에서 **Global 교차 리전 추론 항목만** 확인했습니다. 지역(Geographic)·리전 내 On-Demand 요율은 확인하지 못했습니다. AWS 문서는 Global이 Geographic보다 "약 10% 저렴"하다고 설명하지만, 이 비율로 Geographic 요율을 추정하지 않습니다.
- Global 교차 리전 추론은 **전 세계 AWS 상용 리전 어디에서든** 요청을 처리할 수 있습니다. Geographic 프로필은 지정한 지역 경계 안에서 처리합니다. 실제 프로젝트에 데이터 처리 위치 요구가 있으면 Global 요율을 쓸 수 없고, 이때 요율을 다시 확인해야 합니다. 가격은 추론 프로필을 호출한 리전 기준으로 계산되며 별도 라우팅 비용은 없습니다.
- Claude Haiku 5.5에는 "Long Context" 요율(입력 0.50, 출력 2.50, 캐시 쓰기 0.625, 캐시 읽기 0.05)이 따로 있습니다. 어느 입력 길이부터 적용되는지는 이번에 확인하지 못했습니다.
- Nova 모델은 Price List에 캐시 쓰기 요율 항목이 없습니다. Nova의 자동(implicit) 캐시 재사용은 캐시 사용량 필드에 보고되지 않고 캐시 읽기로 과금되지 않습니다.
- 배치 추론은 일부 모델에서 On-Demand보다 50% 저렴하지만, **프롬프트 캐싱은 배치 추론 API에서 지원되지 않습니다.**

[Amazon Bedrock pricing](https://aws.amazon.com/bedrock/pricing/) · [AWS Price List — AmazonBedrockFoundationModels, ap-northeast-2](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonBedrockFoundationModels/current/ap-northeast-2/index.json) · [AWS Price List — AmazonBedrock, ap-northeast-2](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonBedrock/current/ap-northeast-2/index.json) · [Cross-Region inference](https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html)

## 2. 프롬프트 캐싱의 조건

| 조건 | 내용 |
|---|---|
| 캐시 대상 | 요청마다 변하지 않는 **앞부분(prefix)**. 앞부분이 조금이라도 바뀌면 캐시 미스입니다. 처리 순서는 `tools → system → messages`이므로 도구 정의를 바꾸면 뒤쪽 캐시도 모두 무효가 됩니다. |
| 최소 길이 | 캐시 체크포인트 앞의 **누적 토큰**이 모델별 최소값 이상이어야 합니다. Claude Haiku 5.5·Sonnet 5.5는 512, Claude Haiku 4.5는 4,096, Nova는 1K 토큰입니다. 최소값에 못 미치면 요청은 성공하지만 캐시되지 않습니다. |
| 체크포인트 수 | Claude·Nova 모두 요청당 최대 4개 |
| TTL | 기본 5분이며 **캐시 적중 때마다 갱신**됩니다. Claude 5.5 계열은 1시간 TTL도 지원하지만 캐시 쓰기 요율이 더 높습니다. |
| 적중 보장 없음 | 캐시는 요청을 처리한 서버에 저장됩니다. 다른 서버(다른 리전 포함)가 처리하거나 같은 요청이 응답을 시작하기 전에 들어오면 새로 씁니다. 교차 리전 추론에서는 수요가 높을 때 캐시 쓰기가 늘 수 있습니다. |
| 확인 방법 | 응답의 캐시 사용량 필드로 실제 읽기·쓰기를 확인합니다. |

Anthropic 모델은 캐시 제어를 명시해야 캐시됩니다. 요청 최상위에 `cache_control` 하나를 넣는 자동 캐싱은 Claude Haiku 4.5·Sonnet 5.5·Haiku 5.5 등에서 지원됩니다.

[Prompt caching for faster model inference](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html)

### 캐싱이 손해가 되는 경우

Claude Haiku 5.5에서 앞부분 P 토큰을 캐시하면 첫 요청은 일반 입력보다 25% 비싼 쓰기(0.125 vs 0.10)를 내고, TTL 안의 다음 요청부터 읽기 요율(0.01, 일반 입력의 10%)을 냅니다.

- TTL(5분) 안에 같은 앞부분 요청이 **2번 이상** 오면 이득입니다. `1.25P + 0.1P = 1.35P < 2P`.
- 요청 간격이 항상 5분보다 길면 매번 캐시를 새로 쓰므로 **캐싱하지 않을 때보다 25% 비쌉니다.**
- 1시간 TTL은 쓰기 요율이 일반 입력의 2배(0.20)이므로, 5분~1시간 간격으로 같은 앞부분이 반복될 때만 검토합니다.

Sonnet 5.5는 캐시 읽기가 일반 입력의 5%(0.10 vs 2.00)라 적중 시 이득이 더 크지만, 쓰기 25% 할증 구조는 같습니다. **하루 호출 수만으로는 판단할 수 없고, 같은 앞부분 요청의 시간 간격 분포가 필요합니다.**

## 3. 에이전트 다단계 호출의 토큰 증폭

에이전트는 사용자 요청 한 번에 모델을 여러 번 호출합니다. Bedrock Agents(현재 Agents Classic, 신규 가입 중단) 문서는 오케스트레이션을 이렇게 설명합니다. 모델이 다음 단계를 추론하고, 도구(액션 그룹)나 지식 기반을 부르고, 그 결과(observation)를 기본 프롬프트에 덧붙여 **다시 모델을 호출**하며, 최종 응답이 나올 때까지 반복합니다. 기본 프롬프트에는 지시문·액션 설명·대화 기록이 들어갑니다. 신규 에이전트는 AgentCore·Strands Agents SDK 경로를 안내하지만, "앞부분 + 누적 대화 + 도구 결과"를 매 호출 다시 보낸다는 구조는 같습니다.

### 가상 예제 — 에이전트 1회 실행

| 호출 | 고정 앞부분(지시문·도구 스키마) | 누적 대화·관찰 | 입력 합계 | 출력 |
|---:|---:|---:|---:|---:|
| 1 | 3,000 | 500 | 3,500 | 300 |
| 2 | 3,000 | 1,300 | 4,300 | 300 |
| 3 | 3,000 | 2,100 | 5,100 | 300 |
| 4 | 3,000 | 2,900 | 5,900 | 300 |
| 합계 | 12,000 | 6,800 | **18,800** | 1,200 |

호출마다 이전 출력 300과 새 관찰 500이 누적된다고 가정했습니다. 단일 호출(3,500 토큰)로 생각했을 때보다 입력이 **약 5.4배**입니다. 입력의 64%가 매번 같은 앞부분입니다.

| 모델 | 캐싱 없음 | 앞부분 3,000 캐싱 (1회 쓰기 + 3회 읽기) | 감소율 |
|---|---:|---:|---:|
| Claude Haiku 5.5 | 0.00248 USD | 0.00175 USD | 약 30% |
| Claude Sonnet 5.5 | 0.0496 USD | 0.0340 USD | 약 31% |

같은 실행 안의 4회 호출이 5분 안에 끝난다고 가정했습니다. 실행 사이 간격이 5분보다 짧으면 다음 실행도 캐시를 읽어 감소율이 더 커지고, 사용자가 드물게 쓰면 실행마다 쓰기를 다시 냅니다. 출력 토큰 요율이 입력의 5배이므로, 앞부분 캐싱보다 **호출 수와 출력 길이**가 더 큰 비용 요인일 수 있습니다.

## 4. 낭비 판단에 필요한 자료

| 판단 | 필요한 자료 | 보류 조건 |
|---|---|---|
| 캐싱 적용 후보 | 호출별 입력·출력·캐시 토큰, 앞부분 길이, 같은 앞부분 요청의 시간 간격 | 호출 로그 없이 월 청구 합계만 있음 |
| 캐싱 효과 없음(쓰기만 반복) | `cacheWriteInputTokens` 대비 `cacheReadInputTokens` 비율 | 교차 리전 추론 사용 여부를 모름 |
| 에이전트 호출 수 과다 | 실행당 모델 호출 수 분포, 실패·재시도, 최종 응답 품질 평가 | 품질 평가 기준이 없음 — 호출 수를 줄여 품질이 떨어지면 절감이 아님 |
| 더 작은 모델로 교체 | 같은 평가 세트에서의 정확도·완료율 | 평가 세트가 없음 |

## 5. 확인 문제

1. Converse 응답에서 `inputTokens`=200, `cacheReadInputTokens`=3,000, `cacheWriteInputTokens`=0이면 전체 입력은 몇 토큰인가요?
2. Claude Haiku 5.5에서 같은 앞부분 요청이 항상 10분 간격으로 온다면 5분 TTL 캐싱은 이득인가요?
3. 에이전트 비용을 줄이려고 도구 스키마를 매번 조금씩 바꿔 짧게 보내면 캐싱에는 어떤 영향이 있나요?

## 6. 확인 범위와 다음 질문

Price List에서 서울 리전 토큰·캐시 요율을, Bedrock 문서에서 캐싱 조건·TTL·최소 토큰·교차 리전 동작, 에이전트 오케스트레이션 구조를 확인했습니다. Claude의 리전 내 요율, Long Context 적용 기준, 실제 캐시 적중률, AgentCore 자체의 과금은 확인하지 않았습니다. 손익분기 계산은 [실험 020](../../../experiments/020-bedrock-token-caching/README.md)에서 재현합니다.

> 다음 질문: 실제 에이전트의 호출 간격 분포가 주어지면, 5분과 1시간 TTL 중 어느 쪽이 싼가?

## 7. 사용량은 어디서 측정하는가 (2026-11-15 추가)

같은 호출의 토큰 수를 세 곳에서 볼 수 있다. 용도와 한계가 다르다.

| 출처 | 켜는 방법 | 담기는 것 | 담기지 않는 것 | 용도 |
|---|---|---|---|---|
| **런타임 지표** (CloudWatch `AWS/Bedrock`, 차원 `ModelId`) | 설정 없음 | 모델별 `Invocations`, `InputTokenCount`, `OutputTokenCount`, `CacheReadInputTokenCount`, `CacheWriteInputTokenCount`, 지연, 오류, 제한 | 에이전트·사용자 요청·세션 구분 | 모델별 합계, 앱 기록의 교차 확인 |
| **모델 호출 로깅** (CloudWatch Logs 또는 S3) | 계정·리전 설정에서 켬(기본 꺼짐) | 호출별 `input.inputTokenCount`, `input.cacheReadInputTokenCount`, `input.cacheWriteInputTokenCount`, 출력 토큰, 요청·응답 본문 전체, 호출자 ARN, 요청 메타데이터(`requestMetadata`) | 에이전트 단계 구조(상위 요청), 품질 결과 | 프롬프트 디버깅 |
| **애플리케이션 기록** (Converse 응답의 `usage`) | 앱 코드에서 기록 | `inputTokens`, `outputTokens`, `cacheReadInputTokens`, `cacheWriteInputTokens` + 앱이 붙이는 에이전트 이름·요청 ID·상위 요청 ID | 앱이 기록하지 않은 호출 | 요청 1건당 비용 분해, 호출 증폭 |

- **정정:** 이전 수집 계획([3-4절](../../../experiments/real-account-calibration-plan.md#3-4-bedrock-데이터에-대한-주의))은 "모델 호출 로깅에 캐시 토큰 필드가 없다"고 적었으나 틀렸다. 실제 로그 예시와 AWS 관측성 가이드의 쿼리에 `input.cacheReadInputTokenCount`·`input.cacheWriteInputTokenCount`가 있다. 그래도 운영 중 비용 분석에는 쓰지 않는다. 본문 전체가 기록되고, 요청 메타데이터도 호출 로깅을 켠 리전에서만 남기 때문이다.
- **입력 토큰의 뜻이 출처마다 다르다.** 런타임 지표의 `InputTokenCount`와 Converse `inputTokens`는 캐시 토큰을 **뺀** 입력이다. 할당량 소모는 `InputTokenCount + CacheWriteInputTokenCount`로 계산하고, 캐시 읽기는 할당량에 포함되지 않는다. OpenTelemetry를 받는 도구 중에는 캐시 읽기를 입력 토큰의 일부로 다루는 곳이 있다. 출처를 섞어 더하면 캐시 토큰이 두 번 계산될 수 있으므로, 기록할 때 "입력 토큰에 캐시 포함 여부"를 명시한다.
- **`Invocations`는 성공한 호출만 센다.** 제한(throttle)된 요청은 `InvocationThrottles`로 따로 나온다. 앱이 실패·제한 호출까지 기록하면 합계가 다른 것이 정상이다.
- **교차 리전 추론 프로필**을 쓰면 지표의 모델 ID 차원과 앱이 기록한 모델 ID 표기가 다를 수 있다. 비교할 때 매핑표가 필요하다.
- **OpenTelemetry 표준 이름:** 캐시 토큰은 `gen_ai.usage.cache_read.input_tokens`(캐시에서 읽음), `gen_ai.usage.cache_creation.input_tokens`(캐시에 씀)다. "write"가 아니라 "creation"이다. 생성형 AI 규약은 아직 Development 단계라 이름이 바뀔 수 있으므로 기록에 규약 버전을 함께 남긴다.
- **앱 기록을 CloudWatch 지표로 낼 때의 비용:** 사용자 정의 지표는 차원 값 조합마다 별도 지표로 과금된다. 세션 ID·요청 ID를 차원으로 넣으면 세션 수만큼 지표가 늘어난다. 차원은 값 종류가 적은 것(에이전트 이름, 모델, 환경)만 쓰고, 세션·요청 ID는 로그에만 남긴다. 임베디드 지표 형식(EMF)을 쓰면 로그 한 줄에서 지정한 필드만 지표로 뽑힌다. 자세한 내용은 [CloudWatch 노트](../cloudwatch/README.md#사용자-정의-지표의-차원과-비용-2026-11-15-추가).

## 공식 참고 자료

확인일은 **2026-11-13**입니다.

| 자료 | 확인 범위 |
|---|---|
| [Amazon Bedrock pricing](https://aws.amazon.com/bedrock/pricing/) | Global·Geographic 구분 표기, 배치 50% 할인, Sonnet 5.5 캐시 읽기 인하 공지 |
| [AWS Price List — AmazonBedrockFoundationModels](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonBedrockFoundationModels/current/ap-northeast-2/index.json) · [AmazonBedrock](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonBedrock/current/ap-northeast-2/index.json) | 서울 요율, 게시일 2026-11-09·2026-11-11 |
| [Prompt caching for faster model inference](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html) | 과금 구분, 최소 토큰, 체크포인트, TTL, 적중 비보장, 배치 미지원, 토큰 필드 |
| [Cross-Region inference](https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html) | Global·Geographic 처리 위치, 약 10% 차이, 호출 리전 기준 가격 |
| [How Amazon Bedrock Agents works](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-how.html) | 오케스트레이션 반복, 기본 프롬프트 구성, Agents Classic 상태 |
| [Monitor bedrock-runtime inference using CloudWatch metrics](https://docs.aws.eu/bedrock/latest/userguide/monitoring-runtime-metrics.html) | 런타임 지표 목록(`CacheReadInputTokenCount`·`CacheWriteInputTokenCount` 포함). 2026-11-15 확인 |
| [How tokens are counted in Amazon Bedrock](https://docs.aws.eu/bedrock/latest/userguide/quotas-token-burndown.html) | `InputTokenCount`는 캐시 토큰 제외, 할당량 = 입력 + 캐시 쓰기 + 출력 × 소진율, 캐시 읽기 미포함. 2026-11-15 확인 |
| [Cost management with request metadata](https://docs.aws.amazon.com/bedrock/latest/userguide/cost-mgmt-request-metadata.html) | 요청 메타데이터는 호출 로깅을 켠 리전에서만 기록. 2026-11-15 확인 |
| [Creating Custom Dashboards for GenAI Telemetry (AWS Observability)](https://aws-observability.github.io/observability-best-practices/guides/genai/custom-dashboards-for-genai-telemetry/) | 호출 로그의 `input.cacheReadInputTokenCount`·`input.cacheWriteInputTokenCount` 집계 쿼리. 2026-11-15 확인 |
| [OpenTelemetry — Semantic conventions for generative client AI spans](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/) | 캐시 토큰 속성 이름, Development 상태. 2026-11-15 확인 |

## 확인 문제 정답과 해설

1. `200 + 3,000 + 0 = 3,200` 토큰입니다.
2. 아닙니다. 매번 TTL이 만료되어 캐시를 새로 쓰므로 일반 입력보다 25% 비쌉니다. 1시간 TTL은 쓰기 요율이 2배지만 이후 요청이 읽기 요율을 내므로, 1시간 안에 3회 이상 반복되면 검토할 수 있습니다.
3. 앞부분이 바뀌므로 캐시 미스가 나고 매번 쓰기 요율을 냅니다. 처리 순서상 `tools`가 바뀌면 `system`·`messages` 캐시도 무효가 됩니다.

## 추가(2026-11-15) — Guardrails 텍스트 단위, Knowledge Base 저장 최소 요금, 모델 배분

> 모델 토큰 비용만 계산하면 챗봇 1건당 비용을 얼마나 놓치는가?

**과금 단위.** Guardrails는 정책마다 **텍스트 단위(최대 1,000자)** 로 과금하고, 입력(질문)과 출력(응답)을 각각 평가하면 각각 셉니다. 요금 페이지 예시도 질문 200자 = 1단위, 응답 1,500자 = 2단위로 계산합니다. 서울 요율([2026-11-15 사본](../../../references/aws-price-list-apn2-2026-11-15.json), AmazonBedrock 게시일 2026-11-11):

| 정책 | USD/텍스트 단위 |
|---|---:|
| 콘텐츠 필터 | 0.00015 |
| 거부 주제 | 0.00015 |
| 민감 정보(정규식 외) | 0.0001 |
| 민감 정보(정규식) · 단어 필터 | 0 |
| 맥락 근거 확인 | 0.0001 |

관리형 Knowledge Base 인덱스 저장은 요금 페이지에 **원본 데이터 1 GB당 월 5 USD**로 나오지만, 페이지 일부만 읽혔고 Price List에서 해당 행을 찾지 못했습니다(`missing`). 벡터 저장소를 OpenSearch Serverless로 두면 그쪽 최소 OCU가 따로 붙습니다([OpenSearch 노트](../opensearch/README.md)).

**가상 예시.** 월 10만 건, 요청당 입력 1,500 토큰·출력 400 토큰(Claude Haiku 4.5: 입력 1.00, 출력 5.00 USD/100만 토큰), 질문 200자·응답 1,500자에 콘텐츠 필터와 거부 주제를 입출력 모두 적용합니다.

| 항목 | 요청당 | 월 |
|---|---:|---:|
| 모델 토큰 | 0.0035 USD | 350.00 USD |
| Guardrails (3단위 × 2정책 × 0.00015) | 0.0009 USD | 90.00 USD |

Guardrails가 모델 비용의 26%입니다. 응답이 1,001자가 되는 순간 단위가 하나 늘어나는 **단위 올림**이 있으므로, 길이 분포를 모르면 평균 길이로 계산한 값이 과소 추정이 됩니다.

**모델 배분.** 요청을 쉬운 것과 어려운 것으로 나눠 다른 모델로 보내는 경우 1건당 비용은 `Σ 배분 비율 × 모델별 1건당 비용`입니다. 이 노트와 [실험 032](../../../experiments/032-llm-request-cost-breakdown/README.md)는 비용만 계산하고, 품질이 유지되는지는 판정하지 않습니다(평가 데이터 없음 → **판단 보류**).

**낭비 판단 자료.** 정책별 적용 위치(입력·출력), 질문·응답 길이 분포, Guardrails 차단률, KB 원본 크기와 벡터 저장소 종류.

**확인 문제.** (1) 응답 2,100자에 맥락 근거 확인만 출력 쪽에 적용하면 요청당 얼마인가요? (2) 단어 필터만 쓰면 Guardrails 비용은 얼마인가요?

**해설.** (1) 2,100자는 3단위이므로 3 × 0.0001 = 0.0003 USD입니다. (2) 단어 필터 요율이 0이므로 0 USD입니다. 다른 정책을 함께 켜면 그 정책만큼 붙습니다.

| 공식 자료 (확인일 2026-11-15) | 확인 범위 |
|---|---|
| [Amazon Bedrock pricing — Guardrails, Knowledge Bases](https://aws.amazon.com/bedrock/pricing/) | 텍스트 단위 1,000자, 정책별 과금, 입출력 예시, KB 관리형 인덱스 저장(일부만 확인) |
| [AWS Price List — AmazonBedrock ap-northeast-2](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonBedrock/current/ap-northeast-2/index.json) | Guardrail 정책별 서울 요율 |
