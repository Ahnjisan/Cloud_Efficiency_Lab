# Athena·Glue 비용 산정 01 — 스캔량·열 기반 형식·파티션·크롤러

[AWS 서비스 목차](../README.md)

> S3에 쌓인 센서 데이터를 분석할 때, 저장 형식과 파티션은 쿼리 비용을 얼마나 바꾸며, 테이블 정보를 관리하는 Glue 비용은 언제 의미 있게 커지는가?

커리큘럼 02. AWS Infrastructure & Pricing의 학습 노트입니다. [Firehose](../kinesis-firehose/README.md)가 S3에 쓴 데이터를 Glue Data Catalog에 등록하고 Athena SQL로 조회하는 단계를 다룹니다. 요율은 서울 리전 공개 요율입니다.

## 1. Athena 과금 단위

| 항목 | 계량 방식 | 서울 리전 요율 |
|---|---|---|
| SQL 쿼리(S3 데이터) | Athena가 **스캔한 바이트**. 메가바이트 단위로 올림하고 **쿼리당 최소 10 MB**를 과금합니다. | **5.00 USD/TB** (`APN2-DataScannedInTB`) |
| 프로비저닝 용량 | DPU 예약 시간 | 0.33 USD/DPU-시간 |
| S3 | Athena가 읽고 쓴 S3 요청·저장·전송은 S3 요금으로 별도 청구. 실패한 쿼리의 S3 요청도 포함 | S3 요율 적용 |

- 10 MB 최소 과금은 AWS Glue 요금 페이지의 Athena 설명에 "메가바이트 단위 올림, 쿼리당 10 MB 최소"로 적혀 있습니다. Athena 요금 페이지 본문에서는 같은 문장을 페더레이션 쿼리(S3 밖 데이터)에 대해서만 확인했습니다. S3 데이터 쿼리에도 같은 최소값이 적용된다고 보고 계산하되, **실제 청구에서 다시 확인할 점**으로 둡니다.
- 실패·취소된 쿼리의 스캔량 과금 여부는 이번에 확인한 요금 페이지에서 찾지 못했습니다.
- 이 저장소의 실험에서 로컬 도구로 측정하는 "읽은 바이트"는 Athena의 과금 스캔량과 같지 않습니다. 계산 범위와 최소 과금 단위의 차이를 실험 문서에 따로 적습니다.

[Amazon Athena pricing](https://aws.amazon.com/athena/pricing/) · [AWS Glue pricing — Athena 항목](https://aws.amazon.com/glue/pricing/) · [AWS Price List — AmazonAthena, ap-northeast-2](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonAthena/current/ap-northeast-2/index.json)

## 2. 스캔량을 줄이는 세 가지 방법

| 방법 | 원리 (AWS 문서) | 효과가 작아지는 조건 |
|---|---|---|
| 열 기반 형식(Parquet·ORC) | 쿼리에 필요한 열만 읽습니다. 열 단위로 데이터 형식에 맞는 압축을 적용합니다. | `SELECT *`처럼 대부분의 열을 읽는 쿼리 |
| 술어 푸시다운(블록 통계) | Parquet·ORC 블록의 최솟값·최댓값 통계로 읽지 않아도 되는 블록을 건너뜁니다. | 값이 파일마다 고르게 섞여 있음, 파일이 매우 작아 블록이 적음 |
| 파티션 | `WHERE` 절에 파티션을 지정하면 해당 파티션의 데이터만 스캔합니다. | 파티션 열로 거르지 않는 쿼리, 파티션이 너무 잘게 나뉨 |

압축만으로도 스캔량이 줄어듭니다. Athena 요금 페이지는 GZIP 압축 시 "3:1 압축 이득을 볼 수 있다"고 예시합니다. 실제 압축률은 데이터 내용에 따라 다르므로 이 값을 계산 가정으로 쓰지 않고 실험으로 측정합니다.

AWS는 파티션을 나누지 않은 버킷에 객체가 매우 많으면 S3 `GET` 요청 한도에 걸릴 수 있다고 경고합니다. Athena는 한 번에 100만 개 넘는 파티션을 읽지 못하므로, 센서 ID처럼 값이 많은 열로 잘게 나누는 설계는 피합니다. 파티션 값과 경로를 테이블 속성으로 계산하는 **파티션 프로젝션**을 쓰면 파티션 등록 작업 없이 쿼리할 수 있습니다.

[Use columnar storage formats](https://docs.aws.amazon.com/athena/latest/ug/columnar-storage.html) · [Partition your data](https://docs.aws.amazon.com/athena/latest/ug/partitions.html)

## 3. 가상 예제 — 10 MB 최소 과금의 영향

| 쿼리 | 실제 스캔 | 과금 스캔 | 쿼리 1회 요금 | 1,000회 요금 |
|---|---:|---:|---:|---:|
| 하루치 한 구역 Parquet, 2개 열 | 0.2 MB (가상) | 10 MB | 0.0000477 USD | 0.048 USD |
| 같은 하루치를 CSV로 전체 읽기 | 3 MB (가상) | 10 MB | 0.0000477 USD | 0.048 USD |
| 한 달 CSV 전체 읽기 | 250 MB (가상) | 250 MB | 0.00119 USD | 1.19 USD |

계산: `10 MB ÷ 1,048,576 MB/TB × 5 USD = 0.0000477 USD`. 데이터가 작으면 형식·파티션을 바꿔 실제 스캔을 줄여도 **10 MB 최소 과금 아래로는 비용이 내려가지 않습니다.** 형식·파티션 개선의 비용 효과는 쿼리당 스캔이 10 MB를 넘는 규모에서 나타납니다. 데이터가 작은 초기 단계에서는 쿼리 지연, S3 요청 수, 이후 데이터가 커졌을 때의 확장성을 더 중요한 판단 근거로 둡니다.

## 4. Glue 과금 단위

| 항목 | 계량 방식 | 서울 리전 요율 |
|---|---|---|
| 크롤러 | DPU-시간, 초 단위 과금 | **0.44 USD/DPU-시간** |
| Spark ETL 작업 (표준) | DPU-시간, 초 단위 과금 | 0.44 USD/DPU-시간, Glue 6.0 이상 **0.308 USD/DPU-시간** |
| Spark ETL 작업 (Flex) | 실행 중인 워커별 시간 합계 | 0.29 USD/DPU-시간, Glue 6.0 이상 0.203 USD/DPU-시간 |
| Data Catalog 저장 | 월 객체 수 | 첫 100만 개 무료, 이후 **1 USD/10만 객체-월** |
| Data Catalog 요청 | 요청 수 | 월 첫 100만 건 무료, 이후 1 USD/100만 건 |

- DPU 1개는 vCPU 4개와 메모리 16 GB입니다. G.1X 워커가 1 DPU입니다.
- 크롤러와 ETL 작업의 **최소 과금 시간은 이번에 확인한 요금 페이지·개발자 가이드에서 찾지 못했습니다.** 요금 페이지는 "초 단위 과금"만 명시하고, 1분 최소는 통계·압축·Data Quality 등 다른 작업 유형에만 적혀 있습니다. 실험에서 Glue 실행 비용을 계산할 때는 최소 과금 시간을 변수로 두고 0분·1분·10분을 모두 계산합니다.
- 요금 페이지 예제: Spark 작업이 6 DPU로 15분 실행되면 `6 × 0.25 × 0.44 = 0.66 USD`입니다. 같은 작업을 Glue 6.0 이상 요율로 계산하면 0.46 USD입니다.

[AWS Glue pricing](https://aws.amazon.com/glue/pricing/) · [Configuring job properties for Spark jobs](https://docs.aws.amazon.com/glue/latest/dg/add-job.html) · [AWS Price List — AWSGlue, ap-northeast-2](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSGlue/current/ap-northeast-2/index.json)

## 5. 센서 파이프라인에서 Glue 비용이 커지는 조건

1. **스키마가 고정인데 크롤러를 매일 돌림**: 요금 페이지 예제와 같은 2 DPU로 하루 10분씩 30일 실행하면 `2 × (10/60) × 0.44 × 30 = 4.40 USD/월`입니다. Firehose가 날짜 경로로 쓰고 스키마가 변하지 않는다면 파티션 프로젝션으로 대체할 수 있는지 검토합니다. 스키마 변경을 자동으로 감지해야 한다면 크롤러가 하는 일이 있으므로 유지 근거가 됩니다.
2. **작은 파일 합치기(compaction) ETL**: 작은 파일 문제를 해결하지만 DPU 비용이 생깁니다. 버퍼를 키워 처음부터 큰 파일을 쓰는 방법과 비교합니다.
3. **Data Catalog 객체 수**: 테이블·파티션 수가 100만 개를 넘을 때만 저장 요금이 생깁니다. 시간 단위 파티션을 몇 년 보관하면 커질 수 있습니다.

## 6. 낭비 판단에 필요한 자료

| 판단 | 필요한 자료 | 보류 조건 |
|---|---|---|
| 형식·파티션 변경 후보 | 쿼리별 스캔량(Athena 쿼리 기록의 `DataScannedInBytes`), 쿼리 빈도, 쿼리의 `WHERE` 열 | 대표 쿼리를 모름, 쿼리 수가 적어 스캔량 대부분이 10 MB 최소 과금 |
| 크롤러 축소·대체 후보 | 크롤러 실행 시간·DPU, 스키마 변경 이력 | 스키마 변경 빈도를 모름 |
| ETL 축소 후보 | 작업별 DPU-시간, 실패·재시도 횟수 | 작업의 결과를 누가 쓰는지 모름 |

## 7. 확인 문제

1. 쿼리 하나가 4 MB를 스캔하면 과금 스캔량은 얼마인가요?
2. Parquet으로 바꾸고도 비용이 줄지 않는 쿼리 유형 두 가지는 무엇인가요?
3. 크롤러를 파티션 프로젝션으로 대체하면 잃는 기능은 무엇인가요?

## 8. 확인 범위와 다음 질문

Price List에서 Athena·Glue 서울 요율을, AWS 문서에서 열 기반 형식·파티션의 원리와 Glue 과금 방식을 확인했습니다. S3 데이터 쿼리의 10 MB 최소는 Glue 요금 페이지의 문장에 근거했으며, 크롤러·ETL 최소 과금 시간은 확인하지 못했습니다. 형식·파티션별 읽은 바이트는 [실험 018](../../../experiments/018-format-partition-scan/README.md)에서 로컬로 대리 측정합니다.

> 다음 질문: 수집·저장·조회 단계를 연결하면 센서 1,000건당 비용 중 어느 단계가 가장 큰가?

## 공식 참고 자료

확인일은 **2026-11-13**입니다.

| 자료 | 확인 범위 |
|---|---|
| [Amazon Athena pricing](https://aws.amazon.com/athena/pricing/) | TB당 스캔 과금, 페더레이션 쿼리 10 MB 최소, S3 요금 별도·실패 쿼리 포함, GZIP 예시 |
| [AWS Glue pricing](https://aws.amazon.com/glue/pricing/) | 초 단위 과금, ETL 예제, Data Catalog 무료 제공량, Athena 10 MB 최소 문장 |
| [AWS Price List — AmazonAthena](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonAthena/current/ap-northeast-2/index.json) · [AWSGlue](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSGlue/current/ap-northeast-2/index.json) | 서울 요율, 게시일 2026-09-11·2026-11-08 |
| [Use columnar storage formats](https://docs.aws.amazon.com/athena/latest/ug/columnar-storage.html) | 열 압축, 술어 푸시다운 |
| [Partition your data](https://docs.aws.amazon.com/athena/latest/ug/partitions.html) | 파티션 스캔 제한, 객체 수와 GET 한도, 100만 파티션 한도, 파티션 프로젝션 |
| [Configuring job properties for Spark jobs](https://docs.aws.amazon.com/glue/latest/dg/add-job.html) | DPU 정의, 워커 유형, Flex 과금 방식 |

## 확인 문제 정답과 해설

1. 10 MB 최소가 적용되어 10 MB입니다.
2. 대부분의 열을 읽는 쿼리(`SELECT *`), 그리고 원래 스캔이 10 MB 미만이라 최소 과금에 걸리는 쿼리입니다.
3. 새로운 열이나 형식 변경을 자동으로 감지해 스키마를 갱신하는 기능입니다. 프로젝션은 미리 정한 파티션 규칙만 계산합니다.
