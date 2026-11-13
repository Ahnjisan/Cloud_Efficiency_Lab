# InfraFit 보고서

> 예상 절감은 실제 청구 절감이 아닙니다. 공개 요율과 입력 사용량으로 계산한 값입니다.
> 실제 청구 대사: 미검증

- 입력 데이터: **합성** (EC2·EBS 기본 입력: 합성, workloads.json: 합성, workloads-ops.json: 합성)
- 평가 기간·시점: peak-01 / 2

## 요약

| 구분 | 변경 검토 후보 | 유지 | 판단 보류 |
|---|---:|---:|---:|
| EC2·EBS 판정 | 1 | 1 | 3 |
| 워크로드 규칙 | 9 | 18 | 18 |

예상 절감은 계산 기준(월·관측 기간 등)이 같은 항목끼리만 더한다. 기준이 다르면 줄을 나눈다.

## 규칙별

| 규칙 | 후보 | 유지 | 보류 | 예상 절감 USD | 계산 기준 |
|---|---:|---:|---:|---:|---|
| EC2·EBS | 1 | 1 | 3 |  |  |
| R-IOT-1 | 1 | 2 | 2 | 38.413440 | 월, 5,000 B 기준(보수적), 메시지+규칙+액션 |
| R-FH-1 | 1 | 1 | 3 | 4.275649 | 월, 올림 손실 상한(첫 구간 요율) |
| R-BR-1 | 1 | 2 | 1 | 0.007350 | 관측 기간 전체, 5분 TTL, 앞부분만 캐싱 |
| R-BR-2 | 1 | 1 | 0 | 0.025000 | 관측 기간 전체, 캐싱을 끄면 줄어드는 입력 비용 |
| R-BR-1/2 | 0 | 0 | 1 |  |  |
| R-FH-2 | 1 | 3 | 2 | 0.181440 | 월(30일), S3 PUT 요청만. 조회 단계의 GET·지연 변화는 미포함 |
| R-ATH-1 | 1 | 3 | 2 | 6.748233 | 월, 018의 최소 감소율 91% 적용(로컬 대리 측정), 형식 변환 요금 차감 |
| R-ATH | 0 | 0 | 1 |  |  |
| R-ATH-2 | 1 | 2 | 1 | 0.222374 | 월, 절감 상한(10 MB 초과 스캔 전부 제거 가정)에서 합치기 비용 차감 |
| R-SM-1 | 2 | 4 | 5 | 626.734667 | 입력 기간, 노트북·학습 볼륨·S3 아티팩트 스토리지 포함 |
| | | | | 101.440000 | 입력 기간, 서버리스 처리 시간 요금만(데이터 처리·콜드 스타트 영향 미포함) |

## 항목별

### EC2·EBS · aws_instance.orders — 변경 검토 후보
- 이유: 가상 비용이 감소하고 피크 p99 기준을 충족합니다.
- 근거: `가상 USD baseline` 120.00, `가상 USD candidate` 100.00, `가상 USD difference` 20.00, `peak_p99_ms` 180, `plan_status` extracted

### EC2·EBS · aws_instance.worker — 유지
- 이유: 피크 p99가 기준을 초과했습니다.
- 근거: `가상 USD baseline` 100.00, `가상 USD candidate` 70.00, `가상 USD difference` 30.00, `peak_p99_ms` 250, `plan_status` extracted

### EC2·EBS · aws_instance.conflict — 판단 보류
- 이유: 같은 청구 행 ID의 내용이 충돌합니다.
- 이유: 일치하는 Terraform Plan 주소가 없습니다.

### EC2·EBS · aws_instance.missing — 판단 보류
- 이유: 해당 자원과 기간의 청구 행이 없습니다.
- 이유: 일치하는 Terraform Plan 주소가 없습니다.

### EC2·EBS · aws_instance.stale — 판단 보류
- 이유: 후보 구성과 기간에 일치하는 피크 관측이 하나로 확정되지 않았습니다.
- 이유: 일치하는 Terraform Plan 주소가 없습니다.

### R-IOT-1 · sensor-telemetry — 변경 검토 후보
- 이유: 허용 지연 안에서 묶으면 계량 메시지가 줄어듭니다.
- 근거: `max_batch` 20, `added_max_wait_s` 190, `metered_messages` 25920000, `metered_after_batching` 1296000
- 예상 절감 USD 38.413440 (월, 5,000 B 기준(보수적), 메시지+규칙+액션)
- 기준값 `iot.kb_definitions_bytes` = [5000, 5120] (공식 자료)
- 기준값 `iot.payload_max_bytes` = 1024 (임시값)
- 기준값 `iot.batch_size_limit_bytes` = 4750 (임시값)
- 기준값 `iot.metering_tolerance` = 0.01 (임시값)

### R-IOT-1 · door-alarm — 유지
- 이유: 경보·제어 토픽은 묶음 대상이 아닙니다.
- 기준값 `iot.kb_definitions_bytes` = [5000, 5120] (공식 자료)
- 기준값 `iot.payload_max_bytes` = 1024 (임시값)
- 기준값 `iot.batch_size_limit_bytes` = 4750 (임시값)
- 기준값 `iot.metering_tolerance` = 0.01 (임시값)

### R-IOT-1 · camera-metadata — 유지
- 이유: 평균 페이로드가 커서 묶어도 계량이 크게 줄지 않습니다.
- 근거: `avg_payload_bytes` 4000
- 기준값 `iot.kb_definitions_bytes` = [5000, 5120] (공식 자료)
- 기준값 `iot.payload_max_bytes` = 1024 (임시값)
- 기준값 `iot.batch_size_limit_bytes` = 4750 (임시값)
- 기준값 `iot.metering_tolerance` = 0.01 (임시값)

### R-IOT-1 · air-quality — 판단 보류
- 이유: 토픽의 허용 지연이 입력되지 않았습니다.
- 기준값 `iot.kb_definitions_bytes` = [5000, 5120] (공식 자료)
- 기준값 `iot.payload_max_bytes` = 1024 (임시값)
- 기준값 `iot.batch_size_limit_bytes` = 4750 (임시값)
- 기준값 `iot.metering_tolerance` = 0.01 (임시값)

### R-IOT-1 · vibration-raw — 판단 보류
- 이유: 계량 메시지 수가 발행 수와 평균 페이로드로 설명되지 않습니다.
- 근거: `metered_messages` 8640000, `published_messages` 4320000
- 기준값 `iot.kb_definitions_bytes` = [5000, 5120] (공식 자료)
- 기준값 `iot.payload_max_bytes` = 1024 (임시값)
- 기준값 `iot.batch_size_limit_bytes` = 4750 (임시값)
- 기준값 `iot.metering_tolerance` = 0.01 (임시값)

### R-FH-1 · sensor-raw — 변경 검토 후보
- 이유: 작은 레코드의 5 KB 올림으로 청구 GB가 실제보다 큽니다.
- 근거: `billed_gb` 123.596, `raw_gb` 4.828, `billed_to_raw_ratio` 25.60, `mean_record_bytes` 200.0
- 예상 절감 USD 4.275649 (월, 올림 손실 상한(첫 구간 요율))
- 기준값 `firehose.record_unit_bytes` = 5120 (공식 자료)
- 기준값 `firehose.ratio_keep_below` = 1.5 (임시값)
- 기준값 `firehose.ratio_candidate_at` = 3.0 (임시값)

### R-FH-1 · sensor-batched — 유지
- 이유: 청구 GB가 실제 수집 GB에 가깝습니다.
- 근거: `billed_gb` 6.180, `raw_gb` 4.828, `billed_to_raw_ratio` 1.28, `mean_record_bytes` 4000.0
- 기준값 `firehose.record_unit_bytes` = 5120 (공식 자료)
- 기준값 `firehose.ratio_keep_below` = 1.5 (임시값)
- 기준값 `firehose.ratio_candidate_at` = 3.0 (임시값)

### R-FH-1 · gateway-logs — 판단 보류
- 이유: 청구 GB와 실제 수집 GB의 비율이 판정 구간 사이에 있습니다.
- 근거: `billed_gb` 4.768, `raw_gb` 2.384, `billed_to_raw_ratio` 2.00, `mean_record_bytes` 2560.0
- 기준값 `firehose.record_unit_bytes` = 5120 (공식 자료)
- 기준값 `firehose.ratio_keep_below` = 1.5 (임시값)
- 기준값 `firehose.ratio_candidate_at` = 3.0 (임시값)

### R-FH-1 · legacy-feed — 판단 보류
- 이유: 상류에서 레코드를 합칠 수 있는지 입력되지 않았습니다.
- 근거: `billed_gb` 123.596, `raw_gb` 4.828, `billed_to_raw_ratio` 25.60, `mean_record_bytes` 200.0
- 기준값 `firehose.record_unit_bytes` = 5120 (공식 자료)
- 기준값 `firehose.ratio_keep_below` = 1.5 (임시값)
- 기준값 `firehose.ratio_candidate_at` = 3.0 (임시값)

### R-FH-1 · direct-put-app — 판단 보류
- 이유: 적용 조건을 확인하지 못한 no-rounding 수집 요율이 청구에 있습니다.
- 기준값 `firehose.record_unit_bytes` = 5120 (공식 자료)
- 기준값 `firehose.ratio_keep_below` = 1.5 (임시값)
- 기준값 `firehose.ratio_candidate_at` = 3.0 (임시값)

### R-BR-1 · Claude Haiku 5.5 \| sha256:agent-planner — 변경 검토 후보
- 이유: 같은 앞부분이 실행마다 2회 이상 반복되는데 캐싱하지 않습니다.
- 근거: `calls` 40, `runs` 10, `median_calls_per_run` 4.0, `prefix_tokens` 3000, `estimated_hit_ratio_5m` 0.7500, `break_even_hit_ratio_5m` 0.2174
- 예상 절감 USD 0.007350 (관측 기간 전체, 5분 TTL, 앞부분만 캐싱)
- 기준값 `bedrock.supported_profiles` = ["global"] (공식 자료)
- 기준값 `bedrock.ttl_seconds` = {"5m": 300, "1h": 3600} (공식 자료)
- 기준값 `bedrock.min_cache_tokens` = {"Claude Haiku 5.5": 512, "Claude Sonnet 5.5": 512, "Claude Haiku 4.5": 4096, "Claude Sonnet 4.5": null} (공식 자료)
- 기준값 `bedrock.min_observed_cache_writes` = 20 (임시값)

### R-BR-2 · Claude Haiku 5.5 \| sha256:cached-dense — 유지
- 이유: 캐시 적중률이 손익분기보다 높습니다.
- 근거: `cache_ttl` 5m, `cache_write_calls` 25, `hit_ratio` 0.7500, `break_even_hit_ratio` 0.2174
- 기준값 `bedrock.supported_profiles` = ["global"] (공식 자료)
- 기준값 `bedrock.ttl_seconds` = {"5m": 300, "1h": 3600} (공식 자료)
- 기준값 `bedrock.min_cache_tokens` = {"Claude Haiku 5.5": 512, "Claude Sonnet 5.5": 512, "Claude Haiku 4.5": 4096, "Claude Sonnet 4.5": null} (공식 자료)
- 기준값 `bedrock.min_observed_cache_writes` = 20 (임시값)

### R-BR-1 · Claude Haiku 5.5 \| sha256:faq-single — 유지
- 이유: 같은 앞부분이 TTL 안에 반복되는 비율이 손익분기보다 낮습니다.
- 근거: `calls` 30, `runs` 30, `median_calls_per_run` 1.0, `prefix_tokens` 1000, `estimated_hit_ratio_5m` 0.0000, `break_even_hit_ratio_5m` 0.2174
- 기준값 `bedrock.supported_profiles` = ["global"] (공식 자료)
- 기준값 `bedrock.ttl_seconds` = {"5m": 300, "1h": 3600} (공식 자료)
- 기준값 `bedrock.min_cache_tokens` = {"Claude Haiku 5.5": 512, "Claude Sonnet 5.5": 512, "Claude Haiku 4.5": 4096, "Claude Sonnet 4.5": null} (공식 자료)
- 기준값 `bedrock.min_observed_cache_writes` = 20 (임시값)

### R-BR-1/2 · Claude Haiku 5.5 \| sha256:geo-agent — 판단 보류
- 이유: 이 모델·추론 프로필의 서울 리전 요율을 확인하지 못했습니다.
- 기준값 `bedrock.supported_profiles` = ["global"] (공식 자료)
- 기준값 `bedrock.ttl_seconds` = {"5m": 300, "1h": 3600} (공식 자료)
- 기준값 `bedrock.min_cache_tokens` = {"Claude Haiku 5.5": 512, "Claude Sonnet 5.5": 512, "Claude Haiku 4.5": 4096, "Claude Sonnet 4.5": null} (공식 자료)
- 기준값 `bedrock.min_observed_cache_writes` = 20 (임시값)

### R-BR-1 · Claude Sonnet 4.5 \| sha256:sonnet45-agent — 판단 보류
- 이유: 이 모델의 캐시 최소 토큰 수를 확인하지 못했습니다.
- 기준값 `bedrock.supported_profiles` = ["global"] (공식 자료)
- 기준값 `bedrock.ttl_seconds` = {"5m": 300, "1h": 3600} (공식 자료)
- 기준값 `bedrock.min_cache_tokens` = {"Claude Haiku 5.5": 512, "Claude Sonnet 5.5": 512, "Claude Haiku 4.5": 4096, "Claude Sonnet 4.5": null} (공식 자료)
- 기준값 `bedrock.min_observed_cache_writes` = 20 (임시값)

### R-BR-2 · Claude Sonnet 5.5 \| sha256:cached-sparse — 변경 검토 후보
- 이유: 캐시 적중률이 손익분기보다 낮아 캐싱이 비용을 늘립니다.
- 근거: `cache_ttl` 5m, `cache_write_calls` 25, `hit_ratio` 0.0000, `break_even_hit_ratio` 0.2083
- 예상 절감 USD 0.025000 (관측 기간 전체, 캐싱을 끄면 줄어드는 입력 비용)
- 기준값 `bedrock.supported_profiles` = ["global"] (공식 자료)
- 기준값 `bedrock.ttl_seconds` = {"5m": 300, "1h": 3600} (공식 자료)
- 기준값 `bedrock.min_cache_tokens` = {"Claude Haiku 5.5": 512, "Claude Sonnet 5.5": 512, "Claude Haiku 4.5": 4096, "Claude Sonnet 4.5": null} (공식 자료)
- 기준값 `bedrock.min_observed_cache_writes` = 20 (임시값)

### R-BR-1 · Claude Sonnet 5.5 \| sha256:short-prompt — 유지
- 이유: 앞부분이 캐시 최소 토큰 수보다 짧습니다.
- 근거: `prefix_tokens` 400, `min_cache_tokens` 512
- 기준값 `bedrock.supported_profiles` = ["global"] (공식 자료)
- 기준값 `bedrock.ttl_seconds` = {"5m": 300, "1h": 3600} (공식 자료)
- 기준값 `bedrock.min_cache_tokens` = {"Claude Haiku 5.5": 512, "Claude Sonnet 5.5": 512, "Claude Haiku 4.5": 4096, "Claude Sonnet 4.5": null} (공식 자료)
- 기준값 `bedrock.min_observed_cache_writes` = 20 (임시값)

### R-FH-2 · sensor-raw-60s — 변경 검토 후보
- 이유: 허용 신선도 안에서 버퍼 시간을 늘리면 작은 객체가 줄어듭니다.
- 근거: `partitions` 1, `seconds_to_fill_buffer` 2621.4, `objects_per_day_observed` 1440, `objects_per_day_modeled` 1440.0, `mean_object_bytes` 120000, `proposed_interval_s` 900, `objects_per_day_after` 96.0, `mean_object_bytes_after` 1800000, `added_max_wait_s` 840
- 예상 절감 USD 0.181440 (월(30일), S3 PUT 요청만. 조회 단계의 GET·지연 변화는 미포함)
- 기준값 `firehose_buffer.max_interval_s` = 900 (공식 자료)
- 기준값 `firehose_buffer.small_object_bytes` = 1048576 (임시값)
- 기준값 `firehose_buffer.object_count_tolerance` = 0.5 (임시값)

### R-FH-2 · sensor-high-rate — 유지
- 이유: 버퍼 크기가 먼저 차서 버퍼 시간을 늘려도 객체 수가 줄지 않습니다.
- 근거: `partitions` 1, `seconds_to_fill_buffer` 26.2, `objects_per_day_observed` 3200, `objects_per_day_modeled` 3295.9, `mean_object_bytes` 5400000
- 기준값 `firehose_buffer.max_interval_s` = 900 (공식 자료)
- 기준값 `firehose_buffer.small_object_bytes` = 1048576 (임시값)
- 기준값 `firehose_buffer.object_count_tolerance` = 0.5 (임시값)

### R-FH-2 · gateway-large-objects — 유지
- 이유: 평균 객체 크기가 기준 이상입니다.
- 근거: `partitions` 1, `seconds_to_fill_buffer` 524.3, `objects_per_day_observed` 288, `objects_per_day_modeled` 288.0, `mean_object_bytes` 3000000
- 기준값 `firehose_buffer.max_interval_s` = 900 (공식 자료)
- 기준값 `firehose_buffer.small_object_bytes` = 1048576 (임시값)
- 기준값 `firehose_buffer.object_count_tolerance` = 0.5 (임시값)

### R-FH-2 · sensor-no-freshness — 판단 보류
- 이유: 하류 소비자의 허용 신선도가 입력되지 않았습니다.
- 근거: `partitions` 1, `seconds_to_fill_buffer` 2621.4, `objects_per_day_observed` 1440, `objects_per_day_modeled` 1440.0, `mean_object_bytes` 120000
- 기준값 `firehose_buffer.max_interval_s` = 900 (공식 자료)
- 기준값 `firehose_buffer.small_object_bytes` = 1048576 (임시값)
- 기준값 `firehose_buffer.object_count_tolerance` = 0.5 (임시값)

### R-FH-2 · zone-partitioned — 판단 보류
- 이유: 동적 파티셔닝을 쓰지만 활성 파티션 수를 모릅니다.
- 기준값 `firehose_buffer.max_interval_s` = 900 (공식 자료)
- 기준값 `firehose_buffer.small_object_bytes` = 1048576 (임시값)
- 기준값 `firehose_buffer.object_count_tolerance` = 0.5 (임시값)

### R-FH-2 · alarm-feed — 유지
- 이유: 허용 신선도 때문에 버퍼 시간을 늘릴 수 없습니다.
- 근거: `partitions` 1, `seconds_to_fill_buffer` 2621.4, `objects_per_day_observed` 1440, `objects_per_day_modeled` 1440.0, `mean_object_bytes` 120000
- 기준값 `firehose_buffer.max_interval_s` = 900 (공식 자료)
- 기준값 `firehose_buffer.small_object_bytes` = 1048576 (임시값)
- 기준값 `firehose_buffer.object_count_tolerance` = 0.5 (임시값)

### R-ATH-1 · sensor_csv_dashboard — 변경 검토 후보
- 이유: 행 기반 테이블을 쿼리마다 크게 스캔합니다.
- 근거: `format` row, `successful_dml_queries` 212, `median_scan_bytes` 261230663.0, `median_billed_mb` 250, `athena_usd_month_observed` 7.5817, `mean_scan_share_of_table` 1.0, `athena_usd_month_after` 0.6975, `conversion_usd_month` 0.1360
- 예상 절감 USD 6.748233 (월, 018의 최소 감소율 91% 적용(로컬 대리 측정), 형식 변환 요금 차감)
- 기준값 `athena.min_billed_mb` = 10 (공식 자료)
- 기준값 `athena.min_queries` = 10 (임시값)
- 기준값 `athena.full_scan_share` = 0.5 (임시값)
- 기준값 `athena.parquet_scan_reduction` = 0.91 (실험 확인)

### R-ATH-1 · sensor_csv_archive — 유지
- 이유: 형식 변환 요금이 예상 스캔 절감보다 큽니다.
- 근거: `format` row, `successful_dml_queries` 30, `median_scan_bytes` 261230663.0, `median_billed_mb` 250, `athena_usd_month_observed` 0.0358, `mean_scan_share_of_table` 1.0, `athena_usd_month_after` 0.0033, `conversion_usd_month` 0.1360
- 기준값 `athena.min_billed_mb` = 10 (공식 자료)
- 기준값 `athena.min_queries` = 10 (임시값)
- 기준값 `athena.full_scan_share` = 0.5 (임시값)
- 기준값 `athena.parquet_scan_reduction` = 0.91 (실험 확인)

### R-ATH-1 · events_json_pruned — 유지
- 이유: 쿼리가 테이블의 일부만 읽고 있습니다.
- 근거: `format` row, `successful_dml_queries` 40, `median_scan_bytes` 52000000.0, `median_billed_mb` 50, `athena_usd_month_observed` 0.0095, `mean_scan_share_of_table` 0.026
- 기준값 `athena.min_billed_mb` = 10 (공식 자료)
- 기준값 `athena.min_queries` = 10 (임시값)
- 기준값 `athena.full_scan_share` = 0.5 (임시값)
- 기준값 `athena.parquet_scan_reduction` = 0.91 (실험 확인)

### R-ATH-1 · device_registry_csv — 유지
- 이유: 쿼리 스캔 중앙값이 10 MB 최소 과금 이하입니다.
- 근거: `format` row, `successful_dml_queries` 40, `median_scan_bytes` 3000000.0, `median_billed_mb` 10, `athena_usd_month_observed` 0.0019
- 기준값 `athena.min_billed_mb` = 10 (공식 자료)
- 기준값 `athena.min_queries` = 10 (임시값)
- 기준값 `athena.full_scan_share` = 0.5 (임시값)
- 기준값 `athena.parquet_scan_reduction` = 0.91 (실험 확인)

### R-ATH-1 · sensor_csv_no_volume — 판단 보류
- 이유: 형식 변환 대상 월 수집량(과금 GB)이 입력되지 않았습니다.
- 근거: `format` row, `successful_dml_queries` 50, `median_scan_bytes` 261230663.0, `median_billed_mb` 250, `athena_usd_month_observed` 1.7881, `mean_scan_share_of_table` 1.0
- 기준값 `athena.min_billed_mb` = 10 (공식 자료)
- 기준값 `athena.min_queries` = 10 (임시값)
- 기준값 `athena.full_scan_share` = 0.5 (임시값)
- 기준값 `athena.parquet_scan_reduction` = 0.91 (실험 확인)

### R-ATH · legacy_custom — 판단 보류
- 이유: SerDe·입력 형식으로 테이블 형식을 판별할 수 없습니다.
- 기준값 `athena.min_billed_mb` = 10 (공식 자료)
- 기준값 `athena.min_queries` = 10 (임시값)

### R-ATH-2 · sensor_parquet_daily — 유지
- 이유: 모든 쿼리가 10 MB 최소 과금 이하라 합치기로 비용이 줄지 않습니다.
- 근거: `format` parquet, `successful_dml_queries` 30, `median_scan_bytes` 306032.0, `median_billed_mb` 10, `athena_usd_month_observed` 0.0014, `file_count` 30, `mean_file_bytes` 676840
- 기준값 `athena.min_billed_mb` = 10 (공식 자료)
- 기준값 `athena.min_queries` = 10 (임시값)
- 기준값 `athena.small_file_bytes` = 1048576 (임시값)

### R-ATH-2 · sensor_parquet_5min — 변경 검토 후보
- 이유: 작은 Parquet 파일이 10 MB를 넘는 스캔을 만들고 있습니다.
- 근거: `format` parquet, `successful_dml_queries` 500, `median_scan_bytes` 15408373.0, `median_billed_mb` 15, `athena_usd_month_observed` 1.2016, `file_count` 8640, `mean_file_bytes` 9588, `saving_upper_bound_usd_month` 0.4864, `compaction_usd_month` 0.2640
- 예상 절감 USD 0.222374 (월, 절감 상한(10 MB 초과 스캔 전부 제거 가정)에서 합치기 비용 차감)
- 기준값 `athena.min_billed_mb` = 10 (공식 자료)
- 기준값 `athena.min_queries` = 10 (임시값)
- 기준값 `athena.small_file_bytes` = 1048576 (임시값)

### R-ATH-2 · sensor_parquet_5min_costly_compaction — 유지
- 이유: 합치기 비용이 절감 상한보다 큽니다.
- 근거: `format` parquet, `successful_dml_queries` 200, `median_scan_bytes` 8278877.5, `median_billed_mb` 10, `athena_usd_month_observed` 0.4077, `file_count` 8640, `mean_file_bytes` 9588, `saving_upper_bound_usd_month` 0.1216, `compaction_usd_month` 26.4000
- 기준값 `athena.min_billed_mb` = 10 (공식 자료)
- 기준값 `athena.min_queries` = 10 (임시값)
- 기준값 `athena.small_file_bytes` = 1048576 (임시값)

### R-ATH-2 · sensor_parquet_5min_no_compaction — 판단 보류
- 이유: 합치기 작업의 DPU-시간이 입력되지 않았습니다.
- 근거: `format` parquet, `successful_dml_queries` 200, `median_scan_bytes` 8278877.5, `median_billed_mb` 10, `athena_usd_month_observed` 0.4077, `file_count` 8640, `mean_file_bytes` 9588
- 기준값 `athena.min_billed_mb` = 10 (공식 자료)
- 기준값 `athena.min_queries` = 10 (임시값)
- 기준값 `athena.small_file_bytes` = 1048576 (임시값)

### R-ATH-1 · sparse_table — 판단 보류
- 이유: 판정에 필요한 성공 쿼리 수가 부족합니다.
- 근거: `successful_dml_queries` 5
- 기준값 `athena.min_billed_mb` = 10 (공식 자료)
- 기준값 `athena.min_queries` = 10 (임시값)

### R-SM-1 · gpu-always-on — 변경 검토 후보
- 이유: GPU 노트북이 켜진 시간의 대부분 동안 GPU를 쓰지 않습니다.
- 근거: `in_service_hours` 720, `busy_hours` 16, `busy_basis` gpu_busy_hours, `busy_share` 0.0222, `current_usd` 660.8000, `alternative_usd` 34.0653, `current_to_alternative_ratio` 19.40, `alternative` ml.t3.medium 176h + ml.g4dn.xlarge 학습 작업 16h
- 예상 절감 USD 626.734667 (입력 기간, 노트북·학습 볼륨·S3 아티팩트 스토리지 포함)
- 기준값 `sagemaker.gpu_busy_share` = 0.1 (임시값)
- 기준값 `sagemaker.cpu_notebook_type` = ml.t3.medium (실험 확인)
- 기준값 `sagemaker.hours_per_month` = 720 (실험 확인)

### R-SM-1 · gpu-busy — 유지
- 이유: 켜진 시간 대비 GPU 사용 비율이 기준 이상입니다.
- 근거: `in_service_hours` 720, `busy_hours` 200, `busy_basis` gpu_busy_hours, `busy_share` 0.2778
- 기준값 `sagemaker.gpu_busy_share` = 0.1 (임시값)
- 기준값 `sagemaker.cpu_notebook_type` = ml.t3.medium (실험 확인)
- 기준값 `sagemaker.hours_per_month` = 720 (실험 확인)

### R-SM-1 · cpu-explore — 유지
- 이유: GPU 인스턴스가 아닙니다.
- 기준값 `sagemaker.gpu_busy_share` = 0.1 (임시값)
- 기준값 `sagemaker.cpu_notebook_type` = ml.t3.medium (실험 확인)
- 기준값 `sagemaker.hours_per_month` = 720 (실험 확인)

### R-SM-1 · gpu-no-activity — 판단 보류
- 이유: 노트북의 GPU·커널 활동 자료가 없습니다.
- 기준값 `sagemaker.gpu_busy_share` = 0.1 (임시값)
- 기준값 `sagemaker.cpu_notebook_type` = ml.t3.medium (실험 확인)
- 기준값 `sagemaker.hours_per_month` = 720 (실험 확인)

### R-SM-1 · gpu-unknown-jobs — 판단 보류
- 이유: 노트북 안에서 장시간 작업이 도는지 입력되지 않았습니다.
- 기준값 `sagemaker.gpu_busy_share` = 0.1 (임시값)
- 기준값 `sagemaker.cpu_notebook_type` = ml.t3.medium (실험 확인)
- 기준값 `sagemaker.hours_per_month` = 720 (실험 확인)

### R-SM-1 · g5-notebook — 판단 보류
- 이유: 이 인스턴스 유형의 서울 리전 요율이 요율 사본에 없습니다.
- 기준값 `sagemaker.gpu_busy_share` = 0.1 (임시값)
- 기준값 `sagemaker.cpu_notebook_type` = ml.t3.medium (실험 확인)
- 기준값 `sagemaker.hours_per_month` = 720 (실험 확인)

### R-SM-1 · anomaly-scorer — 변경 검토 후보
- 이유: 호출량에 비해 상시 엔드포인트 비용이 큽니다.
- 근거: `endpoint_usd` 102.2400, `serverless_usd` 0.8000, `invocations` 100000, `serverless_memory_gb` 2
- 예상 절감 USD 101.440000 (입력 기간, 서버리스 처리 시간 요금만(데이터 처리·콜드 스타트 영향 미포함))
- 기준값 `sagemaker.serverless_cost_share` = 0.5 (임시값)

### R-SM-1 · busy-scorer — 유지
- 이유: 서버리스 예상 비용이 기준만큼 낮지 않습니다.
- 근거: `endpoint_usd` 102.2400, `serverless_usd` 160.0000, `invocations` 20000000, `serverless_memory_gb` 2
- 기준값 `sagemaker.serverless_cost_share` = 0.5 (임시값)

### R-SM-1 · alarm-scorer — 유지
- 이유: 엔드포인트 상시 대기가 요구사항입니다.
- 기준값 `sagemaker.serverless_cost_share` = 0.5 (임시값)

### R-SM-1 · gpu-scorer — 판단 보류
- 이유: GPU 엔드포인트의 서버리스 대체 가능 여부를 확인하지 못했습니다.
- 기준값 `sagemaker.serverless_cost_share` = 0.5 (임시값)

### R-SM-1 · batch-scorer — 판단 보류
- 이유: 콜드 스타트 허용 여부가 입력되지 않았습니다.
- 기준값 `sagemaker.serverless_cost_share` = 0.5 (임시값)

## 판단 보류 사유

- **같은 청구 행 ID의 내용이 충돌합니다.** — EC2·EBS aws_instance.conflict
- **일치하는 Terraform Plan 주소가 없습니다.** — EC2·EBS aws_instance.conflict, EC2·EBS aws_instance.missing, EC2·EBS aws_instance.stale
- **해당 자원과 기간의 청구 행이 없습니다.** — EC2·EBS aws_instance.missing
- **후보 구성과 기간에 일치하는 피크 관측이 하나로 확정되지 않았습니다.** — EC2·EBS aws_instance.stale
- **토픽의 허용 지연이 입력되지 않았습니다.** — R-IOT-1 air-quality
- **계량 메시지 수가 발행 수와 평균 페이로드로 설명되지 않습니다.** — R-IOT-1 vibration-raw
- **청구 GB와 실제 수집 GB의 비율이 판정 구간 사이에 있습니다.** — R-FH-1 gateway-logs
- **상류에서 레코드를 합칠 수 있는지 입력되지 않았습니다.** — R-FH-1 legacy-feed
- **적용 조건을 확인하지 못한 no-rounding 수집 요율이 청구에 있습니다.** — R-FH-1 direct-put-app
- **이 모델·추론 프로필의 서울 리전 요율을 확인하지 못했습니다.** — R-BR-1/2 Claude Haiku 5.5 \| sha256:geo-agent
- **이 모델의 캐시 최소 토큰 수를 확인하지 못했습니다.** — R-BR-1 Claude Sonnet 4.5 \| sha256:sonnet45-agent
- **하류 소비자의 허용 신선도가 입력되지 않았습니다.** — R-FH-2 sensor-no-freshness
- **동적 파티셔닝을 쓰지만 활성 파티션 수를 모릅니다.** — R-FH-2 zone-partitioned
- **형식 변환 대상 월 수집량(과금 GB)이 입력되지 않았습니다.** — R-ATH-1 sensor_csv_no_volume
- **SerDe·입력 형식으로 테이블 형식을 판별할 수 없습니다.** — R-ATH legacy_custom
- **합치기 작업의 DPU-시간이 입력되지 않았습니다.** — R-ATH-2 sensor_parquet_5min_no_compaction
- **판정에 필요한 성공 쿼리 수가 부족합니다.** — R-ATH-1 sparse_table
- **노트북의 GPU·커널 활동 자료가 없습니다.** — R-SM-1 gpu-no-activity
- **노트북 안에서 장시간 작업이 도는지 입력되지 않았습니다.** — R-SM-1 gpu-unknown-jobs
- **이 인스턴스 유형의 서울 리전 요율이 요율 사본에 없습니다.** — R-SM-1 g5-notebook
- **GPU 엔드포인트의 서버리스 대체 가능 여부를 확인하지 못했습니다.** — R-SM-1 gpu-scorer
- **콜드 스타트 허용 여부가 입력되지 않았습니다.** — R-SM-1 batch-scorer

## 비용 급증 조사 대기열 (판정이 아니라 조사 대상)

| 서비스 | 날짜 | 관측 USD | 기준 중앙값 USD | 경보 기준 USD | 잠정 |
|---|---|---:|---:|---:|---|
| Amazon Bedrock | 2026-02-20 | 60.0000 | 20.0000 | 22.0000 |  |
| Amazon Bedrock | 2026-03-01 | 45.0000 | 20.0000 | 22.0000 | 잠정 |
| AWS IoT | 2026-02-05 | 19.4000 | 10.0000 | 12.1786 |  |
| AWS IoT | 2026-02-06 | 20.0000 | 10.0000 | 12.1786 |  |
| AWS IoT | 2026-02-07 | 20.6000 | 10.0000 | 12.1786 |  |
| AWS IoT | 2026-02-08 | 19.7000 | 10.0000 | 12.1786 |  |
| AWS IoT | 2026-02-09 | 20.3000 | 10.0750 | 12.2699 |  |
| AWS IoT | 2026-02-10 | 19.4000 | 10.1500 | 12.3613 |  |
| AWS IoT | 2026-02-11 | 20.0000 | 10.1500 | 12.3613 |  |
| AWS IoT | 2026-02-12 | 20.6000 | 10.1500 | 12.3613 |  |
| AWS IoT | 2026-02-13 | 19.7000 | 10.1500 | 12.3613 |  |
| AWS IoT | 2026-02-14 | 20.3000 | 10.1500 | 12.3613 |  |
| AWS IoT | 2026-02-15 | 19.4000 | 10.2250 | 11.8929 |  |
| AWS IoT | 2026-02-16 | 20.0000 | 10.2250 | 12.2265 |  |
| AWS IoT | 2026-02-17 | 20.6000 | 10.3000 | 12.9687 |  |
| AWS IoT | 2026-02-18 | 19.7000 | 10.3000 | 12.9687 |  |

- Amazon SageMaker: 판단 보류 — 기준선 계산에 필요한 이력이 부족합니다.
- Amazon Simple Storage Service: 판단 보류 — 일별 비용 시계열에 빠진 날짜나 중복 날짜가 있습니다.

## 사용한 기준값

| 기준값 | 값 | 근거 수준 | 출처 |
|---|---|---|---|
| `iot.kb_definitions_bytes` | [5000, 5120] | 공식 자료 | AWS IoT Core pricing: messages metered in 5 KB increments; byte definition unconfirmed, so both are evaluated (experiment 016) |
| `iot.payload_max_bytes` | 1024 | 임시값 | experiments/infrafit-pipeline-ai-rules.md R-IOT-1 |
| `iot.batch_size_limit_bytes` | 4750 | 임시값 | 5% margin under the 5,000 B boundary (experiment 016 H3) |
| `iot.metering_tolerance` | 0.01 | 임시값 | allowed relative gap between metered and expected metered messages |
| `firehose.record_unit_bytes` | 5120 | 공식 자료 | Amazon Data Firehose pricing: billed per GB ingested in 5KB increments |
| `firehose.ratio_keep_below` | 1.5 | 임시값 | experiments/infrafit-pipeline-ai-rules.md R-FH-1 |
| `firehose.ratio_candidate_at` | 3.0 | 임시값 | experiments/infrafit-pipeline-ai-rules.md R-FH-1 |
| `bedrock.supported_profiles` | ["global"] | 공식 자료 | Only Global cross-Region rates for Claude were found in the Seoul price list |
| `bedrock.ttl_seconds` | {"5m": 300, "1h": 3600} | 공식 자료 | Amazon Bedrock prompt caching: 5 minute TTL, 1 hour option |
| `bedrock.min_cache_tokens` | {"Claude Haiku 5.5": 512, "Claude Sonnet 5.5": 512, "Claude Haiku 4.5": 4096, "Claude Sonnet 4.5": null} | 공식 자료 | Bedrock prompt caching supported-models table; Sonnet 4.5 not listed (null = unknown) |
| `bedrock.min_observed_cache_writes` | 20 | 임시값 | minimum cache-write calls before judging a hit ratio |
| `firehose_buffer.max_interval_s` | 900 | 공식 자료 | BufferingHints IntervalInSeconds valid range 0-900 |
| `firehose_buffer.small_object_bytes` | 1048576 | 임시값 | experiments/infrafit-pipeline-ai-rules.md R-FH-2 |
| `firehose_buffer.object_count_tolerance` | 0.5 | 임시값 | allowed relative gap between observed and modeled daily object count |
| `athena.min_billed_mb` | 10 | 공식 자료 | AWS Glue pricing page, Athena: rounded up to the nearest megabyte, 10 MB minimum per query |
| `athena.min_queries` | 10 | 임시값 | minimum successful DML queries before judging a table |
| `athena.full_scan_share` | 0.5 | 임시값 | experiments/infrafit-pipeline-ai-rules.md R-ATH-1 |
| `athena.parquet_scan_reduction` | 0.91 | 실험 확인 | experiment 018: smallest CSV-to-Parquet reduction among queries/layouts (local proxy, not Athena) |
| `athena.small_file_bytes` | 1048576 | 임시값 | experiments/infrafit-pipeline-ai-rules.md R-ATH-2 |
| `sagemaker.gpu_busy_share` | 0.1 | 임시값 | experiments/infrafit-pipeline-ai-rules.md R-SM-1 |
| `sagemaker.cpu_notebook_type` | ml.t3.medium | 실험 확인 | experiment 022 alternative notebook |
| `sagemaker.hours_per_month` | 720 | 실험 확인 | experiment 022 month length; used to prorate training volume storage |
| `sagemaker.serverless_cost_share` | 0.5 | 임시값 | serverless must cost less than this share of the endpoint to become a candidate |
