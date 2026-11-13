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
