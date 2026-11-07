# Lambda 비용 산정 02 — 콜드 스타트와 Provisioned Concurrency

> 초기화 시간을 줄이는 것과 실행 환경을 미리 준비하는 것은 응답 지연과 비용을 어떻게 바꾸는가?

[Lambda 비용 산정 01](README.md)에 이어, 일반 Lambda Event Function의 동기 호출을 비교합니다. 메모리 설정을 고정하고 초기화 시간과 동시 처리 수가 달라질 때를 살펴봅니다.

## 1. 콜드 스타트가 응답시간에 미치는 영향

Lambda가 새 실행 환경을 만들면 런타임과 확장을 시작하고 핸들러 밖의 초기화 코드를 실행합니다. 이 초기화가 호출 경로에 들어가는 경우를 **콜드 스타트**라고 합니다. 기존 환경을 재사용하는 웜 호출은 정상적으로 이미 끝낸 초기화를 반복하지 않습니다. 배포 직후나 트래픽 급증으로 환경을 추가할 때는 평균 응답시간의 변화가 작아도 일부 요청의 지연이 크게 늘 수 있습니다. [Lambda 실행 환경 수명 주기 — Init phase, Cold starts and latency](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtime-environment.html)

CloudWatch의 `Duration`은 콜드 스타트 시간을 제외합니다. 사용자 지연은 호출자에서 측정한 응답시간의 p95·p99와 오류율을 보고, 원인 분석에는 초기화 로그의 `Init Duration`과 호출 로그를 사용합니다. 비용에는 실제 과금 시간인 `Billed Duration` 등 과금 대상 초기화·실행 기록을 사용합니다. 같은 응답 지연이라도 INIT, 핸들러, 외부 서비스 대기, 재시도의 비중은 달라질 수 있습니다. [Lambda 지표](https://docs.aws.amazon.com/lambda/latest/dg/monitoring-metrics-types.html) · [REPORT 로그 필드](https://docs.aws.amazon.com/lambda/latest/dg/python-logging.html) · [INIT 과금 안내](https://aws.amazon.com/blogs/compute/aws-lambda-standardizes-billing-for-init-phase/)

## 2. 동시성과 응답시간

동시성은 한 시점에 처리 중인 호출 수입니다. 유입과 처리 시간이 비교적 안정적인 구간에서는 `초당 요청 수 × 평균 처리 시간(초)`로 평균 동시성을 추정할 수 있습니다. 초당 35건을 평균 0.2초에 처리하면 약 7개, 외부 API 지연으로 평균이 0.4초가 되면 약 14개가 필요합니다. 이 값은 순간 피크의 상한이 아닙니다. 트래픽이 몰리면 환경을 추가하는 동안 콜드 스타트가 생길 수 있고, 가용 동시성이나 확장·요청률 한도에 닿으면 제한(Throttling)이 발생할 수 있습니다. 동기 호출에서 클라이언트가 재시도하면 사용자 대기와 업무당 호출량이 늘 수 있습니다. [Lambda Event Function scaling — Calculating concurrency, Concurrency quotas](https://docs.aws.amazon.com/lambda/latest/dg/lambda-concurrency.html)

| 기능 | 하는 일 | 응답시간과 비용 |
|---|---|---|
| Reserved Concurrency | 함수에 동시성 용량을 확보하면서 함수의 최대 동시성도 정합니다. | 별도 용량 요금은 없습니다. 실행 환경을 미리 초기화하지 않으며, 한도에 도달하면 요청이 제한될 수 있습니다. |
| Provisioned Concurrency | 게시된 버전 또는 별칭에 초기화된 실행 환경을 미리 할당합니다. | 준비된 용량이 요청을 처리하면 일반적인 초기화 대기를 줄일 수 있습니다. 호출이 없어도 할당 요금이 발생합니다. |

Provisioned Concurrency를 설정한 버전이나 별칭으로 트래픽이 들어와야 준비된 환경을 사용합니다. `$LATEST`에는 설정할 수 없습니다. 준비된 용량을 초과하면 가용 한도 내에서 On-Demand로 처리되는 **spillover**가 생길 수 있습니다. 이 구간에는 On-Demand 실행 단가와 콜드 스타트 가능성이 다시 적용됩니다. On-Demand 여유도 없으면 제한이 생길 수 있으므로 할당량과 계정·함수 한도를 함께 봅니다. [Reserved와 Provisioned 동시성](https://docs.aws.amazon.com/lambda/latest/dg/lambda-concurrency.html) · [Provisioned Concurrency 설정](https://docs.aws.amazon.com/lambda/latest/dg/provisioned-concurrency.html) · [Lambda 요금](https://aws.amazon.com/lambda/pricing/)

## 3. 두 가지 접근과 비용 구성

**초기화 최적화**는 필요한 라이브러리만 불러오고 시작 시점의 불필요한 작업을 줄이는 방식입니다. 특정 경로에서만 쓰는 의존성은 지연 초기화를 검토할 수 있습니다. 작업이 첫 호출의 핸들러로 옮겨진다면 `Init Duration`만 줄고 사용자 지연은 그대로일 수 있으므로 그 경로의 종단 간 시간도 비교합니다. 공통 클라이언트나 연결을 재사용할 때는 요청별 데이터를 공유 상태에 남기지 않도록 구분합니다. [Optimizing static initialization](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtime-environment.html#static-initialization)

**Provisioned Concurrency**는 초기화를 요청 전에 수행합니다. 비용은 세 부분으로 나눕니다.

1. **할당료**는 메모리(GB) × 준비한 동시성 수 × 활성 과금 시간(초) × 할당 단가입니다. 활성 시간은 5분 단위로 올림합니다.
2. **실행료**는 준비 용량의 과금 GB-초에 해당 실행 단가를 곱합니다. 사전 초기화와 환경 재생성 시 재초기화도 과금 대상이며, 해당 환경이 요청을 처리하지 않아도 초기화 비용이 발생할 수 있습니다. Spillover의 GB-초는 On-Demand 실행 단가로 분리합니다.
3. **요청료**는 과금 요청 건수에 적용합니다. 준비 용량의 실행료와 할당료는 별개입니다.

[AWS Lambda pricing — Provisioned Concurrency Pricing](https://aws.amazon.com/lambda/pricing/) · [Provisioned Concurrency — Logging and billing behavior](https://docs.aws.amazon.com/lambda/latest/dg/provisioned-concurrency.html)

## 4. 가상 예제. 같은 요청 36만 건을 비교

1,024 MB(1 GB), 한 달 중 같은 트래픽 구간 **60시간**, 호출 **360,000건**을 비교합니다. 메모리·입력·아키텍처는 같고, 호출당 과금 요청 1건, 핸들러 과금 시간 200 ms를 가정합니다. 두 On-Demand 구성에서 콜드 스타트는 10%(36,000건)이며, 초기화 최적화는 발생률을 그대로 두고 추가 과금 시간을 400 ms에서 100 ms로 줄인다고 가정합니다.

Provisioned Concurrency 구성은 원래 코드에 준비 용량 10개를 적용합니다. 준비 시간이 포함된 과금 활성 시간의 합을 60시간으로 놓고, 모든 요청이 준비된 환경에서 처리된다고 가정합니다. 사전·재초기화의 합계 **2,000 GB-초**는 별도의 가상 값입니다. 어느 행에도 실패·재시도는 없습니다.

| 가상 단가 | 값 |
|---|---:|
| On-Demand 실행 | 0.000020 USD/GB-초 |
| 준비 용량에서의 실행·초기화 | 0.000012 USD/GB-초 |
| Provisioned Concurrency 할당 | 0.000005 USD/GB-초 |
| 요청 | 0.25 USD/100만 건 |

공통 핸들러 사용량은 `1 × 0.200 × 360,000 = 72,000 GB-초`, 요청료는 `360,000 ÷ 1,000,000 × 0.25 = 0.090 USD`입니다.

| 구성 | 과금 실행·초기화 | 할당료 | 요청료 | 비교 구간 합계 |
|---|---|---:|---:|---:|
| 기존 On-Demand | `(72,000 + 36,000 × 0.400) × 0.000020 = 1.728 USD` | 0 | 0.090 USD | **1.818 USD** |
| 초기화 최적화 후 On-Demand | `(72,000 + 36,000 × 0.100) × 0.000020 = 1.512 USD` | 0 | 0.090 USD | **1.602 USD** |
| Provisioned Concurrency 10개 | `(72,000 + 2,000) × 0.000012 = 0.888 USD` | `1 × 10 × 60 × 3,600 × 0.000005 = 10.800 USD` | 0.090 USD | **11.778 USD** |

준비 용량의 실행 단가는 낮지만 이 예제에서는 호출을 기다리는 동안의 할당료가 합계에서 가장 큽니다. 트래픽 구간 밖의 사용량, 무료 제공량, 할인·세금, 로그·전송·추가 임시 스토리지, 외부 서비스와 개발 비용은 제외했습니다. 실제 단가나 청구액은 리전·아키텍처·사용량 조건과 실제 초기화·spillover 기록으로 다시 계산합니다.

## 5. 응답시간 목표로 후보 고르기

같은 비교 구간에 다음과 같은 **가상 종단 간 p99**를 가정합니다. 표의 p99는 평균 과금 시간으로 계산한 값이 아닙니다.

| 구성 | 사용자 응답 p99 | 가상 목표 p99 ≤ 350 ms |
|---|---:|---|
| 기존 On-Demand | 680 ms | 미충족 |
| 초기화 최적화 후 On-Demand | 370 ms | 미충족 |
| Provisioned Concurrency | 290 ms | 충족 |

이 경우 준비 용량을 쓰는 구성만 지연 목표를 충족합니다. 목표가 400 ms라면 초기화 최적화 후 On-Demand도 통과하며, 가상 비용은 그쪽이 낮습니다. 운영 비교에서는 성공률·타임아웃·피크 처리량까지 충족하는 후보끼리 비용을 비교합니다.

- **지연 원인을 먼저 나눕니다.** 콜드 스타트 비율과 INIT 시간, 피크 처리 시간, 외부 서비스 대기, 제한·재시도를 함께 봅니다. 외부 호출이 느리다면 미리 초기화해도 그 대기는 남습니다.
- **준비 용량을 검토할 때는 피크를 봅니다.** `ConcurrentExecutions`, `Throttles`, `ProvisionedConcurrencyUtilization`, `ProvisionedConcurrencySpilloverInvocations`를 함께 확인합니다. 평균 동시성만으로 용량을 확정하면 짧은 급증을 놓칠 수 있습니다.
- **필요한 시간대와 실제 사용을 맞춥니다.** 피크가 예측 가능하면 AWS가 제공하는 예약 시간 기반 조정을 검토할 수 있습니다. 준비 완료까지 걸리는 시간과 사용하지 않는 구간의 할당료도 포함합니다. 두 접근을 함께 적용할 수도 있으므로, 그 경우 초기화량과 지연을 다시 비교합니다.

[Lambda 지표 — 호출·동시성](https://docs.aws.amazon.com/lambda/latest/dg/monitoring-metrics-types.html) · [Provisioned Concurrency — Application Auto Scaling](https://docs.aws.amazon.com/lambda/latest/dg/provisioned-concurrency.html)

## 6. 학습 확인과 한계

1. 초당 35건의 처리 시간이 200 ms에서 400 ms로 바뀌면 평균 동시성 추정값은 어떻게 달라지나요?
2. 호출이 전혀 없는 구간에도 Provisioned Concurrency 비용이 생길 수 있는 이유는 무엇인가요?

공식 문서로 초기화와 동시성 동작, 할당·실행·요청 과금 항목을 확인했습니다. 비용과 지연은 가상 값이며 실제 콜드 스타트 발생률, 준비 시간, spillover와 청구액은 측정하지 않았습니다.

## 공식 참고 자료

확인일은 **2026-11-07**입니다.

| 자료 | 확인 범위 |
|---|---|
| [Understanding the Lambda execution environment lifecycle](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtime-environment.html) | Init phase, Cold starts and latency, Optimizing static initialization |
| [Understanding Lambda Event Function scaling](https://docs.aws.amazon.com/lambda/latest/dg/lambda-concurrency.html) | 동시성 추정, Reserved·Provisioned Concurrency, 요청률 및 동시성 한도 |
| [Configuring provisioned concurrency for an Event Function](https://docs.aws.amazon.com/lambda/latest/dg/provisioned-concurrency.html) | 버전·별칭, 초과 트래픽, 초기화 과금, Application Auto Scaling |
| [AWS Lambda pricing](https://aws.amazon.com/lambda/pricing/) · [AWS Lambda standardizes billing for INIT Phase](https://aws.amazon.com/blogs/compute/aws-lambda-standardizes-billing-for-init-phase/) | Provisioned Concurrency Pricing, On-Demand 초과 실행, INIT 과금 |
| [Types of metrics for Lambda Event Functions](https://docs.aws.amazon.com/lambda/latest/dg/monitoring-metrics-types.html) · [Log and monitor Python Lambda Event Functions](https://docs.aws.amazon.com/lambda/latest/dg/python-logging.html) | Duration, 호출·동시성 지표, REPORT 필드 |

[AWS 학습 목차](../README.md) · [전체 학습 목차](../../README.md)

## 확인 문제 정답

1. `35 × 0.2 = 7`에서 `35 × 0.4 = 14`로 늘어납니다. 피크 순간의 필요 용량은 별도로 확인합니다.
2. 환경을 준비한 채 유지한 시간에 할당료가 붙습니다. 요청이 없어도 환경 할당이나 재생성 중에 실행된 초기화에는 별도 실행료가 생길 수 있습니다.
