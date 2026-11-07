# Amazon Aurora — 클러스터 저장소와 I/O 구성

[RDS 비용](../rds/README.md)의 인스턴스·저장 구분을 Aurora의 공유 클러스터 볼륨에 적용한다.

Amazon RDS는 관리형 관계형 데이터베이스 서비스이며 Aurora는 RDS에서 제공하는 데이터베이스 엔진 중 하나다. 일반 RDS 인스턴스의 구성이나 요율을 Aurora 클러스터에 그대로 적용하지 않는다. 클러스터 볼륨의 저장 복제와 읽기 인스턴스의 장애 조치 역할도 구분한다.

## 구성별 과금

Aurora DB 클러스터에서는 쓰기 인스턴스와 읽기 복제본이 클러스터 저장소를 공유한다. 복제본은 컴퓨팅과 읽기·장애 대응에 영향을 준다. Aurora Standard는 인스턴스·저장과 요청 I/O 과금이 있고 Aurora I/O-Optimized는 해당 읽기·쓰기 I/O 요청에 별도 요금을 부과하지 않는 대신 인스턴스·저장 요율이 다를 수 있다. 백업, 복원, 전송의 적용 범위는 별도 확인한다.

## 가상 비교

Standard의 인스턴스·저장이 월 $120, I/O가 $0.20/백만 요청, I/O-Optimized의 인스턴스·저장이 $160이라면 손익분기는 200백만 요청/월이다. 300백만에서는 $180 대 $160이다. 같은 인스턴스·복제본, 데이터량과 읽기·쓰기 지연 조건을 전제로 둔다. 리전·엔진·지원 구성, 백업 및 복제 요구가 다르면 다시 산정한다. CloudWatch 볼륨 I/O 지표와 비용 행이 동일 시간·클러스터를 가리키는지 확인한다.

## 이해도 확인

읽기 복제본을 추가하면 I/O만의 손익분기 비교를 왜 다시 검토해야 하는가?

## 근거와 확인 범위

- [AWS · Amazon Aurora DB clusters — Cluster volume and instances](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/Aurora.Overview.html) · 2026-11-08 확인
- [Amazon Aurora Pricing — Aurora Standard, I/O-Optimized, Backup Storage](https://aws.amazon.com/rds/aurora/pricing/) · 2026-11-08 확인

이 문서의 예시는 설명용 가정이다. 실제 환경의 결과와 적용 가능성은 별도로 확인한다.
