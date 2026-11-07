# AWS Services

## 학습 목적

AWS 서비스별 과금 구조와 실제 자원 사용의 관계를 이해하고 비용 낭비의 발생 조건, 판단 근거, 기존 해결 방법을 공부합니다.

비용·자원·성능을 함께 살피며 서비스별 공식 과금 문서를 우선합니다. 실제 가격 계산에는 리전, 가격 기준·확인일, 기간과 포함 비용을 명시합니다.

## 학습 범위와 영역 구분

EC2·EBS·S3·RDS 및 Aurora·Lambda·VPC와 네트워크 비용을 핵심 학습 후보로 둡니다. AWS 비용 데이터와 비용 관리 기능도 이 영역에서 다룹니다. ECS·Fargate·ECR·EKS 등은 연구 질문에 따라 확장하며 AWS 고유의 서비스 구성과 과금을 기록합니다.

Docker·Kubernetes 자체의 구조와 자원 관리는 [Platforms](../platforms/README.md), 여러 환경에서 재사용할 분석·예측·비용 배분·최적화 방법은 [Methods](../methods/README.md)에서 다룹니다. 세부 계획은 [전체 커리큘럼](../curriculum.md)을 참고합니다.

## 서비스별 학습 내용

학습할 때 다음 관점을 필요한 범위에서 참고합니다. 모든 학습 노트에 동일한 목차를 강제하지 않습니다.

1. 서비스의 역할과 작동 원리
2. 과금 구조와 비용 산정 기준
3. 설정·사용량·성능의 관계
4. 낭비 발생 원인
5. 기존 해결 방법과 적용 조건
6. 판단에 필요한 자료와 확인하지 못한 부분
7. 관련 공식 자료·논문·연구 질문

## 서비스별 문서 탐색

- [EC2 비용 산정 01 — 인스턴스 실행 상태와 컴퓨팅 비용](ec2/README.md): 중지 후 남는 비용, 상태별 컴퓨팅 과금과 가상 계산 예제
- [EBS 비용 산정 01 — 볼륨 유형·용량·IOPS·Throughput](ebs/README.md)에서 gp2·gp3의 과금 구조와 전환 조건을 비교합니다.
- [A-03. EBS 스냅샷 비용 산정 — 증분 저장·삭제·보존](ebs/snapshots.md)
- [S3 비용 산정 01 — Storage Class와 요청·조회·전송 비용](s3/README.md)
- [S3 비용 산정 02 — Lifecycle과 Intelligent-Tiering 비교](s3/lifecycle-intelligent-tiering.md)
- [RDS 비용 산정 01 — DB 인스턴스·스토리지·Multi-AZ](rds/README.md)
- [RDS 비용 산정 02 — Rightsizing과 성능·가용성의 균형](rds/rightsizing.md)
- [Lambda 비용 산정 01 — 메모리·실행시간·요청 비용](lambda/README.md)
- [Lambda 비용 산정 02 — 콜드 스타트와 Provisioned Concurrency](lambda/cold-start-concurrency.md)
- [VPC 비용 산정 01 — NAT Gateway·VPC Endpoint·데이터 전송](vpc/README.md)
- [VPC 비용 산정 02 — 중앙 NAT와 AZ별 NAT의 손익분기점](vpc/nat-gateway-break-even.md)

문서 작성은 사용자의 학습 완료를 뜻하지 않습니다. 새로운 서비스 학습을 시작할 때 해당 폴더를 만들고, 실제 작성한 문서의 상대 링크를 이 목차에 추가합니다.

[전체 학습 목차와 순서](../README.md) · [공통 기초](../foundations/README.md) · [분석 방법론](../methods/README.md)
