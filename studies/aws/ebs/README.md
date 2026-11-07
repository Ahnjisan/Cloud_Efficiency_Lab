# EBS 비용 산정 01 — 볼륨 유형·용량·IOPS·Throughput

## 1. 학습 질문과 범위

> Amazon EBS는 프로비저닝한 저장 용량과 성능 설정에 따라 어떻게 과금되며, 어떤 상황에서 불필요한 비용이 발생하는가?

[EC2 비용 산정 01](../ec2/README.md)에서는 인스턴스를 중지해도 EBS 비용이 남는 이유를 살펴봤습니다. 이번에는 볼륨 용량과 실제 저장량의 차이, IOPS와 처리량의 의미, gp2·gp3의 과금 구조를 비교합니다. 유형 변경의 비용 효과는 업무에 필요한 저장 공간과 성능을 유지할 수 있는 조건에서 판단합니다.

## 2. EBS 기본 구조

EBS는 EC2에 디스크처럼 연결하는 블록 스토리지입니다. 운영체제의 루트 디스크나 데이터베이스의 데이터 디스크로 사용할 수 있습니다. 볼륨의 **프로비저닝 용량**은 미리 할당한 공간입니다. 예를 들어 100 GiB 볼륨에 파일을 20 GiB만 저장해도 볼륨 저장료 계산에는 100 GiB를 사용합니다. [Amazon EBS volumes](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-volumes.html) · [Amazon EBS pricing](https://aws.amazon.com/ebs/pricing/)

AWS 볼륨 상태에서 연결됨(attached)은 `in-use`, 미연결은 `available`입니다. 두 상태 모두 볼륨이 유지되는 동안 저장료가 발생합니다. EC2의 컴퓨팅 사용료와 별도이므로 인스턴스를 중지하거나 볼륨을 분리해도 할당된 저장 공간의 과금은 이어집니다. [Volume states](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-describing-volumes.html#volume-states) · [Amazon EBS pricing](https://aws.amazon.com/ebs/pricing/)

볼륨은 애플리케이션이 읽고 쓰는 디스크입니다. 스냅샷은 특정 시점의 볼륨 데이터를 새 볼륨으로 복원할 수 있게 보관하는 백업이며, 저장량을 별도로 과금합니다. [Amazon EBS snapshots](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-snapshots.html)

## 3. EBS 볼륨 유형

| 유형 | 매체 | 주로 검토할 업무 |
|---|---|---|
| gp2 | 범용 SSD | 시스템 디스크와 일반 트랜잭션. 기본 IOPS가 용량에 연동됨 |
| gp3 | 범용 SSD | 시스템 디스크와 일반 트랜잭션. 용량과 성능을 별도로 설정 가능 |
| io1 / io2 | 프로비저닝 IOPS SSD | 지속적으로 높은 IOPS나 낮은 지연이 필요한 데이터베이스 |
| st1 | 처리량 최적화 HDD | 로그 처리나 대규모 순차 읽기 |
| sc1 | 저빈도 접근용 HDD | 접근 빈도가 낮고 저장 단가를 우선하는 대용량 순차 업무 |

작고 무작위인 I/O에는 SSD를, 큰 데이터를 순차 처리하는 업무에는 HDD를 검토합니다. 여기서는 gp2와 gp3의 요금과 성능을 비교합니다. [Amazon EBS volume types](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-volume-types.html)

## 4. gp2 비용·성능 구조

gp2 볼륨 사용료는 프로비저닝한 용량과 유지 기간으로 계산합니다. I/O 요금은 볼륨 가격에 포함됩니다. AWS 요금 예제는 저장 시간을 초 단위로 계산하며 최소 60초를 적용합니다. [Amazon EBS pricing — gp2 예제](https://aws.amazon.com/ebs/pricing/)

- **기본 IOPS**는 GiB당 3 IOPS로 증가하며 최저 100, 최고 16,000 IOPS입니다. 100 GiB는 기본 300 IOPS입니다.
- **버스트**는 1 TiB 미만이면서 기본 3,000 IOPS 미만인 볼륨에 적용됩니다. 크레딧이 있으면 최대 3,000 IOPS까지 일시적으로 올라갑니다. 기본치보다 많이 처리한 만큼 크레딧을 쓰며, 수요가 기본치 이하로 내려가면 다시 적립됩니다.
- **처리량 상한**은 170 GiB 이하에서 128 MiB/s입니다. 170 GiB 초과·334 GiB 미만에서는 최대 250 MiB/s까지 버스트할 수 있고, 334 GiB 이상에서는 상한이 250 MiB/s입니다. I/O 크기와 인스턴스 한도에 따라 실제 처리량은 달라집니다. [Amazon EBS General Purpose SSD volumes — gp2 성능](https://docs.aws.amazon.com/ebs/latest/userguide/general-purpose.html)

100 GiB 볼륨을 200 GiB로 키우면 기본 IOPS가 300에서 600으로 올라갑니다. 데이터에 필요한 공간이 100 GiB 그대로라면, 성능을 확보하기 위해 늘린 용량에도 저장료를 내게 됩니다.

## 5. gp3 비용·성능 구조

gp3는 저장료에 **3,000 IOPS와 125 MiB/s**를 포함하며 gp2처럼 버스트 크레딧에 의존하지 않습니다. 일반 AWS 환경의 볼륨 크기는 1 GiB~64 TiB이며, 기본 제공량을 포함한 **총 설정 상한은 80,000 IOPS와 2,000 MiB/s**입니다. 추가 요금은 기본 제공량을 초과해 설정한 부분에 적용됩니다. 기본치를 넘겨 설정할 때 IOPS는 500 IOPS/GiB 제약을 따르며 80,000 IOPS에는 160 GiB 이상이 필요합니다. 처리량은 설정 IOPS당 0.25 MiB/s 제약을 따르며 2,000 MiB/s에는 8,000 IOPS와 16 GiB 이상이 필요합니다. Outposts에는 별도 상한이 있습니다. [Amazon EBS General Purpose SSD volumes — gp3 성능과 크기](https://docs.aws.amazon.com/ebs/latest/userguide/general-purpose.html)

| 항목 | 과금 대상 |
|---|---|
| 저장 용량 | 프로비저닝한 전체 용량 |
| 추가 IOPS | 설정 IOPS 중 3,000을 초과한 부분 |
| 추가 처리량 | 설정 처리량 중 125 MiB/s를 초과한 부분 |

각 과금 대상에 해당 단가와 유지 기간을 곱해 더합니다. 예를 들어 5,000 IOPS로 설정한 뒤 실제 사용량이 1,000 IOPS에 그쳐도, 해당 기간의 추가 IOPS 과금 대상은 2,000입니다. AWS 요금 페이지는 성능 단가 예제에서 MB/s로 표기하고, 사용자 가이드의 성능 사양과 이 문서의 가상 계산은 MiB/s를 사용합니다. 실제 견적에는 해당 요금표의 단위를 확인합니다. [Amazon EBS pricing — gp3 예제](https://aws.amazon.com/ebs/pricing/) · [gp3 성능 사양](https://docs.aws.amazon.com/ebs/latest/userguide/general-purpose.html)

## 6. IOPS와 Throughput의 차이

**IOPS**는 초당 완료되는 입출력 작업 수이며, **처리량(Throughput)**은 초당 전송되는 데이터량입니다. 모든 작업의 크기가 같고 볼륨과 인스턴스에 성능 병목이 없다고 가정하면, `처리량(MiB/s) = IOPS × 작업당 크기(KiB) ÷ 1,024`로 계산할 수 있습니다.

| 작업 수 | 작업당 크기 | 계산한 처리량 |
|---|---|---|
| 3,000 IOPS | 4 KiB | 11.72 MiB/s |
| 1,000 IOPS | 64 KiB | 62.5 MiB/s |

두 번째 구성은 작업 수가 적어도 각 작업이 더 커서 초당 더 많은 데이터를 전송합니다. 반대로 125 MiB/s 상한에서 64 KiB 작업만 처리한다면, 처리량 한도에 닿는 시점은 2,000 IOPS입니다. 실제 측정값에는 요청 크기 분포, I/O 병합·분할, 대기열, 인스턴스의 EBS 한도와 다른 연결 볼륨의 부하가 영향을 줍니다. 볼륨과 인스턴스 중 먼저 한계에 도달하는 쪽부터 확인합니다. [Amazon EBS I/O characteristics and monitoring](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-io-characteristics.html)

## 7. 가상 비용 계산

두 예제 모두 1개월 동안 설정을 유지한다고 가정합니다. 아래 단가는 학습용 가상 값이며, 할인·세금·스냅샷·기타 부가 비용을 제외합니다.

### 예제 A. 100 GiB 저장 비용 비교

| 구성 | 계산 | 월 비용 |
|---|---|---:|
| gp2 100 GiB | `100 GiB × 0.12 USD/(GiB·월) × 1개월` | 12 USD |
| gp3 100 GiB, 기본 성능 | `100 GiB × 0.09 USD/(GiB·월) × 1개월` | 9 USD |

저장 비용 차이는 `12 − 9 = 3 USD`입니다. 두 볼륨의 기본 IOPS와 처리량 특성이 다르므로 이 차이는 동일 I/O 성능을 전제로 한 비교에 해당하지 않습니다.

### 예제 B. gp3에 5,000 IOPS와 200 MiB/s 설정

| 항목 | 계산 | 월 비용 |
|---|---|---:|
| 저장 | `100 GiB × 0.09 USD/(GiB·월) × 1개월` | 9 USD |
| 추가 IOPS | `(5,000 − 3,000) IOPS × 0.006 USD/(IOPS·월) × 1개월` | 12 USD |
| 추가 처리량 | `(200 − 125) MiB/s × 0.05 USD/((MiB/s)·월) × 1개월` | 3.75 USD |
| **합계** | `9 + 12 + 3.75` | **24.75 USD** |

예제 A의 기본 gp3와 예제 B는 성능 설정이 다릅니다. 업무가 기본 성능에서 목표 지연 시간과 처리량을 충족한다면 추가 설정을 재검토할 수 있습니다. 반대로 피크에 추가 성능이 필요하면 그 비용까지 포함해 비교합니다.

## 8. 낭비 후보와 판단에 필요한 자료

다음은 과금 구조에 근거한 판단 기준입니다. 낮은 평균 사용량은 조사의 출발점으로 삼고, 대표적인 업무 주기와 복구 요구를 확인합니다.

| 후보 | 비용이 생기는 이유 | 판단 자료 | 유지 조건 | 권고 보류 조건 |
|---|---|---|---|---|
| 과다 저장 용량 | 실제 파일 크기와 별개로 할당 공간을 과금 | 파일시스템 사용량 추이, 성장률, 피크 임시 공간 | 향후 데이터 증가나 작업 여유 공간이 필요 | 파일시스템·성장 자료가 없거나 축소 시 데이터 이관 위험이 미확인 |
| 과다 IOPS | gp3의 기본 초과 설정을 유지하는 동안 과금 | 피크 읽기·쓰기 IOPS, 지연, 대기열, 측정 구간 | 트랜잭션 집중 시간이나 복구 시 피크를 처리해야 함 | 평균만 있거나 제한으로 실제 수요가 가려짐 |
| 과다 처리량 | gp3의 기본 초과 처리량 설정을 유지하는 동안 과금 | 피크 MiB/s, I/O 크기, 배치·백업 구간, 인스턴스 한도 | 대량 읽기·쓰기 작업에 완료 시한이 있음 | 월말 등 주요 작업이 관측 기간에서 빠짐 |
| 미연결 볼륨 | 분리해도 프로비저닝한 볼륨이 남음 | 연결 이력, 소유자, 태그, 복구·이관 계획 | 교체·복구·이관을 위한 대기 볼륨 | 소유자, 백업 또는 복구 의존성이 미확인 |
| 미사용 의심 볼륨 | 연결 상태나 낮은 I/O와 무관하게 공간 유지료가 발생 | 마운트와 앱 설정, 장기 I/O 추이, 대기·정기 업무 | 장애 대비나 간헐적 업무에 사용 | 측정 누락 또는 애플리케이션 의존성이 미확인 |
| 장기 보존 스냅샷 | 보존 중인 백업 데이터가 과금됨 | 보존 정책, 복구 목표, 종속 리소스와 복원 가능 여부 | 감사·복구·규정에 필요한 복원 시점 | 보존 의무나 백업 복구 가능성이 미확인 |

`available`은 연결 여부만 알려 줍니다. 삭제 판단에는 데이터의 소유자와 용도, 보존 의무, 검증된 복구 경로가 필요합니다.

## 9. gp2에서 gp3로 변경할 때

1. **용량과 업무 요구를 분리합니다.** 기존·목표 용량과 성장 여유를 기록하고, 피크 IOPS·MiB/s·지연을 확인합니다. 기존 gp2의 기본 IOPS, 버스트 사용 여부, 처리량 상한을 함께 봅니다. Elastic Volumes에서 기존 볼륨의 크기를 직접 줄이는 기능은 제공하지 않으므로 용량 축소는 데이터 이관을 포함한 별도 변경입니다. [Elastic Volumes — Limitations](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-modify-volume.html)
2. **목표 성능을 비용에 반영합니다.** gp3 기본 성능으로 충분한지 판단하고 초과분을 더합니다. 변경 시 IOPS·처리량을 지정하지 않으면 EBS는 원본 gp2의 동등 성능과 gp3 기본값 중 항목별로 높은 값을 사용합니다. 예를 들어 250 MiB/s를 제공하는 gp2의 처리량 설정이 전환 후에도 250 MiB/s라면 기본 125 MiB/s 초과분이 생깁니다. 용량 단가 차이만으로 절감액을 계산하면 이 항목을 놓칩니다. [Elastic Volumes — Considerations](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-modify-volume.html)
3. **인스턴스와 애플리케이션을 함께 비교합니다.** EC2의 EBS 성능 한도와 다른 볼륨의 부하를 확인합니다. 변경 전후에 같은 업무량·I/O 패턴을 기준으로 지연과 오류, 처리량, 배치 완료 시간을 비교해야 실제 업무 적합성을 판단할 수 있습니다. [Amazon EBS I/O characteristics and monitoring](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-io-characteristics.html)
4. **운영 위험을 확인합니다.** Elastic Volumes를 지원하는 구성은 연결 상태로 유형을 변경할 수 있지만, 변경에 시간이 걸리고 제출한 요청은 취소할 수 없습니다. 지원 조건, 복구 가능한 백업, 변경 시간대와 복구 계획을 검토합니다. 이 문서에서는 변경 전후 성능과 실제 절감 효과를 측정하지 않았습니다. [Elastic Volumes — 도입부·Considerations·Limitations](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-modify-volume.html)

## 10. Snapshot 비용 기초

표준 티어에서 같은 볼륨의 EBS 스냅샷은 특정 시점으로 복원할 수 있는 **증분 백업**을 구성합니다. 첫 스냅샷은 기록된 데이터 블록을 저장하고, 후속 스냅샷은 이전 시점 이후 새로 쓰거나 바꾼 블록을 저장합니다. 복원 시에는 필요한 블록을 모아 해당 시점의 볼륨을 재구성합니다. 따라서 프로비저닝한 100 GiB를 스냅샷마다 그대로 저장한다고 가정할 수 없습니다. [Amazon EBS snapshots](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-snapshots.html) · [How Amazon EBS snapshots work](https://docs.aws.amazon.com/ebs/latest/userguide/how_snapshots_work.html)

보존 비용은 실제로 저장하는 백업 데이터에 따라 발생합니다. 스냅샷을 삭제할 때 그 스냅샷만 참조하는 블록은 제거되지만 다른 스냅샷에서 필요한 블록은 남습니다. 예상한 만큼 저장료가 줄어들지 않을 수 있으므로 삭제 전에 보존 정책, 필요한 복원 시점, 복구 가능 여부를 확인합니다. 상세 과금과 Lifecycle은 후속 주제입니다. [Amazon EBS snapshots — Snapshot pricing](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-snapshots.html)

## 11. 확인 문제

1. 100 GiB gp2와 기본 성능의 100 GiB gp3는 각각 어떤 항목으로 과금되나요? 두 볼륨의 기본 IOPS를 비교해 보세요.
2. 예제 B의 가상 단가를 사용해 100 GiB gp3에 4,000 IOPS와 150 MiB/s를 한 달 설정하면 각 항목과 합계는 얼마인가요?
3. 한 달 동안 분리된 `available` 볼륨을 발견했습니다. 어떤 비용이 계속 발생하며, 삭제 판단 전에 어떤 자료를 확인해야 하나요?

## 12. 확인 범위와 한계

| 구분 | 확인 범위 |
|---|---|
| AWS 공식 문서 | 볼륨 상태, 유형별 용도, gp2 버스트·처리량 상한, gp3 기본 성능·추가 설정 범위, 과금 항목, 증분 스냅샷 |
| 가상 산술 | 예제 A의 월 12 USD와 9 USD 및 차이 3 USD, 예제 B의 월 24.75 USD |
| 실제 AWS 비용 | 리전별 단가, 할인·세금 적용 결과, 실제 청구 내역은 검증 범위 밖 |
| 성능 측정 | 실제 IOPS·처리량·지연과 gp2에서 gp3로 전환했을 때의 서비스 영향은 미측정 |
| 낭비 판단 보류 | 업무 주기, 복구 필요성, 소유자, 보존 의무 또는 성능 요구를 확인할 자료가 부족한 경우 |

## 13. 다음 학습 질문

> EBS Snapshot은 어떤 방식으로 저장·과금되며, 백업과 복구 요구사항을 유지하면서 불필요한 스냅샷 비용을 줄일 수 있는가?

## 공식 참고 자료와 확인 범위

확인일은 2026-11-07입니다.

| AWS 공식 자료 | 확인한 절과 범위 |
|---|---|
| [Amazon EBS pricing](https://aws.amazon.com/ebs/pricing/) | Overview, Pricing examples의 gp3·gp2 예제 |
| [Amazon EBS General Purpose SSD volumes](https://docs.aws.amazon.com/ebs/latest/userguide/general-purpose.html) | gp3 volume performance·size, gp2 volume performance의 IOPS·Throughput |
| [Amazon EBS volume types](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-volume-types.html) | SSD 및 HDD 볼륨의 용도와 특성 |
| [Amazon EBS snapshots](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-snapshots.html) | 도입부의 증분 백업·복원, Snapshot pricing |
| [Amazon EBS I/O characteristics and monitoring](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-io-characteristics.html) | I/O 크기와 볼륨·인스턴스 한도, CloudWatch 관측 |
| [Amazon EBS volumes](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-volumes.html) · [View information about an Amazon EBS volume](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-describing-volumes.html) | 블록 스토리지와 EC2 실행 수명, Volume states |
| [Modify an Amazon EBS volume using Elastic Volumes operations](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-modify-volume.html) | 도입부, Considerations, Limitations |
| [How Amazon EBS snapshots work](https://docs.aws.amazon.com/ebs/latest/userguide/how_snapshots_work.html) | 첫 스냅샷과 후속 증분 저장 |

[AWS 학습 목차](../README.md) · [전체 학습 목차](../../README.md)

## 확인 문제 정답과 해설

1. gp2는 100 GiB 저장료에 I/O가 포함되고 기본 성능은 `100 × 3 = 300 IOPS`입니다. gp3도 기본 설정에서는 100 GiB 저장료만 계산하며 3,000 IOPS와 125 MiB/s가 포함됩니다. 추가 설정 시 기본치를 초과한 부분에 별도 요금이 붙습니다.
2. 한 달 저장료는 9 USD입니다. 추가 IOPS는 `(4,000 − 3,000) × 0.006 = 6 USD`, 추가 처리량은 `(150 − 125) × 0.05 = 1.25 USD`입니다. 합계는 **16.25 USD**입니다.
3. 분리한 뒤에도 볼륨을 유지하는 동안 저장료가 발생합니다. 마지막 연결 이력, 소유자·용도, 보존 기간, 백업과 복원 가능 여부를 확인해야 합니다. 복구용 볼륨일 수 있으므로 이 자료가 부족하면 삭제 권고를 보류합니다.
