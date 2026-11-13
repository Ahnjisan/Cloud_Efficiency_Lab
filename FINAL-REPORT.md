# Cloud Efficiency Lab — 최종 연구 보고서

[프로젝트 README](README.md) · [실험 목차](experiments/README.md) · [InfraFit 실행 방법](infrafit/README.md)

## 연구 결론

비용을 줄일 수 있는 구성이라도, 같은 업무량에서 품질 기준을 충족하고 청구 근거가 연결되어야 변경 검토 후보로 볼 수 있다. 실험 016~022에서는 같은 원칙을 IoT 파이프라인·생성형 AI·모델 학습으로 넓혀, 데이터 신선도와 캐시 적중률 같은 품질·운영 조건이 판정을 바꾸는 지점을 계산과 합성 데이터로 확인했다. 이 프로젝트는 그 조건을 합성 청구·Terraform Plan·관측 데이터와 제한된 로컬 실측으로 확인했다. 연구와 읽기 전용 MVP의 현재 범위는 마무리했다. 실제 청구 대사와 운영 환경에서의 실현 절감은 미검증이다.

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

## 실험 016~022 — IoT 파이프라인·생성형 AI·모델 학습

실제 프로젝트에서 운영할 IoT 센서 파이프라인(센서 → IoT Core → Firehose → S3 → Glue/Athena), Bedrock 에이전트, 이상탐지 모델 학습의 비용 구조를 InfraFit 규칙으로 옮기기 전에 확인했다. AWS 계정 없이 로컬·합성·계산으로만 수행했다. 요율은 AWS Price List의 서울 리전 공개 On-Demand 요율(2026-11-13 확인)이다.

| 실험 | 검증 결과 | 적용 범위 |
|---|---|---|
| [016 · IoT 메시지 묶음](experiments/016-iot-message-batching/README.md) | 200 B 측정값을 20건씩 묶으면 메시지·규칙·액션 비용이 95% 줄고 최대 190초 늦어졌다. 묶음이 5 KB를 넘는 26건에서는 25건보다 비용이 36% 늘었다. 4,000 B 페이로드는 20%만 줄었다. | 결정적 계산, 5 KB 바이트 정의 미확인 |
| [017 · Firehose 버퍼](experiments/017-firehose-buffer-small-files/README.md) | 초당 2 KB에서 버퍼 60→900초는 하루 조회 객체 수를 1/15로, PUT 비용을 월 0.18 USD 줄였고 레코드 평균 대기를 30→450초로 늘렸다. 1 MiB 버퍼에서는 크기 조건이 먼저 닫혀 가설이 부분 기각됐다. | 1초 단위 시뮬레이션, 압축 전 크기 |
| [018 · 형식·파티션 스캔량](experiments/018-format-partition-scan/README.md) | CSV를 Parquet으로 바꾸면 대표 쿼리 5개의 읽은 바이트가 일별 파일에서 98% 이상, 5분 파일에서 91% 이상 줄었다. Parquet 이후의 차이는 대부분 10 MB 최소 과금 아래에 있었다. 다만 Firehose식 5분 파일은 일별 파일보다 저장 크기 4.1배, 한 달 쿼리 읽은 바이트 최대 71배였다. | 로컬 대리 측정, Athena 실측 아님 |
| [019 · 파이프라인 단위 비용](experiments/019-pipeline-unit-cost/README.md) | 1,000건당 비용이 0.003675→0.000123 USD(3.3%)로 줄고 최대 신선도는 60→490초로 나빠졌다. 기준 구성의 비용 1위는 가정 쿼리량에 따라 IoT Core에서 Athena로 바뀌어, IoT가 50%를 넘는다는 가설은 기각됐다. | 016~018 결과와 가정 쿼리량의 합성 |
| [020 · Bedrock 캐싱](experiments/020-bedrock-token-caching/README.md) | 실행당 호출 2회 이상이면 5분 캐싱이 항상 이득이었다(최소 11.1%). 손해는 단발 호출이 드문 경우뿐이었다. 1시간 TTL이 평균 간격 5~60분에서만 유리하다는 가설은 기각됐다. 미스율이 TTL 선택을 좌우했다. | Global 교차 리전 요율, 캐시 모형 단순화 |
| [021 · 일별 급증 탐지](experiments/021-daily-cost-spike-detection/README.md) | 세 규칙 모두 +50% 이상 급증을 97% 이상 잡았다. 오탐은 규칙·설정에 따라 30일당 0.025~0.76건이었다. 경보일을 기준선에서 빼면 수준 이동 뒤 경보가 멈추지 않았다. 두 가설 모두 기각됐다. | 합성 시계열, 조정·평가 시드 분리 |
| [022 · GPU 유휴 비용](experiments/022-gpu-training-idle-cost/README.md) | 월 학습 16시간에서 상시 GPU 노트북은 CPU 노트북+학습 작업 분리의 19.4배였다. 컴퓨팅을 멈춘 뒤에도 스토리지 월 3.69~8.48 USD가 남았다. | 결정적 계산 |

규칙 후보와 입력·기준값의 근거 수준은 [InfraFit 적용 메모](experiments/infrafit-pipeline-ai-rules.md)에 정리했다. 9개 모두 InfraFit에 선택 옵션(`--workloads`)으로 구현했다. 일별 비용 급증(R-COST-1)은 판정이 아니라 조사 대기열로 출력한다.

### 다음 질문

1. 실제 계정에서 IoT 메시지의 5 KB 계량이 5,000 B와 5,120 B 중 어느 쪽이며, MQTT 헤더가 포함되는가?
2. IoT 규칙의 Firehose 액션은 메시지를 레코드로 어떻게 넘기며, 청구에 `no-rounding` 수집 요율이 나타나는 조건은 무엇인가?
3. 실제 Athena 쿼리 기록의 `DataScannedInBytes`는 018의 대리 측정과 얼마나 다른가? 작은 Parquet 파일이 쿼리 지연에 주는 영향은 얼마인가?
4. 실제 에이전트 호출 로그의 캐시 적중률과 미스율은 손익분기(약 21%)와 비교해 어떤가? Geographic·리전 내 요율은 얼마인가?
5. +10%~+30% 수준의 작은 급증과 월초 일괄 청구에서 급증 규칙의 오탐·미탐은 어떤가? 경보일 제외 상한은 며칠이 적절한가?

## InfraFit MVP

읽기 전용 Python CLI는 청구 행, Terraform Plan JSON, 피크 관측을 명시적 자원·기간·후보 구성 매핑으로 연결한다. 결과에는 변경 검토 후보·유지·판단 보류, 판정 이유, 확인된 가상 비용과 p99가 포함된다.

| 기본 예제 | 판정 | 근거 |
|---|---|---|
| 주문 서비스 | 변경 검토 후보 | 가상 $120→$100, 피크 p99 180ms |
| 작업자 서비스 | 유지 | 가상 비용은 감소하지만 피크 p99 250ms로 기준 200ms 초과 |
| 기타 3개 주소 | 판단 보류 | 청구 충돌·누락, 관측 또는 Plan 근거 부족 |

마지막 독립 리뷰에서 종단 간 테스트 **11개**가 통과했다. 중복 청구 재입력, 지연 도착, 구성 불일치, 민감값 미출력, 복합 누락에도 보고서가 유지되는 동작을 확인했다. 비용 관련 전후 속성이 확인되는 EC2·EBS 갱신이 MVP 지원 범위다. 이후 `--workloads` 옵션으로 IoT·Firehose·Bedrock·Athena·SageMaker·일별 비용 합성 입력의 규칙 9개를 추가했다. 입력 필드 이름은 AWS 공식 API·지표 문서에서 확인했다. 테스트는 기존 11개, 워크로드 규칙 19개, 운영 규칙 24개가 모두 통과했다. 옵션을 주지 않은 기본 출력은 이전 버전과 같다. 기준값 일부는 임시값이며 실제 계정 데이터로 다시 정해야 한다. Terraform 주소와 실제 클라우드 자원 ID의 자동 매핑, 운영 승인과 변경 적용은 검증 범위 밖이다. [MVP 문서](infrafit/README.md)

## 실제 청구 자료 확보 후의 검증

1. **한 청구 기간을 읽기 전용으로 대사한다.** 비식별 청구 행, 자원 ID 매핑, 변경 시점과 관측 기간을 준비한다. 중복·누락·늦은 행을 분리하고, 매핑되지 않은 금액과 설명되지 않은 차이를 포함해 원본 청구 합계에 맞춘다.
2. **약정 반영액을 확인한다.** 적용 사용 행·상계 행·약정료를 같은 기준으로 비교하고, 남는 약정이 같은 시간대의 다른 적격 사용에 적용됐는지 확인한다.
3. **변경 전후가 비교 가능한 경우 실현 절감을 검증한다.** 업무량·품질·가격·기간을 맞추고 전환비를 포함한다. Kubernetes 노드 축소 효과를 청구 절감으로 연결하려면 실제 노드 수와 동일 기간 청구 내역도 필요하다.

실제 청구 외의 후속 검증은 AWS provider의 추가 변경 유형·버전, 독립 EBS 사례의 검토 시간, 운영 환경의 복구와 자동 롤백을 지원할 때 수행한다. [상세 연구 기록](experiments/infrafit-predevelopment-review.md)
