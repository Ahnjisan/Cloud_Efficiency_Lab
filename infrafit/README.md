# InfraFit 읽기 전용 MVP

로컬 합성 청구 행, Terraform Plan JSON, 후보별 피크 관측을 연결해 **변경 검토 후보·유지·판단 보류**와 이유를 출력한다. Python 표준 라이브러리를 사용하고 입력 파일은 읽기만 한다. 실제 청구 대사는 미검증이다.

[최종 연구 보고서](../FINAL-REPORT.md)에서 실험 001~015, 종단 간 테스트 11개의 최종 검증 범위와 실제 청구 자료가 필요한 다음 단계를 확인할 수 있다.

```powershell
py -3 -B infrafit/cli.py
py -3 -B infrafit/cli.py --json
py -3 -B infrafit/cli.py --as-of 1
py -3 -B infrafit/test_cli.py -v
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
