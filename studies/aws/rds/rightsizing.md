# RDS 비용 산정 02 — Rightsizing과 성능·가용성의 균형

> CPU 사용률이 낮은 RDS 인스턴스는 과다 할당된 것인가? 어떤 관측 지표와 운영 조건을 확인해야 서비스 품질을 유지하면서 자원 축소를 검토할 수 있는가?

[RDS 비용 산정 01](README.md)에 이어 RDS for MySQL DB 인스턴스를 다룹니다. 과금 구조를 바탕으로 축소 후보를 고르고, 변경 판단에 필요한 근거와 판단을 보류할 조건을 구분합니다.

## 1. Rightsizing의 기본 개념

Rightsizing은 업무 부하와 서비스 목표에 맞게 자원 구성을 조정하는 일입니다. 과다 할당(Overprovisioning)은 필요한 여유까지 감안해도 자원이 남는 경우이고, 과소 할당(Underprovisioning)은 요구 부하를 감당할 자원이 부족한 경우입니다. DB Instance Class는 vCPU와 메모리뿐 아니라 네트워크와 스토리지 연결 성능에도 영향을 줍니다. 메모리를 줄이면 캐시에 담을 수 있는 데이터가 줄고 디스크 읽기가 늘 수 있어, CPU 여유가 곧 전체 구성의 여유를 뜻하지는 않습니다. 같은 계열의 작은 크기 외에도 메모리 비율이 다른 클래스, I/O가 병목인 경우의 스토리지 조정, 쿼리 개선을 비교할 수 있습니다. [RDS 모범 사례 — Evaluating performance metrics, Tuning queries](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_BestPractices.html)

| 단계 | 확보한 근거 |
|---|---|
| 낮은 사용률 | 특정 자원과 관측 구간의 값이 낮습니다. |
| 과다 할당 의심 | 대표 부하에서도 자원 여유가 반복해서 관찰됩니다. |
| 축소 검토 후보 | 주요 업무 주기를 관측했고 후보 클래스와 비교할 자료가 있습니다. |
| 검증을 통과한 변경안 | 대표 부하에서 성능 기준을 충족하고 가용성·복구 조건도 확인했습니다. |
| 실제 적용 후 비용 절감 | 비교 가능한 업무량·기간과 가격 조건으로 변경 전후 청구액을 확인했습니다. |

## 2. 주요 지표와 해석 한계

아래 단위는 CloudWatch RDS 지표 참조를 기준으로 합니다. 콘솔에서 표시 단위를 바꾼 경우 비교 전에 환산합니다. 지표 지원과 수집 여부는 엔진, 클래스, 배포 형태, 모니터링 설정에 따라 확인합니다. **관측되지 않은 값은 미확인으로 표시합니다.** [Amazon CloudWatch metrics for Amazon RDS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-metrics.html) · [Performance Insights API의 DB load 정의](https://docs.aws.amazon.com/performance-insights/latest/APIReference/Welcome.html)

| 영역·지표 | 측정값·단위 | 축소 판단에서 볼 신호 | 단독 해석의 한계 |
|---|---|---|---|
| CPU · `CPUUtilization` | CPU 사용률, % | 피크 높이와 지속 시간, 후보 vCPU의 여유 | 평균이 낮아도 배치 피크나 I/O 대기가 숨을 수 있음 |
| 메모리 · `FreeableMemory` | 사용 가능한 RAM, 바이트. MySQL은 Linux의 `MemAvailable` | 부하 피크에서 여유가 줄어드는지 확인 | 단순 미사용 RAM만 세는 값이 아니며, 현재 값으로 축소 후 캐시 적중률을 알 수 없음 |
| 메모리 · `SwapUsage` | 사용 중인 스왑 공간, 바이트 | 가용 메모리 감소와 스왑 증가가 겹치는지 확인 | 누적된 사용량이 현재 스왑 입출력 속도를 뜻하지 않음 |
| 연결 · `DatabaseConnections` | 클라이언트 네트워크 연결 수, 개 | 피크 연결과 후보 클래스·파라미터의 연결 여유 비교 | 유휴 연결도 있으므로 실행 중인 쿼리 수나 DB 부하를 확정할 수 없음 |
| 스토리지 I/O · `ReadIOPS`, `WriteIOPS` | 평균 읽기·쓰기 작업 수, 회/초 | 읽기·쓰기 피크와 후보의 스토리지 및 인스턴스 한도 비교 | 높은 IOPS도 지연이 안정적이면 정상 업무량일 수 있음. 바이트 처리량은 별도 |
| I/O 지연 · `ReadLatency`, `WriteLatency` | 평균 읽기·쓰기 디스크 I/O 소요 시간, 초 | 피크 업무에서 평소보다 지연이 늘어나는지 확인 | 앱 응답시간과 다르며 개별 I/O의 꼬리 지연을 보여 주지 않음 |
| I/O 대기 · `DiskQueueDepth` | 디스크 접근을 기다리는 미완료 I/O 수, 개 | 지연과 함께 대기열이 지속해서 늘면 병목을 조사 | 순간 값만으로 정상 병렬 처리와 포화를 구분하기 어려움 |
| 스토리지 · `FreeStorageSpace` | 남은 스토리지 공간, 바이트 | 데이터 증가와 배치 임시 공간 여유 확인 | 남은 공간이 IOPS 여유를 보장하지 않음 |
| 네트워크 · `NetworkReceiveThroughput`, `NetworkTransmitThroughput` | 수신·송신 트래픽, 바이트/초 | 피크를 후보의 네트워크 한도와 비교 | 고객 트래픽 외에 모니터링·복제 트래픽도 포함 |
| DB 부하 · `DBLoad` | 평균 활성 세션 수(AAS) | CPU에서 실행 중인 부하와 I/O·잠금 등에 대기하는 부하를 구분 | 지원·수집 조건이 필요하며, 활성 세션 수만으로 원인을 단정할 수 없음 |

## 3. 평균과 피크 읽기

**Average**는 정해진 집계 구간의 평균이고, **Maximum**은 그 구간에서 관측된 최댓값입니다. **p95·p99**는 관측 표본의 분포에서 각각 상위 약 5%·1% 경계에 해당하는 값입니다. 긴 집계 구간의 평균은 짧은 피크를 가릴 수 있고, Maximum은 피크의 지속 시간을 알려 주지 않습니다. 집계 주기, 전체 관측 기간, 사용한 표본의 종류를 함께 기록합니다. 예를 들어 1분 단위 평균 지연의 p99는 개별 I/O 지연의 p99와 다릅니다. CloudWatch의 직접 백분위수 지원은 지표와 원시 표본 또는 통계 집합 조건에 따라 달라집니다. [CloudWatch Metrics concepts — Percentiles](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/cloudwatch_concepts.html) · [RDS 모범 사례 — Viewing performance metrics](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_BestPractices.html)

- **가상 사례 A**는 CPU 평균 12%, 배치 시간대 85%입니다. 배치 피크 지속 시간, 처리 완료 시한, 후보의 vCPU와 I/O 여유를 확인하기 전에는 축소를 확정할 수 없습니다.
- **가상 사례 B**는 CPU 평균 12%지만 주요 피크 구간과 메모리 값이 누락됐습니다. 수집 누락과 실제 저부하를 구분할 자료가 필요합니다.

두 사례의 수치는 설명용이며 AWS 권고 임계값이 아닙니다.

## 4. AWS Compute Optimizer의 권고 읽기

Compute Optimizer는 지원되는 자원의 구성과 관측 지표를 분석해 대안을 제시합니다. RDS for MySQL은 지원 엔진에 포함되지만, DB 클래스가 지원 목록에 들어가는지 확인해야 합니다. **Instance** 권고는 DB 클래스와 현재·후보의 가격·성능 위험을 비교합니다. **Storage** 권고는 별도로 스토리지 유형, 할당 용량, IOPS·처리량과 비용을 다룹니다. 확인일 기준 RDS 스토리지 지원 목록은 gp2·gp3·io1입니다. 일반 EBS와 Aurora의 요구사항은 별도입니다. [Supported resources](https://docs.aws.amazon.com/compute-optimizer/latest/ug/supported-resources.html) · [RDS 권고 화면과 상세 정보](https://docs.aws.amazon.com/compute-optimizer/latest/ug/view-rds-recommendations.html)

| 항목 | 문서에서 확인한 조건 |
|---|---|
| 기본 데이터 요건 | RDS DB 인스턴스 권고는 최근 **14일 중 최소 30시간**의 CloudWatch 지표를 요구합니다. |
| 향상된 인프라 지표 | **유료** 권고 설정입니다. 활성화 시 최대 **93일**을 돌아보며 이 구간에서 최소 30시간의 지표를 요구합니다. Database Insights 모드와 별개입니다. |
| 분석에 쓰는 지표 | CPU·연결·송수신·읽기/쓰기 IOPS·처리량, 해당 버스트 크레딧 지표, 남은 저장 공간을 문서가 열거합니다. 추가 조건을 충족하면 DBLoad와 OS 스왑 입출력도 분석합니다. 2절은 운영 판단용 지표 목록이며, 그 표의 모든 지표가 도구 입력인 것은 아닙니다. |
| 권고가 없을 때 | 지원 여부, 서비스 참여 상태, 자료량과 분석 대기를 확인합니다. 상세 권고 문서는 RDS 권고 생성에 최대 12시간, 공통 요건 문서는 분석에 최대 24시간이 걸릴 수 있다고 안내합니다. 미생성을 적정 사양으로 해석하지 않습니다. |

[Resource requirements — Amazon Aurora and RDS instances](https://docs.aws.amazon.com/compute-optimizer/latest/ug/requirements.html) · [Aurora and RDS database metrics](https://docs.aws.amazon.com/compute-optimizer/latest/ug/rds-metrics-analyzed.html) · [Enhanced infrastructure metrics](https://docs.aws.amazon.com/compute-optimizer/latest/ug/enhanced-infrastructure-metrics.html) · [RDS 권고 생성 안내](https://docs.aws.amazon.com/compute-optimizer/latest/ug/view-rds-recommendations.html)

**Over-provisioned**는 도구가 초과 사양을 발견한 경우, **Under-provisioned**는 부족한 사양을 발견한 경우, **Optimized**는 관측한 범위에서 요구에 맞는 것으로 평가한 경우입니다. Instance와 Storage의 분류·근거는 따로 읽습니다. 후보 클래스의 성능 위험은 도구가 분석한 자원 사양 중 가장 높은 위험을 반영하는 예측치입니다. 예상 월 절감액은 사용 시간과 요율 차이를 바탕으로 하며, 할인 반영 여부는 비용 데이터 설정에 따라 달라집니다. 권고를 받은 뒤에도 지원 조건과 서비스 성능·가용성 검증이 필요합니다. [RDS 권고 — Finding classifications, Estimated monthly savings, Performance risk](https://docs.aws.amazon.com/compute-optimizer/latest/ug/view-rds-recommendations.html)

### Performance Insights 종료와 Database Insights

**2026-11-07 확인 기준**, CloudWatch는 Performance Insights의 종료일을 **2026-07-31**로 밝히고 기존 사용자를 CloudWatch Database Insights로 이전했다고 안내합니다. Database Insights Standard는 기본 모드이며, 상세 DB·쿼리 지표를 최대 7일까지 추가 비용 없이 보존하고 장기 보존은 유료로 설정할 수 있습니다. Advanced는 모드 자체의 요금이 있으며 장기 상세 지표 보존이 그 요금에 포함됩니다. 제공 기능은 엔진·리전 등에 따라 다릅니다. [CloudWatch Database Insights — 종료 안내, Modes, Data retention, Pricing](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Database-Insights.html)

같은 날짜에 확인한 Compute Optimizer 문서는 과다 할당 인스턴스 권고에 **Performance Insights 활성화**가 필요하다고 표기합니다. 분석 지표 문서도 해당 조건으로 `DBLoad`, `os.swap.in`, `os.swap.out`을 열거하고, 조건을 충족하지 않으면 vCPU 축소 권고를 제공하지 않는다고 설명합니다. 현재 RDS 설정 문서에서는 Standard 모드와 상세 지표 수집을 제어하는 기존 API 필드 `EnablePerformanceInsights`를 따로 설명하며, AWS는 Performance Insights API 참조도 제공합니다. 종료된 사용자 경험과 남아 있는 지표·설정 이름을 구분할 근거입니다. [Compute Optimizer 요건](https://docs.aws.amazon.com/compute-optimizer/latest/ug/requirements.html) · [분석 지표](https://docs.aws.amazon.com/compute-optimizer/latest/ug/rds-metrics-analyzed.html) · [RDS Database Insights Standard 설정](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_DatabaseInsights.TurningOnStandard.html) · [Performance Insights API 참조](https://docs.aws.amazon.com/performance-insights/latest/APIReference/Welcome.html)

공개 문서에서 Compute Optimizer의 문구를 Database Insights 모드별 권고 생성 조건으로 직접 대응시킨 안내는 확인하지 못했습니다. **Standard 표시만으로 충분한지, Advanced가 필요한지 단정하지 않습니다.** 후속 확인 항목은 대상 엔진·리전·클래스의 상세 지표 수집 상태, 실제 DBLoad·스왑 입력 가용성, 권고 생성 여부입니다.

## 5. 관측 기간을 정하는 방법

하루치 자료는 짧은 병목을 찾는 데 쓸 수 있지만, 평일과 주말의 패턴이 다르면 두 구간을 모두 봅니다. 월말 정산·백업·데이터 이관이나 계절 이벤트가 있다면 그 구간도 포함합니다. 평시와 피크의 요청량·동시 연결·작업 완료 시간 및 지연 목표를 함께 기록합니다. 과거에 없는 이벤트는 별도 불확실성으로 남깁니다. [RDS 모범 사례 — Using metrics to identify performance issues](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_BestPractices.html)

도구의 30시간은 권고 생성의 최소 자료량입니다. 안전한 축소를 검토할 기간은 서비스가 실제로 겪는 업무 주기에 따라 정합니다. 중요한 시간대의 메모리·I/O나 업무량이 누락됐다면 누락 구간을 보완할 때까지 관련 자원의 축소 판단을 보류합니다.

## 6. 가상 판단 사례

| 사례 | 가상 관측 | 판단 |
|---|---|---|
| A. 축소 검토 후보 | 평일·주말과 월말 업무를 포함해 CPU가 지속적으로 낮고, 메모리·I/O에서 뚜렷한 압박이 관측되지 않음. 후보 클래스의 vCPU·RAM·EBS 한도 자료가 있음 | 축소 검토 후보로 분류합니다. 후보의 실제 지원 여부와 피크 부하에서의 지연·처리량, 가용성 기준을 검증한 뒤 변경 여부를 판단합니다. |
| B. 성능 위험 | CPU 평균 12%. 중요한 배치 때 디스크 지연이 2 ms에서 15 ms로, 대기열이 1건에서 20건으로 증가 | I/O 포화, 쿼리 변화, 동시 작업 등 원인을 먼저 확인합니다. 후보 클래스의 IOPS·처리량 한도를 확인하기 전에는 축소를 보류합니다. |
| C. 근거 부족 | CPU 평균 10%만 확인 가능. 메모리·I/O·업무량 자료와 가용성 요구가 불명확 | 판단을 보류합니다. 피크별 메모리·스왑·연결·I/O 지표와 요청량, 서비스 지연 목표, RTO·RPO를 확보해야 합니다. |

## 7. 가상 비용 비교

RDS for MySQL을 **720시간** 운영하고 비교 가능한 배포 구성과 가격 조건을 가정합니다. 아래는 학습용 가상 단가입니다.

| 구성 | 컴퓨팅 비용 |
|---|---:|
| 현재 | `0.24 USD/시간 × 720시간 = 172.80 USD` |
| 변경 후보 | `0.16 USD/시간 × 720시간 = 115.20 USD` |
| **예상 차이** | **57.60 USD** |

이는 컴퓨팅 비용 기준 약 33.3% 차이입니다. 스토리지·I/O·백업·전송 및 할인·크레딧·세금은 별도입니다. 후보 클래스의 지원 여부와 성능·가용성 유지 여부는 미확인입니다. 동일한 업무를 실제로 운영한 뒤 청구액을 비교해야 실현된 절감액을 알 수 있습니다.

## 8. 인스턴스 변경의 운영 위험

- 대상 클래스가 엔진 버전, 리전, 배포 형태에 맞는지 확인하고 메모리·네트워크·EBS 성능 및 연결 여유를 비교합니다.
- **Maintenance Window**는 변경을 예약하는 운영 시간대이고, **Apply Immediately**는 변경을 즉시 적용하도록 요청하는 옵션입니다. AWS 공식 설정 문서는 기존 DB 인스턴스의 **DB Instance Class 변경 중 다운타임이 발생한다**고 명시합니다. 즉시 적용을 선택하면 대기 중인 다른 변경도 함께 적용될 수 있으므로, 작업 전에 대기 중인 변경과 유지보수 일정, 중단이 영향을 줄 서비스를 확인합니다. [DB 인스턴스 설정](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_ModifyInstance.Settings.html) · [변경 적용 시점](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_ModifyInstance.ApplyImmediately.html)
- Multi-AZ는 일부 유지보수 작업의 중단을 줄일 수 있습니다. 클래스 변경을 계획할 때는 Multi-AZ에서도 다운타임을 반영하고, 재부팅이나 장애 조치에 따른 연결 끊김, DNS 갱신과 재연결을 고려합니다. 실제 중단과 복구 목표 충족 여부는 앱에서 확인해야 합니다. [RDS Multi-AZ DB 인스턴스](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZSingleStandby.html)
- 백업과 복원 가능 여부를 확인하고 RTO(허용 복구 시간)·RPO(허용 데이터 손실 시간)를 정합니다. 원래 클래스로 되돌리는 조건, 그 과정에 필요한 추가 중단, 복원이 필요한 경우의 데이터 시점을 계획합니다.

[Modifying an Amazon RDS DB instance](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Overview.DBInstance.Modifying.html) · [Failing over a Multi-AZ DB instance](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZ.Failover.html) · [RDS 모범 사례](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_BestPractices.html)

## 9. 기존 판단 방법과 한계

| 접근 | 장점 | 해석할 때의 한계 |
|---|---|---|
| 단순 규칙 | CPU 평균·피크, 자료 누락, 배치 여부 같은 조건을 명시하면 판단 근거를 설명하기 쉽습니다. | 하나의 임계값은 병목과 업무 변화를 놓칠 수 있습니다. 자료 누락은 별도로 표시해야 합니다. |
| Compute Optimizer | 여러 지표를 활용해 지원 구성의 후보, 예상 절감액, 성능 위험을 비교할 수 있습니다. | 관측 기간·지원 범위·모니터링·가격 설정에 의존합니다. 분석 결과는 서비스 목표와 변경 위험을 별도로 검토할 출발점입니다. |

향후 사용량 예측이나 구성 최적화 연구에서는 업무량 변동과 오판 비용을 평가 기준에 포함할 수 있습니다.

## 10. 확인 문제

1. CPU 평균이 10%여도 축소를 확정할 수 없는 이유는 무엇인가요?
2. FreeableMemory와 SwapUsage를 함께 보는 이유는 무엇인가요?
3. IOPS·Latency·DiskQueueDepth는 각각 무엇을 측정하나요?
4. 가상 비용 차이 57.60 USD를 실제 절감 성과로 볼 수 없는 이유는 무엇인가요?

## 11. 확인 범위와 한계

AWS 공식 문서에서 지표 정의, 도구 지원 범위와 관측 요건, Database Insights 이전 안내, 변경 위험을 확인했습니다. 메트릭 사례와 비용은 가상입니다. 실제 AWS 지표·권고·청구, 변경 후 성능과 장애 조치 시간은 관측하지 않았습니다. 후보 지원과 서비스 기준을 확인해야 하며, 지표가 비어 있으면 그 자원에 대한 판단은 보류합니다.

## 12. 다음 학습 질문

> AWS Lambda에서는 메모리 설정에 따라 실행시간과 비용이 어떻게 달라지며, 어떤 구성이 필요한 성능을 유지하면서 더 낮은 비용을 제공하는가?

## 공식 참고 자료

확인일은 **2026-11-07**입니다.

| 자료 | 확인한 절과 범위 |
|---|---|
| [Best practices for Amazon RDS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_BestPractices.html) · [Amazon CloudWatch metrics for Amazon RDS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-metrics.html) | Using metrics to identify performance issues, Tuning queries, 지표 정의·단위·적용 범위 |
| [CloudWatch Metrics concepts](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/cloudwatch_concepts.html) · [Performance Insights API](https://docs.aws.amazon.com/performance-insights/latest/APIReference/Welcome.html) | Percentiles, DB load의 평균 활성 세션 정의 |
| [Aurora and RDS database metrics](https://docs.aws.amazon.com/compute-optimizer/latest/ug/rds-metrics-analyzed.html) · [Resource requirements](https://docs.aws.amazon.com/compute-optimizer/latest/ug/requirements.html) | RDS DB instances의 입력 지표·조건, Amazon Aurora and RDS instances의 최소 관측량 |
| [Supported resources](https://docs.aws.amazon.com/compute-optimizer/latest/ug/supported-resources.html) · [Enhanced infrastructure metrics](https://docs.aws.amazon.com/compute-optimizer/latest/ug/enhanced-infrastructure-metrics.html) | RDS 엔진·클래스·스토리지 지원 목록, 유료 관측 기간 |
| [Accessing Aurora and RDS database recommendations and details](https://docs.aws.amazon.com/compute-optimizer/latest/ug/rds-view-recommendations.html) · [Viewing Aurora and RDS database recommendations](https://docs.aws.amazon.com/compute-optimizer/latest/ug/view-rds-recommendations.html) | Instance·Storage 상세 화면, Finding classifications, Estimated monthly savings, Performance risk |
| [CloudWatch Database Insights](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Database-Insights.html) · [Turning on the Standard mode of Database Insights for Amazon RDS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_DatabaseInsights.TurningOnStandard.html) | 종료·이전 안내, Modes, Data retention, Pricing, Standard와 EnablePerformanceInsights의 구분 |
| [Modifying an Amazon RDS DB instance](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Overview.DBInstance.Modifying.html) · [Failing over a Multi-AZ DB instance](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZ.Failover.html) | 유지보수 시간과 즉시 적용, 재부팅·중단, 장애 조치와 연결 재수립 |

[AWS 학습 목차](../README.md) · [전체 학습 목차](../../README.md)

## 확인 문제 정답과 해설

1. 평균은 배치 피크를 가릴 수 있고 메모리·연결·I/O 병목을 설명하지 못합니다. 대표 업무의 피크와 후보 클래스 한도, 서비스 목표를 함께 확인합니다.
2. FreeableMemory는 확보 가능한 RAM의 여유를, SwapUsage는 사용 중인 스왑 공간을 보여 줍니다. 둘의 시간 추세와 실제 스왑 입출력·지연을 함께 보면 메모리 압박을 더 잘 판단할 수 있습니다.
3. IOPS는 초당 I/O 작업 수, Latency는 작업당 소요 시간, DiskQueueDepth는 디스크 접근을 기다리는 요청 수입니다. 세 지표를 같은 시간대의 업무량과 맞춰 해석합니다.
4. 57.60 USD는 가상 단가에 동일한 720시간을 적용한 컴퓨팅 차이입니다. 실제 지원 구성, 성능과 가용성, 전체 비용과 청구 내역을 확인해야 절감이 실현됐는지 판단할 수 있습니다.
