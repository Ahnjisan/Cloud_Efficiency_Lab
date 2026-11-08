# Cloud Efficiency Lab — 최종 연구 보고서

[프로젝트 README](README.md) · [실험 목차](experiments/README.md) · [InfraFit 실행 방법](infrafit/README.md)

## 연구 결론

비용을 줄일 수 있는 구성이라도, 같은 업무량에서 품질 기준을 충족하고 청구 근거가 연결되어야 변경 검토 후보로 볼 수 있다. 이 프로젝트는 그 조건을 합성 청구·Terraform Plan·관측 데이터와 제한된 로컬 실측으로 확인했다. 연구와 읽기 전용 MVP의 현재 범위는 마무리했다. 실제 청구 대사와 운영 환경에서의 실현 절감은 미검증이다.

## 실험 001~015

| 실험 | 검증 결과 | 적용 범위 |
|---|---|---|
| [001 · EBS 낭비 탐지](experiments/001-ebs-waste-rules/README.md) | 합성 볼륨 8건과 충돌 우선순위 2건을 재현했다. 소유·복구 근거를 포함한 규칙에서 오탐이 1건에서 0건으로 줄었다. | 가상 표본 |
| [002 · EBS 신규 반례](experiments/002-ebs-rule-robustness/README.md) | 합성 11건에서 오탐 4→1건, 즉시 재현율 75→25%를 확인했다. | 운영 정확도 미측정 |
| [003 · EC2·EBS 비용 모형](experiments/003-aws-cost-simulation/README.md) | 가상 8개 시나리오와 EBS ID 누락·중복 보류를 검증했다. | 합성 요율과 약정 |
| [004 · Terraform 변경 근거](experiments/004-terraform-evidence/README.md) | 합성 Plan에서 EC2·EBS의 선택 필드를 추출하고 민감·미확정·중복 입력을 분리했다. | 합성 Plan |
| [005 · Docker CPU 한도](experiments/005-container-resource-efficiency/README.md) | 1.0과 0.5 CPU에서 각 2회 측정했다. 낮은 한도에서 지연과 미시작 반복이 늘고 성공 처리량이 줄었다. | 로컬 HTTP 워크로드 |
| [006 · Kubernetes 자원 검증](experiments/006-kubernetes-resource-efficiency/README.md) | Requests에 따른 실제 Pod 배치 차이와 1,000m·500m Limits의 부하 결과를 확인했다. | 단일 전용 Minikube, 노드 비용은 가상 |
| [007 · 통합 판정](experiments/007-infrafit-feasibility/README.md) | 합성 6건에서 비용·품질·결측·중복을 근거로 후보·유지·보류를 구분했다. | 실제 데이터 수집 미검증 |
| [008 · 근거 대사](experiments/008-evidence-reconciliation/README.md) | 자원·구성·기간이 일치할 때만 피크 관측을 사용했다. 지연 도착에 따른 재판정과 중복 입력의 이중 집계 방지를 확인했다. | 명시적 매핑을 사용한 합성 대사 |
| [009 · EBS 보류 비용](experiments/009-ebs-review-cost/README.md) | 최신성 기준 없음·90일·30일의 가상 검토 시간은 각각 55·90·100분이었다. | 검토자의 실제 소요 시간 미측정 |
| [010 · CPU 품질 기준](experiments/010-cpu-quality-envelope/README.md) | 기존 로그를 p99·오류율·제공 부하 대비 성공률로 재평가했다. | 보존 로그 분석, 후속 반복은 015 |
| [011 · 채택 민감도](experiments/011-cost-quality-sensitivity/README.md) | 가상 135개 조합에서 후보 9건·유지 81건·보류 45건을 분류했다. | 전환비 포함 첫 달 모형 |
| [012 · 실제 Terraform Plan JSON](experiments/012-terraform-plan-compatibility/README.md) | Terraform 1.13.5 내장 리소스로 모듈 주소, 두 교체 순서, 민감도와 미확정 값 처리를 검증했다. | 내장 리소스 |
| [013 · Docker 롤백](experiments/013-peak-rollback/README.md) | CPU 1.0→0.25→1.0에서 p99 104.31→893.47→35.85ms를 관측했다. 복원 후 첫 창에서 품질 기준을 다시 충족했다. | 전용 컨테이너 1회, 최초 회복 시각 미측정 |
| [014 · AWS provider Plan](experiments/014-aws-provider-plan/README.md) | AWS provider 5.100.0의 실제 EC2·EBS 생성 Plan에서 비용 관련 필드를 추출했다. 민감·미확정 값은 보류했다. | 루프백 차단을 사용한 로컬 Plan. 기존 AWS 자원의 갱신·삭제·교체 미검증 |
| [015 · Kubernetes 롤백](experiments/015-kubernetes-rollback/README.md) | 3회 모두 복원 후 p99가 기준으로 돌아왔다. 성공률까지 포함한 전체 품질 회복은 **1/3회**였다. | 전용 단일 노드, 운영 자동 롤백과 RTO·RPO 미검증 |

실험 PASS는 해당 입력과 절차에서 결과가 검증됐음을 뜻한다. 원본과 재현 방법은 실험별 문서에 연결돼 있다.

## InfraFit MVP

읽기 전용 Python CLI는 청구 행, Terraform Plan JSON, 피크 관측을 명시적 자원·기간·후보 구성 매핑으로 연결한다. 결과에는 변경 검토 후보·유지·판단 보류, 판정 이유, 확인된 가상 비용과 p99가 포함된다.

| 기본 예제 | 판정 | 근거 |
|---|---|---|
| 주문 서비스 | 변경 검토 후보 | 가상 $120→$100, 피크 p99 180ms |
| 작업자 서비스 | 유지 | 가상 비용은 감소하지만 피크 p99 250ms로 기준 200ms 초과 |
| 기타 3개 주소 | 판단 보류 | 청구 충돌·누락, 관측 또는 Plan 근거 부족 |

마지막 독립 리뷰에서 종단 간 테스트 **11개**가 통과했다. 중복 청구 재입력, 지연 도착, 구성 불일치, 민감값 미출력, 복합 누락에도 보고서가 유지되는 동작을 확인했다. 비용 관련 전후 속성이 확인되는 EC2·EBS 갱신이 MVP 지원 범위다. Terraform 주소와 실제 클라우드 자원 ID의 자동 매핑, 운영 승인과 변경 적용은 검증 범위 밖이다. [MVP 문서](infrafit/README.md)

## 실제 청구 자료 확보 후의 검증

1. **한 청구 기간을 읽기 전용으로 대사한다.** 비식별 청구 행, 자원 ID 매핑, 변경 시점과 관측 기간을 준비한다. 중복·누락·늦은 행을 분리하고, 매핑되지 않은 금액과 설명되지 않은 차이를 포함해 원본 청구 합계에 맞춘다.
2. **약정 반영액을 확인한다.** 적용 사용 행·상계 행·약정료를 같은 기준으로 비교하고, 남는 약정이 같은 시간대의 다른 적격 사용에 적용됐는지 확인한다.
3. **변경 전후가 비교 가능한 경우 실현 절감을 검증한다.** 업무량·품질·가격·기간을 맞추고 전환비를 포함한다. Kubernetes 노드 축소 효과를 청구 절감으로 연결하려면 실제 노드 수와 동일 기간 청구 내역도 필요하다.

실제 청구 외의 후속 검증은 AWS provider의 추가 변경 유형·버전, 독립 EBS 사례의 검토 시간, 운영 환경의 복구와 자동 롤백을 지원할 때 수행한다. [상세 연구 기록](experiments/infrafit-predevelopment-review.md)
