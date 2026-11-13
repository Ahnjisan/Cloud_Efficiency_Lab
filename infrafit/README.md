# InfraFit 읽기 전용 MVP

로컬 합성 청구 행, Terraform Plan JSON, 후보별 피크 관측을 연결해 **변경 검토 후보·유지·판단 보류**와 이유를 출력한다. Python 표준 라이브러리를 사용하고 입력 파일은 읽기만 한다. 실제 청구 대사는 미검증이다.

[최종 연구 보고서](../FINAL-REPORT.md)에서 실험 001~022, 종단 간 테스트 11개와 워크로드 규칙 테스트 19개의 최종 검증 범위와 실제 청구 자료가 필요한 다음 단계를 확인할 수 있다.

```powershell
py -3 -B infrafit/cli.py
py -3 -B infrafit/cli.py --json
py -3 -B infrafit/cli.py --as-of 1
py -3 -B infrafit/test_cli.py -v
py -3 -B infrafit/cli.py --workloads infrafit/workloads.json
py -3 -B infrafit/test_workload_rules.py -v
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

나머지 규칙 후보(R-FH-2, R-ATH-1, R-ATH-2, R-SM-1, R-COST-1)는 구현하지 않았다. R-COST-1은 자원 판정이 아니라 조사 대기열을 만드는 규칙이라 출력 구조가 다르다. R-FH-2는 하류 신선도 요구와 일별 객체 통계, R-ATH-1·2는 Athena 쿼리 기록, R-SM-1은 커널 활동·GPU 사용률이 필요하다. 이 자료들은 합성 입력으로 흉내 내면 판정 근거가 약해지므로, 실제 계정에서 수집 형식을 정한 뒤 구현한다.

