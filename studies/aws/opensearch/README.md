# Amazon OpenSearch Service 비용 산정 01 — Serverless OCU 최소치와 관리형 도메인 상시 요금

[AWS 서비스 목차](../README.md) · [누수 패턴 방법 노트](../../methods/cost-leak-patterns.md)

> 검색·벡터 저장소를 거의 쓰지 않는 개발 환경에서도 월 수백 USD가 나오는 이유는 무엇이고, 어떤 배포 방식을 고르면 쓰지 않는 시간의 비용을 줄일 수 있는가?

요율은 **AWS Price List 서울 리전(ap-northeast-2) 온디맨드 공개 요율**([2026-11-15 사본](../../../references/aws-price-list-apn2-2026-11-15.json), AmazonES 게시일 2026-11-12)이고, 작업량은 가상 값입니다. 한 달은 730시간으로 계산합니다.

## 1. 과금 단위

| 배포 방식 | 과금 항목 | 계량 방식 | 서울 요율 |
|---|---|---|---|
| Serverless (Classic 컬렉션) | 색인·검색 OCU | 컬렉션 그룹 단위, 초 단위 정밀도의 OCU-시간. **최소 2 OCU로 과금**. 개발·테스트 구성은 색인 0.5 + 검색 0.5 OCU | 색인 0.293, 검색 0.293 USD/OCU-시간 |
| Serverless (NextGen 컬렉션) | 색인·검색 OCU | 최소 OCU 없음. **10분간 요청이 없으면 0으로 줄어듦** | 오퍼에서 Classic과 구분되지 않음 → 같은 행을 쓴다고 가정(**미확인**) |
| Serverless 공통 | 관리형 저장 | 저장된 데이터 GB-월 | 0.026 USD/GB-월 |
| Serverless 공통 | 수집 파이프라인 OCU | OCU-시간 | 0.266 USD/OCU-시간 |
| 관리형 도메인 | 인스턴스 | 가용 상태인 인스턴스 시간. **중지 기능 없음, 과금을 멈추려면 도메인 삭제** | t3.small 0.056, m7g.large 0.166 USD/시간 |
| 관리형 도메인 | EBS gp3 | 프로비저닝한 GB-월 | 0.1391 USD/GB-월 |

- OCU 1개는 메모리 6 GiB와 그에 맞는 CPU·저장 캐시입니다.
- 컬렉션 그룹의 최소 OCU는 0으로 둘 수 있습니다. 단, **벡터 검색 컬렉션은 검색·시계열 컬렉션과 OCU를 공유하지 않으므로** 벡터 컬렉션을 하나 더 만들면 별도 OCU가 붙습니다.
- 관리형 도메인의 Multi-AZ with Standby는 추가 요금이 없지만, 대기 노드 인스턴스 자체는 과금됩니다.

## 2. 가상 예제 — 하루 2시간 쓰는 개발용 검색

개발 팀이 근무일에 하루 약 2시간(월 60시간) 색인·검색을 하고 데이터는 10 GB라고 가정합니다.

| 구성 | 계산 | 월 비용 |
|---|---|---:|
| Classic 컬렉션(최소 2 OCU 상시) | 2 × 0.293 × 730 | **427.78 USD** |
| Classic 개발·테스트 구성(0.5 + 0.5 OCU) | 1 × 0.293 × 730 | 213.89 USD |
| NextGen 컬렉션(사용 시간만 2 OCU, 요율 동일 가정) | 2 × 0.293 × 60 + 10 × 0.026 | 35.42 USD |
| 관리형 도메인 t3.small 1대 + gp3 10 GB | 0.056 × 730 + 10 × 0.1391 | 42.27 USD |
| 관리형 도메인 m7g.large 2대 + gp3 20 GB씩 | 2 × 0.166 × 730 + 40 × 0.1391 | 247.92 USD |

- Classic 컬렉션은 쓰지 않는 670시간에도 최소 OCU가 과금됩니다. 비용의 86%(670/730)가 유휴 시간 몫입니다.
- NextGen의 실제 비용은 "10분 비활성 후 0" 규칙 때문에 사용 구간마다 최대 10분이 더해집니다. 하루 사용 구간이 여러 번 끊기면 그만큼 늘어납니다.
- 관리형 도메인은 중지가 없으므로 개발용이라도 상시 비용입니다. 일정 기반 중지로 줄일 수 없고, 삭제·재생성(스냅샷 복원) 절차가 필요합니다.

## 3. 낭비가 생기는 조건과 판단 근거

1. **유휴 Classic 컬렉션**: 검색 요청이 거의 없는데 최소 OCU를 계속 내는 경우입니다. 판단에는 컬렉션 종류(Classic/NextGen), 컬렉션 그룹 구성, 시간대별 OCU 사용량(CloudWatch `IndexingOCU`·`SearchOCU`)이 필요합니다.
2. **벡터 컬렉션을 따로 만듦**: OCU 공유가 안 되므로 바닥 비용이 하나 더 생깁니다. 같은 그룹에 넣을 수 있는 컬렉션인지 확인합니다.
3. **개발용 관리형 도메인 상시 운영**: 인스턴스 수·유형과 사용 시간대를 확인합니다. 데이터를 다시 색인하는 비용과 시간이 삭제·재생성의 대가입니다.
4. 성능 요구(지연 p95, 동시 질의 수)를 모르면 OCU 축소나 인스턴스 축소는 **판단 보류**입니다.

## 4. 확인 문제

1. Classic 컬렉션 하나를 만들고 한 번도 쓰지 않으면 한 달에 얼마가 나오나요?
2. 검색 컬렉션 1개와 벡터 컬렉션 1개를 Classic으로 만들면 최소 OCU는 어떻게 되나요?
3. 관리형 도메인을 주말 동안 멈춰 비용을 줄일 수 있나요?

## 5. 확인 범위와 다음 질문

OCU 최소치·초 단위 정밀도·컬렉션 그룹·벡터 공유 제한, NextGen의 0 축소, 관리형 도메인의 중지 불가는 공식 문서에서 확인했습니다. NextGen OCU 요율이 Classic과 같은지는 오퍼에서 구분되지 않아 **미확인**이며 `missing` 목록에 있습니다. 실제 OCU 자동 확장 패턴과 질의 지연은 측정하지 않았습니다.

> 다음 질문: Bedrock Knowledge Base의 벡터 저장소로 OpenSearch Serverless를 쓸 때 최소 비용은 챗봇 전체 비용에서 몇 %인가? → [실험 030](../../../experiments/030-hidden-minimum-charges/README.md)

## 공식 참고 자료

확인일은 **2026-11-15**입니다.

| 자료 | 확인 범위 |
|---|---|
| [Amazon OpenSearch Service pricing](https://aws.amazon.com/opensearch-service/pricing/) | Serverless OCU 과금, 최소 2 OCU, 개발·테스트 0.5 OCU, 관리형 저장, 인스턴스 시간 과금 |
| [Managing capacity limits for Amazon OpenSearch Serverless](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless-scaling.html) | OCU 정의(6 GiB), 컬렉션 그룹 최소 OCU 0, 벡터 컬렉션 OCU 비공유, NextGen 10분 비활성 축소 |
| [Multi-AZ with Standby](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/managedomains-multiaz.html) | 추가 요금 없음 |
| [AWS Price List — AmazonES ap-northeast-2](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonES/current/ap-northeast-2/index.json) | 서울 요율, 게시일 2026-11-12 |

## 확인 문제 정답과 해설

1. 최소 2 OCU × 0.293 × 730 = 427.78 USD입니다. 개발·테스트 구성이면 213.89 USD입니다. 저장 데이터가 없으면 저장 요금은 0입니다.
2. 벡터 컬렉션은 OCU를 공유하지 못하므로 검색용과 벡터용 최소치가 각각 붙습니다. 정확한 그룹별 최소치는 구성에 따라 다르므로 콘솔의 용량 설정을 확인해야 합니다.
3. 없습니다. 관리형 도메인에는 중지 기능이 없어 삭제해야 과금이 멈춥니다. 대신 스냅샷에서 복원하는 시간과 재색인 부담을 계산에 넣어야 합니다.
