# 공식 기술·과금 문서

확인일은 2026-11-08이다. 요금 페이지는 과금 항목과 단위의 근거로 사용했다. 실제 견적에는 서비스별 리전·OS·모드·무료 범위와 할인 조건을 다시 대조한다. 문서별 상세 인용은 [학습 목차](../studies/README.md)에서 따라갈 수 있다.

| AWS 원문 | 확인 범위 |
|---|---|
| [EC2 On-Demand Pricing](https://aws.amazon.com/ec2/pricing/on-demand/) · [Amazon EBS Pricing](https://aws.amazon.com/ebs/pricing/) | 컴퓨팅 시간과 볼륨·스냅샷 |
| [Amazon S3 Pricing](https://aws.amazon.com/s3/pricing/) · [Amazon RDS Pricing](https://aws.amazon.com/rds/pricing/) · [AWS Lambda Pricing](https://aws.amazon.com/lambda/pricing/) | 저장·요청·전송, DB 엔진별 가격 경로, 실행·요청 |
| [Amazon VPC Pricing](https://aws.amazon.com/vpc/pricing/) · [Elastic Load Balancing pricing](https://aws.amazon.com/elasticloadbalancing/pricing/) | NAT, ALB·NLB 용량 단위 |
| [Amazon CloudWatch Pricing](https://aws.amazon.com/cloudwatch/pricing/) · [Amazon ECR Pricing](https://aws.amazon.com/ecr/pricing/) · [AWS Fargate Pricing](https://aws.amazon.com/fargate/pricing/) | 관측·레지스트리 저장과 전송·태스크 시간 |
| [Amazon DynamoDB Pricing](https://aws.amazon.com/dynamodb/pricing/) · [Amazon Aurora Pricing](https://aws.amazon.com/rds/aurora/pricing/) · [Amazon EKS Pricing](https://aws.amazon.com/eks/pricing/) | 용량 모드, 클러스터 I/O 구성, EKS 관련 비용 |
| [AWS Data Exports](https://docs.aws.amazon.com/cur/latest/userguide/what-is-data-exports.html) · [AWS Compute Optimizer](https://docs.aws.amazon.com/compute-optimizer/latest/ug/what-is-compute-optimizer.html) | 내보내기 유형과 추천 기능 |

Docker는 구조, multi-stage 빌드, CPU·메모리 제한을 확인했다. Kubernetes는 구성요소, 자원 요청·제한, 오토스케일링 역할을 확인했다. 배포 시에는 사용하는 버전의 문서와 기능 상태를 적용한다.

## 데이터 파이프라인·생성형 AI·ML 학습 (2026-11-13 확인)

서울 리전(ap-northeast-2) 요율은 [AWS Price List Bulk API](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/index.json)의 리전별 오퍼 파일에서 확인했다. 사용한 요율만 추린 사본은 [aws-price-list-apn2-2026-11-13.json](aws-price-list-apn2-2026-11-13.json)에 오퍼별 게시일과 함께 저장했다. 무료 제공량·할인·세금은 포함하지 않는다.

| AWS 원문 | 확인 범위 |
|---|---|
| [AWS IoT Core pricing](https://aws.amazon.com/iot-core/pricing/) · [Basic Ingest](https://docs.aws.amazon.com/iot/latest/developerguide/iot-basic-ingest.html) | 5 KB 메시지 계량, 1분 연결 계량, 규칙·액션 계량, 메시지 요금 없는 예약 토픽 |
| [Amazon Data Firehose pricing](https://aws.amazon.com/firehose/pricing/) · [BufferingHints](https://docs.aws.amazon.com/firehose/latest/APIReference/API_BufferingHints.html) · [Record format conversion](https://docs.aws.amazon.com/firehose/latest/dev/record-format-conversion.html) | 레코드당 5 KB 올림, 형식 변환·동적 파티셔닝, 버퍼 범위·기본값 |
| [Amazon Athena pricing](https://aws.amazon.com/athena/pricing/) · [Columnar storage](https://docs.aws.amazon.com/athena/latest/ug/columnar-storage.html) · [Partitions](https://docs.aws.amazon.com/athena/latest/ug/partitions.html) | TB당 스캔 과금, 열 기반 형식·술어 푸시다운, 파티션 |
| [AWS Glue pricing](https://aws.amazon.com/glue/pricing/) · [Spark job properties](https://docs.aws.amazon.com/glue/latest/dg/add-job.html) | DPU-시간 초 단위 과금, Data Catalog 무료 제공량, Athena 10 MB 최소 문장, 워커 DPU |
| [Amazon Bedrock pricing](https://aws.amazon.com/bedrock/pricing/) · [Prompt caching](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html) · [Cross-Region inference](https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html) · [How Agents works](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-how.html) | 토큰·캐시 과금, 캐시 최소 토큰·TTL, Global·Geographic 처리 위치, 에이전트 오케스트레이션 |
| [Amazon SageMaker AI pricing](https://aws.amazon.com/sagemaker/ai/pricing/) | 노트북·학습·엔드포인트·서버리스·배치 변환 과금 방식 |
| [AWS Cost Anomaly Detection](https://docs.aws.amazon.com/cost-management/latest/userguide/manage-ad.html) | 실행 빈도, 데이터 지연, 신규 서비스 이력 요건 |

## InfraFit 확장 범위 — 누수 패턴·컨테이너·LLM 비용 (2026-11-15 확인)

서울 리전 요율은 같은 Price List Bulk API의 오퍼 18개(오퍼별 게시일 2026-09-11 ~ 2026-11-14)에서 다시 추출해 [aws-price-list-apn2-2026-11-15.json](aws-price-list-apn2-2026-11-15.json)에 저장했다. 추출 조건은 오퍼마다 `selection`에, 찾지 못한 요율 5건은 `missing`에 있다. 추출 스크립트는 [extract-price-snapshot.py](extract-price-snapshot.py)다.

| AWS 원문 | 확인 범위 | 미확인으로 남긴 것 |
|---|---|---|
| [Amazon OpenSearch Service pricing](https://aws.amazon.com/opensearch-service/pricing/) · [Serverless capacity](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless-scaling.html) · [Multi-AZ with Standby](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/managedomains-multiaz.html) | Classic 최소 2 OCU(개발·테스트 0.5 + 0.5), NextGen 10분 비활성 후 0, OCU = 6 GiB, 벡터 컬렉션 OCU 비공유, 관리형 도메인 중지 불가, Standby 추가 요금 없음 | NextGen OCU 요율이 Classic과 같은지 |
| [Amazon ElastiCache pricing](https://aws.amazon.com/elasticache/pricing/) | 서버리스 최소 저장량(Valkey 100 MB, Redis OSS·Memcached 1 GB), 1 KB당 1 ECPU, 노드 부분 시간 1시간 과금 | ECPU 소수 KB 올림, 명령별 추가 ECPU |
| [Amazon API Gateway pricing](https://aws.amazon.com/api-gateway/pricing/) | HTTP·REST 요청 구간, WebSocket 32 KB 계량·ping/pong 제외·연결 분, 스트리밍 응답 추가 요금 없음 | HTTP API 512 KB 단위(예시에만 있음) |
| [Amazon Bedrock pricing](https://aws.amazon.com/bedrock/pricing/) · [Prompt caching](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html) · [Runtime metrics](https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-runtime-metrics.html) | Guardrails 텍스트 단위 1,000자·입출력 각각 계산, 체크포인트당 최소 토큰(Haiku 4.5 = 4,096, Claude 5.5 계열 = 512), Converse `inputTokens`는 캐시 제외·Responses `input_tokens`는 포함, `Invocations` 범위와 ModelId 차원 | KB 관리형 인덱스 저장(원본 GB당 월 5 USD, 페이지 일부만 확인), CloudWatch `InputTokenCount`의 캐시 포함 여부 |
| [Using Lambda with Amazon SQS](https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html) · [AWS Lambda pricing](https://aws.amazon.com/lambda/pricing/) | 배치당 1회 호출, 기본 최대 10건, 배치 창 최대 5분, 프로비저닝 모드 폴러 | — |
| [Stopping an RDS DB instance temporarily](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_StopInstance.html) | 최대 7일 중지 후 자동 시작, 중지 중 과금 항목, 중지 불가 조건 | — |
| [Gateway endpoints](https://docs.aws.amazon.com/vpc/latest/privatelink/gateway-endpoints.html) · [AWS PrivateLink pricing](https://aws.amazon.com/privatelink/pricing/) · [Amazon VPC pricing](https://aws.amazon.com/vpc/pricing/) | 게이트웨이 엔드포인트 추가 요금 없음, 인터페이스 엔드포인트 AZ별 시간 과금·부분 시간 올림·리전 합산 GB 구간, NAT 시간·GB·부분 시간 올림 | — |
| [Amazon EKS pricing](https://aws.amazon.com/eks/pricing/) · [Maximum Pods per node](https://docs.aws.amazon.com/eks/latest/userguide/choosing-instance-type.html) · [Fargate Pod configuration](https://docs.aws.amazon.com/eks/latest/userguide/fargate-pod-configuration.html) · [EC2 general purpose network specifications](https://docs.aws.amazon.com/ec2/latest/instancetypes/gp.html) | 표준 0.10·연장 지원 0.60 USD/시간, maxPods 식과 관리형 노드 그룹 상한, Fargate 허용 조합·+256 MB, m5·m7g·m7i.large ENI 3·IP 10 | EKS AMI 예약 CPU·메모리 식(031에서 가정으로 사용) |
| [AWS Fargate pricing](https://aws.amazon.com/fargate/pricing/) · [ECS task CPU and memory](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/fargate-tasks-services.html) | 이미지 다운로드 시작부터 과금, 초 단위 올림, Linux 최소 1분·Windows 5분, ECS 32 vCPU 조합 | — |
| [Amazon ECR pricing](https://aws.amazon.com/ecr/pricing/) · [Lifecycle policies](https://docs.aws.amazon.com/AmazonECR/latest/userguide/LifecyclePolicies.html) | 저장·아카이브 요금, 수명 주기 만료 기준 | 저장소 안 공통 레이어 중복 제거 |
| [AWS Glue pricing](https://aws.amazon.com/glue/pricing/) · [Python shell jobs](https://docs.aws.amazon.com/glue/latest/dg/add-job-python.html) | 초 단위 과금, Python Shell 최대 용량 0.0625·1 DPU, Data Quality 2 DPU·1분 최소 | Python Shell 요율·최소 과금 시간, Spark 작업 최소 과금 시간 |
| [Amazon CloudWatch pricing](https://aws.amazon.com/cloudwatch/pricing/) | 차원 조합마다 별도 지표, 시간 비례 과금, EMF 세 가지 과금, 로그 기본 보관 무기한 | 로그 저장의 압축 후 크기 과금 여부 |

## 이해도 확인

같은 이름의 비용 지표라도 가격표와 비용 내보내기의 시간 단위가 다르면 어떻게 대조하는가?

## 근거와 확인 범위

- [Amazon ECS — Terminology and components](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/Welcome.html) · 2026-11-08 확인
- [AWS Billing and Cost Management — Billing and payments, Cost organization](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/billing-what-is.html) · 2026-11-08 확인
- [AWS Cost Explorer — Cost analysis](https://docs.aws.amazon.com/cost-management/latest/userguide/ce-what-is.html) · 2026-11-08 확인
- [Docker overview — Architecture](https://docs.docker.com/get-started/docker-overview/) · 2026-11-08 확인
- [Docker Multi-stage builds](https://docs.docker.com/build/building/multi-stage/) · 2026-11-08 확인
- [Docker Resource constraints](https://docs.docker.com/engine/containers/resource_constraints/) · 2026-11-08 확인
- [Kubernetes Components](https://kubernetes.io/docs/concepts/overview/components/) · 2026-11-08 확인
- [Resource Management for Pods and Containers](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/) · 2026-11-08 확인
- [Kubernetes Autoscaling](https://kubernetes.io/docs/concepts/workloads/autoscaling/) · 2026-11-08 확인

이 문서의 예시는 설명용 가정이다. 실제 환경의 결과와 적용 가능성은 별도로 확인한다.
