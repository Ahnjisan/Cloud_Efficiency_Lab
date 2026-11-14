# RDS 비용 산정 01 — DB 인스턴스·스토리지·Multi-AZ

[AWS 서비스 목차](../README.md)

> 동일한 MySQL 데이터베이스라도 인스턴스 사양, 스토리지 구성, 고가용성 설정에 따라 비용은 어떻게 달라지며, 비용을 줄이기 전에 무엇을 확인해야 하는가?

커리큘럼 02. AWS Infrastructure & Pricing의 학습 노트입니다. RDS for MySQL DB 인스턴스의 On-Demand 비용을 중심으로 비교합니다. Aurora의 구조와 과금은 별도 학습 주제로 남깁니다.

## 1. RDS 기본 구조

Amazon RDS는 AWS가 기반 인프라와 DB 소프트웨어 설치·패치, 설정에 따른 백업과 장애 조치를 관리하는 관계형 데이터베이스 서비스입니다. 고객은 엔진과 사양, 네트워크 접근, 백업·가용성 요건을 정하고 스키마와 쿼리를 관리합니다. [What is Amazon RDS? — Advantages and shared responsibility](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Welcome.html)

| 개념 | RDS for MySQL에서의 의미 |
|---|---|
| DB Instance | MySQL 엔진이 동작하는 격리된 DB 환경입니다. 앱은 DB 엔드포인트를 통해 연결합니다. |
| DB Instance Class | vCPU, 메모리, 네트워크와 스토리지 연결 성능 등 컴퓨팅 사양을 정합니다. |
| Storage | 데이터와 로그를 저장할 용량입니다. 스토리지 유형과 성능 설정을 선택합니다. |
| Availability Zone | 리전 내 장애 격리 단위입니다. Multi-AZ DB 인스턴스는 다른 AZ에 대기 인스턴스를 둡니다. |
| Backup·Snapshot | 자동 백업은 보존기간 내 시점 복구에 쓰이고, 수동 스냅샷은 특정 시점의 DB 인스턴스를 복원할 때 쓰입니다. |

EC2에 MySQL을 설치하면 OS·엔진 패치, 백업 일정, 복제와 장애 조치의 설계·운영을 사용자가 맡습니다. RDS에서는 AWS가 선택한 구성에 맞춰 이를 운영하므로 반복 작업이 줄어듭니다. 비용과 성능은 실제 사양, 부하, 운영 인력과 복구 요건에 따라 비교해야 합니다. [RDS 관리 책임 비교](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Welcome.html) · [RDS 백업](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithAutomatedBackups.html)

## 2. RDS 비용 구성

| 항목 | 산정 기준 |
|---|---|
| DB 인스턴스 | 클래스와 배포 형태에 해당하는 단가 × 과금 실행 시간 |
| 스토리지 용량 | 프로비저닝한 용량과 유지 기간. 월중 용량 변경은 기간을 나눠 계산 |
| 스토리지 성능 | io1/io2는 프로비저닝한 IOPS, gp3는 기본치를 초과해 설정한 IOPS·처리량의 해당 항목 |
| 백업과 스냅샷 | 자동 백업·수동 스냅샷의 백업 저장 사용량과 계정·리전별 무료 허용량 |
| 데이터 전송 | 인터넷, 리전·AZ 간 경로 등 실제 출발지와 목적지에 따른 과금 조건 |
| 선택 기능과 추가 요금 | 해당 T 계열 CPU 크레딧, 지원 종료 버전의 Extended Support, 스냅샷 내보내기 등 실제 사용 항목 |

리전·엔진·배포 형태·스토리지 유형·구매 옵션을 먼저 고르고 해당 비용만 합산합니다. 예를 들어 SSD의 프로비저닝 성능 비용을 실제 I/O 요청 건수로 계산하지 않습니다. [Amazon RDS for MySQL pricing](https://aws.amazon.com/rds/mysql/pricing/) · [DB instance billing](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/User_DBInstanceBilling.html)

## 3. DB 인스턴스 과금

On-Demand의 **DB instance-hour**는 DB 클래스와 배포 형태의 시간 단가에 곱하는 사용량입니다. RDS for MySQL의 부분 시간은 초 단위로 과금하고, 생성·시작·클래스 변경 등 과금 상태가 바뀐 뒤 **최소 10분**을 적용합니다. 예를 들어 해당 조건에서 실행 시간이 3분이어도 10분분을 계산합니다. [EC2 학습 노트](../ec2/README.md)의 60초 최소 과금 예제와 구분합니다. [MySQL 요금 — On-Demand 및 FAQ](https://aws.amazon.com/rds/mysql/pricing/)

- **Reserved DB Instance**는 1년 또는 3년 약정에 따른 인스턴스 요금 할인입니다. 중지한다고 약정이 종료되지는 않습니다. 상세 할인 비교는 후속 범위입니다.
- **중지 상태**에는 추가 인스턴스 시간이 발생하지 않지만, 프로비저닝 스토리지와 IOPS, 보관 중인 백업의 적용 요금은 남을 수 있습니다. 중지 가능한 DB 인스턴스는 7일 연속 중지 후 자동으로 시작됩니다.
- **T4g·T3**는 Unlimited 모드에서 24시간 이동 평균 CPU 사용률이 기준선을 초과하면 CPU 크레딧 요금이 발생할 수 있습니다. 작은 클래스의 기본 시간 단가를 비교할 때 지속 부하도 확인합니다. [MySQL 요금 — Reserved Instances, T4g and T3 CPU Credits](https://aws.amazon.com/rds/mysql/pricing/) · [Stopping an Amazon RDS DB instance temporarily](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_StopInstance.html)

## 4. RDS 스토리지 과금

**Allocated Storage**는 미리 할당한 용량입니다. 예를 들어 100 GiB를 할당하고 실제 데이터가 35 GiB라면, 주 스토리지 비용은 100 GiB를 기준으로 계산합니다. **IOPS**는 초당 I/O 작업 수이고, **Throughput**은 초당 전송량으로 여기서는 MiB/s를 사용합니다. 동일 IOPS라도 I/O 크기에 따라 처리량이 달라집니다. [RDS 인스턴스 스토리지](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_Storage.html)

| 유형 | 성능과 비용 |
|---|---|
| gp2 | 기본 IOPS가 용량과 연동되며 버스트는 크레딧의 영향을 받습니다. MySQL의 100 GiB 예에서는 기본 300 IOPS입니다. 비용은 할당 용량 중심입니다. |
| gp3 | 용량 구간별 기본 성능을 포함합니다. 지원 구간에서 기본치를 넘겨 설정한 IOPS·처리량을 추가 과금합니다. |
| io1 / io2 | 지속적인 I/O와 지연 시간 요구에 맞춰 IOPS를 프로비저닝합니다. 할당 용량과 설정 IOPS가 주요 비용 항목이며, 지원 범위와 처리량 한계는 유형·구성에 따라 달라집니다. |

**RDS for MySQL DB 인스턴스의 gp3 기본 성능과 설정 범위**는 다음과 같습니다. [RDS gp3 storage](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_Storage.html)

| 할당 용량 | 기본 IOPS·처리량 | 프로비저닝 가능한 성능 범위 |
|---|---|---|
| 20–399 GiB | 3,000 IOPS · 125 MiB/s | 추가 설정 불가 |
| 400–65,536 GiB | 12,000 IOPS · 500 MiB/s | 12,000–64,000 IOPS · 500–4,000 MiB/s, 비율 및 구성 제약 적용 |

MySQL은 400 GiB부터 RDS가 네 볼륨으로 스트라이핑하므로 기본 성능이 달라집니다. [일반 EBS gp3](../ebs/README.md)의 기준을 그대로 대입하면 이 차이를 놓칩니다. 표의 최대값은 모든 조합에서 동시에 도달할 수 있다는 뜻이 아닙니다. 예를 들어 MySQL에서 40,000 IOPS를 설정하면 처리량은 최소 625 MiB/s여야 합니다. 실제 성능은 인스턴스 클래스의 EBS 연결 한도, I/O 크기, 동시성·쿼리 부하에도 제한됩니다. [RDS 스토리지 — gp3, striping, 성능 요인](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_Storage.html)

## 5. Single-AZ와 Multi-AZ 배포

| 구성 | 인스턴스와 역할 | 가용성·읽기 특성 |
|---|---|---|
| Single-AZ DB Instance | 단일 AZ의 DB 인스턴스 | 한 AZ에서 서비스합니다. 다른 AZ의 관리형 대기 인스턴스로 자동 전환하는 구성이 없으므로 장애 시 복구 경로를 확인합니다. |
| Multi-AZ DB Instance | Primary와 다른 AZ의 Standby 한 개 | 동기식으로 복제하고 지원되는 장애 상황에서 자동 장애 조치합니다. 대기 인스턴스는 읽기 트래픽을 처리할 수 없습니다. |
| Multi-AZ DB Cluster | Writer와 읽기 가능한 대기 인스턴스 두 개 | 대기 인스턴스가 장애 조치와 읽기 처리를 지원합니다. 배포 형태와 가격표가 별도입니다. |
| MySQL Read Replica | 소스에서 비동기 복제하는 별도 읽기 인스턴스 | 읽기 부하를 분산합니다. 복제 지연이 가능하며 장애 복구에 사용할 경우 승격과 연결 전환을 별도로 고려합니다. |

대기 인스턴스 한 개를 사용하는 구성에는 다른 AZ의 컴퓨팅과 스토리지가 필요합니다. 비용은 배포 유형의 인스턴스·스토리지 단가로 산정합니다. 동기 복제는 쓰기·커밋 지연에도 영향을 줄 수 있습니다. [Multi-AZ 구성 비교](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZ.html) · [Single-standby 배포](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZSingleStandby.html) · [Read Replicas](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_ReadRepl.html)

## 6. 가상 비용 계산

RDS for MySQL을 30일 동안 24시간씩 운영합니다. 총 **720시간**과 할당 스토리지 **100 GiB**를 두 구성에 동일하게 적용하고, 30일을 1개월로 가정합니다.

| 항목 | Single-AZ | Multi-AZ DB Instance · Standby 1개 |
|---|---:|---:|
| 인스턴스 | `720시간 × 0.20 USD/시간 = 144.00 USD` | `720시간 × 0.38 USD/시간 = 273.60 USD` |
| 스토리지 | `100 GiB × 0.10 USD/(GiB·월) × 1개월 = 10.00 USD` | `100 GiB × 0.19 USD/(GiB·월) × 1개월 = 19.00 USD` |
| **합계** | **154.00 USD** | **292.60 USD** |

차이는 `292.60 − 154.00 = 138.60 USD`입니다. Multi-AZ 열의 단가는 **대기 인스턴스를 포함한 배포 구성의 가상 단가**이므로 대기 자원을 다시 곱하지 않습니다. 이 단가와 비율은 학습용 가정입니다. 추가 IOPS·Throughput, 백업 초과분, 데이터 전송, CPU 크레딧 등 추가 요금과 할인·크레딧·세금은 제외했습니다. 두 구성의 복구 특성이 다르므로 비용 차이는 요건을 충족하는지를 확인한 뒤 해석합니다.

## 7. RDS 백업과 스냅샷

자동 백업은 스냅샷과 트랜잭션 로그를 이용해 보존기간 내 복원 가능한 시점으로 DB 인스턴스를 복구할 수 있게 합니다(PITR). DB 인스턴스의 보존기간은 0~35일이며, 0이면 자동 백업이 꺼집니다. 수동 스냅샷은 선택한 시점의 DB를 복원하기 위해 별도로 만들며 인스턴스를 삭제해도 남습니다. 삭제 시 보존을 선택한 자동 백업은 남은 보존기간 동안 유지될 수 있습니다. [Introduction to backups](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithAutomatedBackups.html) · [Backup retention period](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithAutomatedBackups.BackupRetention.html) · [Retaining automated backups](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithAutomatedBackups.Retaining.html)

무료 백업 저장량은 **계정·리전별 전체 프로비저닝 DB 스토리지의 100%**에 해당합니다. 해당 범위의 백업 저장량과 비교해 초과분을 계산합니다. 예를 들어 같은 계정·리전에서 할당량 200 GiB와 백업 저장량 230 GiB가 한 달 내내 일정했다면, 무료 허용량을 뺀 30 GiB·월이 과금 대상입니다. 실제 집계는 기간 중 변동도 반영합니다. [RDS 백업 무료 허용량](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithAutomatedBackups.html) · [Amazon RDS FAQs — Backup storage](https://aws.amazon.com/rds/faqs/)

중지 중에는 새 자동 백업이 생성되지 않지만 기존 백업은 남습니다. DB 삭제 후에는 무료 허용량도 달라질 수 있으므로 남은 수동 스냅샷과 보존 자동 백업의 비용을 확인합니다. [EBS 스냅샷 노트](../ebs/snapshots.md)와 같이 증분 저장 개념을 활용하되, RDS 견적에는 계정·리전별 허용량과 DB 복원 정책을 적용합니다. [Backup retention period](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithAutomatedBackups.BackupRetention.html) · [Retaining automated backups — Retention costs](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithAutomatedBackups.Retaining.html)

## 8. 낭비 후보와 판단 근거

| 후보와 비용 원인 | 확인할 자료 | 검토할 AWS 기능·조치 | 위험과 보류 조건 |
|---|---|---|---|
| 과도한 DB 사양 · 높은 클래스 시간 단가 | 피크 CPU, 가용 메모리, 연결 수, 처리량·지연 | CloudWatch와 Database Insights로 병목을 확인한 뒤 DB 클래스 변경 검토 | 피크·배치 관측이 빠지면 보류. 축소 시 메모리 압박, 연결 한도, 지연 악화 가능 |
| 과도한 스토리지 성능 · 설정 IOPS·처리량 비용 | IOPS와 MiB/s의 피크, 지연·큐, 인스턴스 한도 | RDS 스토리지 유형·성능 설정 변경 검토 | 변경 과정과 이후의 I/O 여유를 확인. 평균치만 있으면 보류 |
| 필요성이 확인되지 않은 고가용성 · 대기 자원 비용 | 서비스 가용성 목표, 장애 이력, 허용 중단·데이터 손실 | RDS Multi-AZ 배포 설정을 복구 요구와 비교 | 요건 또는 대체 복구 절차가 미확인이라면 전환 판단 보류 |
| 미사용 의심 인스턴스 · 실행 시간과 유지 자원 비용 | 접속 이력, 예약 작업, 소유자, 의존 서비스 | 지원되는 개발·테스트 DB의 일시 중지 검토 | 재시작 시간과 자동 재시작, 주기성 업무를 확인. 소유·의존성이 미확인이라면 보류 |
| 과다 백업 · 무료 허용량 초과 저장 | 스냅샷별 소유권·보존 사유, 복원 시험, 법적 보존기간 | RDS 보존 설정과 수동 스냅샷 목록 검토 | 필요한 복구 시점과 복원 경로가 확인되기 전 보존 축소나 삭제 판단 보류 |

위 표는 공식 과금·동작을 바탕으로 정리한 검토 기준입니다. 실제 낭비 여부는 서비스 자료와 운영 요구를 함께 확인해 판단합니다. [RDS 스토리지 성능 요인](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_Storage.html) · [RDS 모니터링 지표](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-metrics.html)

## 9. 자원 적정성 판단에 필요한 지표

| CloudWatch 지표 | 해석 |
|---|---|
| CPUUtilization | CPU 사용률. 피크와 지속 시간을 확인합니다. |
| FreeableMemory | 사용 가능한 RAM 바이트. 낮아지는 추이와 부하를 함께 봅니다. |
| DatabaseConnections | 클라이언트 네트워크 연결 수. 피크 연결과 클래스·엔진 한도를 비교합니다. |
| ReadIOPS / WriteIOPS | 초당 읽기·쓰기 작업 수. 각각의 피크와 스토리지 성능을 비교합니다. |
| ReadLatency / WriteLatency | 읽기·쓰기 I/O당 평균 소요 시간. 처리량과 함께 지연 악화를 확인합니다. |
| DiskQueueDepth | 스토리지 접근을 기다리는 미완료 I/O 요청 수. 지속 증가 여부를 봅니다. |
| FreeStorageSpace | 사용 가능한 저장 공간. 성장률과 배치 작업의 임시 공간을 확인합니다. |

평균 CPU가 낮아도 피크 연결, 메모리 압박, 쿼리 잠금, 디스크 대기가 성능을 제한할 수 있습니다. 일간 평균에 가려진 피크와 월말·백업 시간대도 살피고, 후보 클래스의 CPU·메모리·EBS 한도와 애플리케이션의 지연 목표를 함께 비교합니다. [Amazon CloudWatch metrics for Amazon RDS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-metrics.html)

## 10. 비용과 고가용성의 관계

운영 중단이 결제나 주문 처리에 직접 영향을 주고 단일 AZ 장애에도 빠른 재개가 필요하면, 다른 AZ의 대기 자원과 자동 장애 조치가 요구사항에 기여합니다. **RTO**는 서비스 재개까지 허용할 시간이며 **RPO**는 장애 시 허용할 데이터 손실 범위입니다. 장애 조치 시간은 트랜잭션 상태 등에 따라 달라지고, 앱의 DNS 갱신·재연결도 실제 복구 시간에 포함해야 합니다. [Failing over a Multi-AZ DB instance](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZ.Failover.html)

동기식 Standby는 인프라 장애에 대응하는 수단입니다. 논리적 데이터 손상이나 과거 시점 복구에는 백업과 복원 검증이 필요합니다. Single-AZ 전환을 검토하려면 허용 중단, 데이터 손실 범위, 복원 절차와 실제 소요 시간을 먼저 확인합니다. 이 정보가 없다면 예제의 138.60 USD 차이로 전환을 결정할 수 없습니다. [Multi-AZ DB instance deployments](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZSingleStandby.html) · [Introduction to backups](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithAutomatedBackups.html)

## 11. 확인 문제

1. DB 인스턴스를 중지하면 실행 시간 비용과 할당 스토리지 비용은 각각 어떻게 달라지나요?
2. 예제의 인스턴스 단가와 스토리지 단가를 사용해 720시간·100 GiB 구성의 Single-AZ와 Multi-AZ 총액과 차이를 계산하세요.
3. 평균 CPU가 낮은 RDS의 클래스를 줄이기 전에 어떤 지표와 업무 조건을 확인해야 하나요?

## 12. 확인 범위와 한계

AWS 공식 문서에서 MySQL의 과금 단위, RDS gp3의 구간별 사양, 배포 형태별 대기 인스턴스 역할, 백업 보존과 허용량을 확인했습니다. 154.00 USD와 292.60 USD는 가상 단가로 계산한 결과입니다. 실제 청구액, 쿼리 부하와 지연, 장애 조치·복원 시간은 측정하지 않았습니다. 피크 부하, 서비스 가용성 목표, 백업 보존 의무가 확인되기 전에는 자원 축소나 배포 변경 판단을 보류합니다.

## 13. 다음 학습 질문

> RDS 인스턴스의 CPU·메모리·I/O 사용량을 분석해 자원 축소 가능성을 판단하려면 어떤 근거가 필요하며, 성능과 가용성을 유지하면서 비용을 줄일 수 있는가?

## 공식 참고 자료

확인일은 **2026-11-07**입니다.

| 자료 | 확인 범위 |
|---|---|
| [Amazon RDS for MySQL pricing](https://aws.amazon.com/rds/mysql/pricing/) · [DB instance billing for Amazon RDS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/User_DBInstanceBilling.html) | On-Demand, T4g and T3 CPU Credits, Reserved Instances, Database storage costs, FAQ와 과금 항목 |
| [What is Amazon RDS?](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Welcome.html) · [Stopping an Amazon RDS DB instance temporarily](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_StopInstance.html) | 관리 모델과 DB 인스턴스, 중지 시 유지 비용과 자동 시작 |
| [Amazon RDS DB instance storage](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_Storage.html) | gp2, gp3, Provisioned IOPS SSD, Automatic striping, Factors that affect database performance |
| [Configuring and managing a Multi-AZ deployment](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZ.html) · [Multi-AZ DB instance deployments](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZSingleStandby.html) | 배포 형태, 읽기 지원과 동기 복제 |
| [Working with DB instance read replicas](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_ReadRepl.html) · [Failing over a Multi-AZ DB instance](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZ.Failover.html) | 복제 방식과 장애 조치·재연결 |
| [Introduction to backups](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithAutomatedBackups.html) · [Amazon RDS FAQs](https://aws.amazon.com/rds/faqs/) | 자동·수동 백업, PITR, 계정·리전별 무료 백업 허용량 |
| [Backup retention period](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithAutomatedBackups.BackupRetention.html) · [Retaining automated backups](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithAutomatedBackups.Retaining.html) | 보존기간, 중지·삭제 뒤 남는 백업과 비용 |
| [Amazon CloudWatch metrics for Amazon RDS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-metrics.html) | CPU·메모리·연결·I/O·저장 여유 지표 |

[AWS 학습 목차](../README.md) · [전체 학습 목차](../../README.md)

## 확인 문제 정답과 해설

1. 중지 기간에는 추가 DB 인스턴스 실행 시간이 발생하지 않습니다. 할당 스토리지는 유지되므로 과금이 이어지며, 설정 IOPS와 백업에도 해당 요금이 남을 수 있습니다.
2. Single-AZ는 `720 × 0.20 + 100 × 0.10 = 154.00 USD`, Multi-AZ는 `720 × 0.38 + 100 × 0.19 = 292.60 USD`입니다. 차이는 **138.60 USD**입니다.
3. 피크 CPU·연결 수와 FreeableMemory, 읽기·쓰기 IOPS와 지연, DiskQueueDepth, FreeStorageSpace를 봅니다. 업무 피크와 배치, 응답시간 목표, 후보 클래스의 한도까지 확인해야 축소 가능성을 판단할 수 있습니다.

## 추가(2026-11-15) — 중지와 7일 자동 재시작

> 개발용 DB를 "한 달 동안 멈춰 두면" 정말 인스턴스 요금이 0이 되는가?

**과금 규칙.** DB 인스턴스는 **최대 7일 연속 중지**할 수 있고, 7일이 지나면 **자동으로 시작**됩니다. 중지 중에도 스토리지, 프로비저닝 IOPS, 백업 저장, 공인 IPv4는 과금됩니다. 읽기 복제본이 있거나 자신이 복제본이면 중지할 수 없고, SQL Server Multi-AZ도 중지할 수 없습니다.

**가상 예시.** PostgreSQL db.t4g.medium Single-AZ 0.102 USD/시간, gp3 100 GB 0.131 USD/GB-월([2026-11-15 사본](../../../references/aws-price-list-apn2-2026-11-15.json)).

| 운영 방식 | 계산 | 월 비용 |
|---|---|---:|
| 상시 실행 | 0.102 × 730 + 13.10 | 87.56 USD |
| 평일 10시간만 실행(일정 기반 시작·중지, 월 220시간) | 0.102 × 220 + 13.10 | 35.54 USD |
| 한 번 중지하고 잊음(7일 뒤 자동 시작, 남은 23일 실행) | 0.102 × 552 + 13.10 | 69.40 USD |
| 공인 IPv4 1개를 쓰는 경우 추가 | 0.005 × 730 | +3.65 USD |

"멈춰 뒀다"는 기록만 보고 절감을 계산하면 틀립니다. 절감은 **일정에 따라 반복 중지하는 자동화가 있을 때만** 성립합니다.

**낭비 판단 자료.** 인스턴스 상태 이벤트(중지·자동 시작), 근무 시간 외 연결 수, 복제본 유무, 스토리지·백업 크기. 장기간 쓰지 않을 DB는 스냅샷 후 삭제와 비교합니다.

**확인 문제.** 중지한 DB의 월 비용에서 사라지는 항목과 남는 항목은? **해설.** 인스턴스 시간만 사라지고, 스토리지·IOPS·백업·공인 IPv4는 남습니다.

| 공식 자료 (확인일 2026-11-15) | 확인 범위 |
|---|---|
| [Stopping an Amazon RDS DB instance temporarily](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_StopInstance.html) | 7일 제한과 자동 시작, 중지 중 과금 항목, 중지 불가 조건 |
| [Price List — AmazonRDS ap-northeast-2](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonRDS/current/ap-northeast-2/index.json) | 인스턴스·gp3·백업 서울 요율, 게시일 2026-11-13 |
