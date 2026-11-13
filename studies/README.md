# Studies

[프로젝트 README](../README.md) · [최종 연구 보고서](../FINAL-REPORT.md)

개념을 학습하고 기존 지식과 방법을 검토하는 공간입니다. 이 문서는 실제 문서의 목차와 탐색을 담당하며, 상세 학습 계획과 순서는 [전체 8개 과정 커리큘럼](curriculum.md)에서 관리합니다.

## 학습 영역

### [Foundations](foundations/README.md)

Linux·운영체제·네트워크, 클라우드 비용과 FinOps, 자원 할당·사용량·성능 비교의 공통 기초를 기록하는 영역입니다.

### [AWS Services](aws/README.md)

AWS 서비스별 작동 원리, 과금 항목과 비용 산정, 자원 구성과 실제 사용량, 낭비 발생 원인, 기존 최적화 방법과 적용 조건을 공부합니다. 필요한 공식 자료와 관련 연구도 함께 기록합니다.

### [Platforms](platforms/README.md)

애플리케이션·Docker·컨테이너의 실행과 자원 효율, Kubernetes 구조·Requests·Limits·Scheduling·Autoscaling을 다룹니다. AWS 고유의 ECS·EKS 서비스 및 과금은 AWS Services에서 구분해 기록합니다.

### [Methods](methods/README.md)

여러 환경에 재사용할 규칙 기반 분석, Rightsizing, 비용·사용량 예측, 이상탐지, 구성 최적화, 비용 배분, 서비스 간 분석과 논문·모델 비교를 다룹니다. 필수 구현 목록이나 확정 일정이 아닙니다.

## 현재 문서와 다음 학습 대상

현재 작성된 학습 본문은 다음과 같습니다.

- [클라우드 비용과 자원 효율의 기초](foundations/README.md)
- [EC2 비용 산정 01 — 인스턴스 실행 상태와 컴퓨팅 비용](aws/ec2/README.md)
- [EBS 비용 산정 01 — 볼륨 유형·용량·IOPS·Throughput](aws/ebs/README.md)
- [A-03. EBS 스냅샷 비용 산정 — 증분 저장·삭제·보존](aws/ebs/snapshots.md)
- [S3 비용 산정 01 — Storage Class와 요청·조회·전송 비용](aws/s3/README.md)
- [S3 비용 산정 02 — Lifecycle과 Intelligent-Tiering 비교](aws/s3/lifecycle-intelligent-tiering.md)
- [RDS 비용 산정 01 — DB 인스턴스·스토리지·Multi-AZ](aws/rds/README.md)
- [RDS 비용 산정 02 — Rightsizing과 성능·가용성의 균형](aws/rds/rightsizing.md)
- [Lambda 비용 산정 01 — 메모리·실행시간·요청 비용](aws/lambda/README.md)
- [Lambda 비용 산정 02 — 콜드 스타트와 Provisioned Concurrency](aws/lambda/cold-start-concurrency.md)
- [VPC 비용 산정 01 — NAT Gateway·VPC Endpoint·데이터 전송](aws/vpc/README.md)
- [VPC 비용 산정 02 — 중앙 NAT와 AZ별 NAT의 손익분기점](aws/vpc/nat-gateway-break-even.md)

### 기초

- [Linux 자원](foundations/linux-resources.md)
- [네트워크와 데이터 흐름](foundations/network-and-data-flow.md)
- [워크로드 성능](foundations/workload-performance.md)
- [FinOps 비용 지표](foundations/finops-cost-metrics.md)

### AWS 확장

- [EC2 Rightsizing·Auto Scaling](aws/ec2/rightsizing-and-autoscaling.md)
- [ELB](aws/elb/README.md)
- [CloudWatch](aws/cloudwatch/README.md)
- [ECR](aws/ecr/README.md)
- [ECS·Fargate](aws/ecs-fargate/README.md)
- [DynamoDB](aws/dynamodb/README.md)
- [Aurora](aws/aurora/README.md)
- [EKS](aws/eks/README.md)
- [AWS 비용 데이터](aws/cost-data/README.md)

### AWS 확장 — 데이터 파이프라인·생성형 AI·ML 학습 (서울 리전 공개 요율, 2026-11-13 확인)

- [IoT Core 비용 산정 01 — 메시지 계량·연결 시간·Rules Engine](aws/iot-core/README.md)
- [Kinesis Data Firehose 비용 산정 01 — 수집량 올림·버퍼·형식 변환](aws/kinesis-firehose/README.md)
- [Athena·Glue 비용 산정 01 — 스캔량·열 기반 형식·파티션·크롤러](aws/athena-glue/README.md)
- [Bedrock 비용 산정 01 — 토큰 과금·프롬프트 캐싱·에이전트 호출 증폭](aws/bedrock/README.md)
- [SageMaker 비용 산정 01 — 학습·노트북·엔드포인트와 유휴 비용](aws/sagemaker/README.md)

### Docker

- [Docker 구조](platforms/docker/README.md)
- [이미지 최적화](platforms/docker/image-optimization.md)
- [자원 제한](platforms/docker/resource-constraints.md)

### Kubernetes

- [Kubernetes 구조](platforms/kubernetes/README.md)
- [자원 관리](platforms/kubernetes/resource-management.md)
- [배치와 확장](platforms/kubernetes/scheduling-and-autoscaling.md)
- [관측과 비용](platforms/kubernetes/observability-and-cost.md)

### 방법론

- [Rightsizing](methods/rightsizing.md)
- [예측](methods/forecasting.md)
- [이상탐지](methods/anomaly-detection.md) — 일별 비용 급증 탐지 절 포함
- [구성 최적화](methods/configuration-optimization.md)
- [비용 배분](methods/cost-allocation.md)
- [서비스 간 분석](methods/cross-service-analysis.md)
- [연구 방법](methods/research-methodology.md)
- [EC2·EBS 가상 연구 사례 — 청구 행에서 축소와 롤백 판단까지](methods/ec2-ebs-case-study.md)
- [EC2·EBS 가상 데이터 — 낭비 탐지 규칙 평가](methods/ec2-ebs-waste-detection-evaluation.md)
- [ADR 001 — 주문 조회 서비스의 EC2 용량 선택](methods/ec2-capacity-decision.md)
- [EBS 낭비 권고 — 팀 검토와 사후 확인 흐름](methods/ebs-waste-review-workflow.md)

### 참고 자료

- [공식 기술 문서](../references/official-docs.md)
- [표준·프레임워크](../references/standards.md)
- [학술 논문](../references/papers.md)
- [공식 데이터 예제](../references/datasets.md)

### 실험 설계

- [실험 안내](../experiments/experiment-guide.md)

사용자 학습 완료 여부는 미확인입니다. 가상 볼륨으로 실행한 [EBS 탐지 규칙 로컬 검증](../experiments/001-ebs-waste-rules/README.md)이 있습니다. 첫 학습에서는 기존 비용 기초와 Linux 자원을 읽고 과금 대상과 관측 사용률을 구분해 봅니다.

[커리큘럼의 권장 순서](curriculum.md#권장-학습-흐름)에 따라 연구 질문과 학습 진도에 맞춰 순서를 조정합니다. 모든 주제에 실험이나 모델 학습을 요구하지 않습니다.

기록은 날짜나 주차보다 주제를 중심으로 묶고, 디렉터리 이름에 chapter-01·chapter-02나 주차 번호를 붙이지 않습니다. 논문과 코드는 관련 주제에서 함께 검토하고, 내용이 커질 때만 별도 파일로 나눕니다.

## 학습 기록

학습 노트에는 필요한 만큼 다음을 남깁니다.

1. 공부하게 된 질문
2. 읽은 자료와 확인한 범위
3. 핵심 개념·계산·기존 방법
4. 원문의 주장과 자신의 해석
5. 직접 확인한 내용
6. 현재 결론과 남은 질문

실험을 수행하면 해당 [experiments](../experiments/README.md) 문서로 연결하고, 같은 결과를 여러 문서에 중복해서 작성하지 않습니다.
