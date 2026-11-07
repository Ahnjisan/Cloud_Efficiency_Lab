# Amazon DynamoDB — 요청·프로비저닝 용량과 병목

DynamoDB의 비용은 데이터 크기와 읽기·쓰기 패턴의 영향을 받는다. [워크로드 성능](../../foundations/workload-performance.md)의 피크와 평균을 구분해 용량 모드를 선택한다.

DynamoDB는 키-값과 문서 모델을 지원하는 NoSQL 데이터베이스다. 테이블의 기본 키로 항목을 찾고, 다른 조회 경로에 GSI를 사용할 수 있다. 저장 비용은 읽기·쓰기 단위와 분리해 테이블과 인덱스를 살핀다.

## 단위와 동작

온디맨드는 읽기·쓰기 요청 단위를 사용한다. 프로비저닝은 RCU·WCU로 초당 처리 용량을 지정하며 Auto Scaling은 사용 패턴에 따라 프로비저닝 용량을 조정한다. 일반적인 강한 일관성 읽기는 최대 4 KB당 한 단위, 일반 쓰기는 최대 1 KB당 한 단위가 기준이다. 최종적 일관성 읽기와 트랜잭션은 단위가 달라진다. GSI에는 인덱스 저장 및 읽기·쓰기 비용이 생기며 인덱스 쓰기 용량 부족이 테이블 쓰기 스로틀링으로 이어질 수 있다.

## 가상 비교

1 KB 일반 쓰기 200만 건과 4 KB 강한 읽기 400만 건에 가상 $1/백만 WRU·$0.25/백만 RRU를 적용하면 요청 비용은 $3이다. 가상 월 100 RCU·50 WCU를 720시간 유지하고 단가를 각각 $0.0001·$0.0005/단위·시간으로 두면 $25.20이다. 이 예는 예산 규모 비교이며 해당 프로비저닝 값이 동일 품질을 보장하는지는 요청 분포와 핫 키, 인덱스·저장·백업 비용, 스로틀링 지표로 확인한다.

## 이해도 확인

동일한 월 쓰기 건수에서 특정 키로 트래픽이 몰리면 어떤 지표를 봐야 하는가?

## 근거와 확인 범위

- [Using Global Secondary Indexes — Provisioned throughput](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GSI.html) · 2026-11-08 확인
- [AWS · What is Amazon DynamoDB? — Data model](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Introduction.html) · 2026-11-08 확인
- [Amazon DynamoDB Pricing — On-demand 및 Provisioned capacity modes](https://aws.amazon.com/dynamodb/pricing/) · 2026-11-08 확인

이 문서의 예시는 설명용 가정이다. 실제 환경의 결과와 적용 가능성은 별도로 확인한다.
