# Amazon ECS·AWS Fargate — 실행 방식과 태스크 비용

[AWS 서비스 목차](../README.md)

ECS는 태스크를 배치·운영한다. ECS on EC2는 인스턴스 풀을 운영하고 Fargate는 태스크가 요청한 자원 기준으로 실행 용량을 사용한다.

## 과금 대상과 확장

태스크 정의에는 이미지, CPU·메모리, 네트워크, 로그 설정 등을 기록한다. Fargate 비용의 핵심은 요청 vCPU·메모리와 과금 시간이며 추가 임시 저장 공간도 조건에 따라 포함한다. AWS 문서는 이미지 다운로드 시작부터 태스크 종료까지를 초 단위로 올림해 과금하며, 최소 과금 시간은 Linux 1분, Windows 5분이다. 서비스 확장 정책으로 태스크 수를 바꿀 때 시작·건강 확인·요청 처리 지연을 함께 본다. EC2 방식은 노드의 실행 시간과 배치 밀도, 유휴 공간이 비용을 좌우한다.

ECS 서비스는 원하는 수의 태스크 복제본을 유지하고, 필요에 따라 일회성 태스크도 실행할 수 있다. CPU·메모리를 과하게 지정하면 Fargate에서 실제 사용률이 낮아도 태스크 비용이 유지된다. EC2에서는 동일한 설정이 노드당 배치 가능 수를 줄일 수 있다.

## 가상 비교

1 vCPU·2 GB 태스크가 합계 200 태스크·시간 과금된다면 가상 $0.04/vCPU·시간과 $0.005/GB·시간에서 200×(0.04+2×0.005)=$10이다. 같은 요청·가용성을 만족하는 EC2 노드가 합계 200대·시간×$0.06이라면 컴퓨팅만 $12다. EC2 가용 용량으로 같은 동시 피크와 장애 조건을 감당할 수 있는지 확인하지 않으면 이 차이를 적용할 수 없다. EBS·로드 밸런서·전송·로그·운영 부담을 양쪽 동일 기준으로 넣는다.

## 이해도 확인

태스크 수를 줄여도 EC2 노드 비용이 그대로 남을 수 있는 이유는 무엇인가?

## 근거와 확인 범위

- [What is Amazon Elastic Container Service? — Terminology and components](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/Welcome.html) · 2026-11-08 확인
- [AWS Fargate Pricing — Duration, vCPU and Memory](https://aws.amazon.com/fargate/pricing/) · 2026-11-08 확인

이 문서의 예시는 설명용 가정이다. 실제 환경의 결과와 적용 가능성은 별도로 확인한다.

## 추가(2026-11-15) — 허용 조합 올림, 과금 시작·종료, EKS Fargate vs ECS Fargate

> Pod에 1 vCPU·8 GB를 요청했는데 왜 2 vCPU 요금이 나오는가?

**과금 단위.** Fargate는 vCPU·메모리·임시 저장(20 GB 초과분)을 초 단위로 과금합니다. 서울 x86: vCPU 0.04656, GB 0.00511 USD/시간, ARM: vCPU 0.03725, GB 0.00409([2026-11-15 사본](../../../references/aws-price-list-apn2-2026-11-15.json)). **과금은 컨테이너 이미지 다운로드를 시작한 순간부터 ECS 태스크나 EKS Pod가 끝날 때까지**이고, 초 단위로 올림하며 Linux는 **최소 1분**(Windows 5분)입니다.

**허용 조합 올림.** 요청은 다음 조합 중 맞는 가장 작은 것으로 올라갑니다.

| vCPU | 메모리 |
|---:|---|
| 0.25 | 0.5, 1, 2 GB |
| 0.5 | 1~4 GB |
| 1 | 2~8 GB |
| 2 | 4~16 GB (1 GB 단위) |
| 4 | 8~30 GB (1 GB 단위) |
| 8 | 16~60 GB (4 GB 단위) |
| 16 | 32~120 GB (8 GB 단위) |
| 32 (ECS만) | 60, 120, 244 GB |

**EKS Fargate는 Pod 메모리에 256 MB를 더한 뒤** 올립니다(Kubernetes 구성 요소 몫).

**가상 예시.**

| 요청 | ECS Fargate 프로비저닝 | EKS Fargate 프로비저닝 | 시간당(ECS → EKS) |
|---|---|---|---|
| 1 vCPU · 8 GB | 1 vCPU · 8 GB | 8.25 GB → **2 vCPU · 9 GB** | 0.08744 → 0.13911 USD (+59%) |
| 0.25 vCPU · 0.5 GB | 0.25 · 0.5 GB | 0.75 GB → 0.25 · 1 GB | 0.01420 → 0.01675 USD (+18%) |

EKS Fargate에서는 메모리를 조합 경계에 딱 맞춰 요청하면 256 MB 때문에 한 단계 올라갑니다. 경계보다 256 MB 이상 작게 요청하면 됩니다. 또 EKS는 클러스터 요금(0.10 USD/시간)이 따로 붙습니다. 실행이 1분보다 짧은 작업은 최소 1분이 과금되므로 짧은 작업을 많이 띄우는 구조는 **최소 과금**에 걸립니다.

**낭비 판단 자료.** 요청한 vCPU·메모리와 실제 프로비저닝된 크기(EKS는 Pod 주석 `CapacityProvisioned`), 작업 실행 시간 분포, 이미지 다운로드 시간.

**확인 문제.** EKS Fargate에서 2 vCPU · 15.9 GB를 요청하면? **해설.** 15.9 + 0.25 = 16.15 GB > 16 GB이므로 4 vCPU · 17 GB로 올라갑니다.

| 공식 자료 (확인일 2026-11-15) | 확인 범위 |
|---|---|
| [AWS Fargate pricing](https://aws.amazon.com/fargate/pricing/) | 과금 시작(이미지 다운로드 시작)·종료, 초 단위 올림, Linux 최소 1분·Windows 5분 |
| [Fargate Pod configuration (EKS)](https://docs.aws.amazon.com/eks/latest/userguide/fargate-pod-configuration.html) | 허용 조합, 256 MB 추가, 올림 예시 |
| [Amazon ECS task CPU and memory](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/fargate-tasks-services.html) | ECS 허용 조합(32 vCPU 포함) |
| [Price List — AmazonECS](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonECS/current/ap-northeast-2/index.json) | 서울 Fargate 요율, 게시일 2026-11-11 |
