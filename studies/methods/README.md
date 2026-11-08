# Methods

[학습 목차](../README.md) · [최종 연구 보고서](../../FINAL-REPORT.md)

여러 AWS 서비스에 적용할 수 있는 분석·예측·최적화 방법을 공부하는 공간입니다.

## 학습 범위

- 규칙 기반 분석(Rule-based Analysis): 임계값·조건·판단 근거와 보류 조건
- 자원 적정성 판단(Rightsizing): 사용량·여유 용량·성능 위험과 추천
- 예측(Forecasting): 비용·자원 사용량과 단순 시계열 기준선
- 이상탐지(Anomaly Detection): 통계·머신러닝 방법과 오탐·탐지 지연
- 구성 최적화(Configuration Optimization): 후보·목적 함수·제약과 탐색 비용
- 비용 배분(Cost Allocation): 직접·공유·유휴 비용과 배분 정책
- 서비스 간 분석(Cross-service Analysis): 의존성과 전체 비용 영향
- 관측 자료 분석, 관련 통계·머신러닝 방법과 기존 논문·모델 비교

위 항목은 연구 영역의 예시이며 필수 구현 목록이나 확정 일정이 아닙니다.

Docker·Kubernetes의 기본 구조와 자원 관리 기능은 [Platforms](../platforms/README.md), AWS 고유의 비용 관리 기능은 [AWS Services](../aws/README.md)에서 다룹니다. 학습 순서와 세부 범위는 [전체 커리큘럼](../curriculum.md)을 참고합니다.

## 기록 원칙

각 방법을 공부할 때 필요한 범위에서 다음을 기록합니다.

- 해결하려는 문제와 입력 데이터
- 방법의 핵심 원리와 가정
- 기존 기준선과의 차이
- 평가 지표
- 적용 조건 및 한계
- 관련 학습·실험 문서

기존 논문을 읽는 것과 모델을 직접 재현하는 것을 구분하며, 기존 결과를 자신의 실험 성과처럼 표현하지 않습니다. 실제 코드 실행 및 결과는 [Experiments](../../experiments/README.md)에 기록하고 해당 실험 문서와 연결합니다.

## 방법별 문서 탐색

- [Rightsizing](rightsizing.md)
- [예측](forecasting.md)
- [이상탐지](anomaly-detection.md)
- [구성 최적화](configuration-optimization.md)
- [비용 배분](cost-allocation.md)
- [서비스 간 분석](cross-service-analysis.md)
- [연구 방법](research-methodology.md)

[전체 학습 목차와 순서](../README.md) · [AWS 서비스 학습](../aws/README.md)
