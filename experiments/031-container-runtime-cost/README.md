# 031 — 컨테이너 실행 방식별 비용: 요청을 줄이면 청구가 주는가

[실험 목차](../README.md) · [EKS 노트](../../studies/aws/eks/README.md#추가2026-11-15--표준연장-지원-클러스터-요금-maxpods-시스템-pod-몫) · [ECS·Fargate 노트](../../studies/aws/ecs-fargate/README.md) · [006 Kubernetes 자원 효율](../006-kubernetes-resource-efficiency/README.md)

**재현 PASS. H0 기각, H1·H2 기각, H3·H4 지지.** 같은 웹 서비스(복제 20개)를 EKS+EC2, EKS+Fargate, ECS Fargate, Lambda로 운영할 때, 컨테이너의 CPU·메모리 요청을 단계적으로 줄이면 월 비용이 어떻게 변하는지 계산했다.

## 실행 전 결정

| 항목 | 내용 |
|---|---|
| 질문 | "Requests 감소 → 비용 감소"는 어떤 실행 방식에서 성립하는가? 프롬프트의 가정은 "Fargate형에서만 성립"이다. |
| 가설 H0 | Fargate형은 요청을 줄이면 비용이 줄고, EKS+EC2는 단계의 절반 미만에서만 줄며, Lambda는 줄지 않는다(세 조건 모두 성립해야 지지). |
| 가설 H1 | Fargate형은 요청을 줄이는 모든 단계에서 비용이 준다. |
| 가설 H2 | EKS+EC2는 단계의 절반 미만에서만 비용이 바뀐다. |
| 가설 H3 | Lambda 비용은 컨테이너 요청과 무관하다. |
| 가설 H4 | 작은 Pod가 많으면 EKS+EC2 노드 수는 Pod 슬롯(maxPods)이 정하고, 요청을 줄여도 비용이 줄지 않는다. |
| 단계 | CPU: 1 → 0.5 → 0.4 → 0.25 → 0.2 → 0.1 → 0.05 vCPU(메모리 0.5 GB 고정). 메모리: 2 → 1.5 → 1 → 0.75 → 0.5 → 0.25 GB(CPU 0.25 고정). 작은 Pod: 복제 60개, 0.05 → 0.02 vCPU(메모리 0.1 GB) |
| EKS+EC2 | m7g.large(2 vCPU, 8 GiB, maxPods 29), 첫 적합(first-fit) 배치. **가정(미확인)**: 예약 CPU 0.07·메모리 0.658 GiB(255 Mi + 11 Mi × maxPods + 축출 100 Mi), 노드마다 DaemonSet 3개(합계 0.15 vCPU·0.2 GiB), CoreDNS 2개(각 0.1 vCPU·0.07 GiB) |
| Fargate | [service_pack.py](../scenarios/service_pack.py) 허용 조합, EKS는 +256 MB. EKS Fargate는 CoreDNS 2개도 Fargate Pod |
| Lambda | 같은 트래픽(월 300만 요청 × 120 ms), 1,024 MB. 비교용 기준선 |
| 요율 | [2026-11-15 사본](../../references/aws-price-list-apn2-2026-11-15.json): EKS 0.10/시간, m7g.large 0.1003/시간, Fargate 0.04656/vCPU-시간·0.00511/GB-시간 |

## 실행

```powershell
cd experiments/031-container-runtime-cost
py -3 -B evaluate.py > result.json
py -3 -B test_evaluate.py
```

## 결과

**CPU 요청을 줄일 때 (메모리 0.5 GB, 복제 20개, 월 USD)**

| CPU 요청 | EKS+EC2 (노드 수, 병목) | EKS+Fargate (프로비저닝) | ECS Fargate (프로비저닝) | Lambda |
|---:|---:|---:|---:|---:|
| 1 | 1,537.38 (20, CPU) | 922.71 (1 vCPU·2 GB) | 828.99 (1·2) | 6.60 |
| 0.5 | 585.53 (7, CPU) | 508.22 (0.5·1) | 414.49 (0.5·1) | 6.60 |
| 0.4 | **512.31** (6, CPU) | 508.22 (0.5·1) **변화 없음** | 414.49 **변화 없음** | 6.60 |
| 0.25 | 292.66 (3, CPU) | 338.27 (0.25·1) | 207.25 (0.25·0.5) | 6.60 |
| 0.2 | 292.66 **변화 없음** | 338.27 **변화 없음** | 207.25 **변화 없음** | 6.60 |
| 0.1 | **219.44** (2, CPU) | 338.27 **변화 없음** | 207.25 **변화 없음** | 6.60 |
| 0.05 | 219.44 (2, 메모리) | 338.27 | 207.25 | 6.60 |
| 비용이 준 단계 | **4 / 6** | 2 / 6 | 2 / 6 | 0 / 6 |

**메모리 요청을 줄일 때 (CPU 0.25)**: 비용이 준 단계는 EKS+EC2 2/5, EKS+Fargate 3/5, ECS Fargate 2/5, Lambda 0/5.

**작은 Pod 60개 (0.05 → 0.02 vCPU, 0.1 GB)**: 네 방식 모두 비용 변화 0. EKS+EC2는 노드 3대(슬롯 26개/노드가 병목, CPU로는 1~2대면 충분), Fargate는 최소 조합(0.25 vCPU·0.5 GB, EKS는 0.25·0.5)에 이미 닿아 있었다.

- **H0 기각**: Fargate형만 반응하는 것이 아니었다. EKS+EC2는 노드 수가 바뀌는 단계마다 비용이 줄었고(CPU 4/6), Fargate는 **허용 조합 경계를 넘을 때만** 줄었다(2/6). 두 방식 모두 연속적이지 않고 계단식이다.
- **H1 기각**: 0.5 → 0.4, 0.25 → 0.2 → 0.1 → 0.05 vCPU에서 Fargate 비용은 그대로였다. 0.4 vCPU 요청은 0.5 vCPU로, 0.25 미만은 0.25로 올라간다.
- **H2 기각**: 이 설정(노드 크기 대비 큰 Pod)에서는 EKS+EC2가 오히려 더 자주 반응했다. Pod가 노드에 비해 클수록 노드 수가 요청에 민감하다.
- **H3 지지**: Lambda는 요청 개념이 없어 변화가 없다. 비용은 실행 시간 × 메모리 설정 × 호출 수로 정해진다.
- **H4 지지**: 작은 Pod가 많으면 슬롯이 노드 수를 정해 CPU 요청 감소가 비용으로 이어지지 않았다.
- EKS+Fargate는 같은 요청에서 ECS Fargate보다 항상 비쌌다(클러스터 73 USD + 256 MB 추가로 인한 조합 상승 + CoreDNS Pod). 0.25 vCPU · 0.5 GB에서 338.27 대 207.25 USD.

## 해석

- "요청을 줄이면 비용이 준다"는 규칙은 실행 방식마다 **다른 계단 함수**다. 판정에 필요한 것: EKS+EC2는 노드 수 변화(CPU·메모리·슬롯 중 병목), Fargate는 허용 조합 경계(EKS는 +256 MB 포함), Lambda는 메모리 설정과 실행 시간.
- 권고 금액을 "요청 감소량 × 단가"로 계산하면 대부분의 단계에서 틀린다. InfraFit은 요청 변경 후의 **프로비저닝 결과(노드 수 또는 Fargate 조합)를 다시 계산**해 금액을 내야 하고, 다음 계단에 닿지 않으면 "절감 0"으로 보고해야 한다.
- 이 결과는 [006](../006-kubernetes-resource-efficiency/README.md)·[015](../015-kubernetes-rollback/README.md)의 "요청을 낮춰도 노드가 그대로면 청구는 그대로"를 실행 방식 비교로 넓힌 것이다.

## 가정·제외·한계

- EKS AMI의 예약량 식, DaemonSet·CoreDNS 요청은 이번에 공식 문서로 확인하지 않은 가정이다. 값이 바뀌면 노드 수 경계가 이동한다.
- 첫 적합 배치는 스케줄러의 실제 점수 방식과 다르다. 하한(자원 합 ÷ 할당 가능량)도 결과에 함께 남겼다.
- Savings Plans·Spot, 오토스케일링 지연, 노드 교체 비용은 넣지 않았다. Lambda 수치는 트래픽 가정에 크게 좌우되므로 컨테이너 비용과 절대값을 비교하는 용도가 아니다.

## 테스트

`test_evaluate.py` 5개: 1 vCPU Pod 1개/노드 배치와 CPU 하한, 작은 Pod 슬롯 병목(26 슬롯, 3노드), Lambda 일정, Fargate 0.5 → 0.4 정체, `result.json` 재현.
