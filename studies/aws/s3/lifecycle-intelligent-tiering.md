# S3 비용 산정 02 — Lifecycle과 Intelligent-Tiering 비교

> 저장량이 같아도 객체 크기, 접근 간격, 보관기간에 따라 어느 방식이 더 저렴한가?

[S3 비용 산정 01](README.md)에서 구분한 저장·요청·조회 비용을 바탕으로, 범용 버킷의 동일 데이터에 세 가지 방식을 비교합니다. Standard 유지, Lifecycle로 30일 경과 후 Standard-IA 전환, 업로드 시점부터 Intelligent-Tiering 사용입니다. 예제는 모두 밀리초 접근이 가능한 범위로 맞춥니다.

## 1. 비용이 달라지는 조건

| 기준 | Lifecycle로 Standard-IA 전환 | Intelligent-Tiering |
|---|---|---|
| 이동 기준 | 객체 나이와 규칙의 필터로 전환 대상을 정합니다. 전환한 객체를 읽어도 Standard로 자동 복귀하지 않습니다. | Frequent Access에서 시작합니다. 연속 미접근 30일에 Infrequent Access, 90일에 Archive Instant Access로 이동합니다. GET 등 해당 접근이 발생하면 Frequent Access로 복귀합니다. |
| 객체 크기 | 현행 기본 설정에서는 128 KB 미만 객체를 전환하지 않습니다. 명시적인 크기 필터 등 예외가 있으며, Standard-IA에 들어간 작은 객체는 최소 128 KB로 과금합니다. | 128 KB 미만 객체는 Frequent Access에 머물며 자동 계층화와 모니터링료가 적용되지 않습니다. |
| 이동·조회 비용 | 대상 클래스의 전환 요청료를 객체마다 계산합니다. 전환 자체의 조회료는 없지만, 전환 이후 Standard-IA에서 읽은 데이터에는 조회료가 붙습니다. | 대상 객체 수에 따라 모니터링·자동화 비용이 발생합니다. 클래스 내부 이동에는 별도 전환료가 없고, 예제의 자동 계층에서 일반 조회료는 없습니다. GET 등 요청료는 별개입니다. |
| 보관기간 | Standard-IA 전환 후 최소 30일입니다. 조기 삭제·덮어쓰기·전환 시 남은 기간의 저장료가 추가될 수 있습니다. | 클래스의 최소 저장 기간은 없습니다. 30일·90일은 할인 계층으로 이동하기 위한 연속 미접근 기간입니다. |

Lifecycle을 사용해 기존 객체를 Intelligent-Tiering **클래스에 처음 넣을 때**는 전환 요청료를 따로 계산합니다. 같은 클래스 내부의 자동 계층 이동과 구분해야 합니다. 접근 이력을 볼 때도 GET과 LIST를 구분합니다. AWS 문서에 따르면 LIST와 HEAD는 Infrequent Access 또는 Archive Instant Access에서 Frequent Access로 복귀시키는 요청에 해당하지 않습니다. [Lifecycle 관리](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html) · [Lifecycle 전환 제약](https://docs.aws.amazon.com/AmazonS3/latest/userguide/lifecycle-transition-general-considerations.html) · [Intelligent-Tiering 동작](https://docs.aws.amazon.com/AmazonS3/latest/userguide/intelligent-tiering-overview.html) · [S3 요금](https://aws.amazon.com/s3/pricing/)

Intelligent-Tiering의 선택적 Archive Access·Deep Archive Access를 켜면 해당 객체는 사전 복원이 필요하고 메타데이터 저장료도 고려해야 합니다. Archive Access의 Expedited 복원에는 별도 요금이 붙습니다. 아래 계산은 이 두 선택적 계층을 사용하지 않습니다. [Intelligent-Tiering 접근 계층](https://docs.aws.amazon.com/AmazonS3/latest/userguide/intelligent-tiering-overview.html) · [S3 요금의 복원 조건](https://aws.amazon.com/s3/pricing/)

## 2. 가상 단가와 계산 범위

예제 A·B는 같은 날 업로드한 **1 MiB 객체 1,024개**, 총 **1 GiB**입니다. 30일을 1개월로 놓고, Lifecycle의 과금 전환 시점은 30일 경과 시로 단순화합니다. Intelligent-Tiering 모니터링료는 대상 객체의 체류 일수에 비례하는 것으로 가정합니다. 모든 단가는 학습용 가상 값입니다.

| 항목 | 가상 단가 |
|---|---:|
| Standard 및 Intelligent-Tiering Frequent Access | 0.025 USD/(GiB·월) |
| Standard-IA 및 Intelligent-Tiering Infrequent Access | 0.015 USD/(GiB·월) |
| Intelligent-Tiering Archive Instant Access | 0.005 USD/(GiB·월) |
| Lifecycle의 Standard-IA 전환 | 0.004 USD/1,024객체 |
| Standard-IA에서 데이터 조회 | 0.010 USD/GiB |
| Intelligent-Tiering 모니터링·자동화 | 0.004 USD/(1,024객체·월) |

계산에는 저장료, 전환료, 클래스별 조회료, 모니터링료만 넣습니다. 초기 업로드, 일반 GET·LIST 요청, 전송, 복제, 이전 버전, 세금과 할인은 제외합니다. 실제 비교에는 클래스별 요청 단가와 건수도 반영해야 합니다.

## 3. 예제 A. 접근 간격에 따라 유리한 방식이 달라진다

120일 동안 보관합니다. 첫 시나리오는 업로드 이후 읽지 않습니다. 두 번째는 20·35·50·65·80·95·110일에 모든 객체를 한 번씩 읽습니다. 두 번째 시나리오에서 Lifecycle 전환 후 조회량은 여섯 번의 전체 읽기에 해당하는 6 GiB입니다. Intelligent-Tiering 객체는 미접근 30일을 채우지 않으므로 Frequent Access에 머뭅니다.

| 방식 | 업로드 후 읽기 없음 | 반복 읽기 |
|---|---:|---:|
| Standard | `0.025 × 4 = 0.100 USD` | `0.025 × 4 = 0.100 USD` |
| Lifecycle → Standard-IA | `0.025 + 0.015 × 3 + 0.004 = 0.074 USD` | `0.074 + 6 × 0.010 = 0.134 USD` |
| Intelligent-Tiering | `0.025 + 0.015 × 2 + 0.005 + 0.004 × 4 = 0.076 USD` | `0.025 × 4 + 0.004 × 4 = 0.116 USD` |

읽지 않는 경우에는 30일 후 일괄 전환이 이 가상 단가에서 가장 저렴합니다. 반복해서 읽으면 Intelligent-Tiering이 Standard-IA 조회료를 피하지만, Frequent Access에 머무르는 동안의 모니터링료로 인해 Standard가 가장 저렴합니다. 평균 조회량에 더해 **어떤 객체를 몇 일 간격으로 읽는지** 확인해야 계층별 체류 시간을 추정할 수 있습니다.

## 4. 예제 B. 40일 보관하면 전환 비용을 회수할 시간이 줄어든다

같은 객체를 읽지 않고 40일에 삭제합니다. Lifecycle은 Standard 30일 후 Standard-IA에 10일 머무르지만, Standard-IA의 최소 30일 중 남은 20일분을 더 냅니다.

| 방식 | 계산 | 합계 |
|---|---|---:|
| Standard | `0.025 × 40/30` | 약 0.0333 USD |
| Lifecycle → Standard-IA | `0.025 + 0.015 × (10 + 20)/30 + 0.004` | 0.0440 USD |
| Intelligent-Tiering | `0.025 + 0.015 × 10/30 + 0.004 × 40/30` | 약 0.0353 USD |

이 가정에서는 10일치 저렴한 저장료로는 Intelligent-Tiering의 모니터링료를 상쇄하지 못합니다. Lifecycle은 남은 최소 기간과 전환 요청료가 더해집니다. 예상 만료일에서 **전환 후 남은 보관기간**을 계산해 비교합니다.

## 5. 예제 C. 같은 1 GiB를 64 KiB 객체로 나누면

이번에는 읽지 않는 데이터 1 GiB가 **64 KiB 객체 16,384개**로 구성되고 120일 동안 보관됩니다. 두 기본 동작은 모두 120일 저장료가 **0.100 USD**입니다. Lifecycle은 작은 객체를 Standard에 그대로 두고, Intelligent-Tiering은 모니터링료 없이 Frequent Access에 유지합니다.

명시적인 크기 필터로 작은 객체도 Standard-IA에 전환한다고 가정하면, 객체별 과금 크기가 128 KiB 상당으로 올라가 전체 과금 용량은 2 GiB입니다. 전환 요청 수도 예제 A의 16배입니다. 이 가상 계산에서는 AWS 문서의 128 KB 기준을 128 KiB로 표시합니다.

`0.025 × 1 GiB × 1개월 + 0.015 × 2 GiB × 3개월 + 0.004 × 16 = 0.179 USD`

동일한 실제 저장량이라도 객체별 과금 크기와 전환 요청 수가 달라지면 저장 단가 차이보다 비용 영향이 커질 수 있습니다.

## 6. 적용 전에 확인할 자료

- **객체 크기와 수**를 접두사나 데이터 종류별로 집계합니다. 128 KB 미만 객체 비중이 높으면 용량만으로 전환 효과를 추정하기 어렵습니다.
- **객체별 접근 간격과 전환 후 조회량**을 업무 주기별로 확인합니다. 계절성, 일괄 재처리, 복구 시의 집중 읽기를 포함합니다.
- **예상 만료일과 보존 의무**를 확인합니다. Lifecycle 규칙은 기존 객체에도 적용될 수 있으므로 만료 규칙의 범위와 버전별 동작을 점검합니다.
- **접근 시간과 복원 요건**을 먼저 정합니다. 즉시 접근이 필요한 데이터와 복원 대기를 허용하는 데이터를 구분하고, 그 요건을 충족하는 후보끼리 비용을 비교합니다.

가상 예제에서는 조건을 하나씩 바꿔 비용 차이를 확인했습니다. 실제 청구액, 객체별 접근 이력, 계층 체류일, 복원 지연은 측정하지 않았습니다.

## 공식 참고 자료

확인일은 **2026-11-07**입니다.

| 자료 | 확인한 범위 |
|---|---|
| [Amazon S3 pricing](https://aws.amazon.com/s3/pricing/) | Storage pricing, Requests & data retrievals의 모니터링·조회·전환료와 최소 과금 조건 |
| [Managing the lifecycle of objects](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html) | 전환과 만료, 기존 객체에 적용되는 규칙, 과금 시점 |
| [Transitioning objects using Amazon S3 Lifecycle](https://docs.aws.amazon.com/AmazonS3/latest/userguide/lifecycle-transition-general-considerations.html) | 소형 객체의 기본 전환 제한·예외와 최소 저장 기간 |
| [How S3 Intelligent-Tiering works](https://docs.aws.amazon.com/AmazonS3/latest/userguide/intelligent-tiering-overview.html) | 30일·90일 미접근, 계층을 바꾸는 요청, 소형 객체와 선택적 아카이브 |

[AWS 학습 목차](../README.md) · [전체 학습 목차](../../README.md)
