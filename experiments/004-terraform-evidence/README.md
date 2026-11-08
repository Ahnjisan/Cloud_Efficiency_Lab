# 004 — Terraform 변경 근거 추출

[실험 목차](../README.md) · [최종 연구 보고서](../../FINAL-REPORT.md) · [실제 AWS provider 생성 Plan](../014-aws-provider-plan/README.md)

가설은 Plan JSON에서 EC2·EBS 비용 모델에 필요한 일부 변경 속성을 추출할 수 있지만, 값이 미확정·민감·중복이면 계산을 보류해야 한다는 것이다. 기준은 [HashiCorp JSON Output Format](https://developer.hashicorp.com/terraform/internals/json-format)의 변경 표현과 [show](https://developer.hashicorp.com/terraform/cli/commands/show)·[plan](https://developer.hashicorp.com/terraform/cli/commands/plan) 문서다. 입력은 공식 구조 일부를 따르는 [합성 Plan JSON](plan.json)이며 실제 State나 Plan에서 추출하지 않았다.

Windows 11, Python 3.14.7에서 `py -3 -B experiments/004-terraform-evidence/analyze.py`를 실행했다. 종료 코드 0. [원본 JSON](result.json) · [실행 로그](../infrafit-execution-log.json)

- 입력 11행을 주소 기준 10개 결과로 표현했다. `no-op`, `create`, `update`, `delete`, 두 순서의 `replace`를 확인했다. 교체는 한 변경으로 남기며 전환 시 동시 가동 비용은 별도 근거가 필요하다.
- EC2의 `instance_type`과 EBS의 `type/size/iops/throughput`만 꺼냈다. EBS 용량 미확정은 계산 보류, 미지원 S3 행은 미지원, 중복 주소는 비용 후보에서 제외한다.
- 전후 민감도 마스크가 지정된 값과 허용 목록 밖의 속성은 원문을 출력하지 않았다. 값이 있는 쪽의 마스크가 누락되거나 형식이 잘못되면 해당 쪽 값을 전부 숨기고 보류한다. 마스크 누락과 잘못된 형식 두 반례에서 합성 민감값 표식이 출력되지 않음을 확인했다. 지원하지 않는 JSON 포맷 버전은 거부했다.

이 추출기는 구조가 정해진 연구용 스칼라 입력에 한정된다. `resource_drift`는 건수만 표시하고, 이동·deposed·가져오기·임의 provider 확장과 실제 버전별 호환성은 검증하지 않았다. 입력 파일 자체가 안전해지는 것은 아니다. Terraform CLI는 설치돼 있지 않았고 provider 조회도 하지 않았다. 다음 질문은 이동이나 교체가 있을 때 청구 자원 ID와 중복 없는 계보를 어떻게 연결할 것인가이다.
