# A-03. EBS 스냅샷 비용 산정 — 증분 저장·삭제·보존

## 1. 학습 질문

> EBS 스냅샷을 삭제하면 저장료는 얼마나 줄고, 어떤 복구 시점을 잃게 되는가?

[EBS 비용 산정 01](README.md)에서 구분한 볼륨 저장료와 스냅샷 저장료 중, 여기서는 백업 블록의 저장 기간과 복구 요건을 다룹니다. 볼륨 용량, 스냅샷에서 복원하는 데이터량, 여러 스냅샷이 실제로 보관하는 블록량을 따로 계산합니다.

## 2. 표준 티어의 증분 저장과 삭제

같은 볼륨의 첫 스냅샷에는 그 시점까지 기록된 블록이 들어갑니다. 이후 스냅샷은 새로 쓰거나 변경한 블록을 추가로 저장하고, 그대로인 블록은 기존 저장 데이터를 참조합니다. 각 스냅샷으로 해당 시점의 새 볼륨을 만들 수 있습니다. [How Amazon EBS snapshots work](https://docs.aws.amazon.com/ebs/latest/userguide/how_snapshots_work.html)

스냅샷을 삭제하면 그 복구 시점은 사라집니다. 남은 스냅샷이 참조하는 블록은 유지되므로, **삭제한 스냅샷만 참조하던 블록의 크기**가 저장량 감소분입니다. 이전 스냅샷을 지워도 남은 스냅샷으로 해당 시점의 볼륨을 복원할 수 있습니다. Recycle Bin 보존 규칙에 걸리면 즉시 영구 삭제되지 않습니다. [Delete an Amazon EBS snapshot — Considerations and incremental deletion](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-deleting-snapshot.html)

### 예제 A. 스냅샷 하나를 지우면 얼마나 줄어드는가?

**가상 단가**는 표준 저장 0.06 USD/(GiB·월)이며, 30일을 1개월로 계산합니다. 같은 200 GiB 볼륨의 두 스냅샷만 있다고 가정합니다.

| 시점 | 복원에 필요한 블록 | 해당 시점에 새로 저장한 블록 |
|---|---|---:|
| A | 공통 40 GiB + 변경 전 블록 8 GiB | 48 GiB |
| B | 공통 40 GiB + 변경 후 블록 8 GiB + 새 블록 4 GiB | 12 GiB |

둘 다 유지하면 `48 + 12 = 60 GiB`를 보관합니다. A를 영구 삭제하면 A만 참조하던 8 GiB가 제거됩니다. B가 참조하는 공통 40 GiB는 남으므로, 삭제 후 저장량은 `40 + 8 + 4 = 52 GiB`입니다.

| 시나리오 | 저장료 계산 | 30일 저장료 |
|---|---|---:|
| A와 B를 30일간 유지 | `60 GiB × 0.06 USD/(GiB·월) × 1개월` | 3.60 USD |
| 처음 10일은 둘 다 유지하고 이후 20일은 B만 유지 | `(60 × 10/30 + 52 × 20/30) GiB·월 × 0.06 USD/(GiB·월)` | 3.28 USD |

차이 **0.32 USD**는 8 GiB를 20일 덜 보관한 값입니다. 이 예제의 대가는 A 시점으로 돌아갈 수 있는 선택지를 잃는 것입니다. 보존 요건에 A가 포함된다면 두 번째 시나리오는 적용할 수 없습니다.

## 3. 장기 보존과 아카이브 비용

표준 티어는 실제 보관 중인 백업 데이터를 기준으로 과금합니다. 증분 스냅샷을 아카이브하면 해당 시점의 전체 스냅샷으로 전환되므로, 비교할 아카이브 용량에 증분 크기만 넣으면 비용을 과소평가할 수 있습니다. 원본 표준 스냅샷 집합에서 계속 필요한 블록도 별도로 고려합니다. [Amazon EBS pricing — Example 7](https://aws.amazon.com/ebs/pricing/) · [How Amazon EBS snapshots work — archive conversion](https://docs.aws.amazon.com/ebs/latest/userguide/how_snapshots_work.html)

아카이브에는 최소 90일 보존 과금이 있습니다. 그 전에 삭제하거나 표준 티어로 영구 복원하면 남은 기간에 해당하는 비용이 청구됩니다. 아카이브에서 꺼낼 때는 데이터 인출 비용이 붙으며, 임시 복원 기간에는 아카이브와 표준 티어 저장료가 함께 발생합니다. [Pricing and billing for archiving Amazon EBS snapshots](https://docs.aws.amazon.com/ebs/latest/userguide/snapshot-archive-pricing.html)

### 예제 B. 90일 보존과 임시 복원

다른 스냅샷과 공유하는 블록이 없는 **50 GiB 복구 시점 하나**를 90일간 보존한다고 가정합니다. 표준 저장 단가는 예제 A와 같고, 아카이브 저장은 0.02 USD/(GiB·월), 인출은 0.04 USD/GiB라는 **가상 단가**를 사용합니다.

| 시나리오 | 계산 | 합계 |
|---|---|---:|
| 90일 표준 보존 | `50 × 0.06 × 3` | 9.00 USD |
| 90일 아카이브, 인출 없음 | `50 × 0.02 × 3` | 3.00 USD |
| 90일 아카이브, 1회 인출 후 표준 사본 1일 유지 | `3.00 + (50 × 0.04) + (50 × 0.06 × 1/30)` | 5.10 USD |

같은 아카이브를 30일에 영구 삭제하는 별도 시나리오에서는, 이미 보존한 30일분 1.00 USD에 남은 60일분 2.00 USD가 붙어 총 3.00 USD입니다. 두 예제는 단순화한 저장·인출 계산이며, 복원용 EBS 볼륨, 리전 간 복사, Fast Snapshot Restore, 세금과 할인은 제외했습니다.

## 4. 복구 요건을 비용 계산에 적용하기

| 확인할 요건 | 보존·복원 판단 |
|---|---|
| **RPO** — 장애 시 허용할 데이터 손실 시간 | RPO가 4시간이라면, 하루 1회 스냅샷만으로는 부족합니다. 생성 주기와 실패 여부를 함께 확인해 최근 복원 가능한 시점이 4시간 안에 있는지 판단합니다. |
| **RTO** — 장애 후 서비스 재개까지 허용할 시간 | RTO가 2시간이면 Archive 스냅샷에만 의존할 수 없습니다. Archive 상태에서는 EBS 볼륨을 직접 만들 수 없으며, 먼저 Standard 계층으로 복원해야 합니다. AWS 안내에 따르면 이 단계만 스냅샷 크기에 따라 최대 72시간이 걸릴 수 있습니다. 별도 복구 경로로 볼륨 생성·초기화, 앱 기동, 데이터 검증까지 2시간 안에 마칠 수 있는지 실제 복구 시험으로 확인해야 합니다. [AWS 아카이브 복원 제약](https://docs.aws.amazon.com/ebs/latest/userguide/snapshot-archive-considerations.html) |
| **복구 시점과 보존 의무** | 최근 복구본과 과거 월말 복구본의 역할을 구분합니다. 최신 스냅샷을 남겨도 과거 손상 직전으로 되돌아갈 필요가 있으면 이전 복구본을 보존합니다. |
| **일관성·복구 의존성** | 스냅샷 요청 시 볼륨에 기록된 데이터가 대상입니다. 앱이나 OS 캐시에 남은 데이터, 여러 볼륨 간 일관성, 복원 환경에서의 KMS 키 접근과 애플리케이션 기동을 확인합니다. |
| **삭제 제약과 비용 반영** | 등록된 AMI의 루트 스냅샷, AWS Backup 관리 복구 지점, 공유 대상, Recycle Bin 정책을 확인합니다. 삭제 후 예상 비용 차이는 고유 블록과 실제 보존 기간으로 계산합니다. |

복구 시간은 볼륨을 생성한 시점에서 끝나지 않습니다. 스냅샷으로 만든 볼륨은 초기화 중 I/O 성능이 낮아질 수 있으므로, 서비스가 요구 성능으로 돌아온 시점까지 검증합니다. [Create Amazon EBS snapshots](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-creating-snapshot.html) · [Initialize Amazon EBS volumes](https://docs.aws.amazon.com/ebs/latest/userguide/initalize-volume.html) · [Delete an Amazon EBS snapshot](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-deleting-snapshot.html)

복구 시점과 보존 기간을 합의한 뒤에는 Amazon Data Lifecycle Manager로 해당 정책이 생성한 스냅샷의 생성·보존·삭제를 관리할 수 있습니다. 기존 수동 스냅샷과 AWS Backup 복구 지점은 관리 주체를 따로 확인합니다. [Automate backups with Amazon Data Lifecycle Manager](https://docs.aws.amazon.com/ebs/latest/userguide/snapshot-lifecycle.html)

## 5. 학습 확인 문제

1. 예제 A에서 A를 비교 기간 시작과 동시에 영구 삭제하면 30일 저장료와 두 스냅샷 유지 대비 차이는 얼마인가요?
2. 90일 아카이브가 더 저렴하다는 계산만으로 RTO 2시간인 서비스에 적용할 수 있나요?

## 6. 확인 범위와 다음 질문

공식 문서로 증분 저장, 고유 블록 삭제, 아카이브 과금과 복원 동작을 확인했습니다. 실제 청구액, 고유 블록 크기, 아카이브 인출 시간과 서비스 복구 시간은 미측정입니다. 실제 절감액을 평가하려면 리전별 단가와 사용 내역, 복원 시험 결과가 필요합니다.

> 다음 질문: 업무별 RPO·RTO에 맞춰 스냅샷 보존 정책과 복원 시험을 어떻게 설계할 수 있는가?

## 공식 참고 자료

확인일은 **2026-11-07**입니다.

| 문서 | 확인 범위 |
|---|---|
| [Amazon EBS pricing](https://aws.amazon.com/ebs/pricing/) | Example 7–8의 스냅샷 저장·복사와 Fast Snapshot Restore |
| [How Amazon EBS snapshots work](https://docs.aws.amazon.com/ebs/latest/userguide/how_snapshots_work.html) | 첫 스냅샷, 후속 증분, 아카이브의 전체 스냅샷 전환 |
| [Delete an Amazon EBS snapshot](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-deleting-snapshot.html) | 삭제 제약과 공유 블록 유지 |
| [Pricing and billing for archiving Amazon EBS snapshots](https://docs.aws.amazon.com/ebs/latest/userguide/snapshot-archive-pricing.html) | 최소 보존 기간, 인출, 임시·영구 복원 과금 |
| [Create Amazon EBS snapshots](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-creating-snapshot.html) · [Initialize Amazon EBS volumes](https://docs.aws.amazon.com/ebs/latest/userguide/initalize-volume.html) | 기록된 데이터와 캐시, 암호화, 볼륨 초기화 시 성능 |
| [Automate backups with Amazon Data Lifecycle Manager](https://docs.aws.amazon.com/ebs/latest/userguide/snapshot-lifecycle.html) | 생성·보존·삭제 자동화와 관리 범위 |

[AWS 학습 목차](../README.md) · [전체 학습 목차](../../README.md)

## 확인 문제 정답

1. B가 참조하는 52 GiB가 남아 `52 × 0.06 = 3.12 USD`입니다. 60 GiB를 유지하는 비용 3.60 USD와의 차이는 **0.48 USD**입니다. A 시점이 보존 대상이면 이 선택지는 제외합니다.
2. 인출부터 서비스 검증까지 2시간을 보장하려면 별도 복구 경로가 필요합니다. Archive에서 Standard로 복원하는 단계만 AWS 안내상 최대 72시간이 걸릴 수 있고, 그 단계가 끝나야 EBS 볼륨을 만들 수 있습니다. 별도 경로의 전체 복구 시간을 시험으로 확인한 뒤 목표를 충족하는 경로의 비용을 비교합니다. [AWS 아카이브 복원 제약](https://docs.aws.amazon.com/ebs/latest/userguide/snapshot-archive-considerations.html)
