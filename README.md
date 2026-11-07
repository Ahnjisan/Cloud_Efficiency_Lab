# Cloud Efficiency Lab

> 같은 서비스를 운영해도 자원 구성과 실행 환경에 따라 비용과 성능은 어떻게 달라질까?

클라우드 비용 구조, 자원 사용, 워크로드, 성능·안정성의 관계를 학습하고 검증하는 독립적인 개인 스터디·연구 저장소입니다. AWS에서 비용이 발생하는 원리와 자원 구성·실제 사용량의 차이를 살펴보고, 낭비와 과다 할당의 판단 근거를 공부합니다. Linux·Docker·Kubernetes 등 실행 환경까지 범위를 넓히며, 공식 자료·논문·기존 최적화 방법을 검토하고 필요한 계산·재현·실험으로 확인합니다.

## 장기 연구 방향

1. AWS 비용은 어디에서 불필요하게 발생하며, 어떤 근거로 낭비를 판단할 수 있는가?
2. 현재 워크로드를 더 적은 클라우드 자원으로 운영하면서 필요한 서비스 품질을 유지하고, 실제 비용을 줄일 수 있는가?

장기적으로 연구 결과를 비용 낭비 탐지와 자원 최적화 서비스의 기반으로 활용할 계획입니다. 이 저장소는 학습·연구를 위한 공간이며, 향후 제품 개발은 별도 프로젝트로 구분합니다. 특정 기능 구현이나 제품 개발을 학습 완료 조건으로 삼지 않습니다.

## 학습·연구 방식

개념·공식 자료 학습 → 기존 기술·방법·논문 검토 → 필요한 계산·재현·실험 → 결과와 한계 정리 → 새로운 질문으로 확장합니다. 주제에 따라 읽기와 비교, 계산만으로 마무리할 수도 있으며, 모든 주제에 모델 개발이나 AWS 실험을 요구하지 않습니다.

## 학습 커리큘럼

[전체 커리큘럼](studies/curriculum.md)에서 세부 주제와 이해도 확인 기준, 유연한 학습 순서를 관리합니다. 아래 과정은 학습 계획입니다.

| 과정 | 학습 범위 |
|---|---|
| 01. Infrastructure & FinOps Foundations | Linux·네트워크·성능과 비용 비교의 공통 기초 |
| 02. AWS Infrastructure & Pricing | AWS 서비스의 자원 구조와 과금·낭비 판단 |
| 03. Application & Container Efficiency | 애플리케이션·Docker 이미지·컨테이너 자원 효율 |
| 04. Observability & Cost Data | 관측 지표와 비용 데이터의 연결 및 해석 한계 |
| 05. Optimization Methods | 규칙·Rightsizing·예측·이상탐지·배분·최적화 방법 |
| 06. Kubernetes Resource Management | Requests·Limits·배치·Autoscaling과 자원 사용 |
| 07. EKS & Kubernetes FinOps | EKS 과금과 클러스터 비용 배분·자원 효율 |
| 08. Research & Reproduction | 연구 질문 구체화와 기존 연구 검토·재현·평가 |

## 저장소 탐색

| 영역 | 역할 |
|---|---|
| [studies](studies/README.md) | 전체 학습 목차와 현재 문서 탐색 |
| [curriculum](studies/curriculum.md) | 8개 과정의 상세 학습 계획과 권장 순서 |
| [foundations](studies/foundations/README.md) | 기존 비용·자원 효율 기초 문서; Linux·네트워크 등 공통 기초의 기록 영역 |
| [aws](studies/aws/README.md) | AWS 서비스별 자원·과금·성능과 비용 관리 기능 |
| [platforms](studies/platforms/README.md) | 애플리케이션·Docker·Kubernetes 실행 환경 |
| [methods](studies/methods/README.md) | 여러 환경에 적용할 분석·예측·최적화 방법 |
| [experiments](experiments/README.md) | 계산 검증, 모델·방법 재현, 소규모 실험 |
| [references](references/README.md) | 공식 기술 문서, 표준, 논문, 공식 데이터셋 |

## 기록·운영 원칙

- 출처의 주장, 자신의 해석, 직접 확인한 결과를 구분합니다.
- 실제 관측 자료, 공개 자료, 합성 자료를 구분합니다.
- 예상 비용·절감액과 실제 관측 결과를 구분합니다.
- 판단에 필요한 자료가 부족하면 판단을 보류하고 그 한계를 남깁니다.
- 결과와 적용 조건, 확인하지 못한 한계를 함께 기록합니다.
- Issue·PR 없이 README와 주제별 문서에 진행 상태와 결론을 기록합니다.
- 중요한 결론이 바뀌면 해당 본문을 정정하고 변경 이유를 함께 남깁니다.

## 현재 진행 상태

[클라우드 비용과 자원 효율의 기초](studies/foundations/README.md)와 [AWS 서비스별 학습 자료](studies/aws/README.md)가 작성돼 있습니다. Platforms·Methods에는 안내 문서가 있으며, 등록된 실험은 없습니다. 자료 작성, 사용자 학습 완료, 실제 환경 검증·실험은 별도로 기록합니다. 다음 학습 대상으로 기존 Foundations 내용 확인과 필요한 보완을 제안하며, 학습 완료 여부는 사용자의 확인에 따라 기록합니다.
