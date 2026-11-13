# Cloud Efficiency Lab — Study & Research Curriculum

클라우드 비용 구조, 자원 사용, 워크로드, 성능·안정성의 관계를 공부하기 위한 독립적인 학습·연구 가이드입니다. AWS에서 출발해 Linux·Docker·Kubernetes 실행 환경과 분석·최적화 방법으로 확장합니다.

아래 내용은 학습 범위와 이해도 확인 기준입니다. 자료의 탐색 경로는 각 과정과 [Studies 목차](README.md)에 있습니다. 사용자 학습 완료 여부는 미확인입니다. 실험 결과는 별도로 기록합니다.

## 권장 학습 흐름

| 순서 | 과정 | 연결할 질문 |
|---|---|---|
| 01 | Infrastructure & FinOps Foundations | 자원·사용량·성능·비용을 어떻게 구분할 것인가? |
| 02 | AWS Infrastructure & Pricing | 어떤 자원과 사용량에 비용이 발생하는가? |
| 03 | Application & Container Efficiency | 실행 환경과 설정이 자원 요구에 어떤 영향을 주는가? |
| 04 | Observability & Cost Data | 판단에 필요한 관측·비용 자료를 어떻게 연결할 것인가? |
| 05 | Optimization Methods | 어떤 근거와 방법으로 개선안을 평가할 것인가? |
| 06 | Kubernetes Resource Management | 클러스터에서 요청·배치·사용·확장은 어떻게 연결되는가? |
| 07 | EKS & Kubernetes FinOps | 클러스터 자원 관리와 실제 청구 비용은 어떻게 연결되는가? |
| 08 | Research & Reproduction | 구체적인 질문에 대해 기존 연구를 어떻게 검토·검증할 것인가? |

- 위 순서는 권장 경로이며 연구 질문과 실제 학습 진도에 따라 조정합니다.
- AWS 서비스를 모두 공부해야 Docker나 Kubernetes로 넘어갈 수 있는 것은 아닙니다.
- 논문 검토와 실험은 과정 08에 한정하지 않고 관련 질문이 생길 때 진행합니다.
- 모든 주제에 코드 구현·모델 개발·실제 AWS 실행을 요구하지 않습니다. 읽기·설명·수기 계산으로 마무리할 수 있습니다.
- 과정 번호는 안내용입니다. 디렉터리에 챕터·주차 번호를 붙이거나 고정된 4주·8주·12주 완료 일정을 강제하지 않습니다.
- 실제 AWS·EKS 실행은 사용자 승인 범위, 예상 비용·실행 시간·중단 조건·정리 방법을 먼저 정해야 합니다.

### 핵심 학습과 선택적 심화

핵심 학습은 Foundations, 주요 AWS 서비스의 비용 구조, Docker·컨테이너 자원 관리, 관측·비용 데이터, Rightsizing 등 기본 최적화, Kubernetes Requests·Limits·Scheduling, EKS 비용·공유 비용 개념입니다. 과정 08의 문제 정의와 근거·한계 구분은 학습 전반에 적용합니다.

대규모 머신러닝 모델, 복잡한 최적화 알고리즘, 멀티클라우드 확장, 실제 EKS 대규모 실험, 고급 서비스 간 비용 분석은 선택적 심화입니다. 연구 질문에 필요한 경우에만 선택하며 필수 구현이나 완료 조건으로 삼지 않습니다.

## 과정 01. Infrastructure & FinOps Foundations

학습 자료 — [Linux 자원](foundations/linux-resources.md) · [네트워크와 데이터 흐름](foundations/network-and-data-flow.md) · [워크로드 성능](foundations/workload-performance.md) · [FinOps 비용 지표](foundations/finops-cost-metrics.md)

### 목적과 필요성

비용·자원 사용·성능을 비교할 공통 언어를 익힙니다. 운영체제·네트워크·워크로드의 기본 원리를 바탕으로 낮은 사용률, 과다 할당, 낭비를 구분할 판단 기준을 마련합니다. Linux 커널을 직접 개발하는 수준은 요구하지 않습니다.

### 주요 학습 주제

| 영역 | 세부 개념과 학습 범위 |
|---|---|
| Linux·운영체제 | Process와 Thread, CPU Scheduling, Memory Management, Virtual Memory, OOM, Disk I/O, File System, cgroups·namespaces의 기본 개념 |
| 네트워크 | TCP/IP, DNS, Port, Routing, NAT, Load Balancing, Latency·Bandwidth, 요청량과 데이터 전송량 |
| 애플리케이션·워크로드 성능 | Workload 특성, CPU-bound·I/O-bound, 동시성, Latency·Throughput·Error Rate, p95/p99, JVM·GC의 기본 자원 사용 특성 |
| 클라우드 비용·FinOps | Usage·Pricing, Provisioned/Allocated Resources·Utilization, Overprovisioning·Underutilization, Waste·Anomaly의 구분, Unit Economics, 비용·성능 Trade-off, FinOps Framework 기본 개념 |

### 핵심 질문

- 할당 자원과 실제 사용량은 왜 다르며, 관측 사용률과 과금 대상 사용량은 어떻게 구분하는가?
- 사용률이 낮으면 반드시 낭비인가? 여유 용량과 업무·복구 목적은 어떻게 확인할 것인가?
- 자원을 줄이기 전에 어떤 성능·안정성 지표와 피크 구간을 살펴야 하는가?
- 비용 비교에서 기간·리전·요금 방식·업무량·포함 비용 등 어떤 가정을 명시해야 하는가?

### 추천 학습 방법

기존 [클라우드 비용과 자원 효율의 기초](foundations/README.md)를 먼저 확인합니다. 공식 자료의 정의와 작은 예제를 대조하며, 원문의 주장과 자신의 해석을 구분합니다. 실행 실험 없이 핵심 개념과 판단 보류 이유를 설명하는 것도 학습 산출물입니다.

### 관련 기술·도구·연구 방법

Linux 공식 문서의 프로세스·메모리·자원 제어 설명, 네트워크 표준, JVM·GC 공식 자료, FinOps Framework를 학습 후보로 검토합니다. 특정 도구 설치나 커널 분석을 필수로 삼지 않고 개념 비교와 단위·기간 확인부터 시작합니다.

### 선택적 작은 검증 예시

기존 문서의 가상 단가·실행 시간 계산에서 CPU 사용률만 바꿨을 때 과금 가정이 바뀌는지 수기로 설명할 수 있습니다. 평균과 피크가 다른 작은 가상 관측표로 자원 축소 판단에 부족한 자료를 찾아볼 수도 있습니다. 이는 향후 검증 후보이며 이번에 수행한 결과가 아닙니다.

### 학습 산출물과 이해도 확인 기준

용어 비교, 계산의 가정, 남은 질문을 기록합니다. 과금량·사용률·성능의 차이와 낭비를 확정할 수 없는 사례를 자신의 말로 설명할 수 있는지 확인합니다. 기존 Foundations 문서의 존재를 사용자의 이해 완료로 간주하지 않습니다.

### 기록 위치와 다음 과정 연결

[Foundations](foundations/README.md)에 공통 기초를 기록합니다. 기존 본문과 별도 주제 문서를 함께 참고합니다. 다음 과정에서는 이 비교 기준으로 AWS 서비스별 자원과 과금 항목을 살펴봅니다.

## 과정 02. AWS Infrastructure & Pricing

학습 자료 — [기존 AWS 자료](aws/README.md) · [EC2 Rightsizing·Auto Scaling](aws/ec2/rightsizing-and-autoscaling.md) · [ELB](aws/elb/README.md) · [CloudWatch](aws/cloudwatch/README.md) · [ECR](aws/ecr/README.md) · [ECS·Fargate](aws/ecs-fargate/README.md) · [DynamoDB](aws/dynamodb/README.md) · [Aurora](aws/aurora/README.md) · [EKS](aws/eks/README.md) · [AWS 비용 데이터](aws/cost-data/README.md) · [IoT Core](aws/iot-core/README.md) · [Firehose](aws/kinesis-firehose/README.md) · [Athena·Glue](aws/athena-glue/README.md) · [Bedrock](aws/bedrock/README.md) · [SageMaker](aws/sagemaker/README.md)

### 목적과 필요성

AWS 서비스별 자원 구조와 과금 방식을 이해하고 비용 발생 원인과 낭비 가능성을 분석합니다. 자원 사용 변화와 실제 비용 변화가 연결되는 조건, 최적화가 성능·가용성에 미칠 영향을 함께 검토합니다.

### 주요 학습 주제

| 영역 | 세부 개념과 학습 범위 |
|---|---|
| EC2 | 인스턴스 유형·사양, On-Demand·Spot·RI·Savings Plans 기본 구분, 실행 시간·과금, CPU·메모리 사용률, Rightsizing, 유휴 인스턴스, Auto Scaling과 비용 |
| EBS | Volume 유형, Provisioned Capacity, IOPS·Throughput, Snapshot, 미사용 볼륨·잔존 비용, 유형·크기 조정 |
| S3 | Storage Classes, 저장 용량·보관기간, API Request·Retrieval·Data Transfer 비용, Lifecycle, Versioning·이전 버전 관리 |
| RDS·Aurora | DB 인스턴스, Storage·I/O 비용, Multi-AZ, Read Replica, Backup, 인스턴스 적정성, 성능·가용성 요구 |
| Lambda | Invocation·Duration·Memory·Concurrency, 비용·실행시간 관계, Memory Tuning, 이벤트·요청 패턴 |
| 네트워크 | VPC, NAT Gateway, VPC Endpoint, Load Balancer, AZ·리전 간 전송, Internet Egress, 서비스 간 호출 비용 |
| 필요에 따른 확장 | ECS·Fargate·ECR·CloudWatch·DynamoDB·EKS의 자원 구성과 비용; 핵심 서비스 이후 질문에 따라 선택 |
| 데이터 파이프라인·AI | IoT Core 메시지 계량, Firehose 수집 올림·버퍼, Athena 스캔량·Glue DPU, Bedrock 토큰·캐싱, SageMaker 학습·추론의 유휴 비용 |

### 핵심 질문

- 서비스별 과금 단위는 무엇이며 어떤 자원 설정이 비용에 직접 영향을 주는가?
- 실제 사용량과 과금량은 어떻게 다른가? 자원을 줄여도 남는 비용 항목은 무엇인가?
- AWS 공식 최적화 기능은 어떤 입력과 근거로 권고하며, 확인하지 못하는 조건은 무엇인가?
- 비용을 줄이는 변경이 응답시간·처리량·오류율·가용성을 악화시킬 가능성을 어떻게 검토할 것인가?

### 추천 학습 방법

선택한 서비스의 공식 기술·과금 문서를 먼저 읽고 과금 항목과 설정을 연결합니다. 이후 낭비 사례와 기존 해결법, 공식 권고 도구를 검토합니다. 실제 가격 계산에는 리전·운영체제 등 가격 조건, 기준·확인일, 기간과 포함 비용을 명시하며 가격을 고정된 상수처럼 취급하지 않습니다.

### 관련 기술·도구·연구 방법

AWS 공식 요금 문서·계산 도구와 Compute Optimizer·Trusted Advisor 등 공식 권고 기능을 검토 후보로 둡니다. 기능별 지원 범위·입력·제약은 학습 시 공식 문서에서 확인합니다. 할인 약정 검토와 자원 사용 효율 검토를 구분하고 비용 항목별 계산부터 시작합니다.

### 선택적 작은 검증 예시

EC2 실행 시간 또는 EBS 할당 용량을 바꾸는 가상 계산표에서 어떤 항목을 다시 계산해야 하는지 비교할 수 있습니다. 최신 가격을 사용할 경우 확인 시점과 제외 비용을 남깁니다. 실제 AWS 자원 생성은 필요하지 않습니다.

### 학습 산출물과 이해도 확인 기준

선택 서비스의 자원·과금 항목 대응표, 낭비 후보의 근거와 반례, 공식 권고의 적용 조건을 정리합니다. 주어진 구성의 비용 계산 범위와 누락 항목, 품질 위험을 설명할 수 있는지 확인합니다. 모든 AWS 서비스 학습을 완료 조건으로 묶지 않습니다.

### 기록 위치와 다음 과정 연결

[AWS Services](aws/README.md)에 실제 학습을 시작한 서비스부터 기록합니다. Docker·Kubernetes 자체의 원리는 Platforms와 구분합니다. 다음 과정에서는 애플리케이션·컨테이너의 자원 요구와 설정을 살펴 과금 대상 자원과 연결합니다.

## 과정 03. Application & Container Efficiency

학습 자료 — [Docker 구조](platforms/docker/README.md) · [이미지 최적화](platforms/docker/image-optimization.md) · [자원 제한](platforms/docker/resource-constraints.md) · [워크로드 성능](foundations/workload-performance.md)

### 목적과 필요성

애플리케이션과 컨테이너의 실행 구조를 이해하고 이미지·자원·실행 성능을 효율화하는 기존 방법을 공부합니다. 배포 산출물의 크기와 실행 중 자원 사용, 실제 청구 비용의 차이를 구분하는 것이 목표입니다.

### 주요 학습 주제

| 영역 | 세부 개념과 학습 범위 |
|---|---|
| 애플리케이션 경량화 | 실행에 필요한 자원, JVM Heap·Native Memory, Garbage Collection, 메모리·CPU 사용, 시작 시간·실행 성능, 불필요한 의존성·구성 |
| Docker·컨테이너 기초 | Container·VM 차이, Image·Container, Container Runtime, Linux namespaces·cgroups, Dockerfile, Layer·Build Cache |
| 이미지 경량화 | Multi-stage Build, Base Image 선택, 실행 이미지 최소화, 이미지 크기·다운로드 시간·저장 비용, 런타임 자원 사용과의 구분 |
| 컨테이너 자원 효율 | CPU·Memory 제한, CPU Throttling, OOM, JVM Container Awareness, 시작 시간, 동일 워크로드의 자원 사용 비교 |
| 실행 환경 비교 | 일반 프로세스·Docker 실행, 설정별 성능 차이, EC2·ECS·Fargate와의 연결 |

### 핵심 질문

- 이미지 크기를 줄일 때 어떤 저장·전송·배포 비용을 검토해야 하는가?
- 이미지 경량화와 메모리 사용량 감소는 같은가? 각각 어떤 측정이 필요한가?
- CPU·메모리 제한을 줄이면 응답시간과 오류율에 어떤 문제가 생길 수 있는가?
- 같은 애플리케이션을 공정하게 비교하려면 버전·부하·데이터·워밍업·자원 설정 중 무엇을 통제해야 하는가?

### 추천 학습 방법

Docker와 애플리케이션 런타임 공식 문서에서 실행 구조와 자원 설정을 먼저 공부합니다. 이미지 최적화와 런타임 튜닝을 나누어 비교하고, 변경의 목적·기대 효과·확인할 지표를 정리합니다. 실행이나 애플리케이션 작성은 필수가 아닙니다.

### 관련 기술·도구·연구 방법

Dockerfile·Multi-stage Build·이미지 계층, cgroups·namespaces, JVM의 메모리·GC·컨테이너 인식 자료를 검토합니다. 사용할 버전의 공식 동작을 확인하고, 배포 크기와 런타임 측정을 분리하는 비교 방법을 익힙니다.

### 선택적 작은 검증 예시

향후 필요하면 작은 Spring Boot 애플리케이션의 실행 이미지 두 구성을 비교하거나, 동일 부하에서 컨테이너 자원 제한에 따른 성능·메모리를 비교할 수 있습니다. 로컬 측정만으로 실제 AWS 절감액을 단정하지 않습니다. 이번 작업에서는 애플리케이션·실험 코드를 만들거나 Docker를 실행하지 않습니다.

### 학습 산출물과 이해도 확인 기준

실행 구조 설명, 이미지·런타임 최적화 구분표, 비교에 필요한 통제 조건을 기록합니다. 이미지 크기 감소가 런타임 메모리·AWS 비용 감소로 이어지는지 판단하려면 어떤 추가 근거가 필요한지 설명할 수 있는지 확인합니다.

### 기록 위치와 다음 과정 연결

[Platforms](platforms/README.md)에 실행 환경 학습을, AWS 배포 서비스 고유의 비용은 [AWS Services](aws/README.md)에 기록합니다. 실제 비교 결과는 [Experiments](../experiments/README.md)에 둡니다. 다음 과정에서는 이러한 비교를 뒷받침할 관측 지표와 비용 자료를 검토합니다.

## 과정 04. Observability & Cost Data

학습 자료 — [CloudWatch](aws/cloudwatch/README.md) · [AWS 비용 데이터](aws/cost-data/README.md) · [관측과 비용](platforms/kubernetes/observability-and-cost.md)

### 목적과 필요성

자원 사용·서비스 성능·클라우드 비용을 분석할 자료의 구조와 한계를 이해합니다. 서로 다른 시간·집계·식별 기준의 자료를 연결할 조건을 살피고, 누락·지연·정의 차이로 확정할 수 없는 판단을 구분합니다.

### 주요 학습 주제

| 영역 | 세부 개념과 학습 범위 |
|---|---|
| Observability 기초 | Metrics·Logs·Traces, Monitoring·Observability, SLI·SLO, 성능·오류 지표 |
| 관측 도구와 품질 | CloudWatch·Prometheus·Grafana, 수집 주기·집계 방식, 누락·지연 데이터, 관측 도구 자체의 비용 |
| AWS 비용 자료 | AWS Billing·Cost Explorer·Cost and Usage Report·AWS Data Exports, 비용 사용 유형과 과금 항목 |
| FOCUS | Specification, 비용 데이터 표준화, BilledCost·EffectiveCost 등 비용 정의, 공급자별 차이, 데이터 버전·필드 해석 |
| 비용 배분·비교 | Resource Tag·Cost Allocation Tag·Cost Categories, 공유·미분류 비용, Unit Economics, 비용·업무량 관계 |

### 핵심 질문

- 비용 데이터와 자원 메트릭을 시간·리소스 식별자·범위 기준으로 어떻게 연결할 것인가?
- 평균 CPU만으로 최적화를 판단할 수 없는 이유는 무엇인가?
- 누락·지연 데이터가 있으면 어떤 판단을 보류해야 하는가?
- 여러 서비스 비용을 비교할 때 기간·집계·할인·업무량과 비용 정의를 어떻게 맞출 것인가?

### 추천 학습 방법

공식 문서의 데이터 정의와 공개 가능한 작은 예제를 중심으로 읽습니다. 필드명만 보고 의미를 추정하지 않고 데이터·사양 버전과 비용 정의를 함께 확인합니다. Cost Explorer API 호출이나 지속적인 메트릭 수집을 필수로 요구하지 않습니다.

### 관련 기술·도구·연구 방법

CloudWatch·Prometheus·Grafana, AWS 비용 보고 기능, FOCUS 사양, 태그·Cost Categories를 검토 후보로 둡니다. 시간 정렬, 집계 단위 맞추기, 결측·중복 확인, 단위경제 분모 정의 등 자료 검증 방법을 학습합니다.

### 선택적 작은 검증 예시

향후 작은 가상 비용표와 사용량표에서 기간·식별자가 맞는 행만 연결하고, 연결되지 않는 비용을 따로 표시할 수 있습니다. 같은 표에서 비용 정의나 공유 비용 정책을 바꾸어 비교 결론이 달라지는지 수기로 확인할 수 있습니다. 가상 예시는 실제 청구 분석과 구분합니다.

### 학습 산출물과 이해도 확인 기준

자료 사전, 비용·메트릭 연결 기준, 누락 항목과 보류할 판단을 정리합니다. 비용 합계가 어떤 정의·기간·배분 정책에서 나온 값인지 설명하고, 비교 가능한 자료와 추가 확인이 필요한 자료를 구분할 수 있는지 확인합니다.

### 기록 위치와 다음 과정 연결

공통 관측·분석 방법은 [Methods](methods/README.md), AWS 비용 관리 기능은 [AWS Services](aws/README.md), 실제 검증은 [Experiments](../experiments/README.md)에 기록합니다. 다음 과정의 규칙·예측·추천에 필요한 입력 조건과 평가 기준으로 연결합니다.

## 과정 05. Optimization Methods

학습 자료 — [Rightsizing](methods/rightsizing.md) · [예측](methods/forecasting.md) · [이상탐지](methods/anomaly-detection.md) · [구성 최적화](methods/configuration-optimization.md) · [비용 배분](methods/cost-allocation.md) · [서비스 간 분석](methods/cross-service-analysis.md)

### 목적과 필요성

기존 비용 절감·자원 최적화 방법의 입력, 가정, 적용 조건과 평가 방법을 비교합니다. 설명 가능한 단순 기준선부터 이해하며, 데이터가 부족하거나 품질 위험이 크면 추천을 보류하는 기준도 함께 학습합니다.

### 주요 학습 주제

| 영역 | 세부 개념과 학습 범위 |
|---|---|
| Rule-based Analysis | Threshold·조건 규칙, Finding·Blocker, 추가 검토가 필요한 상황, 데이터 부족 시 판단 보류 |
| Rightsizing | CPU·메모리 사용량, 평균·피크·p95, 여유 용량, 성능 위험, 자원 변경 권고, 예상 비용 효과 |
| Time-series Forecasting | 이동평균·추세·계절성, 수요·비용 예측, 단순 기준선, 예측 오차 |
| Anomaly Detection | Z-score·EWMA·계절성 기반 탐지·Isolation Forest·예측 오차 기반 탐지, 임계값, 오탐·탐지 지연 |
| Configuration Optimization | 설정 후보, 비용·성능 목적 함수, 제약 조건, 탐색 비용, 베이지안 최적화 등 기존 방법 |
| Cost Allocation | 직접·공유 비용, 사용량 기반 배분, 유휴 비용, 배분 정책별 결과 차이 |
| Cross-service Analysis | 서비스 의존성, 전송·요청 증폭, 결합 비용, 개별 최적화와 전체 비용 최적화의 차이 |

### 핵심 질문

- 단순 규칙으로 어디까지 판단할 수 있고, 어떤 조건에서 머신러닝의 추가 복잡성이 필요한가?
- 비용 이상과 실제 낭비를 어떻게 구분하며, 추천을 막는 조건은 무엇인가?
- 개선안의 예상 비용 효과와 실제 관측 효과를 어떤 지표로 평가할 것인가?
- 특정 데이터·기간·임계값이 기존 알고리즘에 유리하도록 선택되지는 않았는가?
- 한 서비스의 변경이 다른 서비스 비용이나 품질을 악화시키지 않는지 어떻게 검토할 것인가?

### 추천 학습 방법

설명 가능한 규칙·단순 기준선을 먼저 살핀 뒤 필요한 통계·머신러닝 방법을 검토합니다. 논문과 모델마다 입력 데이터·가정·비교 대상·평가 지표·한계를 정리합니다. 모델 선택이나 전 방법 구현을 학습 목표로 고정하지 않습니다.

### 관련 기술·도구·연구 방법

위 통계·머신러닝·탐색 방법의 원전·공식 설명과 기존 구현을 질문에 따라 선택합니다. 임계값 민감도, 시계열 순서에 따른 평가, 단순 기준선 비교, 제약 조건을 포함한 비용·성능 비교를 검토합니다. 고급 최적화와 서비스 간 분석의 심화는 선택 사항입니다.

### 선택적 작은 검증 예시

향후 동일한 작은 시계열에서 고정 임계값과 이동 기준선의 판단 차이를 손으로 비교하거나, 가상 자원 후보 중 품질 제약을 충족하는 구성을 비교할 수 있습니다. 오탐·정답 판정 근거가 없다면 탐지 품질을 확정하지 않습니다. 이번에는 알고리즘이나 모델을 실행하지 않습니다.

### 학습 산출물과 이해도 확인 기준

문제·입력·가정·기준선·지표·한계 비교표와 판단 보류 조건을 기록합니다. 더 복잡한 방법이 필요한 이유, 비용 이상의 조사와 낭비 확정의 차이, 예상 절감과 실측의 차이를 설명할 수 있는지 확인합니다.

### 기록 위치와 다음 과정 연결

[Methods](methods/README.md)에 공통 방법과 논문 검토를, 실행·평가 결과는 [Experiments](../experiments/README.md)에 기록합니다. 다음 과정에서는 Kubernetes의 자원 요청·배치·확장 구조를 이해해 이 방법들의 입력·제약으로 연결합니다.

## 과정 06. Kubernetes Resource Management

학습 자료 — [Kubernetes 구조](platforms/kubernetes/README.md) · [자원 관리](platforms/kubernetes/resource-management.md) · [배치와 확장](platforms/kubernetes/scheduling-and-autoscaling.md) · [관측과 비용](platforms/kubernetes/observability-and-cost.md)

### 목적과 필요성

Kubernetes에서 워크로드 자원이 요청·할당·사용·조정되는 과정을 이해합니다. 애플리케이션 사용량만으로 설명되지 않는 배치·확장·용량 제약을 살피고 비용 분석에 필요한 클러스터 관점을 마련합니다.

### 주요 학습 주제

| 영역 | 세부 개념과 학습 범위 |
|---|---|
| 기본 구조 | Control Plane·Node·Pod·Deployment·StatefulSet·Service·Scheduler·kubelet |
| Resource Management | CPU·Memory Requests, CPU·Memory Limits, Node Allocatable, QoS Classes, CPU Throttling, OOMKilled·Eviction |
| Scheduling | Pod 배치, Node 자원 요청량, 배치 제약, 리소스 단편화, Bin Packing·용량 효율 |
| Autoscaling | HPA·VPA·Cluster Autoscaler·Node Autoscaling, Karpenter 역할, 확장 속도·서비스 품질, 요청량·Node 수 관계 |
| Observability | Pod·Node 메트릭, 사용량·요청량 비교, 관련 성능 지표, 워크로드 단위 분석 |

### 핵심 질문

- Requests와 실제 사용량은 어떻게 다르며 배치 판단에는 어떤 자료가 필요한가?
- Limits를 낮출 때 Throttling·OOM 등 어떤 성능·안정성 문제를 확인해야 하는가?
- 과다한 Requests가 Node 수와 비용에 영향을 줄 수 있는 조건은 무엇인가?
- Autoscaling 정책·확장 속도·배치 제약에 따라 비용과 품질은 어떻게 달라질 수 있는가?

### 추천 학습 방법

Kubernetes 공식 문서에서 구성 요소와 자원 관리·배치·확장 개념을 먼저 읽습니다. 작은 로컬 환경이나 저장된 자료로 설명 가능한 부분부터 학습하며, 상시 클러스터 운영을 전제로 하지 않습니다. 애플리케이션 자원 관리 기초가 필요하면 과정 03으로 돌아갑니다.

### 관련 기술·도구·연구 방법

Kubernetes 공식 자원 관리·스케줄링 자료와 HPA·VPA·Cluster Autoscaler·Karpenter의 공식 자료를 검토 후보로 둡니다. 학습 시 각 도구의 버전·역할·적용 환경을 확인하고 워크로드 확장과 Node 용량 조정을 구분합니다.

### 선택적 작은 검증 예시

향후 가상 Node 용량과 Pod Requests 표로 배치 가능 여부와 남는 공간을 비교할 수 있습니다. 저장된 Pod 사용량·요청량 자료에서 차이를 살피되 Node 축소 가능성을 단정하지 않습니다. 실제 로컬 실행은 별도 학습에서 선택하며 이번에는 클러스터를 만들지 않습니다.

### 학습 산출물과 이해도 확인 기준

요청·제한·사용량 비교, 배치 제약과 확장 방식의 역할을 기록합니다. 평균 사용률이 낮아도 Node를 줄이지 못하는 경우와, 축소 전에 확인할 품질·배치 조건을 설명할 수 있는지 확인합니다.

### 기록 위치와 다음 과정 연결

[Platforms](platforms/README.md)에 Kubernetes 자체의 구조와 자원 관리를 기록합니다. 환경 공통의 분석은 [Methods](methods/README.md)에 연결합니다. 다음 과정에서는 이 자원 관리 구조를 EKS의 실제 과금과 비용 배분 문제에 연결합니다.

## 과정 07. EKS & Kubernetes FinOps

학습 자료 — [EKS](aws/eks/README.md) · [관측과 비용](platforms/kubernetes/observability-and-cost.md) · [비용 배분](methods/cost-allocation.md)

### 목적과 필요성

Kubernetes 자원 관리와 클라우드 과금을 연결해 클러스터 비용·자원 효율을 이해합니다. 워크로드에 배분한 비용과 실제 청구 총액의 차이, 자원 변경이 청구 비용을 줄이는 조건을 구분합니다.

### 주요 학습 주제

| 영역 | 세부 개념과 학습 범위 |
|---|---|
| EKS 비용 구조 | 클러스터 관련 비용, Worker Node·스토리지·Load Balancer·네트워크 전송·관측 비용 |
| Kubernetes 비용 배분 | Node·Pod 비용 관계, Namespace·워크로드별 비용, 공유 비용, 유휴 Node 비용, 사용량 기반·Requests 기반 배분 차이 |
| 기존 비용 분석 | AWS Split Cost Allocation Data, OpenCost 공식 자료, Kubernetes 비용 배분 방법, 배분 전제·한계 |
| 클러스터 최적화 | Pod 과다 요청, Node 용량 부족·유휴 용량, 인스턴스 선택, Bin Packing, Autoscaling, Spot·용량 계획, 성능·가용성 위험 |

### 핵심 질문

- Node 비용을 Pod·Namespace·워크로드에 배분할 때 어떤 정책과 가정이 필요한가?
- Requests가 높으면 실제 비용이 반드시 증가하는가? 언제 Node 수를 줄일 수 있는가?
- 공유·유휴 비용 배분 방식을 바꾸면 최적화 판단이 달라지는가?
- 비용 절감과 안정성을 함께 평가하려면 어떤 비용·성능·가용성 지표를 맞춰 측정해야 하는가?

### 추천 학습 방법

공식 문서와 공개·샘플 자료로 가능한 항목별 계산과 배분 비교부터 시작합니다. 배분 결과의 변화와 실제 청구 총액 감소를 별도로 검토합니다. 실제 EKS 실험이 필요한 경우 사용자 승인, 예상 비용, 실행 시간, 중단·정리 방법을 먼저 정합니다. 대규모 실험은 선택적 심화입니다.

### 관련 기술·도구·연구 방법

AWS EKS 공식 과금 문서, AWS Split Cost Allocation Data, OpenCost 공식 자료를 학습 후보로 둡니다. 버전·지원 환경·비용 정의·공유 비용 정책을 학습 시 확인하고, 배분 합계와 전체 비용 범위를 대조하는 방법을 검토합니다.

### 선택적 작은 검증 예시

향후 가상 Node 비용과 Pod의 사용량·Requests를 이용해 두 배분 정책의 차이를 계산할 수 있습니다. 배분 비용이 작아져도 Node 수·과금 조건이 그대로인 경우를 구분해 설명할 수 있습니다. 이는 계획이며 실제 EKS 실행이나 절감 성과가 아닙니다.

### 학습 산출물과 이해도 확인 기준

클러스터 비용 항목표, 배분 정책·가정, 축소 가능 조건과 품질 위험을 기록합니다. 워크로드 배분 비용·유휴 비용·실제 청구 비용을 구분하고 Node 수 감소를 판단하려면 무엇을 추가 확인해야 하는지 설명할 수 있는지 확인합니다.

### 기록 위치와 다음 과정 연결

EKS 서비스·과금은 [AWS Services](aws/README.md), Kubernetes 자원 관리는 [Platforms](platforms/README.md), 배분·최적화 방법은 [Methods](methods/README.md), 실제 검증은 [Experiments](../experiments/README.md)에 기록합니다. 다음 과정에서는 발견한 구체적 질문을 기존 연구·재현과 연결합니다.

## 과정 08. Research & Reproduction

학습 자료 — [연구 방법](methods/research-methodology.md) · [학술 논문](../references/papers.md) · [공식 데이터 예제](../references/datasets.md) · [실험 안내](../experiments/experiment-guide.md)

### 목적과 필요성

앞선 학습에서 발견한 구체적인 질문에 대해 기존 연구를 검토하고 가능한 범위에서 결과를 검증합니다. 원 저자의 주장, 자신의 해석, 직접 확인한 결과를 나누고 재현 범위와 실패·불확실성도 연구 기록으로 남깁니다.

### 주요 학습 주제

| 영역 | 세부 개념과 학습 범위 |
|---|---|
| 연구 질문 구체화 | 문제 정의, 기존 방법 한계, 비교 기준, 가설·검증 범위 |
| 논문 검토 | 공식 논문 원문, 배경·목적, 데이터 출처, 방법의 가정, 평가 방법, 저자가 제시한 결과·한계 |
| 기존 구현 검토 | 공개 코드, 입력·출력, 알고리즘, 실행 환경·의존성, 버전·라이선스 |
| 재현 실험 | 단순 기준선, 전체·축소 재현, 동일 조건 비교, 설정·난수 시드, 학습·평가 자료 분리, 시계열 데이터 누출 방지 |
| 결과 평가 | 정확도·오류, 문제에 맞는 Precision·Recall·F1 등 지표, 탐지 지연·비용 영향, 비용·성능 비교, 반복 측정·편차, 실제 결과·추정 결과 구분 |
| 한계·후속 질문 | 가설 기각, 효과 없음, 데이터 부족, 재현 실패, 환경 차이, 추가 확인 조건 |

### 핵심 질문

- 어떤 문제와 기존 방법의 한계를 검토하며, 반증 가능한 질문으로 범위를 좁혔는가?
- 논문 결과의 데이터·가정·평가 조건 중 무엇을 확인했고 무엇을 재현하지 못했는가?
- 단순 기준선과 동일한 조건으로 비교하며 데이터 누출을 피했는가?
- 평가 지표 개선이 실제 비용·품질 개선으로 이어지는지 확인할 근거가 있는가?
- 실패·효과 없음·환경 차이에서 어떤 결론까지 말할 수 있고 무엇은 보류해야 하는가?

### 추천 학습 방법

질문이 구체화되면 필요한 논문과 방법을 선택합니다. 본문 검토·코드 분석·축소 재현·비교 실험을 구분하며 모든 논문을 직접 재현할 필요는 없습니다. 실제 관측·공개·합성 자료를 구분하고 기존 성과를 자신의 실험 성과로 표현하지 않습니다.

### 관련 기술·도구·연구 방법

공식 논문 원문·공식 데이터셋과 관련 구현을 질문에 맞춰 검토합니다. 단순 기준선, 시간 순서에 맞는 평가 분리, 반복 측정, 평가 조건 비교를 필요한 범위에서 사용합니다. 외부 코드·데이터·독창적 방법 재사용 시 원 출처·버전·라이선스·수정 범위를 해당 학습·실험 문서에 기록합니다.

### 선택적 작은 검증 예시

향후 질문에 맞는 논문 한 편의 입력·가정·지표를 표로 대조하거나, 허용된 작은 자료 범위에서 단순 기준선과 방법 일부를 비교할 수 있습니다. 원문·환경·자료가 부족하면 문헌 검토에서 멈추거나 축소 재현으로 범위를 명시합니다. 이번 작업에서는 논문 요약·실험 설계·코드 실행·모델 다운로드를 수행하지 않습니다.

### 학습 산출물과 이해도 확인 기준

문제 정의, 실제 검토 범위, 비교 조건, 결과 또는 미검증 항목, 한계·후속 질문을 기록합니다. 저자의 주장과 자신의 결과를 구분하고 제3자가 재현 범위와 결론의 한계를 파악할 수 있는지 확인합니다. 실제 재현을 하지 않았다면 실행 결과를 산출물로 요구하거나 만들어내지 않습니다.

### 기록 위치와 후속 연결

개념·논문 방법은 [Studies](README.md)의 해당 주제 영역, 실제 실험·재현은 [Experiments](../experiments/README.md), 공식 원문 정보는 [References](../references/README.md)에 기록합니다. 새 질문에 필요한 앞선 과정으로 돌아가며, 연구 결과를 미래 서비스에 활용하는 일은 별도 제품 프로젝트에서 다룹니다.

## 문서 연결과 진행 기록

| 기록 내용 | 현재 탐색 입구 |
|---|---|
| Linux·네트워크·비용·성능 공통 기초 | [Foundations](foundations/README.md) |
| AWS 서비스·과금·비용 관리 기능 | [AWS Services](aws/README.md) |
| 애플리케이션·Docker·Kubernetes 자체의 실행·자원 관리 | [Platforms](platforms/README.md) |
| 관측 자료 분석·배분·예측·최적화·논문 방법 | [Methods](methods/README.md) |
| 실제 계산 검증·실행·재현 결과 | [Experiments](../experiments/README.md) |
| 공식 자료·표준·학술 원문·공식 데이터셋 정보 | [References](../references/README.md) |

사용자 학습 완료 여부는 미확인입니다. 합성 데이터를 사용한 [EBS 탐지 규칙 로컬 검증](../experiments/001-ebs-waste-rules/README.md)에 실행 결과와 한계를 기록했습니다.

첫 학습은 [기존 비용 기초](foundations/README.md)와 [Linux 자원](foundations/linux-resources.md)에서 시작합니다.

[전체 학습 목차](README.md) · [프로젝트 소개](../README.md)
