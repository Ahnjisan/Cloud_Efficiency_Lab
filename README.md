# Cloud Efficiency Lab

> 같은 서비스를 운영해도 자원 구성과 실행 환경에 따라 비용과 성능은 어떻게 달라질까?

클라우드 비용 구조, 자원 사용, 워크로드, 성능·안정성의 관계를 학습하고 검증하는 독립적인 개인 스터디·연구 저장소입니다. AWS에서 비용이 발생하는 원리와 자원 구성·실제 사용량의 차이를 살펴보고, 낭비와 과다 할당의 판단 근거를 공부합니다. Linux·Docker·Kubernetes 등 실행 환경까지 범위를 넓히며, 공식 자료·논문·기존 최적화 방법을 검토하고 필요한 계산·재현·실험으로 확인합니다.

## 장기 연구 방향

1. AWS 비용은 어디에서 불필요하게 발생하며, 어떤 근거로 낭비를 판단할 수 있는가?
2. 현재 워크로드를 더 적은 클라우드 자원으로 운영하면서 필요한 서비스 품질을 유지하고, 실제 비용을 줄일 수 있는가?

이 저장소에는 학습 자료, 실험 001~015, 연구 결과를 적용한 읽기 전용 InfraFit MVP가 있습니다. 현재 연구 범위의 결과와 실제 청구 자료가 필요한 다음 단계는 [최종 연구 보고서](FINAL-REPORT.md)에 정리했습니다.

## 학습·연구 방식

개념·공식 자료 학습 → 기존 기술·방법·논문 검토 → 필요한 계산·재현·실험 → 결과와 한계 정리 → 새로운 질문으로 확장합니다. 주제에 따라 읽기와 비교, 계산만으로 마무리할 수도 있으며, 모든 주제에 모델 개발이나 AWS 실험을 요구하지 않습니다.

## 대표 연구 사례

1. [연구 질문과 가상 데이터](studies/methods/ec2-ebs-case-study.md)에서 청구 행을 자원과 연결하고, 어떤 구성을 축소·유지·보류할지 비교합니다.
2. [낭비 탐지 로컬 검증](experiments/001-ebs-waste-rules/README.md)에서 가상 볼륨 8개를 재현했습니다. 소유자·복구 기록을 확인하는 규칙은 오탐을 1건에서 0건으로 줄였고 미탐은 1건으로 유지됐습니다. 충돌 입력 2개는 별도로 보류 우선순위를 확인했습니다.
3. [EC2 용량 결정 기록](studies/methods/ec2-capacity-decision.md)에서 현행 유지·사양 축소·피크 확장을 비교하고, 약정 적용 시간과 전환 비용에 따라 선택이 바뀌는 조건을 검산했습니다.
4. [EBS 팀 검토 흐름](studies/methods/ebs-waste-review-workflow.md)에서 경보와 보류를 담당자, 변경 승인, 사후 품질·청구 확인에 연결합니다.

합성 데이터의 판정은 Python으로 실행해 확인했고, 비용 차이는 가상 요율과 약정 조건으로 계산했습니다. 실제 청구 절감, 운영 성능, 팀 검토 시간은 미측정입니다.

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
| [InfraFit MVP](infrafit/README.md) | 기존 합성 실험 입력을 연결하는 읽기 전용 CLI와 종단 간 테스트 |
| [최종 연구 보고서](FINAL-REPORT.md) | 001~015 실험과 MVP의 검증 결과 및 실제 청구 대사 계획 |
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

8개 과정의 기초·AWS·플랫폼·방법론 자료를 [학습 목차](studies/README.md)에 연결했습니다. [참고 자료](references/README.md)에 출처별 확인 범위를, [실험 목록](experiments/README.md)에 실행 기록을 정리했습니다. 첫 학습은 [기존 비용 기초](studies/foundations/README.md)와 [Linux 자원](studies/foundations/linux-resources.md)에서 시작할 수 있습니다.
