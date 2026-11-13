# 실제 계정 데이터로 InfraFit 기준값을 다시 정하는 계획

[실험 목차](README.md) · [InfraFit 적용 메모](infrafit-pipeline-ai-rules.md) · [InfraFit](../infrafit/README.md) · [기준값](../infrafit/thresholds.json)

**상태: 계획 승인됨(승인 1~5 범위, 승인 6 미사용), 수집 전.** 승인 1의 읽기 전용 정책 `cel-readonly`와 이 정책만 붙은 전용 사용자(콘솔 로그인 없음)를 실제 계정에 만들었다. 액세스 키 발급과 로컬 프로필 설정은 계정 소유자가 직접 했고, 프로필로 읽기 전용 사용자 접속을 확인했다(STS 호출 1회). 확인 시점의 청구서에는 Secrets Manager·S3 외의 서비스 사용이 없었다. 즉 IoT Core·Firehose·Athena·Bedrock·SageMaker의 실제 사용량이 아직 없어서, 기준값을 다시 정할 데이터가 생길 때까지 수집(승인 2~5)은 보류한다. 이미 있는 일별 비용 이력만으로 R-COST-1을 점검했다([023](023-real-cost-spike-check/README.md), Cost Explorer 1건 0.01 USD). 계정 접근(읽기 전용 프로필)과 원본 저장 경로가 정해지면 수집을 시작한다. 각 설정 변경(승인 2~5)은 실제로 적용하기 직전에 대상·비용·정리 방법을 다시 확인받는다. 아직 실제 계정 데이터를 하나도 수집하지 않았다. 계획 작성 시점에 이 작업 환경에는 AWS CLI(2.39.1)만 있고, 설정된 프로필·자격 증명은 없다. 아래 비용은 서울 리전 공개 요율(AWS Price List, 2026-11-13 확인)로 계산한 예상값이며, 실제 비용은 수집 후 따로 기록한다.

## 1. 원칙

- **읽기 전용 분석과 설정 변경을 나눈다.** 분석은 읽기 전용 권한으로만 한다. 데이터를 쌓기 위한 설정(Data Exports, S3 Inventory, 호출 로그 등)은 계정 설정을 바꾸는 일이다. 항목마다 따로 승인받고, 정리 방법을 함께 적는다.
- **원본은 저장소 밖에 둔다.** 계정 ID, ARN, 버킷·리소스 이름, 청구 원본, 프롬프트 본문은 저장소에 넣지 않는다. 저장소에는 비식별 집계값(리소스는 일련번호나 해시로 표시)과 집계 방법만 남긴다.
- **조정 기간과 평가 기간을 나눈다.** 시간 순서로 앞 기간에서 기준값을 고르고, 뒤 기간에서 평가한다. 선택 규칙은 데이터를 보기 전에 이 문서에 확정하고, 결과를 본 뒤 바꾸지 않는다.
- **정확도를 주장하지 않는다.** 낭비 판정 규칙은 대부분 정답 라벨이 없다. 기준값을 바꿀 때 판정이 어떻게 변하는지와, 사람이 표본을 검토한 결과로 판단한다. R-COST-1만 실제 사고·변경 기록이 있으면 오탐·미탐을 계산한다.
- **InfraFit은 읽기 전용으로 유지한다.** 변경 적용과 실현 절감 확인은 이번 범위가 아니다.

## 2. 필요한 권한

### 2-1. 분석용 읽기 전용 권한 (승인 1)

작업 이름은 실행 전에 AWS Service Authorization Reference에서 다시 확인한다. 리소스 범위는 실제 프로젝트의 자원으로 좁힌다.

| 용도 | 작업 |
|---|---|
| 일별 비용 | `ce:GetCostAndUsage` |
| 청구 내보내기·Inventory 읽기 | 해당 버킷·접두사에 한정한 `s3:ListBucket`, `s3:GetObject` |
| 지표 | `cloudwatch:GetMetricData`, `cloudwatch:ListMetrics` |
| Firehose·IoT 설정 | `firehose:ListDeliveryStreams`, `firehose:DescribeDeliveryStream`, `iot:ListTopicRules`, `iot:GetTopicRule` |
| Athena·Glue | `athena:ListWorkGroups`, `athena:ListQueryExecutions`, `athena:BatchGetQueryExecution`, `glue:GetTables`, `glue:GetTable`, `glue:GetPartitions` |
| SageMaker | `sagemaker:ListNotebookInstances`, `sagemaker:DescribeNotebookInstance`, `sagemaker:ListEndpoints`, `sagemaker:DescribeEndpoint`, `sagemaker:DescribeEndpointConfig`, `sagemaker:ListTrainingJobs`, `sagemaker:DescribeTrainingJob` |
| Bedrock 로그 설정 확인 | `bedrock:GetModelInvocationLoggingConfiguration` |

쓰기·삭제 작업과 `iam:*`, `sts:AssumeRole`의 범위 확대는 넣지 않는다. 바로 붙여 넣을 수 있는 정책은 [cel-readonly-policy.json](real-account/cel-readonly-policy.json)이다. S3 읽기(청구 내보내기·Inventory 버킷)는 버킷이 정해진 뒤 그 버킷과 접두사에 한정해 따로 추가한다.

### 2-2. 데이터를 쌓기 위한 설정 변경 (항목별 승인 2~6)

| 승인 | 설정 | 왜 필요한가 | 정리 방법 |
|---|---|---|---|
| 2 | Data Exports(CUR 2.0) → S3 | IoT 계량 메시지, Firehose 청구 GB와 사용 유형(`no-rounding` 포함), Athena·SageMaker 사용량을 행 단위로 대조 | 내보내기 삭제, 버킷 수명 주기 |
| 3 | S3 Inventory (Firehose 대상 버킷, 일별) | 객체 수·크기 분포(R-FH-2·R-ATH-2) | Inventory 구성 삭제, 보고서 수명 주기 |
| 4 | 애플리케이션 측 Bedrock 사용량 기록 | 캐시 읽기·쓰기 토큰(R-BR-1·2). 아래 3-4 참고 | 기록 중단, 보존 기간 만료 |
| 5 | 노트북 활동 수집 방법 | GPU·커널 사용 시간(R-SM-1). CloudWatch 지표에 노트북 GPU 지표가 없음 | 수집 스크립트·수명 주기 설정 제거 |
| 6 | (선택) Bedrock 모델 호출 로깅 | 4로 대체할 수 없을 때만. 아래 주의 참고 | 로깅 구성 삭제 |

## 3. 수집할 데이터

| 규칙 | 데이터와 출처 | 최소 기간 | 예상 수집 비용 (서울 공개 요율) | 비식별화 |
|---|---|---|---|---|
| R-IOT-1 | CUR 2.0의 IoT 사용 유형·사용량, 토픽별 발행 수와 페이로드 크기(디바이스·규칙 쪽 기록), 토픽별 허용 지연(사람 입력) | 4주 | CUR 저장 S3 0.025 USD/GB-월. Data Exports 자체의 요금은 이번에 확인하지 못함 | 토픽 이름 → 일련번호 |
| R-FH-1·2 | CloudWatch `IncomingBytes`·`IncomingRecords`·`DeliveryToS3.Success`(일 합계), `DescribeDeliveryStream`의 버퍼 설정, CUR 수집 GB·사용 유형, S3 Inventory 크기 분포, 하류 허용 신선도(사람 입력) | 4주 | `GetMetricData` 0.01 USD/1,000 지표(스트림 10개 × 3지표 × 하루 1회면 월 약 900지표 = 0.009 USD), Inventory 0.0028 USD/100만 객체 | 스트림·버킷 이름 → 일련번호 |
| R-ATH-1·2 | `BatchGetQueryExecution`(상태, `DataScannedInBytes`, 시각, `StatementType`), Glue 테이블 형식·파티션, Inventory 파일 수·크기 | 4주, 성공 DML 쿼리 테이블당 10건 이상 | Athena·Glue 조회 API의 과금 여부는 확인하지 못함. 기록 분석을 Athena로 하면 5 USD/TB, 쿼리당 10 MB 최소 | 쿼리 본문은 저장하지 않음. 테이블 → 일련번호 |
| R-BR-1·2 | 호출별 `inputTokens`·`cacheReadInputTokens`·`cacheWriteInputTokens`·출력 토큰·시각·실행 ID·추론 프로필·앞부분 해시 | 2주, 캐시 쓰기 20건 이상 | 애플리케이션 기록 방식에 따라 다름(CloudWatch Logs 수집 0.76 USD/GB, 저장 0.0314 USD/GB-월. S3에 쓰면 0.025 USD/GB-월) | 프롬프트 본문 저장 금지, 앞부분은 해시만 |
| R-SM-1 | 노트북 상태 기간, GPU·커널 사용 시간(승인 5), 학습 작업 시간, 엔드포인트 `Invocations`·`ModelLatency`(`GetMetricData`) | 4주 | `GetMetricData` 위와 같음 | 리소스 이름 → 일련번호 |
| R-COST-1 | `GetCostAndUsage` DAILY, 서비스별 `NetUnblendedCost`·`Estimated`. 실제 사고·배포 기록이 있으면 라벨로 사용 | 조정 28일 + 평가 28일 이상 | 요청당 0.01 USD(하루 1회 호출이면 월 약 0.30 USD) | 금액은 저장소에 비율·순위로만 |

### 3-4. Bedrock 데이터에 대한 주의

- 모델 호출 로깅의 로그 항목은 `inputTokenCount`·`outputTokenCount`만 정의하고, 캐시 읽기·쓰기 토큰 필드는 문서의 로그 항목 표에 없다. R-BR-1·2에 필요한 캐시 토큰은 Converse 응답의 사용량 필드를 애플리케이션에서 기록하는 방식(승인 4)으로 모은다.
- 모델 호출 로깅은 요청·응답 본문 전체, 계정 ID, 호출자 ARN을 기록한다. 실제 프로젝트의 프롬프트에 민감 정보가 있을 수 있으므로 승인 6은 기본적으로 쓰지 않는다.

## 4. 기준값보다 먼저 확인할 과금 규칙

| 확인할 점 | 방법 | 확정되면 고칠 곳 |
|---|---|---|
| IoT 5 KB 계량의 바이트 정의, MQTT 헤더·토픽 이름 포함 여부 | 크기를 아는 테스트 토픽의 발행 수·크기와 CUR 계량 메시지 수 대조(소량 발행은 승인 필요) | `iot.kb_definitions_bytes`, IoT 학습 노트, 016 |
| Firehose `no-rounding` 요율 적용 조건 | CUR 사용 유형 행과 스트림 소스 유형 대조 | R-FH-1 보류 조건, Firehose 학습 노트 |
| Athena S3 쿼리의 10 MB 최소·MB 올림, 실패·취소 쿼리 과금 | `DataScannedInBytes`와 CUR Athena 사용량 대조 | `athena.min_billed_mb` 근거, Athena 학습 노트 |
| Bedrock 캐시 미스율, Geographic·리전 내 요율(사용 시) | 애플리케이션 기록의 읽기·쓰기 비율, CUR 사용 유형 | `bedrock.supported_profiles`, 020 해석 |
| SageMaker 학습 과금 단위, 노트북 중지 상태 과금 항목 | CUR 사용량과 학습 작업 시간 대조 | SageMaker 학습 노트, 022 |

## 5. 기준값별 선택 규칙 (데이터를 보기 전에 확정)

조정 기간과 평가 기간은 시간 순서로 반씩 나눈다. 판정 결과는 셋 중 하나로 기록한다: 유지(실제 데이터와 맞음) / 변경(새 값과 근거) / 보류(데이터 부족 — 무엇이 얼마나 더 필요한지).

| 기준값 | 지금 값 | 선택 규칙 |
|---|---|---|
| `iot.payload_max_bytes` | 1,024 B | 실제 페이로드 분포의 사분위수와 016 산식으로 묶음 절감률이 50% 이상인 최대 크기. 토픽이 3개 미만이면 보류 |
| `iot.batch_size_limit_bytes` | 4,750 B | 4장에서 바이트 정의가 확정되면 그 정의의 95%로 바꾼다. 미확정이면 유지 |
| `iot.metering_tolerance` | 1% | 조정 기간 토픽별 (계량 − 예상 계량) ÷ 예상 계량의 95번째 백분위수 |
| `firehose.ratio_keep_below` / `ratio_candidate_at` | 1.5 / 3 | 스트림별 청구 GB ÷ 실제 GB 분포를 보고 하되, 사람이 표본 스트림을 검토해 후보로 동의한 비율의 최솟값으로 정한다 |
| `firehose_buffer.small_object_bytes`, `athena.small_file_bytes` | 1 MiB | 실제 쿼리 지연·스캔과 파일 크기의 관계를 보고, 파일 크기가 이보다 작을 때 스캔이 10 MB 최소를 넘는 비율이 처음으로 50%를 넘는 크기 |
| `firehose_buffer.object_count_tolerance` | 50% | 조정 기간의 (관측 객체 수 − 모형 객체 수) ÷ 모형 객체 수의 95번째 백분위수 |
| `athena.min_queries` | 10건 | 평가 기간에 판정이 조정 기간과 같게 유지되는 최소 쿼리 수 |
| `athena.full_scan_share` | 50% | 행 기반 테이블의 쿼리별 스캔 비율 분포를 기록하고, 사람이 "전체 스캔"으로 본 쿼리의 최소 비율 |
| `athena.parquet_scan_reduction` | 91% (018 대리 측정) | 실제 Parquet 테이블이 생기면 같은 쿼리의 CSV 대비 `DataScannedInBytes` 감소율 최솟값으로 바꾼다. 없으면 유지 |
| `bedrock.min_observed_cache_writes` | 20건 | 조정 기간 적중률의 부트스트랩 95% 구간 폭이 10%p 이하가 되는 쓰기 건수 |
| `sagemaker.gpu_busy_share` | 10% | 022 손익분기(학습 비율에 따른 비용비)를 실제 요율·시간에 다시 적용해 분리 운영이 2배 이상 싸지는 비율 |
| `sagemaker.serverless_cost_share` | 50% | 실제 콜드 스타트 지연(`ModelSetupTime`)을 확인한 뒤에만 정한다. 서버리스 엔드포인트가 없으면 보류 |
| `cost.mad_k`, `cost.min_relative_increase` | 3, 10% | 실제 사고·변경 라벨이 있으면 021의 선택 규칙(오탐 30정상일당 1건 이하 중 재현율 최대)을 조정 기간에 적용. 라벨이 없으면 경보 수와 사람 검토 결과만 기록하고 유지 |
| `cost.consecutive_cap_days` | 없음 | 경보일 제외를 쓰기로 결정할 때만 정한다. 조정 기간의 실제 수준 이동 사례에서 경보가 멈추는 가장 짧은 상한 |

## 6. 저장소에 남길 것과 남기지 않을 것

| 남긴다 | 남기지 않는다 |
|---|---|
| 기준값별 판정(유지·변경·보류)과 근거 요약 | 계정 ID, ARN, 리소스·버킷 이름 |
| 비식별 집계(분포 요약, 건수, 비율) | 청구 원본 행과 실제 금액 원본 |
| 기간 길이·표본 수·선택 규칙 | 수집 날짜(공개 문서), 프롬프트 본문 |
| 실제 비용 합계(승인 범위 확인용) | 자격 증명, 원본 로그 |

`thresholds.json`의 근거 수준에는 "실측(실제 계정)"을 추가한다. 기준값을 바꾸면 합성 예제(`workloads.json`, `workloads-ops.json`)의 판정 변화 목록을 보고하고, 테스트 기대값을 근거와 함께 갱신한다. EC2·EBS 기본 출력과 기존 테스트 11개는 그대로 통과해야 한다. 018·020처럼 대리 측정·가정과 실측을 비교한 결과는 실험 023 이후로 기록한다.

## 7. 진행 순서

1. 이 계획과 승인 1~5의 범위를 확정한다(승인 6은 기본 미사용).
2. 설정 변경(승인 2~5)을 적용하고, 데이터가 쌓이는 동안 4장의 과금 규칙부터 확인한다. S3 Inventory는 첫 보고서까지 최대 48시간이 걸릴 수 있다.
3. 조정 기간(최소 4주)이 끝나면 5장의 선택 규칙으로 기준값을 고른다. 평가 기간(최소 4주) 뒤에 판정 변화를 보고한다.
4. 테스트를 모두 실행하고, InfraFit README·적용 메모·FINAL-REPORT를 갱신한다.

## 근거와 확인 범위

확인일은 **2026-11-13**이다.

| 자료 | 확인 범위 |
|---|---|
| [AWS Price List — AmazonCloudWatch, ap-northeast-2](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonCloudWatch/current/ap-northeast-2/index.json) | `GetMetricData` 0.01 USD/1,000 지표, 로그 수집 0.76 USD/GB, 로그 저장 0.0314 USD/GB-월 |
| [AWS Price List — AmazonS3, ap-northeast-2](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonS3/current/ap-northeast-2/index.json) | S3 Inventory 0.0028 USD/100만 객체, Standard 저장 0.025 USD/GB-월 |
| [AWS Cost Explorer pricing](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/) | API 요청당 0.01 USD |
| [What is AWS Data Exports?](https://docs.aws.amazon.com/cur/latest/userguide/what-is-data-exports.html) | CUR 2.0 등 내보내기 유형, 열·행 선택으로 민감 비용 데이터 제외 가능. 요금은 이 문서에서 확인하지 못함 |
| [S3 Inventory](https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage-inventory.html) | 보고서 필드, 첫 보고서 최대 48시간 |
| [Bedrock model invocation logging](https://docs.aws.amazon.com/bedrock/latest/userguide/model-invocation-logging.html) | 기본 비활성, 요청·응답 본문·계정 ID·호출자 ARN 기록, 로그 항목의 토큰 필드 |
| [Bedrock prompt caching](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html) | Converse 응답의 `cacheReadInputTokens`·`cacheWriteInputTokens` |
| [SageMaker CloudWatch 지표](https://docs.aws.amazon.com/sagemaker/latest/dg/monitoring-cloudwatch.html) | 엔드포인트·학습 작업 지표, 노트북 GPU 지표 부재 |
