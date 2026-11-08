# InfraFit 개발 전 통합 연구 결과

[실행 환경·안전 조건](infrafit-preflight-context.md) · [명령과 종료 코드](infrafit-execution-log.json)

저장소 루트에서 `py -3 -B experiments/reproduce-infrafit.py`를 실행하면 001 원본은 보존하면서 Python 실험의 결과를 순서대로 다시 생성한다. 이 명령은 Docker·Kubernetes 실측을 실행하지 않는다.

리뷰 보정 후 기존 결과 파일을 제외한 별도 임시 디렉터리에서 같은 명령을 실행했다. 여섯 실험 모두 종료 코드 0이었으며, 생성된 stdout 6개가 저장소에 기록한 최종 출력과 바이트 단위로 일치했다.

## A. 전체 실험 현황

| 실험 | 상태 | 데이터와 결과 | 남은 한계 |
|---|---|---|---|
| 001 · EBS 규칙 재현 | PASS | 기존 합성 볼륨 8건·충돌 2건 재실행. [이번 stdout](001-reproduction.stdout.txt) | 기존 사례 재현 |
| 002 · 신규 반례 | PASS | 신규 합성 11건에서 오탐 4→1, 즉시 재현율 75→25%. [실험](002-ebs-rule-robustness/README.md) | 운영 정확도·조사 시간 미측정 |
| 003 · 비용 | PASS | 가상 8개 시나리오와 EBS 중복·누락 ID 보류 확인. 최초 입력 불일치 실패는 로그에 보존. [실험](003-aws-cost-simulation/README.md) | 가격·약정 모형 제한 |
| 004 · Terraform | PASS | 합성 Plan 11행→주소별 결과 10개, 민감도 마스크 누락·오류 시 값 미출력 및 보류 확인. [실험](004-terraform-evidence/README.md) | 실제 Plan·버전·provider 미검증 |
| 005 · Docker | 실측 PASS | 격리된 로컬 컨테이너에서 CPU 한도별 2회씩 완료. [실험](005-container-resource-efficiency/README.md) | 3 VU 한도에서 누락된 반복 포함, 실제 AWS 비용 미검증 |
| 006 · Kubernetes | 정적 PASS / 실측 PASS | 가상 노드 비교, 전용 Minikube의 큰·작은 Requests 배치와 CPU Limits별 HTTP 부하 완료. [실험](006-kubernetes-resource-efficiency/README.md) · [실측](006-kubernetes-resource-efficiency/live.md) | 완성된 부하 비교는 조건당 1회, 실제 노드 축소·청구 미검증 |
| 007 · 통합 분석 | PASS | 합성 사례 6건, 가격 근거 불일치 및 잘못된 품질 수치의 보류 확인. [실험](007-infrafit-feasibility/README.md) | 실제 수집·조인·운영 품질 미검증 |

PASS는 해당 검증의 기대 동작을 재현했다는 뜻이다. 특정 탐지 규칙이 우수하거나 운영 변경이 승인됐다는 판정과 구분한다.

## B. 낭비 탐지

001의 A/B는 TP/FP/FN/TN이 2/1/1/2와 2/0/1/3으로 기존 기록과 같았다. 002에서는 보존이 필요한 볼륨의 오탐을 줄였지만, 확정 낭비를 보류한 1건과 연결된 중복·오래된 근거에 의한 미탐 2건이 남았다. 초기 대기열 9→6건은 조사 건수 차이다. 시간 절감은 측정하지 않았다.

## C. AWS 비용

기존 ADR의 $129.20 / $100.40 / $117.20을 독립 산식으로 확인했다. 새 사례에서는 EC2 중지 뒤 월 $8의 EBS가 남고, 고정 약정 사례는 두 구성 모두 $94.40이다. 동일 월 비용도 업무량이 다르면 단위 비용과 결론이 달라진다. $72 차이가 있어도 품질이 누락된 후보는 보류했다.

## D. Terraform 변경 근거

EC2 유형과 EBS 크기·유형·성능 설정을 제한적으로 추출했다. 교체 순서 두 종류를 인식하고, 미지원 리소스와 중복 주소를 분리했다. 민감 속성 원문은 출력하지 않았고 미확정 EBS 크기는 비용 입력으로 넘기지 않았다. 실제 Terraform 명령·State·AWS provider는 사용하지 않았다.

## E. Docker 실측

이전 시도는 호스트 시작 기준 5 GiB에 못 미쳐 차단했다. 사용자 요청 이후 제한된 순차 실행으로 같은 HTTP 워크로드에서 CPU 1.0과 0.5를 두 번씩 비교했다. 1코어에서 성공 처리량은 약 24.93~24.98 req/s, 0.5코어에서 약 10.28~10.69 req/s였다. p99는 각각 45.36~74.09 ms, 460.95~495.57 ms였다. 0.5코어에서 k6가 시작하지 못한 반복은 428~441건이며 전송된 요청의 HTTP 오류는 0건이었다. cgroup throttling, 메모리, 재시작·OOM 결과는 [실험 기록](005-container-resource-efficiency/README.md)에 남겼다.

## F. Kubernetes

정적 모델의 Small 노드는 Requests를 줄일 때 2→1대, Large는 1→1대였다. 최종 로컬 실측에서 작은 Requests의 Pod 두 개는 모두 배정됐고, 큰 Requests는 한 개가 `Insufficient cpu`로 미배정됐다. CPU Limits 1,000m와 500m에서 성공 처리량은 각각 24.77과 9.35 req/s, p99는 110.15와 484.99 ms였다. 시작하지 못한 반복은 7건과 468건이며 전송된 요청의 HTTP 오류는 0건이었다. 실제 노드 축소와 AWS 청구는 미측정이다. [후속 실측](006-kubernetes-resource-efficiency/live.md)

기존 시작 기준에서 차단한 기록은 보존했다. 사용자 요청 이후 두 실험은 축소한 시작 하한과 호스트 중단 하한 1.5 GiB를 적용해 순차 실행했다. Docker 컨테이너와 Minikube 전용 자원을 각각 정리했다. [재점검과 최종 실행](006-kubernetes-resource-efficiency/live.md#저메모리-후속-실행)

## G. InfraFit에 활용할 근거

- **검증한 부분**은 좁은 범위의 금액 산술, 비용 키 중복 거부, 합성 Plan의 선택 필드 추출·민감값 제외, 출처와 결측을 유지한 후보·유지·보류 분리다.
- **추가 검증할 부분**은 오래된 증거의 판정 영향, 운영 사용량·시간대가 달라질 때의 비용 민감도, 실제 Scheduler 동작, 피크 품질이다.
- **별도 구현이 필요한 부분**은 청구 행과 자원 ID의 실제 매핑, 기간별 재대사, 도구별 스키마 검증, 관측 데이터 수집, 사람이 승인하고 결과를 확인하는 워크플로다. 이번 실험으로 제품 아키텍처를 확정하지 않는다.

### 기존 방법과의 연결

- AWS Compute Optimizer는 사용량 기반 추천을 제공하고 Cost Optimization Hub는 여러 소스의 기회를 종합한다. 이 연구의 고정 사례는 추천 엔진의 실제 입력과 평가를 재현하지 않는다. [Compute Optimizer](https://docs.aws.amazon.com/compute-optimizer/latest/ug/what-is-compute-optimizer.html) · [Cost Optimization Hub](https://docs.aws.amazon.com/cost-management/latest/userguide/cost-optimization-hub.html)
- Kubernetes Scheduler의 Requests 관점과 VPA의 요청 조정은 006의 문제와 연결된다. 정적 배치 모델은 스케줄링 정책·VPA 동작과 실제 관측 기간을 재현하지 않는다. [Kubernetes 자원 관리](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/) · [VPA](https://kubernetes.io/docs/concepts/workloads/autoscaling/vertical-pod-autoscale/)
- Terraform JSON의 변경·unknown·민감도 표현은 004의 근거이며, FinOps의 관측·최적화·운영 관점은 가상 비용 차이와 검증된 절감을 구분하는 데 적용했다. [Terraform JSON format](https://developer.hashicorp.com/terraform/internals/json-format) · [FinOps Framework](https://www.finops.org/framework/)
- CherryPick은 공식 초록에서 베이지안 최적화로 분석 작업의 구성을 탐색한다. Autopilot은 저자 공개본의 초록과 제어 구조 부분에서 태스크 수와 CPU·메모리 제한을 함께 조정한다. 여기서는 고정 합성 사례의 제약을 평가했으며 논문을 재현하거나 성능을 비교하지 않았다. [CherryPick](https://www.usenix.org/conference/nsdi17/technical-sessions/presentation/alipourfard) · [Autopilot](https://john.e-wilkes.com/papers/2020-EuroSys-Autopilot.pdf) · [기존 논문 목록](../references/papers.md)

## H. 후속 질문

1. 소유·복구 기록의 최신성을 검증하면 오탐과 보류의 비용이 어떻게 바뀌는가?
2. 실제 청구 행·Plan 주소·워크로드 관측의 키와 시간 범위가 맞지 않을 때 어디에서 보류할 것인가?
3. 전용 환경에서 동일한 부하를 반복했을 때 CPU 제한과 Pod 배치가 지연·오류·재시작에 주는 영향은 무엇인가?

## I. 후속 실험 결과

| 실험 | 검증 결과 | 남은 검증 |
|---|---|---|
| [008 · 근거 대사](008-evidence-reconciliation/README.md) | 합성 입력의 시점·ID 매칭, 늦은 행 재대사, 중복 재입력 및 충돌 보류 | 실제 청구·Plan의 자원 매핑과 기간별 재대사 |
| [009 · EBS 보류 비용](009-ebs-review-cost/README.md) | 기존 11건에서 최신성 기준에 따른 오탐·보류와 가상 검토 시간 비교 | 독립 표본과 담당자 검토 시간 |
| [010 · CPU 품질 기준](010-cpu-quality-envelope/README.md) | 보존된 Docker·Kubernetes 로그의 p99와 제공 부하 대비 성공률을 함께 평가 | 전용 환경의 반복 실측과 부하 수준별 품질 경계 |
| [011 · 비용·품질 민감도](011-cost-quality-sensitivity/README.md) | 가상 135개 조합에서 약정 적용 시간·전환비·품질에 따른 채택 조건 확인 | 실제 약정·피크 관측 및 복구 조건 |

008–011은 통합 재현 명령에 포함했다. 010은 보존 로그를 읽으며 새 클러스터를 실행하지 않는다.

| 추가 실험 | 검증 결과 | 남은 검증 |
|---|---|---|
| [012 · 실제 Terraform Plan](012-terraform-plan-compatibility/README.md) | Terraform 1.13.5의 내장 리소스 Plan에서 교체 순서·모듈 주소·민감도·미확정 값 처리 확인 | AWS provider 속성과 다른 Terraform 버전 |
| [013 · 피크 롤백](013-peak-rollback/README.md) | 전용 Docker 컨테이너에서 CPU 1.0 → 0.25 → 1.0 변경 후 품질 통과 → 위반 → 통과 관측 | 반복 편차, Kubernetes·EC2 운영 롤백과 데이터 복구, 실제 청구 |

012와 013은 각각 Terraform 실행 파일과 Docker·k6가 필요한 별도 명령으로 재현한다.

## J. AWS provider와 Kubernetes 후속 검증

- [014 · AWS provider의 실제 EC2·EBS Plan](014-aws-provider-plan/README.md)에서 AWS provider 5.100.0이 생성한 JSON을 004에 직접 연결했다. 생성 계획의 비용 관련 필드 추출과 민감·미확정 값 보류를 확인했다. 기존 AWS 상태에 대한 갱신·삭제·교체 계획은 미검증이다.
- [015 · Kubernetes 반복 부하와 Deployment 롤백](015-kubernetes-rollback/README.md)에서 전용 Minikube의 세 시퀀스를 완료했다. 복원 후 p99는 3회 모두 기준 이내였고, 기준 → 위반 → 복원 구간의 전체 품질 기준은 1회만 재현했다.

실제 청구 행의 자원 매핑, 약정 상계 및 청구 합계 대사는 비식별 청구 자료가 필요하므로 미검증으로 남긴다.
