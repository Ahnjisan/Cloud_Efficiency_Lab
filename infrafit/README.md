# InfraFit 읽기 전용 MVP

로컬 합성 청구 행, Terraform Plan JSON, 후보별 피크 관측을 연결해 **변경 검토 후보·유지·판단 보류**와 이유를 출력한다. Python 표준 라이브러리를 사용하고 입력 파일은 읽기만 한다. 실제 청구 대사는 미검증이다.

[최종 연구 보고서](../FINAL-REPORT.md)에서 실험 001~022, 종단 간 테스트 11개, 워크로드 규칙 테스트 19개, 운영 규칙 테스트 24개의 최종 검증 범위와 실제 청구 자료가 필요한 다음 단계를 확인할 수 있다.

```powershell
py -3 -B infrafit/cli.py
py -3 -B infrafit/cli.py --json
py -3 -B infrafit/cli.py --as-of 1
py -3 -B infrafit/test_cli.py -v
py -3 -B infrafit/cli.py --workloads infrafit/workloads.json
py -3 -B infrafit/test_workload_rules.py -v
py -3 -B infrafit/cli.py --workloads infrafit/workloads.json infrafit/workloads-ops.json
py -3 -B infrafit/test_ops_rules.py -v
```

기본 입력은 [008의 청구·변경·관측](../experiments/008-evidence-reconciliation/README.md)과 [004의 Plan JSON](../experiments/004-terraform-evidence/plan.json)이다. 008의 worker 사례를 동일 주소의 Plan과 연결하기 위해 [보조 합성 Plan](worker-plan.json)을 추가했다. [구성 연결 근거](config-basis.json)는 Terraform 주소별 자원 ID, 기간, 후보 구성 ID와 비용 관련 전후 속성을 연결한다. Terraform 주소와 클라우드 자원 ID의 연결은 명시적인 입력이다.

| 입력 옵션 | JSON 내용 |
|---|---|
| `--billing` | 008 형식의 청구 행 배열. 행 ID, 자원 ID, 기간, 도착 시점, USD 금액 문자열을 사용한다. |
| `--changes` | 008 형식의 변경 배열. Terraform 주소, 자원 ID, 기간, 후보 구성 ID, 가상 후보 비용을 사용한다. |
| `--peaks` | 008 형식의 피크 관측 배열. 자원 ID, 기간, 구성 ID, 도착 시점, p99를 사용한다. |
| `--plan` | Terraform Plan JSON 경로 하나 이상. 첫 버전은 전후 비용 관련 필드가 확인되는 EC2·EBS 갱신을 지원한다. |
| `--basis` | 주소별 구성 연결 근거. 전후 속성은 Plan에서 안전하게 추출한 값과 정확히 일치해야 한다. |

기본 평가 시점 2에서 주문 서비스는 가상 $120 → $100, p99 180ms로 **변경 검토 후보**다. 작업자 서비스는 가상 비용이 감소하지만 p99 250ms로 **유지**다. 청구 충돌·누락 또는 맞는 후보 관측이 없는 세 주소는 **판단 보류**다. 가상 기준은 p99 200ms이며, 이 판정은 변경 검토를 위한 근거다. 실제 서비스 품질과 실제 청구 감소는 별도 검증 범위다.

청구 행 ID나 후보 비용이 빠지면 해당 자원 또는 주소만 보류한다. 비용 관련 구성이 변경 전후 동일한 갱신도 보류한다. Plan의 미확정 값 마스크를 확인할 수 없으면 JSON의 `plan_status`와 최종 판정 모두 보류로 표시한다.

행 ID가 없는 청구 행은 금액 검증 전에 분리한다. 자원 ID가 있으면 해당 자원의 판정을 보류하고, 자원 ID도 없으면 어느 자원에도 귀속하지 않고 비용 집계에서 제외한 건수를 `unassigned_missing_id_rows`로 보고한다.

## 워크로드 규칙 (실험 016~022 기반, 선택 옵션)

`--workloads 경로`를 주면 IoT·Firehose·Bedrock 합성 입력을 별도로 판정해 보고서에 `workload_decisions`를 붙인다. 옵션을 주지 않으면 기존 출력과 바이트 단위로 같다(구현 시 기본·`--json`·`--json --as-of 1` 세 출력을 이전 버전과 비교해 확인). 규칙 설명과 근거는 [InfraFit 적용 메모](../experiments/infrafit-pipeline-ai-rules.md)에 있다.

| 규칙 | 판정 단위 | 후보 | 유지 | 판단 보류 |
|---|---|---|---|---|
| R-IOT-1 IoT 소형 메시지 묶음 | 토픽 | 평균 페이로드 ≤ 1 KB이고 허용 지연 안에서 2건 이상 묶을 수 있음 | 경보 토픽, 페이로드 > 1 KB, 허용 지연이 짧음 | 허용 지연 미입력, 계량 수가 발행 수·페이로드와 불일치 |
| R-FH-1 Firehose 소형 레코드 | 스트림 | 청구 GB ÷ 실제 GB ≥ 3이고 상류에서 합칠 수 있음 | 비율 < 1.5, 상류에서 합칠 수 없음 | 비율 1.5~3, 상류 정보 없음, no-rounding 사용 유형, 청구 < 실제 |
| R-BR-1 Bedrock 캐싱 미적용 | 모델 × 앞부분 해시 | 실행당 2회 이상 반복, 또는 5분 안 재사용 비율 ≥ 손익분기 | 앞부분 < 캐시 최소 길이, 재사용 비율 < 손익분기 | 요율 미확인(Geographic 등), 최소 길이 미확인 모델, 앞부분 토큰 불일치 |
| R-BR-2 Bedrock 캐싱 역효과 | 모델 × 앞부분 해시 | 캐시 적중률 < TTL별 손익분기 | 적중률 ≥ 손익분기 | TTL 미입력·혼재, 캐시 쓰기 관측 20건 미만 |

- 입력: [workloads.json](workloads.json)의 `iot_topics`, `firehose_streams`, `bedrock_calls`. 모두 합성 값이다. 사람이 넣어야 하는 값은 IoT `max_wait_s`(토픽 허용 지연)와 Firehose `upstream_can_combine`이다. 비어 있으면 그 항목만 보류한다.
- 기준값: [thresholds.json](thresholds.json). 값마다 근거 수준(실험 확인 / 공식 자료 / 임시값)과 출처를 적었다. 요율은 [서울 Price List 사본](../references/aws-price-list-apn2-2026-11-13.json)에서 읽고, Bedrock 손익분기 적중률은 요율로 계산한다.
- 출력: 판정, 이유 코드, 계산 근거(`evidence`), `expected_saving_usd`와 계산 기준(`saving_basis`). 예상 절감은 실제 청구 절감이 아니다. IoT·Firehose는 월 기준, Bedrock은 입력 로그의 관측 기간 전체 기준이다. 입력에 들어 있는 다른 필드(계정 ID 등)는 출력하지 않는다.
- 예제 17건에서 각 규칙의 후보·유지·보류가 모두 나온다. `sensor-telemetry`는 016을 재현해 최대 묶음 20건·예상 절감 월 38.41 USD, `agent-planner`는 020을 재현해 실행당 0.000735 USD(10회 0.00735 USD)를 출력한다.
- [test_workload_rules.py](test_workload_rules.py) 19개: 5 KB 여유 경계, 페이로드 1 KB 경계, 두 5 KB 정의의 계량 일치, 비율 1.5·3 경계, 올림 손실 상한, 캐시 최소 511·512토큰, 손익분기 적중률 바로 아래·위, 각 보류 사유, 한 항목 오류의 격리, 추가 필드 미출력, 기준값 근거 표기, CLI 옵션 유무.

## 운영 규칙 (R-FH-2, R-ATH-1·2, R-SM-1, R-COST-1)

`--workloads`에 여러 파일을 줄 수 있다. [workloads-ops.json](workloads-ops.json)을 함께 주면 아래 규칙이 [ops_rules.py](ops_rules.py)로 판정된다. 옵션 없는 기본 출력과 `workloads.json`만 준 출력은 구현 전과 바이트 단위로 같다(기본 텍스트·`--json`·`--workloads` 텍스트·JSON 네 가지를 구현 전 저장본과 비교).

### 입력 필드의 공식 출처 (2026-11-13 확인)

| 입력 | 필드 | 출처 |
|---|---|---|
| `firehose_buffers` | `DeliveryStreamName`, `BufferingHints.SizeInMBs`·`IntervalInSeconds` | [BufferingHints API](https://docs.aws.amazon.com/firehose/latest/APIReference/API_BufferingHints.html) |
| | `IncomingBytes_daily_sum` (`IncomingBytes`의 일 합계) | [Firehose CloudWatch 지표](https://docs.aws.amazon.com/firehose/latest/dev/monitoring-with-cloudwatch-metrics.html) |
| | `s3_objects_daily.count`·`mean_size_bytes` (S3 Inventory의 `Key`·`Size` 집계) | [S3 Inventory](https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage-inventory.html) |
| `athena_tables` | `query_executions[].QueryExecutionId`, `StatementType`, `Status.State`·`SubmissionDateTime`, `Statistics.DataScannedInBytes` | [QueryExecution](https://docs.aws.amazon.com/athena/latest/APIReference/API_QueryExecution.html) · [Status](https://docs.aws.amazon.com/athena/latest/APIReference/API_QueryExecutionStatus.html) · [Statistics](https://docs.aws.amazon.com/athena/latest/APIReference/API_QueryExecutionStatistics.html) |
| | `table.StorageDescriptor.InputFormat`·`SerdeInfo.SerializationLibrary`·`Compressed`, `PartitionKeys` | [Glue StorageDescriptor](https://docs.aws.amazon.com/glue/latest/webapi/API_StorageDescriptor.html) |
| `sagemaker_notebooks` | `NotebookInstanceName`, `InstanceType`, `VolumeSizeInGB`, `status_intervals[].NotebookInstanceStatus` | [DescribeNotebookInstance](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_DescribeNotebookInstance.html) |
| `sagemaker_endpoints` | `EndpointName`, `VariantName`, `Invocations_sum` (`Invocations` Sum), `ModelLatency_avg_us` (`ModelLatency`, 마이크로초) | [SageMaker CloudWatch 지표](https://docs.aws.amazon.com/sagemaker/latest/dg/monitoring-cloudwatch.html) |
| `daily_costs` | `ResultsByTime[].TimePeriod.Start`, `Estimated`, `Metrics.NetUnblendedCost.Amount` | [GetCostAndUsage](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_GetCostAndUsage.html) |

**공식 필드가 아닌 값.** 아래 값은 비어 있으면 그 항목만 보류한다.
- **사람이 넣는 값**: Firehose `allowed_freshness_s`, 노트북 `long_running_in_notebook`·`proposed_cpu_notebook_hours`, 엔드포인트 `always_on_required`·`cold_start_acceptable`·`serverless_memory_gb`, Athena `conversion_billed_gb_month`·`compaction`·`files`.
- **노트북 활동 값**: `activity.gpu_busy_hours`·`kernel_busy_hours`. SageMaker CloudWatch 지표 문서의 GPU 지표는 엔드포인트·학습 작업에만 있고 **노트북 인스턴스에는 없다**. 그래서 사람이 따로 수집해 넣어야 한다. 커널 시간만 있으면 GPU 사용 상한으로 쓴다.
- **쿼리와 테이블의 연결**: Athena `QueryExecution`에는 테이블 필드가 없다. 쿼리를 테이블별로 묶는 일은 입력 단계에서 한다.

### 판정

| 규칙 | 후보 | 유지 | 판단 보류 |
|---|---|---|---|
| R-FH-2 버퍼 | 버퍼 시간이 먼저 닫히고 평균 객체 < 1 MiB, 허용 신선도 안에서 버퍼 시간을 늘릴 수 있음 | 버퍼 크기가 먼저 참, 객체 ≥ 1 MiB, 신선도가 막음 | 신선도 미입력, 파티션 수 모름, 관측 객체 수가 모형과 50% 넘게 다름, 무버퍼 |
| R-ATH-1 행 기반 전체 스캔 | CSV·JSON이고 스캔 중앙값 > 10 MB, 평균 스캔 ≥ 테이블의 50%, 예상 절감 > 형식 변환 요금 | 대부분 10 MB 최소, 이미 일부만 읽음, 변환 요금이 더 큼 | 성공 DML 쿼리 10건 미만, 형식 판별 불가, 변환 대상 수집량 미입력 |
| R-ATH-2 작은 Parquet 파일 | 평균 파일 < 1 MiB이고 합치기 비용 < 10 MB 초과 스캔 비용(절감 상한) | 파일 ≥ 1 MiB, 모든 쿼리가 10 MB 최소, 합치기 비용이 더 큼 | 파일 통계·합치기 DPU-시간 미입력 |
| R-SM-1 GPU 노트북 | GPU 유형, GPU 사용 ÷ `InService` 시간 < 10% | CPU 유형, 노트북 안 장시간 작업, 사용 비율 ≥ 10% | 활동 자료 없음, 장시간 작업 여부 미입력, 요율 사본에 없는 유형(예: ml.g5.xlarge 노트북) |
| R-SM-1 엔드포인트 | 서버리스 예상 비용 < 엔드포인트 비용의 50% | 상시 대기 요구, 콜드 스타트 불가, 서버리스가 충분히 싸지 않음 | 요구사항 미입력, GPU 엔드포인트(서버리스 대체 미확인), 요율 없는 메모리 크기 |

### R-COST-1 조사 대기열

`daily_costs`가 있을 때만 보고서에 `investigation_queue`와 `investigation_holds`가 생긴다. 판정(후보·유지·보류)과 섞지 않는다.

- **기본 규칙**: 28일 중앙값 + 3 × 1.4826 × MAD이고, 중앙값보다 10% 이상 높을 때 대기열에 넣는다(021의 R2). 경보일은 기준선에 그대로 남긴다.
- **실제 데이터로 보완한 점** ([023](../experiments/023-real-cost-spike-check/README.md)·[024](../experiments/024-cost-spike-rule-fixes/README.md)):
  - 세금(`Tax`)은 판정하지 않습니다(`cost.excluded_services`).
  - 중앙값보다 최소 0.50 USD/일 높아야 합니다(`cost.min_abs_increase_usd`, 임시값).
  - 짧은 달에는 월 고정 요금이 하루 단위로 커지는 만큼 하한을 넓힙니다(`cost.calendar_allowance`).
  - 이 세 가지로 실제 계정의 오탐이 27건에서 0건으로 줄었고, 합성 급증 탐지 성능은 그대로였습니다.
  - 대기열 금액은 소수 넷째 자리까지 표시합니다.
  - +10~30% 수준의 작은 급증은 21.5%만 잡습니다. 이 규칙은 큰 급증용입니다.
- **잠정 표시**: `Estimated=true`인 날의 항목은 `estimated: true`, 텍스트에서는 "(잠정)"으로 표시한다.
- **보류**: 이력이 28일 이하이거나, 날짜가 빠지거나 겹치면 그 서비스를 `investigation_holds`로 보낸다.
- **경보일 제외 설정**:
  - `thresholds.json`의 `cost.exclude_alerts`는 기본 `false`다. 켜면 `consecutive_cap_days`가 반드시 있어야 하며, 없으면 그 서비스를 보류한다.
  - 상한을 넘긴 연속 경보일은 기준선에 다시 들어간다.
  - 10→20 USD 수준 이동 40일에 대한 경보 수:

    | 설정 | 경보 수 |
    |---|---:|
    | 기본(제외 안 함) | 14 |
    | 제외 + 상한 3일 | 17 |
    | 제외 + 상한 7일 | 21 |
    | 제외 + 상한 14일 | 28 |
    | 제외 + 상한 없음 | 40 (021의 폭주 재현) |

### 예제와 테스트

[workloads-ops.json](workloads-ops.json)의 28건에서 각 규칙의 후보·유지·보류가 모두 나온다.

| 예제 | 재현한 실험 | 결과 |
|---|---|---|
| `sensor-raw-60s` | 017 | 하루 객체 1,440→96 |
| `sensor_csv_dashboard`·`sensor_parquet_daily` | 018 | 과금 250 MB·10 MB |
| `gpu-always-on` | 022 | 19.40배 |
| `AWS IoT` 수준 이동 | 021 | 경보 14건 |

`sensor_csv_archive`(쿼리 하루 1회)는 형식 변환 요금이 절감보다 커서 **유지**가 나온다. Parquet 변환이 언제나 이득은 아니라는 사례다.

[test_ops_rules.py](test_ops_rules.py) 24개가 확인하는 것:
- 경계: 버퍼 크기/시간 경계, 1 MiB 경계, 10 MB 최소 과금 경계, 성공 DML만 집계, GPU 사용 비율 10% 경계, 이력 28일 경계
- 021 폭주와 상한
- 보류 사유별 동작, 한 항목 오류 격리, 추가 필드(`RoleArn`, `Query`) 미출력, 새 기준값의 근거 표기
- 여러 파일 결합과 대기열 출력

기준값 일부(1 MiB, 50%, 10%, 10건, 객체 수 허용 오차 50%, 연속 경보 상한)는 임시값이다. 첫 실제 계정 데이터로 다시 정해야 한다.

## 실제 AWS 출력 변환기 (convert.py)

[convert.py](convert.py)는 AWS가 내보낸 파일을 그대로 읽어 `--workloads` 입력 형식으로 바꾼다. 판정 코드와 분리되어 있고, 표준 라이브러리만 쓰며, AWS를 호출하지 않는다. 변환 결과는 저장소 밖에 두고 `cli.py --workloads`에 넘긴다.

```powershell
py -3 -B infrafit/convert.py --cost-explorer ce1.json ce2.json --athena-queries q.json --glue-table t1.json `
  --metric-queries mq.json --metric-data md.json --firehose-describe fh.json --s3-inventory manifest.json `
  --sagemaker-notebook nb.json --sagemaker-endpoint ep.json epc.json --bedrock-usage calls.jsonl `
  --ops-info ops-info.json --out <저장소 밖>\workloads-real.json
py -3 -B infrafit/cli.py --workloads <저장소 밖>\workloads-real.json
py -3 -B infrafit/test_convert.py -v
```

### 지원 형식 (공식 필드 2026-11-14 확인)

| 옵션 | 읽는 파일 | 만드는 항목 | 변환 규칙 |
|---|---|---|---|
| `--cost-explorer` | [GetCostAndUsage](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_GetCostAndUsage.html) 응답(여러 페이지) | `daily_costs` | `GroupDefinitions`에서 `SERVICE` 위치를 찾아 서비스별 `NetUnblendedCost`를 합친다(USAGE_TYPE 등으로 더 나뉘어 있어도 합산). 묶지 않은 응답은 `(total)` 하나. 그날 응답에 없는 서비스는 0. 빠지거나 겹친 날짜는 고치지 않고 넘겨 InfraFit이 보류하게 둔다. 023 `build_series`를 옮겨 확장했다 |
| `--athena-queries` + `--glue-table` | [BatchGetQueryExecution](https://docs.aws.amazon.com/athena/latest/APIReference/API_BatchGetQueryExecution.html) 응답 + Glue `GetTable` 응답 | `athena_tables` | 쿼리 → 테이블 연결은 운영 정보 파일에서 받는다(`QueryExecution`에 테이블 필드가 없음). `observed_days`는 제출 시각의 첫날~마지막 날(UTC). 테이블 크기·파일 수는 S3 Inventory의 테이블 접두사에서 계산한다. `UnprocessedQueryExecutionIds`는 경고 |
| `--metric-queries` + `--metric-data` | [GetMetricData](https://docs.aws.amazon.com/AmazonCloudWatch/latest/APIReference/API_GetMetricData.html) 요청(`MetricDataQueries`)과 응답 | Firehose `IncomingBytes_daily_sum`, 엔드포인트 `Invocations_sum`·`ModelLatency_avg_us` | 응답에는 `Id`와 값만 있어 요청의 `MetricStat`(네임스페이스·지표·차원)과 `Id`로 짝짓는다. `StatusCode`가 `Complete`가 아니면 건너뛴다. 일 합계는 요청 기간의 합 ÷ 일수, 지연 평균은 같은 시각의 호출 수로 가중 평균 |
| `--firehose-describe` | `DescribeDeliveryStream` 응답 | `firehose_buffers` | `ExtendedS3DestinationDescription`의 [BufferingHints](https://docs.aws.amazon.com/firehose/latest/APIReference/API_BufferingHints.html), [DynamicPartitioningConfiguration](https://docs.aws.amazon.com/firehose/latest/APIReference/API_DynamicPartitioningConfiguration.html)`.Enabled`(없으면 미사용). S3 외 대상은 건너뛴다 |
| `--s3-inventory` | [Inventory](https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage-inventory-location.html) `manifest.json` + 같은 폴더의 CSV(.gz) | `s3_objects_daily`, Athena `files`·`table_size_bytes` | CSV에는 머리글이 없어 `fileSchema`로 열을 읽는다(`Key`·`Size`·`LastModifiedDate` 필요). 하루 객체 수는 Inventory를 만든 날(덜 찬 날)을 뺀 기간의 `LastModifiedDate` UTC 날짜별 평균. ORC·Parquet 형식은 건너뛴다 |
| `--sagemaker-notebook` | `DescribeNotebookInstance` 응답 | `sagemaker_notebooks` | 상태 기간·GPU 활동은 응답에 없어 운영 정보 파일에서 받는다 |
| `--sagemaker-endpoint` | `DescribeEndpoint` + `DescribeEndpointConfig` 응답 | `sagemaker_endpoints` | `EndpointConfigName`으로 짝짓고 변형(variant)마다 한 항목. 유형은 설정의 `InstanceType`, 대수는 [CurrentInstanceCount](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_ProductionVariantSummary.html). 인스턴스가 없는(서버리스) 변형은 건너뛴다 |
| `--bedrock-usage` | 애플리케이션이 남긴 Converse 사용량 로그(JSON Lines) | `bedrock_calls` | 줄마다 `timestamp`, `run_id`, `modelId`, `prefix_hash`, `prefix_tokens`, `usage`([TokenUsage](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_TokenUsage.html) 그대로), 선택 `call_id`·`cache_ttl`. `inputTokens`는 캐시 읽기·쓰기를 뺀 토큰이라 InfraFit `input_tokens`와 뜻이 같다([prompt caching](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html)). TTL은 `cache_ttl`, 없으면 `cacheDetails[].ttl`. `modelId`의 `global.` → global, `us.`·`eu.`·`apac.` 등 → geographic, 접두사 없음 → in-region. 프롬프트·메시지 필드가 있으면 버리고 경고 |

**지원하지 않는 것.** IoT 토픽별 발행 수(R-IOT-1)와 Firehose 스트림별 청구 GB(R-FH-1)는 위 API 어디에도 없다. Cost Explorer는 계정 합계만 준다. 두 규칙의 입력은 지금처럼 사람이 만든다.

### 운영 정보 파일 (`--ops-info`, 저장소 밖)

사람이 넣는 값과 연결 정보다. 원래 이름을 키로 쓴다. 비어 있는 값은 결과에서도 비어 있고, InfraFit은 그 항목만 보류한다. 형식은 [예제](convert-examples/ops-info.json)를 따른다.

| 키 | 내용 |
|---|---|
| `firehose.<스트림>` | `allowed_freshness_s`, `active_partitions`(동적 파티셔닝일 때), `s3_prefix`(Inventory에서 이 스트림의 객체를 고르는 접두사) |
| `athena.queries` | `QueryExecutionId` → 테이블 이름 |
| `athena.tables.<테이블>` | `s3_prefix`, `conversion_billed_gb_month`, `compaction`, 선택 `observed_days`·`table_size_bytes` |
| `sagemaker_notebooks.<노트북>` | `status_intervals`, `activity`, `long_running_in_notebook`, `proposed_cpu_notebook_hours`, `training_volume_gb`, `s3_artifact_gb` |
| `sagemaker_endpoints.<엔드포인트>` | `inservice_hours`, `always_on_required`, `cold_start_acceptable`, `serverless_memory_gb` |
| `bedrock_models.<modelId>` | 자동 판별이 틀릴 때 `model`·`profile` 직접 지정 |

### 경고와 민감값

- **경고**는 결과 파일의 `conversion.warnings`에 쌓인다. 최상위 목록이 아니라 객체 안에 있어 InfraFit 판정에 섞이지 않는다. 필드가 없거나 형식이 다르면 변환을 멈추지 않고 그 항목만 건너뛰거나(`skipped-item`), 비운 채 내보낸다(`left-null`).

  ```json
  {"source": "athena", "file": "q.json", "item": "q-lost", "code": "unprocessed-query", "field": "UnprocessedQueryExecutionIds", "action": "skipped-item"}
  ```

- **복사하지 않는 값**: 결과는 허용한 필드만으로 새로 만든다. 그래서 ARN, 계정 ID, 버킷 이름, S3 경로, 역할, 쿼리 본문, 프롬프트는 옵션과 관계없이 나오지 않는다. 경고의 파일 이름에는 경로를 빼고 이름만 남긴다.
- **`--hash-names --hash-salt <비밀값>`**: 자원·테이블·쿼리·실행 ID를 `h-` + 소금값을 섞은 SHA-256 앞 12자로 바꾼다. Athena 제출 시각을 빼고, Bedrock 시각은 첫 호출 기준 상대 초로 바꾼다. Cost Explorer의 날짜와 금액은 규칙(월 일수 보정)에 필요해 그대로 남기고 `dates-and-amounts-kept` 경고를 낸다. 실제 비용 결과는 이름을 가려도 저장소에 넣지 않는다.

### 예제와 테스트

[convert-examples/](convert-examples/)의 응답은 실제 API 구조를 본뜬 합성 값이다. [make_examples.py](convert-examples/make_examples.py)가 기존 예제(`workloads*.json`)에서 만든다. 가짜 계정 ID·ARN·버킷 이름을 일부러 넣어, 결과에 나오지 않는지 확인한다.

[test_convert.py](test_convert.py) 21개가 확인하는 것:
- **원래 판정과 같은지**: 변환한 항목이 원래 예제와 같은 판정·이유·근거·예상 절감을 내는지 본다. 대상은 `sensor-raw-60s`(017, 1,440→96), `sensor_csv_dashboard`·`sensor_parquet_daily`(018), `gpu-always-on`(022), `anomaly-scorer`, `agent-planner`(020, 10회 0.007350 USD), `cached-dense`. 일별 비용 대기열은 021과 같다(AWS IoT 경보 14건).
- **오류 격리**: 필드 누락, 처리 안 된 쿼리, `PartialData` 지표, 사람 입력 누락, 연결 안 된 쿼리, 날짜 빠짐, SERVICE로 묶지 않은 페이지, Parquet Inventory, 서버리스 변형, 읽을 수 없는 파일. 각각 그 항목만 건너뛰거나 보류되는지 본다.
- **민감값**: 민감값이 나오지 않는지, 이름 가리기와 소금값, 프롬프트 필드 제거, 경고 형식, 기존 입력 파일을 바꾸지 않는지 본다.

**한계.** Inventory는 지금 남아 있는 객체만 보여 준다. 수명 주기로 지운 객체는 하루 객체 수에서 빠진다. 지표와 Inventory의 기간이 다르면 R-FH-2의 객체 수 비교가 틀어질 수 있다. 실제 AWS 응답으로는 아직 변환해 보지 않았다(계정에 해당 서비스 사용량이 없음).

## 읽기 전용 수집 명령 (collect.py)

[collect.py](collect.py)는 변환기가 읽는 파일을 `cel-readonly` 프로필의 aws CLI로 모아 **저장소 밖 폴더**에 저장한다. 자원을 만들거나 바꾸거나 지우지 않는다. [읽기 전용 정책](../experiments/real-account/cel-readonly-policy.json)에 있는 작업과, 사람이 지정한 S3 Inventory의 `s3 cp`만 부른다. **실제 계정에서는 아직 실행하지 않았다.** 드라이런과 가짜 aws 명령 테스트만 했다. 지금 계정에는 실제 프로젝트 사용량이 거의 없다(Secrets Manager 정도). 그래서 실행해도 판정할 거리가 거의 없다.

```powershell
# 1) 드라이런: AWS를 한 번도 부르지 않고 호출 목록과 최악 비용만 출력
py -3 -B infrafit/collect.py --out <저장소 밖 새 폴더> --days 14 --glue-databases <DB> --dry-run
# 2) 무료 단계만 실행하고 유료 계획을 출력한 뒤 멈춤
py -3 -B infrafit/collect.py --out <저장소 밖 새 폴더> --days 14 --glue-databases <DB>
# 3) 승인 후: 상한 안에서 유료 호출까지
py -3 -B infrafit/collect.py --out <저장소 밖 새 폴더> --days 14 --glue-databases <DB> --yes
py -3 -B infrafit/test_collect.py -v
```

| 옵션 | 뜻 |
|---|---|
| `--start`·`--end` 또는 `--days` | UTC 기간. `--end`는 그날을 포함하지 않는다(기본 오늘) |
| `--services` | `cost`, `firehose`, `athena`, `sagemaker`, `cloudwatch`, `s3-inventory`. 기본은 `s3-inventory`를 뺀 전부 |
| `--out` | 저장 폴더. 저장소 안이거나 비어 있지 않으면 거부한다 |
| `--glue-databases` | Glue 데이터베이스 이름. 정책에 `glue:GetDatabases`가 없어 직접 받는다 |
| `--inventory-manifest` | `s3://…/manifest.json`. 그 버킷의 `s3:GetObject` 권한을 따로 추가해야 해서 기본에서 뺐다 |
| `--max-ce-requests` (기본 3) | Cost Explorer 요청 상한. 넘으면 남은 페이지를 받지 않고 경고를 남긴다 |
| `--max-metrics` (기본 500) | GetMetricData 지표 수 상한. 넘으면 유료 호출 전에 멈춘다(종료 코드 1) |
| `--max-athena-queries` (기본 5,000), `--max-inventory-files` (기본 20) | 목록 조회와 Inventory 내려받기 상한 |
| `--dry-run` | 호출 0건. 호출할 API, 상한, 최악 비용만 출력 |
| `--yes` | 유료 단계 실행 허용. 없으면 무료 단계 뒤에 멈춘다 |

**단계와 요금** (2026-11-14 확인)

| 단계 | 부르는 API | 요금 |
|---|---|---|
| 무료 | Firehose `ListDeliveryStreams`·`DescribeDeliveryStream`, Athena `ListWorkGroups`·`ListQueryExecutions`·`BatchGetQueryExecution`(50건씩), SageMaker 노트북·엔드포인트·엔드포인트 설정의 List·Describe | 요금 페이지에서 API 요금 항목을 찾지 못했다(무료로 확인한 것은 아님). 호출 수는 요약에 기록한다 |
| 무료 범위 안 | Glue `GetTables` | Data Catalog 요청은 매달 처음 100만 건 무료, 그 뒤 100만 건당 1 USD(요율 사본·Glue 요금 페이지) |
| 유료 | Cost Explorer `GetCostAndUsage`(DAILY, SERVICE, `NetUnblendedCost`·`UsageQuantity`, us-east-1) | 요청당 0.01 USD |
| 유료 | CloudWatch `GetMetricData`(스트림별 `IncomingBytes` 일 합계, 엔드포인트 변형별 `Invocations` 합계·`ModelLatency` 평균) | 지표 1,000개당 0.01 USD. 무료 API 범위에 들지 않는다 |
| 유료(선택) | `s3 cp`로 Inventory manifest와 데이터 파일 | GET 1만 건당 0.0035 USD. 이 PC로의 전송 요금은 요율 사본에 없어 미포함 |

**저장하는 것** (모두 `--out` 안):
- 응답 원본: `firehose-NNN.json`, `athena-queries-NNN.json`, `glue-table-NNN.json`, `notebook-NNN.json`, `endpoint(-config)-NNN.json`, `ce-page-NNN.json`, `metric-queries-NNN.json`·`metric-data-NNN.json`, `inventory/`
  - 파일 이름에는 자원 이름 대신 일련번호를 쓴다.
  - Athena 응답은 기간 밖 쿼리를 빼고 저장한다. 뺀 건수는 요약에 남긴다.
- `requests.log`: 실행한 명령. 자원 이름은 들어가고, 자격 증명은 들어가지 않는다.
- `collect-summary.json`: 상태, API별 호출 수, 유료 단위와 예상 비용, 사용한 요율과 출처, 자원 종류별 개수, 경고. **자원 이름은 넣지 않는다.** aws 오류 메시지의 ARN·12자리 계정 ID는 가린다.

저장소에는 요약의 비식별 숫자(호출 수, 예상·실제 비용, 자원 개수)만 옮겨 적는다. 수집한 파일은 그대로 `convert.py`에 넣는다.

[test_collect.py](test_collect.py) 13개는 가짜 aws 명령([fake_aws.py](convert-examples/fake_aws.py))으로 확인한다:
- 드라이런 호출 0건
- `--yes` 없이 유료 호출 없음
- 지표 상한 초과 시 유료 호출 전에 멈춤, Cost Explorer 상한에서 페이지 자르기
- 저장소 안·비어 있지 않은 `--out` 거부
- 50건씩 나누기, 기간 필터
- aws 오류 메시지의 ARN·계정 ID 가림과 다른 서비스 계속 진행
- 요약에 자원 이름 없음, Inventory 내려받기
- 수집 결과를 변환기에 넣었을 때 경고 없이 원래 예제와 같은 판정

## 보고서 (`--report`)

`--report 경로.html` 또는 `경로.md`를 주면 판정 결과를 사람이 읽기 쉬운 파일 하나로 함께 쓴다([report.py](report.py)). 화면 출력(텍스트·`--json`)은 바뀌지 않는다.

```powershell
py -3 -B infrafit/cli.py --workloads infrafit/workloads.json infrafit/workloads-ops.json --report infrafit/reports/example-report.html
py -3 -B infrafit/test_report.py -v
```

| 절 | 내용 |
|---|---|
| 머리말 | 입력 데이터 종류(파일별 `data_kind`: 합성·실제, 섞이면 "혼합"), 평가 기간·시점, "예상 절감은 실제 청구 절감이 아님"·"실제 청구 대사: 미검증" |
| 요약 | EC2·EBS 판정과 워크로드 규칙 각각의 후보·유지·보류 수 |
| 규칙별 | 규칙마다 후보·유지·보류 수와 예상 절감. 계산 기준(`saving_basis`)이 같은 항목끼리만 더하고, 기준이 다르면 줄을 나눈다(예: R-SM-1 노트북과 엔드포인트) |
| 항목별 | 판정, 이유 문구, 근거 값(`evidence`), 예상 절감과 계산 기준, 사용한 기준값(값·근거 수준) |
| 판단 보류 사유 | 보류 이유별로 해당 항목을 묶는다. 무엇을 채우면 판정되는지 보인다 |
| 비용 급증 조사 대기열 | 판정과 섞지 않고 따로. 잠정(`Estimated`) 날짜 표시, 서비스별 보류 |
| 사용한 기준값 | `thresholds.json`의 값, 근거 수준(실험 확인·공식 자료·임시값, 실측이 생기면 실측), 출처 |

- 보고서는 판정 결과와 `thresholds.json`만으로 만든다. 그래서 입력의 다른 필드(계정 ID, ARN, 쿼리 본문)는 나오지 않는다. 모든 값은 HTML 이스케이프 처리를 한다.
- HTML은 파일 하나에 CSS만 넣고, JavaScript·외부 파일이 없다. 밝은·어두운 화면을 지원하고, 휴대폰 폭에서는 표만 가로로 스크롤된다.
- 생성 시각을 쓰지 않아 같은 입력이면 같은 파일이 나온다.
- 워크로드 파일 중 하나라도 `data_kind: "real"`이면 텍스트 출력 머리글이 "가상 입력"에서 "실제 입력"으로 바뀐다. 합성 예제의 출력은 그대로다.
- 예제 [example-report.html](reports/example-report.html)·[example-report.md](reports/example-report.md)는 합성 입력으로만 만들었다.

[test_report.py](test_report.py) 10개가 확인하는 것:
- 요약 수가 JSON 판정 수와 같은지
- 필수 절, 두 안내 문구, 근거 수준 표시
- 계산 기준이 다른 절감을 더하지 않는지
- 추가 필드(ARN·계정 ID·쿼리)가 나오지 않는지, `<script>` 이스케이프
- 외부 의존성이 없는지
- 같은 입력이면 같은 결과인지, 저장소 예제가 최신인지
- `--report`가 화면 출력을 바꾸지 않는지
- 워크로드 없이도 동작하는지, 잘못된 확장자 거부
- 실제 입력일 때 머리글과 "혼합" 표시
