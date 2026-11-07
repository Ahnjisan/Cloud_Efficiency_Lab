# Amazon EKS — 클러스터 비용과 Pod 배분

EKS는 Kubernetes 제어면을 제공한다. [Kubernetes 자원 관리](../../platforms/kubernetes/resource-management.md)에서 요청을 낮추는 결정과 청구 절감이 연결되는 조건을 살펴본다.

## 전체 비용의 범위

클러스터 요금은 Kubernetes 버전 지원 단계 등 조건에 따른다. Worker EC2 또는 Fargate, EBS·EFS, 로드 밸런서, NAT·전송, 관측과 기타 사용 기능을 분리해 기록한다. 장애 대응·배치 제약으로 필요한 빈 공간과 실제 제거할 수 있는 유휴 노드를 구분한다.

## 가상 배분

한 달에 제어면 $70, 노드 $240, 저장·LB·전송·관측 $90이면 $400이다. 두 팀에 노드의 $180을 2:1로 배분하고 노드 유휴 $60을 별도 표시하면 팀 비용 $120·$60, 유휴 $60, 그 외 $160이다. 팀 A 요청을 낮춰 배분액이 내려가도 노드가 그대로면 $400은 변하지 않는다.

AWS Split Cost Allocation Data는 지원 환경에서 노드 컴퓨팅 비용을 컨테이너 수준으로 나눌 근거를 제공한다. vCPU·메모리의 `SplitUsage`는 예약량과 실제 사용량 중 큰 값이다. [Kubernetes 관측과 비용](../../platforms/kubernetes/observability-and-cost.md#가상-배분)에서 OpenCost의 자원 할당 비용 기준과 비교한다. 기존 노드 행에 분할 행을 더해 합계를 중복 계산하지 않는다. OpenCost는 구성한 가격과 배분 정책에 따른 관점을 제공하며 실제 청구 범위는 [AWS 비용 데이터](../cost-data/README.md)로 대사한다.

## 이해도 확인

Pod 요청을 줄인 뒤 청구 감소를 판단하려면 노드 수 외에 어떤 항목을 확인하는가?

## 근거와 확인 범위

- [Amazon EKS Pricing — Cluster pricing 및 관련 비용](https://aws.amazon.com/eks/pricing/) · 2026-11-08 확인
- [AWS Data Exports · Understanding split cost allocation data](https://docs.aws.amazon.com/cur/latest/userguide/split-cost-allocation-data.html) · 2026-11-08 확인
- [AWS Data Exports — Split line item details](https://docs.aws.amazon.com/cur/latest/userguide/split-line-item-columns.html)

이 문서의 예시는 설명용 가정이다. 실제 환경의 결과와 적용 가능성은 별도로 확인한다.
