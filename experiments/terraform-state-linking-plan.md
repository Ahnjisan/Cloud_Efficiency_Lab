# Terraform 주소 ↔ 실제 자원 ID 자동 연결 설계

[실험 목차](README.md) · [InfraFit](../infrafit/README.md) · [구성 연결 근거](../infrafit/config-basis.json) · [004 Terraform 변경 근거](004-terraform-evidence/README.md) · [012 실제 Plan JSON](012-terraform-plan-compatibility/README.md)

**상태: 설계와 합성 state 테스트까지 완료. 실제 state로는 확인하지 않음.** 실제 프로젝트의 Terraform 자원이 생기면 이 문서의 "실제 state로 확인할 점"을 다시 확인한다.

## 문제

지금 InfraFit은 Terraform 주소(`aws_instance.orders`)와 청구·관측의 자원 ID(`i-orders`)를 [config-basis.json](../infrafit/config-basis.json)에 사람이 적어 연결한다. Plan JSON의 `resource_changes`에는 변경 전후 속성만 있고, 자원 ID가 늘 들어 있지는 않다(새로 만드는 자원은 ID가 미확정이다). 그래서 실제 자원이 생긴 뒤에는 state에서 주소와 ID를 읽는 편이 정확하다.

## 입력 (공식 형식, 2026-11-14 확인)

[Terraform JSON Output Format](https://developer.hashicorp.com/terraform/internals/json-format)의 state 표현을 읽는다.

| 입력 | 위치 | 읽는 필드 |
|---|---|---|
| `terraform show -json` (apply 후 state) | 최상위 `values.root_module` | `resources[].address`, `mode`, `type`, `values.id`, `sensitive_values.id` |
| Plan JSON | `prior_state.values.root_module` | 위와 같음 |
| 하위 모듈 | `child_modules[]` (같은 구조, 재귀) | 위와 같음 |

state 파일(`terraform.tfstate`)을 직접 읽지 않고 `terraform show -json` 출력을 읽는다. 공식 문서가 안정된 형식으로 정의한 것은 JSON 출력이다.

## state의 민감값을 다루는 규칙 (구현보다 먼저 정함)

공식 문서에 따르면 `values`에는 속성 값이 그대로 들어 있고, 민감 여부는 `sensitive_values`에 따로 표시된다. 그래서 state 출력에는 비밀번호·사용자 데이터 같은 민감값이 평문으로 있을 수 있다.

1. **허용 필드만 읽는다.** `address`, `mode`, `type`, `values.id`만 꺼낸다. 다른 속성은 변수에도 담지 않고, 출력·경고·오류 메시지에도 쓰지 않는다.
2. **민감 표시된 ID는 쓰지 않는다.** `sensitive_values.id`가 `true`면 그 자원을 건너뛰고 `id-sensitive` 경고만 남긴다. 경고에는 주소만 쓴다.
3. **데이터 소스는 제외한다.** `mode`가 `data`인 항목은 실제로 관리하는 자원이 아니라서 연결하지 않는다.
4. **모호하면 연결하지 않는다.** 같은 주소가 두 번 나오면 둘 다 버리고 `address-duplicate` 경고를 남긴다. ID가 없으면 `id-missing`.
5. **state 출력은 저장소 밖에 둔다.** 실제 `terraform show -json` 결과와 그것으로 만든 연결 목록은 커밋하지 않는다. 저장소에는 합성 state만 둔다([terraform-show.json](../infrafit/convert-examples/terraform-show.json)).
6. **자동으로 바꾸지 않는다.** 결과는 `config-basis.json`의 후보다. 사람이 확인한 뒤에 옮긴다. 이 도구는 Terraform 명령도 실행하지 않는다(자격 증명이 필요한 `terraform show`는 사람이 실행한다).

## 출력

[tf_links.py](../infrafit/tf_links.py)는 다음을 출력한다.

- `links`: 주소 → `{resource, type}`
- `warnings`: `id-sensitive`, `id-missing`, `address-duplicate`, `no-state-values`
- `--changes`를 주면 `comparison`: 변경 기록(008 형식)의 주소마다 다음 중 하나
  - `match`: state의 ID와 변경 기록의 `resource`가 같음
  - `mismatch`: 다름(예: 자원이 교체돼 ID가 바뀜)
  - `address-not-in-state`: state에 그 주소가 없음
  - `state-only`: state에는 있지만 변경 기록이 없음

```powershell
terraform show -json > <저장소 밖>\state.json      # 사람이 실행
py -3 -B infrafit/tf_links.py <저장소 밖>\state.json --changes <변경 기록>.json
py -3 -B infrafit/test_tf_links.py -v
```

`cli.py`에는 아직 연결하지 않았다. 실제 state로 동작을 확인한 뒤 `--state` 옵션으로 붙일지 정한다. 붙인다면 `mismatch`·`address-not-in-state`인 주소는 판단 보류로 둔다.

## 합성 테스트 (test_tf_links.py 7개, 모두 통과)

- 관리 자원 4개(하위 모듈의 `count` 인덱스 주소 포함)의 주소·ID 연결
- 데이터 소스 제외, 민감 ID 건너뛰기, ID 없는 자원 경고
- 출력에 민감값이 없는지: 다른 속성값, 출력값, 민감 ID, ARN 안의 계정 ID가 나오지 않는다
- 008 변경 기록과 비교: `match` 2, `mismatch` 1, `address-not-in-state` 2, `state-only` 1
- 사람이 적은 `config-basis.json`의 자원 ID와 일치
- Plan JSON의 `prior_state` 읽기, state가 없는 입력, 중복 주소 버리기

## 실제 state로 확인할 점 (남은 일)

1. AWS provider의 자원 유형별로 `values.id`가 청구·지표의 자원 ID와 같은 형식인가? EC2는 `i-…`, EBS는 `vol-…`로 예상되지만, Firehose·Glue·SageMaker처럼 ID가 이름이거나 ARN인 자원은 청구 행의 `resource_id`와 형식이 다를 수 있다. 확인 전까지는 EC2·EBS만 지원 범위로 둔다.
2. `for_each` 주소(`["key"]`)와 모듈 중첩이 실제 출력에서 테스트와 같은 모양인가?
3. state 출력에 실제로 어떤 민감 속성이 평문으로 들어오는가? 규칙 1이 막는지 실제 파일로 다시 확인한다.
4. 원격 state(S3 백엔드 등)를 읽을 때 필요한 권한이 읽기 전용 정책 범위 안인가? `terraform show`는 state 읽기 권한이 필요하다. 이 권한은 지금 `cel-readonly`에 없다.
