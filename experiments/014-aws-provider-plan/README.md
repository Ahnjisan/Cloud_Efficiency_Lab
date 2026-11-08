# 014 — AWS provider의 실제 EC2·EBS Plan

[실험 목차](../README.md) · [최종 연구 보고서](../../FINAL-REPORT.md)

Terraform 1.13.5와 HashiCorp AWS provider 5.100.0으로 [구성](main.tf)의 생성 계획을 만들고, `terraform show -json` 출력을 004의 AWS 전용 추출기에 전달한다. 012가 검증한 내장 리소스의 공통 표현과 달리 이번 실험은 AWS provider가 만든 리소스별 필드와 마스크를 확인한다.

**로컬 검증 PASS.** JSON 형식은 1.2였다. EC2의 `t3.micro`와 EBS의 `gp3`, 20 GiB, 3,000 IOPS, 125 MiB/s를 추출했다. 민감 표시된 EC2 인스턴스 유형과 아직 결정되지 않은 EBS 용량은 각각 `sensitive`, `unknown`으로 보류했다. 민감값 원문은 정제 결과에 없었고, Plan 단계에서 루프백 차단 서버가 수신한 요청은 0건이었다. [정제 결과](result.json)

저장소 루트에서 `py -3 -B experiments/014-aws-provider-plan/run.py <terraform.exe 경로>`를 실행한다. [실행 코드](run.py)

provider 설치에는 Terraform Registry가 필요하다. Plan 단계에서는 사용자 AWS 환경변수를 제거하고 가상 자격 증명만 전달한다. EC2·IAM·STS 주소와 HTTP(S) 프록시는 요청을 거절하는 임시 루프백 서버로 지정하고, 메타데이터·계정·자격 증명 조회와 refresh를 끈다. Plan은 적용하지 않으며 원본 Plan과 JSON은 저장소에 남기지 않는다. [공식 provider 배포본](https://releases.hashicorp.com/terraform-provider-aws/5.100.0/)

`py -3 -B experiments/014-aws-provider-plan/run.py --check-loopback`은 Terraform을 실행하지 않고 루프백에서 HTTP GET과 프록시 CONNECT를 검사한다. 두 요청 모두 403으로 거부됐고 서버 기록과 일치했다. [차단 검증 결과](loopback-check.json)

기존 Plan 결과의 수신 0건과 이번 루프백 검증은 별도 관측이다. 새 Plan 실행은 같은 차단 서버의 사전 점검을 거친 뒤 provider 요청만 별도로 센다. 직접 외부 연결에 대한 OS 수준 방화벽 검증이나 네트워크 캡처는 수행하지 않았다.

실제 AMI와 계정 검증, AWS에 존재하는 상태를 읽는 갱신·삭제·교체 Plan, 다른 provider 버전 및 실제 청구 대사는 별도 범위다.
