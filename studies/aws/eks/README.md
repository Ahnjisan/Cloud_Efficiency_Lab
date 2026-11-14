# Amazon EKS — 클러스터 비용과 Pod 배분

[AWS 서비스 목차](../README.md) · [로컬 Kubernetes 실험](../../../experiments/015-kubernetes-rollback/README.md)

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

## 추가(2026-11-15) — 표준·연장 지원 클러스터 요금, maxPods, 시스템 Pod 몫

> EKS에서 Pod의 CPU 요청을 줄였는데 노드 수가 줄지 않는 경우는 언제인가?

**과금 단위**(서울, [2026-11-15 사본](../../../references/aws-price-list-apn2-2026-11-15.json), AmazonEKS 게시일 2026-11-11, EC2 게시일 2026-11-14):

| 항목 | 요율 | 월(730시간) |
|---|---:|---:|
| 클러스터 — 표준 지원 버전 | 0.10 USD/시간 | 73.00 USD |
| 클러스터 — 연장 지원 버전 | 0.60 USD/시간 (표준 0.10 + 연장 0.50) | 438.00 USD |
| 노드 m7g.large (EC2 Linux 온디맨드) | 0.1003 USD/시간 | 73.22 USD/대 |

버전 업그레이드를 미루면 클러스터 요금이 6배가 됩니다. 노드 수와 무관한 **상시 고정비**입니다.

**maxPods.** VPC CNI 기본 설정에서 노드당 Pod 수 상한은 `ENI 수 × (ENI당 IP − 1) + 2`입니다. 관리형 노드 그룹은 vCPU 30 미만이면 110, 이상이면 250이 추가 상한입니다. EKS Auto Mode는 `min(110, ENI × (IP − 1))`입니다. m7g.large는 ENI 3개, ENI당 IP 10개라 **29개**입니다.

**가상 예시 — 슬롯이 먼저 찬다.** m7g.large(2 vCPU) 2대, 노드마다 DaemonSet Pod 3개(네트워크·프록시·에이전트, 가정), 클러스터 전체 CoreDNS 2개(가정). 시스템 Pod가 슬롯 58개 중 8개를 쓰므로 앱 Pod는 50개까지입니다. 앱 Pod가 0.05 vCPU씩 요청하면 CPU로는 70개 넘게 들어가지만 **슬롯이 먼저 바닥나** 51번째 Pod부터 세 번째 노드가 필요합니다(노드 비용 146.44 → 219.66 USD/월). 이때 요청을 0.05에서 0.03 vCPU로 줄여도 노드 수는 그대로입니다. "요청 감소 → 비용 감소"는 CPU·메모리가 병목일 때만 성립하며, [실험 031](../../../experiments/031-container-runtime-cost/README.md)에서 실행 방식별로 비교합니다.

**낭비 판단 자료.** 클러스터 Kubernetes 버전과 지원 단계, 노드별 Pod 수와 maxPods, 시스템 Pod 수, 노드별 요청 합계 대 할당 가능량. 접두사 위임(prefix delegation) 사용 여부에 따라 maxPods가 달라지므로 CNI 설정을 모르면 **판단 보류**입니다.

**확인 문제.** ENI 4개, ENI당 IP 15개인 노드의 maxPods는? **해설.** 4 × 14 + 2 = 58입니다(관리형 노드 그룹 상한 110보다 작으므로 58).

| 공식 자료 (확인일 2026-11-15) | 확인 범위 |
|---|---|
| [Amazon EKS pricing](https://aws.amazon.com/eks/pricing/) | 표준 0.10, 연장 지원 합계 0.60 USD/시간 |
| [Amazon EKS — maximum Pods per node](https://docs.aws.amazon.com/eks/latest/userguide/choosing-instance-type.html) | maxPods 식, 관리형 노드 그룹 상한 110/250, Auto Mode 식 |
| [Amazon EC2 instance types — general purpose network specifications](https://docs.aws.amazon.com/ec2/latest/instancetypes/gp.html) | m5.large·m7g.large·m7i.large ENI 3개, IP 10개 |
