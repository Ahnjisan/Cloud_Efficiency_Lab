# Platforms

AWS 서비스에 종속되지 않는 애플리케이션·컨테이너·오케스트레이션 실행 환경의 원리와 자원 효율을 공부하는 영역입니다. 세부 학습 계획은 [전체 커리큘럼](../curriculum.md)에서 관리합니다.

## Container & Application Efficiency

- Docker와 Container Runtime, 이미지와 컨테이너의 실행 구조
- 이미지 최적화(Image Optimization), Layer·Build Cache·Multi-stage Build
- CPU·메모리 관리, 제한·Throttling·OOM
- JVM·애플리케이션의 자원 사용과 시작·실행 성능
- 일반 프로세스와 컨테이너 등 실행 환경 비교

이미지 크기와 런타임 자원 사용을 구분해 학습하고, 비용 효과는 실제 과금 대상과 연결해 검토합니다.

## Kubernetes Resource Efficiency

- Kubernetes Architecture와 워크로드 구성
- Requests·Limits와 실제 사용량
- Scheduling과 배치 제약·자원 효율
- Autoscaling과 확장 속도·서비스 품질
- Pod·Node Metrics와 워크로드 단위 자원 사용 분석

## 기록 방식과 문서 탐색

현재는 영역 안내 문서만 있으며 실제 Docker·Kubernetes 학습 문서는 없습니다. 실제 학습을 시작할 때 필요한 하위 폴더나 문서를 추가하고 이 README에 상대 링크를 등록합니다. 챕터별 빈 폴더는 미리 만들지 않습니다.

학습 기록에는 질문, 확인한 공식 자료와 버전, 구성·자원 설정, 해석과 확인하지 못한 조건을 필요한 만큼 남깁니다. 실제 실행·측정 결과는 [Experiments](../../experiments/README.md)에 별도로 기록하고 연결합니다. 로컬 자료 검토만으로 가능한 학습도 있으며 상시 클러스터 운영을 요구하지 않습니다.

EKS·ECS 등 AWS 관리형 서비스의 구성·과금은 [AWS Services](../aws/README.md), 환경 공통의 분석·예측·최적화·비용 배분은 [Methods](../methods/README.md)에서 다룹니다.

[전체 학습 목차](../README.md) · [공통 기초](../foundations/README.md)
