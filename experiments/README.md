# Experiments

학습 중 직접 확인할 필요가 생긴 내용을 검증하는 공간입니다. 작은 입력을 이용한 비용 계산 검증, 공개·저장 자료를 이용한 분석 방법 비교, 기존 논문·도구·모델의 전체 또는 축소 재현을 할 수 있습니다. AWS 실험은 필요한 경우에만 제한된 범위로 수행합니다.

## 분류 기준

실험은 AWS 서비스별이 아니라 연구 질문별로 독립적인 폴더에 묶습니다. 향후 폴더명은 `001-ec2-rightsizing`, `002-cost-anomaly-detection`처럼 정할 수 있습니다. 이는 이름의 예시이며 실제 실험 폴더가 아닙니다.

[커리큘럼](../studies/curriculum.md)의 어느 과정에서든 검증이 필요한 질문이 생기면 독립적인 실험으로 관리합니다. 자체 질문에 대한 실험과 기존 논문·모델의 재현을 구분합니다.

## 실험 기록 원칙

[실험 안내](experiment-guide.md)에서 실행 전 설계, 비용 비교와 재현 기록 기준을 확인할 수 있습니다.

각 실험의 README에서 필요한 범위에 따라 다음을 찾을 수 있도록 기록합니다.

- 질문과 가설 또는 확인 목표
- 데이터 출처와 실제·합성 여부
- 실행 환경과 의존성
- 비교 기준선과 변경 조건
- 측정 지표와 실행 방법
- 원본 결과와 집계 방법
- 결과 해석, 한계, 재현 범위

AWS·Docker·Kubernetes 실험은 사용한 환경·버전, 자원 구성·제한, 부하와 측정 조건을 기록합니다. 비용·성능 비교에서는 동일한 업무량과 품질 요구를 기준으로 삼고, 조건 차이가 있으면 함께 명시합니다. 자료가 부족하면 판단을 보류합니다.

모델 실험에는 필요한 경우 학습·튜닝·평가 자료의 구분과 난수 시드를 남깁니다. 기존 연구와 조건이 다르면 전체 재현이라고 부르지 않고 축소 재현 또는 방법을 참고한 별도 실험으로 구분합니다.

작은 실험은 README 하나와 최소한의 실행 파일만 사용해도 됩니다. `data/`, `scripts/`, `results/` 등의 하위 폴더는 실제 자료가 생길 때만 만듭니다.

AWS 자원 생성·실행은 필수가 아닙니다. AWS 등 유료 자원을 쓰는 실험은 실행 전에 대상, 예상 비용과 가정, 위험, 유지 시간, 중단 조건, 정리 방법을 검토하고 사용자 승인을 받은 범위에서만 수행합니다. 미측정, 실패, 효과가 없었던 결과도 그대로 기록합니다.

## 실험 목록

- [001 · EBS 낭비 탐지 규칙 로컬 검증](001-ebs-waste-rules/README.md) — 가상 볼륨 8건과 충돌 우선순위 2건 재현
- [002 · EBS 규칙 신규 반례 평가](002-ebs-rule-robustness/README.md) — 합성 11건과 보류의 영향
- [003 · EC2·EBS 비용 시뮬레이션](003-aws-cost-simulation/README.md) — 가상 비용 8가지 조건
- [004 · Terraform 변경 근거](004-terraform-evidence/README.md) — 합성 Plan 추출과 민감정보 처리
- [005 · Docker 워크로드 자원 효율 실측](005-container-resource-efficiency/README.md) — CPU 한도별 두 차례 반복
- [006 · Kubernetes 자원 검증](006-kubernetes-resource-efficiency/README.md) — 정적 비용 모형과 실제 Requests 배치·Limits 부하
- [007 · InfraFit 통합 가능성](007-infrafit-feasibility/README.md) — 품질·결측·중복 비용을 포함한 합성 판정
- [008 · 청구·변경·피크 관측 대사](008-evidence-reconciliation/README.md) — 지연 도착, 중복, 불일치와 재대사
- [009 · EBS 기록 최신성과 보류 검토 비용](009-ebs-review-cost/README.md) — 최신성 기준에 따른 오탐과 검토량
- [010 · CPU 한도별 품질 기준 재검증](010-cpu-quality-envelope/README.md) — 보존 로그 분석과 전용 환경 반복 절차
- [011 · 약정·피크 겹침·전환비 민감도](011-cost-quality-sensitivity/README.md) — 비용과 품질에 따른 채택 조건
- [012 · 실제 Terraform Plan JSON 호환성](012-terraform-plan-compatibility/README.md) — 내장 리소스의 모듈 주소·교체·민감도·미확정 값
- [013 · 피크 품질 악화 후 CPU 한도 롤백](013-peak-rollback/README.md) — 전용 로컬 컨테이너의 기준·축소·복원 실측
- [014 · AWS provider의 실제 EC2·EBS Plan](014-aws-provider-plan/README.md) — AWS API를 호출하지 않는 생성 계획과 필드 호환성
- [015 · Kubernetes 반복 부하와 Deployment 롤백](015-kubernetes-rollback/README.md) — 전용 Minikube에서 CPU 축소·복원 반복

[InfraFit 통합 연구 결과](infrafit-predevelopment-review.md)에 001 재실행과 전체 결과를 모았다. Docker와 Kubernetes 후속 실측의 결과 및 한계를 포함한다.

실제 실행한 실험만 문서의 상대 링크와 함께 이 목록에 등록합니다. 관련 [Studies](../studies/README.md) 학습 문서와 실험 문서를 상호 연결해 학습 근거와 재현 경로를 찾을 수 있도록 합니다.
