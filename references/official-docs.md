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
