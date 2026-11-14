# Lambda 비용 산정 01 — 메모리·실행시간·요청 비용

[AWS 서비스 목차](../README.md)

> 메모리를 늘려 실행이 빨라지면 비용은 얼마나 달라지는가? 서비스가 요구하는 응답시간을 충족하는 구성은 어떻게 고르는가?

커리큘럼 02. AWS Infrastructure & Pricing의 학습 노트입니다. [RDS Rightsizing](../rds/rightsizing.md)에 이어, 이번에는 AWS Lambda의 일반 On-Demand **Event Function** 한 개를 비교합니다.

## 1. 메모리 설정이 실행시간에 미치는 영향

Lambda Event Function의 메모리는 128 MB부터 10,240 MB까지 1 MB 단위로 설정할 수 있습니다. AWS는 설정 메모리에 비례해 CPU 용량을 할당하며, 1,769 MB는 vCPU 1개에 해당하는 CPU 용량을 제공합니다. 따라서 메모리를 늘리면 메모리 부족을 완화하거나 CPU 연산을 빠르게 끝낼 수 있습니다. 반면 RDS 쿼리나 외부 API 응답을 기다리는 시간이 대부분이면, CPU 여유가 늘어도 전체 시간의 감소 폭이 작을 수 있습니다. 감소 폭은 워크로드별로 확인해야 합니다. [Configure Lambda Event Function memory](https://docs.aws.amazon.com/lambda/latest/dg/configuration-memory.html)

## 2. 실행시간과 비용을 계산하는 단위

| 항목 | 비용 비교에서의 역할 |
|---|---|
| 설정 메모리 | GB-초 계산에 사용할 할당량입니다. 실제 최대 메모리 사용량은 적정성을 확인하는 지표로 따로 봅니다. |
| 과금 실행시간 | 각 호출의 과금 대상 시간을 1 ms 단위로 올림한 값입니다. 로그의 `Billed Duration`을 확인합니다. |
| GB-초 | 설정 메모리(GB) × 과금 실행시간(초)입니다. 월간 사용량은 호출별 GB-초를 더합니다. |
| 요청 비용 | 과금 요청 수 × 요청 단가입니다. 과금 요청 수가 같으면 메모리 변경만으로 이 항목은 달라지지 않습니다. |

이 문서의 환산은 AWS 요금 예제와 같이 1,024 MB를 1 GB로, 1,000 ms를 1초로 계산합니다. 같은 메모리 구성의 월 GB-초는 `설정 메모리(GB) × 호출별 과금 실행시간 합계(초)`입니다. 이미 올림된 과금 시간을 합산하며, 평균 핸들러 시간에 한 번만 올림을 적용하는 방식은 정확한 청구량과 달라질 수 있습니다. [AWS Lambda pricing — Event Functions](https://aws.amazon.com/lambda/pricing/) · [AWS INIT 과금 안내](https://aws.amazon.com/blogs/compute/aws-lambda-standardizes-billing-for-init-phase/)

**핸들러 시간, 과금 시간, 서비스 응답시간은 따로 기록합니다.** CloudWatch의 `Duration`에는 콜드 스타트가 포함되지 않습니다. AWS는 2025년 8월 1일부터 관리형 런타임의 ZIP 패키지 On-Demand 호출에도 INIT 단계 과금을 적용했습니다. 콜드 스타트가 섞인 비용은 `REPORT`의 `Billed Duration`을 기준으로 추정하고, 서비스 응답시간은 사용자 요청이 들어와 응답할 때까지의 경로에서 확인합니다. [Lambda 지표 — Performance metrics](https://docs.aws.amazon.com/lambda/latest/dg/monitoring-metrics-types.html) · [REPORT 로그 필드](https://docs.aws.amazon.com/lambda/latest/dg/python-logging.html) · [AWS INIT 과금 안내](https://aws.amazon.com/blogs/compute/aws-lambda-standardizes-billing-for-init-phase/)

예제는 호출 1회당 과금 요청 1건을 가정합니다. 실제로는 이벤트와 과금 요청을 따로 집계해야 할 수 있습니다. 예를 들어 비동기 이벤트는 처음 256 KB에 요청 1건이 적용되고, 초과분은 64 KB 단위로 추가 요청이 계산됩니다. 호출 재시도나 이벤트 배치로 업무 건수와 호출 수도 달라질 수 있습니다. [AWS Lambda pricing — Requests](https://aws.amazon.com/lambda/pricing/)

## 3. 가상 예제. 같은 업무에 메모리 세 가지를 비교

같은 코드, 런타임, 아키텍처, 리전과 입력 분포로 월 **2,000,000회**를 처리한다고 가정합니다. 각 구성의 요청 수와 성공한 업무 건수는 같고 재시도는 없습니다. 표의 시간과 메모리 사용량은 모두 가상 값입니다. 평균 과금 시간에는 해당 호출에서 과금된 초기화 시간이 반영됐다고 가정합니다.

- 실행 단가 **0.000020 USD/GB-초**
- 요청 단가 **0.25 USD/100만 건**
- 포함 범위는 On-Demand 실행과 요청 비용입니다. 무료 제공량, 사용량 구간 할인, 세금, Provisioned Concurrency, 추가 임시 스토리지, 로그와 다른 서비스 비용은 제외합니다.

| 설정 메모리 | 평균 과금 시간 | 월 GB-초 | 실행 비용 | 요청 비용 | 월 합계 |
|---|---:|---:|---:|---:|---:|
| 512 MB = 0.5 GB | 800 ms | `0.5 × 0.800 × 2,000,000 = 800,000` | 16.00 USD | 0.50 USD | **16.50 USD** |
| 1,024 MB = 1 GB | 300 ms | `1 × 0.300 × 2,000,000 = 600,000` | 12.00 USD | 0.50 USD | **12.50 USD** |
| 2,048 MB = 2 GB | 210 ms | `2 × 0.210 × 2,000,000 = 840,000` | 16.80 USD | 0.50 USD | **17.30 USD** |

요청 비용은 각 구성에서 `2,000,000 ÷ 1,000,000 × 0.25 = 0.50 USD`입니다. 실행 단가와 요청 수가 같으면, 메모리를 두 배로 늘렸을 때 평균 과금 시간이 절반 미만으로 줄어야 실행 비용이 낮아집니다. 512 MB의 800 ms를 기준으로 1,024 MB의 손익분기점은 **400 ms**입니다. 가상 값 300 ms는 이보다 짧습니다. 1,024 MB의 300 ms에서 2,048 MB로 늘리면 손익분기점은 **150 ms**인데, 가상 값은 210 ms여서 실행 비용이 늘어납니다.

실제 단가는 리전, 아키텍처, 사용량 구간 등에 따라 확인합니다. 위 금액은 특정 AWS 가격표를 적용한 견적이나 측정 결과에 해당하지 않습니다. [AWS Lambda pricing — Event Functions, On-Demand pricing tiers](https://aws.amazon.com/lambda/pricing/)

## 4. 성능 요건을 먼저 적용한 뒤 비용 비교

이 예제의 서비스 목표를 **사용자 응답시간 p95 ≤ 500 ms**로 정합니다. p95는 관측한 응답의 약 95%가 해당 시간 안에 들어오는 경계입니다. 아래 응답시간은 호출 경로 전체의 가상 값이며 3절의 평균 과금 시간과 별개입니다.

| 메모리 | 가상 사용자 응답 p95 | 지연 요건 |
|---|---:|---|
| 512 MB | 1,100 ms | 미충족 |
| 1,024 MB | 460 ms | 충족 |
| 2,048 MB | 340 ms | 충족 |

이 가정에서 1,024 MB는 지연 요건을 충족하는 구성 중 월 비용이 가장 낮습니다. 목표가 400 ms라면 표에서 2,048 MB만 통과합니다. 실제로는 지연 외에 성공률·처리량·메모리 여유까지 확인해야 후보를 확정할 수 있습니다.

1. **비교 조건을 맞춥니다.** 동일 코드·런타임·아키텍처와 입력 크기 분포를 기준으로 평시·피크 부하, 웜 호출과 콜드 스타트를 함께 봅니다. 외부 의존 서비스의 대기가 변하면 원인을 구분합니다.
2. **서비스 기준으로 걸러냅니다.** 사용자 관점 p95·p99, 성공률, 타임아웃, 메모리 부족과 피크 처리량을 확인합니다. `Errors`와 `Throttles`를 따로 보고 동시성 부족이나 비동기 대기 증가도 살핍니다. `Max Memory Used`는 실행 환경을 공유한 호출의 최대값이 반영될 수 있으므로 로그 한 줄만으로 여유를 확정하지 않습니다.
3. **통과 후보의 비용을 비교합니다.** 과금 요청 수와 호출별 `Billed Duration`을 사용합니다. 실패·재시도가 다른 구성은 성공한 업무 건당 총비용도 함께 비교합니다. 중요한 피크 구간이나 콜드 스타트 자료가 빠지면 최종 구성 판단을 보류합니다.

[Lambda 모범 사례 — Event Function configuration](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html) · [Lambda 지표 — 호출·성능·동시성](https://docs.aws.amazon.com/lambda/latest/dg/monitoring-metrics-types.html) · [REPORT 로그 필드](https://docs.aws.amazon.com/lambda/latest/dg/python-logging.html)

## 5. 확인 문제

1. 512 MB에서 1,024 MB로 늘릴 때, 평균 과금 시간 800 ms가 450 ms로 줄면 실행 비용은 어느 쪽이 낮나요?
2. 가상 예제에서 목표가 사용자 응답 p95 400 ms라면 어떤 구성이 지연 요건을 충족하나요?
3. `Duration` 평균만으로 월 GB-초를 계산할 때 어떤 항목을 놓칠 수 있나요?

## 6. 확인 범위와 다음 질문

AWS 문서에서 메모리·CPU 관계, 요청·GB-초 과금, INIT 과금과 관측 지표를 확인했습니다. 실행시간, 사용자 지연, 월 비용은 가상 예제입니다. 실제 호출 분포와 외부 의존 서비스의 응답시간, 요금, 장애율은 측정하지 않았습니다.

> 다음 질문: 콜드 스타트와 동시성 한도가 응답 지연에 영향을 줄 때, 초기화 최적화와 Provisioned Concurrency의 비용을 어떻게 비교할 수 있는가?

## 공식 참고 자료

확인일은 **2026-11-07**입니다.

| 자료 | 확인 범위 |
|---|---|
| [AWS Lambda pricing](https://aws.amazon.com/lambda/pricing/) | Event Functions, 요청·GB-초, 비동기 페이로드, On-Demand 가격 구간 |
| [Configure Lambda Event Function memory](https://docs.aws.amazon.com/lambda/latest/dg/configuration-memory.html) | 메모리 범위, CPU 할당, 메모리 설정 판단 |
| [AWS Lambda standardizes billing for INIT Phase](https://aws.amazon.com/blogs/compute/aws-lambda-standardizes-billing-for-init-phase/) | Understanding the billing changes, 과금 단위와 INIT 반영 |
| [Types of metrics for Lambda Event Functions](https://docs.aws.amazon.com/lambda/latest/dg/monitoring-metrics-types.html) | 호출·성능·동시성 및 비동기 호출 지표 |
| [Log and monitor Python Lambda Event Functions](https://docs.aws.amazon.com/lambda/latest/dg/python-logging.html) · [Best practices for working with AWS Lambda Event Functions](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html) | REPORT 필드, 메모리와 실행 성능 비교 |

[AWS 학습 목차](../README.md) · [전체 학습 목차](../../README.md)

## 확인 문제 정답과 해설

1. 512 MB는 호출당 `0.5 × 0.800 = 0.400 GB-초`이고, 1,024 MB는 `1 × 0.450 = 0.450 GB-초`입니다. 단가와 호출 수가 같으면 512 MB의 실행 비용이 더 낮습니다.
2. 2,048 MB만 p95 400 ms를 충족합니다. 이 예제에서 월 비용은 17.30 USD입니다.
3. 핸들러 시간에는 콜드 스타트 초기화가 포함되지 않으며 호출별 과금 시간은 밀리초 단위로 올림됩니다. 비용 추정에는 호출별 `Billed Duration`을 사용합니다.

## 추가(2026-11-15) — 메시지마다 호출 vs 묶어 호출

> SQS 메시지 1,000만 건을 처리할 때 1건씩 호출하는 것과 10건씩 묶어 호출하는 것은 비용이 얼마나 다른가?

**과금 단위.** SQS 이벤트 소스 매핑은 **배치 1개당 호출 1회**입니다. 기본 최대 배치 크기는 10건이고, 배치 창(batching window)을 최대 5분까지 두면 메시지를 더 모은 뒤 호출합니다. 요청 0.20 USD/100만 건, x86 실행 0.0000166667 USD/GB-초(처음 60억 GB-초). 프로비저닝 모드 이벤트 폴러를 켜면 폴러 단위 시간 요금이 따로 붙습니다(SQS 폴러 0.0113 USD/단위-시간, 서울. [2026-11-15 사본](../../../references/aws-price-list-apn2-2026-11-15.json)).

**가상 예시.** 512 MB 함수, 메시지 처리 20 ms, 호출마다 고정 준비 시간 30 ms(연결 확인·설정 읽기 등, 가정).

| 방식 | 호출 수 | 호출당 시간 | GB-초 | 월 비용 |
|---|---:|---:|---:|---:|
| 1건씩 | 1,000만 | 50 ms | 250,000 | 6.17 USD |
| 10건씩 | 100만 | 230 ms | 115,000 | 2.12 USD |
| 10건씩 + 프로비저닝 폴러 1단위 상시 | 100만 | 230 ms | 115,000 | 2.12 + 8.25 = 10.37 USD |

묶음 효과는 요청 요금 감소(2.00 → 0.20)와 고정 준비 시간의 분할에서 옵니다. 반대로 처리량이 작은데 프로비저닝 폴러를 상시로 두면 **상시 고정비**가 절감분보다 커집니다.

**낭비 판단 자료.** `Invocations`와 SQS 수신 메시지 수의 비율(평균 배치 크기), 호출당 `Billed Duration` 분포, 배치 창 설정, 폴러 모드, 지연 허용치(배치 창만큼 지연이 늘어남). 부분 실패 시 배치 전체를 재처리하면 비용이 늘 수 있어 `ReportBatchItemFailures` 사용 여부도 봅니다.

**확인 문제.** 평균 배치 크기가 1.3이면 묶음 설정이 효과가 있나요? **해설.** 거의 없습니다. 메시지가 드문드문 와서 배치가 차지 않는 경우이므로, 지연을 허용한다면 배치 창을 늘려야 묶입니다.

| 공식 자료 (확인일 2026-11-15) | 확인 범위 |
|---|---|
| [Using Lambda with Amazon SQS](https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html) | 배치당 1회 호출, 기본 최대 10건, 배치 창 최대 5분, 프로비저닝 모드 |
| [AWS Lambda pricing](https://aws.amazon.com/lambda/pricing/) · [Price List — AWSLambda](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSLambda/current/ap-northeast-2/index.json) | 요청·GB-초·이벤트 폴러 단위 요율, 게시일 2026-11-11 |
