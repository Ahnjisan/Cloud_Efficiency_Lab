# 012 — 실제 Terraform Plan JSON 호환성

[실험 목차](../README.md) · [최종 연구 보고서](../../FINAL-REPORT.md)

**로컬 검증 PASS.** Terraform 1.13.5에서 내장 `terraform_data`만 사용했다. 임시 디렉터리에 로컬 상태를 만든 뒤, 입력 세대를 1에서 2로 바꾼 계획을 생성하고 `terraform show -json`의 출력을 메모리에서 검사했다. 교체 계획은 적용하지 않았다. AWS provider, 원격 backend, AWS API는 사용하지 않았다.

| 검증 항목 | 관측 |
|---|---|
| Plan JSON 형식 | `format_version` 1.2 |
| 모듈 주소 | `module.fixture.terraform_data.*`의 두 주소 유지 |
| 교체 순서 | 삭제 후 생성과 생성 후 삭제가 각각 나타났으며, 004의 공통 매핑에서 둘 다 `replace` |
| 아직 결정되지 않은 값 | 공개 입력 리소스의 새 `id`와 `output`을 `unknown`으로 분류 |
| 민감 속성 | 실제 마스크를 통해 선택 입력을 `sensitive`로 분류하고 원문이 결과에 없는지 확인 |
| AWS 전용 추출기 | 004에 실제 Plan을 그대로 전달하면 내장 리소스 두 건을 `unsupported`로 분류 |

[실행 코드](run.py) · [입력 구성](main.tf) · [모듈](fixture/main.tf) · [정제 결과](result.json)

AWS provider의 EC2·EBS 생성 계획은 [014 후속 실험](../014-aws-provider-plan/README.md)에 따로 기록했다.

저장소 루트에서 `py -3 -B experiments/012-terraform-plan-compatibility/run.py <terraform.exe 경로>`를 실행한다. Windows amd64 공식 배포본의 SHA-256을 릴리스 목록과 대조했다. 원본 Plan JSON과 상태에는 민감 표시가 붙은 값도 들어갈 수 있어 임시 영역에서만 사용한다. 결과는 004의 필드 처리 함수를 내장 리소스의 실제 마스크에 직접 적용한 출력이다. Terraform 다른 버전과 기존 AWS 자원의 갱신·삭제·교체 Plan은 미검증이다. [공식 배포본](https://releases.hashicorp.com/terraform/1.13.5/) · [JSON 형식](https://developer.hashicorp.com/terraform/internals/json-format) · [내장 리소스](https://developer.hashicorp.com/terraform/language/resources/terraform-data)
