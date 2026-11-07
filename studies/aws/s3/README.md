# S3 비용 산정 01 — Storage Class와 요청·조회·전송 비용

> 같은 데이터를 Amazon S3에 저장하더라도 저장 클래스, 접근 빈도, 객체 크기와 보관기간에 따라 전체 비용은 어떻게 달라지는가?

커리큘럼 02. AWS Infrastructure & Pricing의 학습 노트입니다. AWS 문서의 과금 조건을 먼저 정리하고, 가상 단가로 비용을 계산한 뒤 클래스 변경에 필요한 운영 자료를 살펴봅니다.

## 1. Amazon S3의 기본 구조

| 개념 | 비용과 사용 방식에 관련된 의미 |
|---|---|
| Object Storage | 데이터를 객체 단위로 저장하고 요청으로 읽거나 씁니다. |
| Bucket | 객체를 담는 컨테이너입니다. 이 노트는 범용 버킷을 기준으로 합니다. |
| Object | 데이터와 메타데이터를 묶은 저장 단위입니다. |
| Object Key | 버킷 안에서 객체를 식별하는 이름입니다. 버전 관리 사용 시 버전 ID로 특정 버전을 구분합니다. |
| Object Metadata | 콘텐츠 유형 등 객체를 설명하는 정보입니다. 일부 아카이브 클래스는 별도의 메타데이터 저장료를 적용합니다. |
| Storage Class | 객체별 저장·접근 방식과 비용 조건입니다. 한 버킷에 서로 다른 클래스의 객체를 둘 수 있습니다. |
| AWS Region | 버킷을 만드는 지리적 영역입니다. 실제 단가와 전송 경로를 확인할 때 출발점입니다. |

[EBS](../ebs/README.md)는 EC2에 연결해 디스크처럼 읽고 쓰는 블록 스토리지입니다. 프로비저닝한 용량과 성능이 주요 비용 기준입니다. S3는 객체의 과금 크기, 보관기간, 요청 횟수와 접근 경로를 함께 봅니다. [What is Amazon S3?](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html) · [Amazon S3 pricing](https://aws.amazon.com/s3/pricing/)

## 2. 비용 구성

| 항목 | 비용이 생기는 경우 |
|---|---|
| Storage | 객체의 과금 크기와 보관기간에 클래스별 단가를 적용합니다. 이전 버전이나 아카이브의 임시 복원 사본도 저장량에 포함될 수 있습니다. |
| Requests | PUT·GET·LIST·COPY·복원 등 요청의 종류와 횟수를 계산합니다. 단가 적용 기준은 요청과 클래스에 따라 달라집니다. |
| Data Retrieval | IA나 일부 Glacier 클래스로부터 데이터를 읽거나 복원할 때 적용되는 조회량 기준 비용입니다. 복원 방식에 따라 별도 요청료도 확인합니다. |
| Data Transfer | 인터넷 송신, 리전 간 전송 등 과금 대상 경로로 데이터를 보낼 때 발생합니다. |
| Lifecycle Transition | Lifecycle이 객체를 다른 클래스로 옮길 때 대상 클래스의 전환 요청 요율을 적용합니다. |
| Monitoring 및 Automation | Intelligent-Tiering의 대상 객체 모니터링·자동화와 Storage Lens 고급 지표 등 사용 기능에 따른 비용입니다. |
| Replication 및 별도 기능 | 복제본 저장, 복제 PUT, 해당하는 조회 비용과 리전 간 송신을 확인합니다. Replication Time Control이나 Batch Operations 사용 시 해당 요금도 따로 봅니다. |

월 비용은 해당하는 항목을 합산합니다. 초기 업로드나 전환처럼 한 번 드는 비용과 매월 반복되는 저장·접근 비용은 비교 기간에 맞춰 구분합니다. [Amazon S3 pricing — Storage, Requests & data retrievals, Data transfer, Management & insights, Replication](https://aws.amazon.com/s3/pricing/)

## 3. Storage Class 비교

표의 가용성은 AWS의 설계값입니다. 복원 시간은 AWS가 제시하는 일반적인 범위로, 데이터 규모나 복원 옵션에 따라 달라집니다.

| 클래스 | 목적·접근 빈도 | 저장 요금 특징 | 조회료 | 최소 보관 | 최소 과금 크기·오버헤드 | 복원·접근 지연 | AZ·설계 가용성 |
|---|---|---|---|---|---|---|---|
| S3 Standard | 자주 읽는 활성 데이터 | 비교 기준이 되는 범용 저장 단가 | 없음 | 없음 | 없음 | 직접 GET, 밀리초 | 3개 이상·99.99% |
| S3 Standard-IA | 드물게 읽지만 즉시 필요한 장기 데이터 | Standard보다 낮은 저장 단가 | 있음 | 30일 | 128 KB | 직접 GET, 밀리초 | 3개 이상·99.9% |
| S3 One Zone-IA | 재생성 가능한 저빈도 데이터 또는 별도 복제본 | Standard-IA보다 낮은 저장 단가 | 있음 | 30일 | 128 KB | 직접 GET, 밀리초 | 1개·99.5%, AZ 상실에 취약 |
| S3 Intelligent-Tiering | 접근 빈도가 바뀌거나 예측하기 어려운 데이터 | 현재 접근 계층별 저장료와 대상 객체 모니터링료 | 일반 조회와 Standard·Bulk 복원은 무료. Archive Access의 Expedited는 유료 | 없음 | 최소 과금 크기 없음. 자동 계층화는 128 KB 이상. 선택적 Archive·Deep Archive Access는 객체당 40 KB 추가 | 자동 계층은 밀리초. 선택적 아카이브 계층은 사전 복원 필요 | 3개 이상·99.9% |
| S3 Glacier Instant Retrieval | 거의 읽지 않지만 즉시 필요한 아카이브 | 장기 저장 중심, 조회 시 별도 비용 | 있음 | 90일 | 128 KB | 직접 GET, 밀리초 | 3개 이상·99.9% |
| S3 Glacier Flexible Retrieval | 복원 대기를 허용하는 장기 아카이브 | 낮은 아카이브 저장 단가와 복원 사본 비용 고려 | 옵션별 적용. Bulk 조회 무료 | 90일 | 객체당 40 KB 추가 | 복원 필요. Standard 조회는 보통 3~5시간 | 3개 이상·복원 후 99.99% |
| S3 Glacier Deep Archive | 장기 보존하며 매우 드물게 복원하는 데이터 | 가장 낮은 저장 단가 쪽이며 보존·복원 조건이 엄격 | 옵션별 적용 | 180일 | 객체당 40 KB 추가 | 복원 필요. Standard 조회는 보통 12시간 이내 | 3개 이상·복원 후 99.99% |

Flexible Retrieval과 Deep Archive의 임시 복원 사본에는 보존한 기간만큼 Standard 저장료가 붙습니다. S3 Express One Zone은 단일 AZ의 지연 민감 애플리케이션에 맞춘 클래스로, 상세 비용은 후속 검토 대상으로 둡니다. [Storage class comparison](https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage-class-intro.html) · [Archive retrieval options](https://docs.aws.amazon.com/AmazonS3/latest/userguide/restoring-objects-retrieval-options.html) · [Amazon S3 pricing](https://aws.amazon.com/s3/pricing/)

## 4. 접근 패턴에 따른 선택

- **자주 읽는 데이터**는 Standard를 기준으로 반복 조회료를 피했을 때의 합계를 비교합니다.
- **드물게 읽고 즉시 접근해야 하는 데이터**는 Standard-IA 또는 Glacier Instant Retrieval의 최소 기간과 조회료를 비교합니다. One Zone-IA는 AZ 상실 후 재생성 또는 다른 사본에서 복구할 수 있는지 확인합니다.
- **접근 빈도를 예측하기 어려운 데이터**는 Intelligent-Tiering의 모니터링 비용을 객체 수에 적용하고, 접근 계층별 체류 시간이 충분한지 평가합니다.
- **장기 백업·아카이브**는 복원 요청과 임시 사본 비용을 포함하고, 복원부터 데이터 검증까지의 시간이 복구 목표에 맞는지 확인합니다.
- **작은 객체가 많은 데이터**는 크기 분포, 객체 수, 요청 횟수를 함께 봅니다. 집계 저장 용량이 작아도 객체별 최소 크기, 메타데이터, 전환 요청료의 비중이 커질 수 있습니다.

## 5. PUT·GET·LIST·COPY·전환 요청

| 요청 | 발생 예 |
|---|---|
| PUT | 새 객체 업로드 또는 같은 키의 객체 덮어쓰기 |
| GET | 키로 객체 데이터 읽기. 일부 클래스는 조회량 비용도 함께 발생 |
| LIST | 버킷이나 접두사의 객체 목록 조회. 페이지가 여러 개면 호출 횟수 증가 |
| COPY | 기존 객체를 같은 버킷 또는 다른 버킷에 복사. 원본 클래스와 전송 경로에 따른 비용 확인 |
| Lifecycle Transition | 규칙에 맞는 객체의 클래스 전환. 대상 클래스 기준 요청료를 적용 |

총 1 GiB를 몇 개의 큰 객체로 읽는 경우와 수만 개의 작은 객체로 읽는 경우, 전송량이 같아도 호출 횟수가 달라집니다. 실제 비교에는 목록 페이지, 반복 호출, 콘솔 탐색 요청도 포함해 집계합니다. [Amazon S3 pricing — Requests & data retrievals](https://aws.amazon.com/s3/pricing/)

## 6. 데이터 조회와 전송 구분

**조회(Retrieval)**는 저장 클래스에서 데이터를 꺼내는 데 따른 항목입니다. **전송(Data Transfer)**은 꺼낸 데이터가 이동한 네트워크 경로에 따라 결정됩니다. 예를 들어 Standard-IA 객체를 같은 리전의 EC2에서 읽으면, 해당 경로의 S3 전송료가 면제돼도 GET과 조회료는 남을 수 있습니다.

- **인터넷 송신**에는 적용되는 무료 구간과 지역 조건을 확인합니다.
- **AWS 서비스 간 전송**은 같은 리전의 S3 버킷이나 AWS 서비스로 보내는 등 S3 요금표의 면제 조건을 확인합니다. 중간 네트워크 기능이나 수신 서비스의 비용은 별개입니다.
- **리전 간 전송**은 출발·도착 리전과 사용 기능을 확인합니다. 예를 들어 Cross-Region Replication에는 출발 리전 기준의 리전 간 송신 요금이 적용됩니다. [Amazon S3 pricing — Data transfer and Replication](https://aws.amazon.com/s3/pricing/)

## 7. 최소 기간과 객체 크기가 만드는 차이

- **기간**은 해당 클래스에 보관한 시간을 기준으로 봅니다. 예를 들어 Standard-IA 객체를 10일 만에 삭제하면 정상 사용분 10일에 최소 기간의 남은 20일분이 더해집니다. 조기 덮어쓰기나 클래스 전환에도 잔여 기간 비용이 생길 수 있습니다.
- **최소 크기**는 객체별로 적용합니다. 16 KB 객체를 Standard-IA에 저장하면 저장료 계산에는 128 KB를 사용합니다. Intelligent-Tiering에서는 128 KB 미만 객체가 Frequent Access에 남으며 모니터링·자동화 비용이 붙지 않습니다.
- **아카이브 메타데이터**는 Flexible Retrieval·Deep Archive와 Intelligent-Tiering의 선택적 Archive Access·Deep Archive Access에서 객체당 40 KB입니다. 8 KB는 Standard 요율, 32 KB는 해당 아카이브 요율로 계산합니다.
- **Lifecycle 전환 대상 크기**는 위 두 기준과 별개입니다. 2024년 9월 이후 기본 동작에서는 128 KB 미만 객체의 전환을 막습니다. 기존 규칙이나 명시적인 객체 크기 필터가 있다면 실제 정책을 확인합니다. [Amazon S3 pricing — Storage notes](https://aws.amazon.com/s3/pricing/) · [How S3 Intelligent-Tiering works](https://docs.aws.amazon.com/AmazonS3/latest/userguide/intelligent-tiering-overview.html) · [Lifecycle transition considerations](https://docs.aws.amazon.com/AmazonS3/latest/userguide/lifecycle-transition-general-considerations.html)

## 8. 가상 비용 계산

같은 객체 구성과 업무량을 두 클래스에 적용합니다. **100 GiB를 30일간 보관하고 30일을 1개월로** 계산합니다. 모든 객체가 128 KB 이상이며 Standard-IA 최소 기간을 충족합니다. 월 GET 100,000회, 실제 읽어낸 데이터는 200 GiB입니다. 같은 데이터를 반복해서 읽으면 월간 조회량은 저장량을 넘을 수 있습니다.

아래 단가는 **가상 값**입니다. 저장·GET·클래스별 조회료만 포함합니다. 전송, 초기 업로드, 전환, 복제, 모니터링, 세금과 할인은 제외합니다.

| 항목 | Standard | Standard-IA |
|---|---:|---:|
| 저장 | `100 GiB × 0.025 USD/(GiB·월) × 1개월` = 2.50 USD | `100 GiB × 0.015 USD/(GiB·월) × 1개월` = 1.50 USD |
| GET | `100,000 ÷ 1,000 × 0.0005 USD` = 0.05 USD | `100,000 ÷ 1,000 × 0.001 USD` = 0.10 USD |
| Retrieval | 0.00 USD | `200 GiB × 0.01 USD/GiB` = 2.00 USD |
| **합계** | **2.55 USD** | **3.60 USD** |

Standard-IA는 저장료가 1.00 USD 낮지만 GET과 조회료가 그 차이를 넘어 총 **1.05 USD** 더 듭니다. 반대로 월 GET 1,000회, 조회 2 GiB로 낮아지면 Standard는 **2.5005 USD**, Standard-IA는 **1.521 USD**입니다. 읽기가 줄면 저장료 차이가 더 크게 작용합니다. 두 결과는 각각의 가상 업무량에 해당합니다.

## 9. 낭비 후보와 판단 기준

| 후보 | 비용 원인 | 필요한 자료 | AWS에서 검토할 방법 | 적용 전 확인 |
|---|---|---|---|---|
| 접근 패턴과 맞지 않는 클래스 | 보관 단가 또는 반복 조회료가 높음 | 클래스별 요청·조회량과 접근 간격 | Storage Class Analysis, Intelligent-Tiering | 계절성, 복원 시간, 모니터링료 |
| 불필요한 장기 보존 | 현재·이전 버전이 계속 저장됨 | 객체 나이, 버전별 용량, 소유자와 보존 정책 | Lifecycle 만료 및 이전 버전 규칙 | 법적 보존, Object Lock, 복구 시점과 버전별 영향 |
| 잦은 요청 | GET·LIST·COPY·재시도 반복 | 호출 종류, 호출 주체, 재시도와 캐시 적중 | 반복 읽기 캐시 검토, Storage Lens의 요청 지표 활용 | 데이터 최신성, 캐시 비용, 분석 범위 |
| 작은 객체가 많음 | 객체별 최소 크기·메타데이터·요청료 누적 | 크기 분포, 객체 수, 개별 접근 방식 | Lifecycle 크기 필터, 필요한 객체만 전환 | 묶어서 저장할 때의 읽기 증폭과 개별 보존 요건 |
| 불필요한 복제·전송 | 대상 저장료, 복제 PUT, 리전 간 송신 | 복제 규칙, 전송 출발·도착, 사용량 | S3 복제 대상·필터와 데이터 경로 재검토 | 재해복구, 데이터 위치, 지연 목표 |
| 잦은 클래스 전환 | 전환 요청과 최소 기간의 잔여 비용 | 전환 이력, 클래스 체류일, 만료 예정일 | Lifecycle 전환·만료 시점 조정 | 규칙 간 상호작용, 조기 삭제·전환 비용 |

보존 변경은 영향을 받는 객체와 버전, 필요한 복구본, 소유자 승인을 확인한 후 검토합니다. Lifecycle 규칙은 기존 객체에도 적용될 수 있으므로 적용 대상을 먼저 확인합니다. [Managing the lifecycle of objects](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html)

## 10. 기존 최적화 기능

| 기능 | 해결하는 문제 | 입력·확인 조건 |
|---|---|---|
| S3 Lifecycle | 나이 등에 따라 전환·만료를 반복 적용 | 접두사·태그·크기 등 적용 범위, 클래스 체류 기간, 버전과 보존 요건. 기존 객체도 평가 |
| S3 Intelligent-Tiering | 바뀌는 접근 빈도에 따라 객체의 접근 계층을 조정 | 128 KB 이상 객체 수, 모니터링료, 선택적 아카이브 복원 지연. 작은 객체는 Frequent Access 유지 |
| S3 Storage Class Analysis | Standard에서 Standard-IA로 옮길 후보 분석 | 버킷 또는 접두사·태그 필터의 접근 이력. 분석 추천 범위는 Standard → Standard-IA |
| S3 Storage Lens | 저장량·객체 수·활동 지표의 추세와 이상치 파악 | 계정·버킷 등 관측 범위와 필요한 지표. 고급 지표 비용 확인 |

[Lifecycle 관리](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html) · [Intelligent-Tiering](https://docs.aws.amazon.com/AmazonS3/latest/userguide/intelligent-tiering.html) · [Storage Class Analysis](https://docs.aws.amazon.com/AmazonS3/latest/userguide/analytics-storage-class.html) · [Storage Lens](https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage_lens.html)

## 11. 확인 문제

1. Standard-IA의 저장 단가가 더 낮아도 총비용이 더 높아지는 이유는 무엇인가요?
2. 예제에서 GET 100,000회를 유지하고 조회량만 50 GiB로 줄이면 각 클래스의 비용과 차이는 얼마인가요?
3. 작은 객체가 많은 버킷을 아카이브 클래스로 전환하기 전에 어떤 자료를 확인해야 하나요?

## 12. 확인 범위와 한계

AWS 공식 문서에서 클래스별 접근 방식과 과금 조건, Lifecycle 및 분석 기능의 범위를 확인했습니다. 2.55 USD와 3.60 USD는 동일 업무량을 가정해 가상 단가로 계산한 결과입니다. 실제 리전별 청구액, 객체 크기 분포, 접근·요청 이력, 전송 경로와 복원 시간은 측정하지 않았습니다. 실제 클래스 선택에는 대표 업무 주기의 접근 자료, 버전과 보존 의무, 필요한 경우 복원 시험 결과가 필요합니다.

## 13. 다음 학습 질문

> S3 Lifecycle 정책과 Intelligent-Tiering은 실제 객체 접근·보관 패턴에 따라 어떤 조건에서 비용 효율을 개선할 수 있는가?

## 공식 참고 자료

확인일은 **2026-11-07**입니다.

| 자료 | 확인한 절과 범위 |
|---|---|
| [What is Amazon S3?](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html) | Amazon S3 concepts, Buckets·Objects·Keys |
| [Amazon S3 pricing](https://aws.amazon.com/s3/pricing/) | Storage, Requests & data retrievals, Data transfer, Management & insights, Replication |
| [Understanding and managing Amazon S3 storage classes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage-class-intro.html) | Comparing the Amazon S3 storage classes, 저빈도·아카이브 접근 조건 |
| [Understanding archive retrieval options](https://docs.aws.amazon.com/AmazonS3/latest/userguide/restoring-objects-retrieval-options.html) | 복원 방식별 일반 소요 시간과 Bulk 조회 조건 |
| [Managing the lifecycle of objects](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html) · [Transitioning objects using Amazon S3 Lifecycle](https://docs.aws.amazon.com/AmazonS3/latest/userguide/lifecycle-transition-general-considerations.html) | 전환·만료, 기존 객체, 소형 객체와 최소 보관기간 |
| [Managing storage costs with Amazon S3 Intelligent-Tiering](https://docs.aws.amazon.com/AmazonS3/latest/userguide/intelligent-tiering.html) · [How S3 Intelligent-Tiering works](https://docs.aws.amazon.com/AmazonS3/latest/userguide/intelligent-tiering-overview.html) | 기능 개요, 대상 객체 크기, 자동·선택적 접근 계층 |
| [Amazon S3 analytics – Storage Class Analysis](https://docs.aws.amazon.com/AmazonS3/latest/userguide/analytics-storage-class.html) · [Monitoring your storage activity and usage with Amazon S3 Storage Lens](https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage_lens.html) | 분석 대상 클래스, 대시보드 범위와 고급 지표 |

[AWS 학습 목차](../README.md) · [전체 학습 목차](../../README.md)

## 확인 문제 정답과 해설

1. 조회량 비용과 클래스별 GET 단가 차이가 저장료 차이를 넘어설 수 있습니다. 작은 객체와 짧은 보관기간에서는 최소 과금 조건도 함께 봅니다.
2. Standard는 `2.50 + 0.05 = 2.55 USD`입니다. Standard-IA는 `1.50 + 0.10 + 50 × 0.01 = 2.10 USD`로, Standard-IA가 **0.45 USD** 낮습니다.
3. 객체 크기 분포와 개수, 요청·조회 패턴, 전환 대상과 요청료, 메타데이터·최소 기간, 필요한 복원 시간과 보존 의무를 확인합니다. 이러한 조건을 충족하는 후보끼리 비용을 비교합니다.
