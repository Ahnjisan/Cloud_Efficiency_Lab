# Kinesis Data Firehose 비용 산정 01 — 수집량 올림·버퍼·형식 변환

[AWS 서비스 목차](../README.md)

> Firehose 요금은 데이터 양에 비례한다고 알려져 있다. 그렇다면 레코드 크기와 버퍼 설정은 비용과 S3 객체 수, 데이터 신선도를 어떻게 바꾸는가?

커리큘럼 02. AWS Infrastructure & Pricing의 학습 노트입니다. [IoT Core](../iot-core/README.md)에서 받은 센서 메시지를 S3에 쌓는 단계를 다룹니다. 서비스 이름은 현재 **Amazon Data Firehose**이며 Price List의 오퍼 코드는 `AmazonKinesisFirehose`입니다. 요율은 서울 리전 공개 요율이고 작업량은 가상 값입니다.

## 1. 과금 단위

| 항목 | 계량 방식 | 서울 리전 요율 |
|---|---|---|
| 수집(Direct PUT·Kinesis Data Streams 소스) | **레코드마다 5 KB 단위로 올림**한 GB. 3 KB 레코드는 5 KB, 12 KB 레코드는 15 KB로 계산됩니다. | 월 500 TB까지 **0.036 USD/GB**, 다음 1.5 PB 0.031 USD, 그 이상 0.025 USD (`APN2-BilledBytes`) |
| 형식 변환(JSON → Parquet·ORC) | 수집 GB와 같은 5 KB 올림 기준 | **0.022 USD/GB** (`APN2-DFCBilledBytes`) |
| 동적 파티셔닝 | 처리 GB + S3로 전달한 객체 수 + (선택) JQ 처리 시간 | 0.027 USD/GB, 0.0066 USD/1,000 객체, 0.092 USD/JQ 시간 |
| VPC 전달 | 대상이 VPC 안일 때만 | 0.01 USD/GB, 0.013 USD/AZ·시간 |

- Price List에는 `APN2-DirectPUT-no-rounding-BilledBytes`(0.0993 USD/GB)라는 별도 항목도 있습니다. 어떤 조건에서 이 항목이 적용되는지는 요금 페이지에서 확인하지 못했습니다. 이 문서와 실험은 요금 페이지가 설명하는 5 KB 올림 요율을 기준으로 하고, 이 항목은 **실제 청구에서 확인할 점**으로 남깁니다.
- 요금 페이지의 계산 예제는 1 GB를 1,024 × 1,024 KB로 환산합니다(3 KB 레코드 초당 100건 → 월 1,235.96 GB). 요금 페이지 예제의 단가(0.029·0.018 USD/GB)는 서울 요율과 다르므로 서울 계산에는 쓰지 않습니다.
- S3에 쓰는 객체마다 S3 PUT 요청 요금과 저장 요금이 따로 붙습니다. 서울 S3 Standard: PUT·COPY·POST·LIST **0.0045 USD/1,000건**, GET **0.0035 USD/10,000건**, 저장 첫 50 TB **0.025 USD/GB-월**.

[Amazon Data Firehose pricing](https://aws.amazon.com/firehose/pricing/) · [AWS Price List — AmazonKinesisFirehose, ap-northeast-2](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonKinesisFirehose/current/ap-northeast-2/index.json) · [AWS Price List — AmazonS3, ap-northeast-2](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonS3/current/ap-northeast-2/index.json)

## 2. 레코드 크기와 5 KB 올림

IoT Core 예제와 같은 작업량(센서 100대, 10초마다 200 B, 30일)을 가정합니다. 실제 원본 데이터는 `25,920,000 × 200 B ≈ 4.83 GB`입니다.

| IoT → Firehose 레코드 | 월 레코드 수 | 과금 GB (5 KB 올림) | 수집 요금 | 형식 변환 요금 |
|---|---:|---:|---:|---:|
| 측정값 1건 = 레코드 1건 (200 B) | 25,920,000 | 123.60 GB | **4.45 USD** | 2.72 USD |
| 측정값 20건 = 레코드 1건 (약 4,000 B) | 1,296,000 | 6.18 GB | **0.22 USD** | 0.14 USD |

200 B 레코드는 원본의 약 25배(5 KB ÷ 200 B)로 과금됩니다. **작은 레코드가 많으면 수집 요금이 원본 데이터 양과 거의 무관해집니다.** IoT Core 규칙이 메시지 1건을 Firehose 레코드 1건으로 넘긴다면, 디바이스 측 묶음이 IoT와 Firehose 두 단계의 계량을 함께 줄입니다. IoT 규칙의 Firehose 액션이 여러 메시지를 한 레코드로 합치는지, 각 메시지를 별도 레코드로 보내는지는 액션 설정에 따라 확인해야 합니다.

## 3. 버퍼 설정과 S3 객체 수

Firehose는 버퍼 크기 또는 버퍼 시간 중 먼저 도달한 조건에서 S3로 전달합니다. API 기준 버퍼 크기는 **1~128 MiB(기본 5 MiB)**, 버퍼 시간은 **0~900초(기본 300초)**입니다. 두 값은 "힌트"이며 Firehose가 다른 값을 쓸 수 있습니다. AWS는 버퍼 크기를 평소 10초 동안 들어오는 양보다 크게 잡도록 권장합니다.

같은 작업량의 유입 속도는 초당 2,000 B(300초에 약 0.57 MiB)이므로, 이 예제에서는 버퍼 크기 5 MiB에 도달하기 전에 **버퍼 시간이 항상 먼저 만료**됩니다.

| 버퍼 시간 | 월 객체 수 (전달 스트림 1개, 파티션 없음) | 평균 객체 크기(압축 전) | S3 PUT 요금 | 수집 후 S3에 나타나기까지 최대 대기 |
|---:|---:|---:|---:|---:|
| 60초 | 43,200 | 약 117 KB | 0.19 USD | 약 60초 |
| 300초 | 8,640 | 약 586 KB | 0.04 USD | 약 300초 |
| 900초 | 2,880 | 약 1.76 MB | 0.01 USD | 약 900초 |

이 작업량에서 PUT 요금 차이는 월 1 USD 미만입니다. 작은 파일의 실제 비용은 **조회 단계**에서 나타납니다. 쿼리 한 번이 읽어야 할 객체가 많을수록 GET·LIST 요청과 파일 열기 오버헤드가 늘고, Parquet처럼 열 통계를 쓰는 형식은 파일이 작으면 건너뛸 수 있는 블록이 적어집니다. 동적 파티셔닝을 켜면 파티션 값마다 버퍼가 따로 생기므로 객체 수가 파티션 수만큼 늘고 객체당 요금(0.0066 USD/1,000)도 붙습니다.

버퍼 시간은 **데이터 신선도와 직접 교환**됩니다. 버퍼를 900초로 늘리면 객체 수는 1/15로 줄지만 대시보드나 이상탐지가 볼 수 있는 가장 최근 데이터가 최대 15분 늦어집니다.

## 4. 형식 변환(Parquet)의 조건

- Firehose는 **JSON 입력만** Parquet·ORC로 변환합니다. CSV 등은 Lambda 변환으로 먼저 JSON으로 바꿔야 합니다.
- 변환에는 **Glue Data Catalog 테이블 스키마**가 필요합니다. 스키마에 없는 속성은 변환 결과에서 빠집니다.
- 여러 JSON 문서를 한 레코드에 합칠 때는 `{"a":1}{"b":1}`처럼 이어 붙여야 하며 JSON 배열(`[{...},{...}]`)은 유효한 입력이 아닙니다. 디바이스 묶음 형식을 정할 때 이 제약을 함께 봅니다.
- 형식 변환을 켤 때 버퍼 크기에 별도 최소값이 적용된다는 설명은 이번에 확인한 문서에서 찾지 못했습니다. 실제 계정에서 설정 화면과 API 응답으로 확인합니다.

형식 변환 요금(0.022 USD/GB)은 Athena 스캔량 감소로 회수할 수 있는지가 판단 기준입니다. 데이터를 거의 조회하지 않으면 변환 요금만 남습니다. → [Athena·Glue 학습 노트](../athena-glue/README.md)

[Convert input data format](https://docs.aws.amazon.com/firehose/latest/dev/record-format-conversion.html) · [BufferingHints API](https://docs.aws.amazon.com/firehose/latest/APIReference/API_BufferingHints.html)

## 5. 낭비 판단에 필요한 자료

| 의심 상황 | 필요한 자료 | 판단 보류 조건 |
|---|---|---|
| 수집 요금이 원본 데이터 양보다 훨씬 큼 | 레코드 수, 평균 레코드 크기(CloudWatch `IncomingRecords`, `IncomingBytes`), 청구 사용량 | 레코드 크기 분포를 모름 |
| S3 객체가 지나치게 작음 | 스트림별 버퍼 설정, 일별 객체 수·평균 크기(S3 Inventory 등) | 다운스트림의 신선도 요구가 정해지지 않음 |
| 형식 변환 요금이 아까움 | 월 쿼리 수와 스캔량 | Athena 사용량을 모름 |

## 6. 확인 문제

1. 레코드 7 KB 1,000,000건의 과금 GB는 얼마인가요? (1 GB = 1,024 × 1,024 KB)
2. 유입 속도가 초당 1 MiB라면 기본 버퍼(5 MiB, 300초)에서 어느 조건이 먼저 도달하나요?
3. 버퍼 시간을 늘려 객체 수를 줄이면 어떤 품질 지표가 나빠지나요?

## 7. 확인 범위와 다음 질문

요금 페이지에서 5 KB 올림과 형식 변환·동적 파티셔닝 과금 방식을, Price List에서 서울 요율을, 개발자 가이드에서 버퍼 범위와 형식 변환 조건을 확인했습니다. `no-rounding` 항목의 적용 조건, 형식 변환 시 버퍼 최소값, 압축 후 객체 크기는 확인하지 않았습니다. 버퍼별 객체 수는 [실험 017](../../../experiments/017-firehose-buffer-small-files/README.md)에서 시뮬레이션합니다.

> 다음 질문: 같은 데이터를 CSV와 Parquet, 날짜 파티션으로 저장하면 Athena가 읽는 바이트는 얼마나 다른가?

## 공식 참고 자료

확인일은 **2026-11-13**입니다.

| 자료 | 확인 범위 |
|---|---|
| [Amazon Data Firehose pricing](https://aws.amazon.com/firehose/pricing/) | 5 KB 올림, 형식 변환·동적 파티셔닝 과금, GB 환산 예제 |
| [AWS Price List — AmazonKinesisFirehose ap-northeast-2](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonKinesisFirehose/current/ap-northeast-2/index.json) | 서울 요율, 게시일 2026-11-04 |
| [AWS Price List — AmazonS3 ap-northeast-2](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonS3/current/ap-northeast-2/index.json) | 서울 S3 Standard 저장·요청 요율, 게시일 2026-11-09 |
| [BufferingHints](https://docs.aws.amazon.com/firehose/latest/APIReference/API_BufferingHints.html) | 버퍼 크기·시간 범위, 기본값, 권장 크기 |
| [Convert input data format in Amazon Data Firehose](https://docs.aws.amazon.com/firehose/latest/dev/record-format-conversion.html) | JSON 입력, Glue 스키마, 결합 레코드 형식 |

## 확인 문제 정답과 해설

1. 7 KB는 10 KB로 올림됩니다. `1,000,000 × 10 KB ÷ 1,048,576 ≈ 9.54 GB`입니다.
2. 초당 1 MiB면 5초 만에 5 MiB가 차므로 버퍼 크기가 먼저 도달합니다.
3. 수집부터 S3에 나타나기까지의 시간, 즉 데이터 신선도가 나빠집니다.
