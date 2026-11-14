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
| [023 · 실제 계정 비용 급증 점검](experiments/023-real-cost-spike-check/README.md) | 실제 청구 410일에 R-COST-1을 돌려 서비스별 오탐 27건을 확인했다. 원인은 월 고정 요금의 2월 일수 효과(+10.7%, 10% 하한 초과)와 중앙값 0인 월초 세금이다. 기준값은 조정하지 않고 보류했다. | 실제 계정(작고 급증 없음), Cost Explorer 1건 |
| [024 · 비용 급증 규칙 보완](experiments/024-cost-spike-rule-fixes/README.md) | 세금 분리, 최소 증가액 0.50 USD/일, 달력 보정을 더해 실제 오탐을 27건에서 0건으로 줄였다. 합성 급증 재현율 97.8%는 그대로였다. +10~30% 작은 급증은 보완 전후 모두 21.5%만 잡았다. 사전 채택 규칙에 따라 기본값으로 바꿨다. | 실제 계정 1개 + 합성, 추가 AWS 비용 없음 |
| [022 · GPU 유휴 비용](experiments/022-gpu-training-idle-cost/README.md) | 월 학습 16시간에서 상시 GPU 노트북은 CPU 노트북+학습 작업 분리의 19.4배였다. 컴퓨팅을 멈춘 뒤에도 스토리지 월 3.69~8.48 USD가 남았다. | 결정적 계산 |

규칙 후보와 입력·기준값의 근거 수준은 [InfraFit 적용 메모](experiments/infrafit-pipeline-ai-rules.md)에 정리했다. 9개 모두 InfraFit에 선택 옵션(`--workloads`)으로 구현했다. 일별 비용 급증(R-COST-1)은 판정이 아니라 조사 대기열로 출력한다.

### 다음 질문

1. 실제 계정에서 IoT 메시지의 5 KB 계량이 5,000 B와 5,120 B 중 어느 쪽이며, MQTT 헤더가 포함되는가?
2. IoT 규칙의 Firehose 액션은 메시지를 레코드로 어떻게 넘기며, 청구에 `no-rounding` 수집 요율이 나타나는 조건은 무엇인가?
3. 실제 Athena 쿼리 기록의 `DataScannedInBytes`는 018의 대리 측정과 얼마나 다른가? 작은 Parquet 파일이 쿼리 지연에 주는 영향은 얼마인가?
4. 실제 에이전트 호출 로그의 캐시 적중률과 미스율은 손익분기(약 21%)와 비교해 어떤가? Geographic·리전 내 요율은 얼마인가?
5. +10%~+30% 수준의 작은 급증과 월초 일괄 청구에서 급증 규칙의 오탐·미탐은 어떤가? 경보일 제외 상한은 며칠이 적절한가? (023에서 찾은 월초 세금과 2월 일수 효과의 오탐은 024에서 고쳤다. 작은 급증은 이 규칙으로 21.5%만 잡혀, 예측 잔차 누적 같은 다른 방법이 필요하다.)

## 026~036: InfraFit 확장 범위 연구

InfraFit의 확장 범위(설계 단계 아키텍처 비용 모델, 비용 누수 패턴 규칙과 서비스 팩, LLM·AI 에이전트 비용, 컨테이너 실행 방식 비용, 실제 환경 연동)를 구현하기 전에 필요한 학습 근거와 검증 근거를 만들었다. 학습은 신규 노트 3개(OpenSearch, ElastiCache, API Gateway), 기존 노트 보강 8개, [비용 누수 패턴 8가지](studies/methods/cost-leak-patterns.md)다. 실험은 일반화한 두 기준 시나리오([scenarios](experiments/scenarios/README.md))와 [서울 요율 사본 2026-11-15](references/aws-price-list-apn2-2026-11-15.json)만 쓰는 계산 10개와 로컬 Redis 실측 1개다. AWS 호출과 실제 LLM 호출은 하지 않았다.

| 실험 | 검증 결과 | 적용 범위 |
|---|---|---|
| [026 · 과금 단위 올림](experiments/026-billing-unit-rounding/README.md) | 평균 크기로 과금량을 추정하면 단위 경계 바로 아래에서 분산이 클 때만 크게 틀렸다(최대 −33%, 경계를 조금 넘으면 +20%). 평균이 단위의 절반 미만이면 낭비율은 늘 50%를 넘었다. 측정값 200 B 개별 전송은 용량 기반 추정의 25.6배가 청구된다. | 로그정규 합성 분포, IoT 5 KB = 5,120 B 가정 |
| [027 · 중복 전송](experiments/027-duplicate-transfer/README.md) | 원본 4.83 GB가 단계마다 다시 과금돼 바이트 과금 양이 189배였다. 규칙 중복·항목별 로그·NAT 재다운로드를 없애 경로 비용이 37% 줄었고, 절감의 70%가 NAT였다. 배수보다 단계별 GB 요율이 금액을 정했다. | 시나리오 ①, 에이전트 동작·로그 크기 가정 |
| [028 · NAT vs 엔드포인트](experiments/028-nat-vs-vpc-endpoint/README.md) | 인터페이스 엔드포인트의 손익분기는 2 AZ·1개당 월 387 GB였다. 소규모 시나리오 ②에서는 S3 게이트웨이 엔드포인트만 이득이었고, 인터페이스 엔드포인트를 모두 두면 2.3배 비쌌다. | 서비스별 GB 가정, 흐름 로그 없음 |
| [029 · 고정비와 일정 중지](experiments/029-fixed-cost-scheduling/README.md) | 근무 시간 일정으로 줄어든 것은 13%뿐이었다. 상시 비용의 79%가 삭제만 가능한 자원(대부분 OpenSearch Classic 최소 OCU)이었다. NextGen으로 바꾸면 63% 줄었다. RDS를 한 번 멈추고 잊으면 7일 뒤 자동 시작돼 절감의 33%만 남았다. | 시나리오 ② 개발 환경, NextGen 요율 미확인 |
| [030 · 숨은 최소 요금](experiments/030-hidden-minimum-charges/README.md) | 시나리오 ②에서 최소치가 정하는 비용(431 USD)이 챗봇 모델 토큰(175 USD)의 2.5배였다. 50 MB 캐시는 서버리스 Valkey(7.37 USD)가 Redis OSS(110.23 USD)보다 93% 쌌다. | 실제 필요 OCU 미측정, KB 저장 요율 제외 |
| [031 · 컨테이너 실행 방식](experiments/031-container-runtime-cost/README.md) | "요청 감소 → 비용 감소"가 Fargate형에서만 성립한다는 가정은 기각됐다. Fargate는 허용 조합 경계를 넘을 때만(2/6 단계), EKS+EC2는 노드 수가 바뀔 때만(4/6) 줄었고 Lambda는 무관했다. 작은 Pod 60개는 슬롯·최소 조합에 막혀 네 방식 모두 그대로였다. | EKS 예약량·시스템 Pod는 가정 |
| [032 · LLM 요청 비용 분해](experiments/032-llm-request-cost-breakdown/README.md) | 챗봇 요청 비용에서 모델 토큰은 27%였고 벡터 저장소 최소치가 66%였다. 에이전트 호출 4회는 단일 호출의 5.83배였다. Haiku 4.5의 최소 캐시 길이(4,096토큰) 때문에 2,000토큰 고정 앞부분은 캐시되지 않아 절감 가설이 기각됐다. 모델 배분은 비용만 계산하고 판단을 보류했다. | 요청 안 캐시 재사용 상한, 품질 미평가 |
| [033 · 입력 토큰 정의](experiments/033-input-token-definitions/README.md) | Converse `inputTokens`는 캐시를 빼고 Responses `input_tokens`는 포함한다. CloudWatch `InputTokenCount`의 정의는 문서에 없다. 정의를 잘못 잡으면 −57%~+115% 틀렸고, 청구 수량과 비교하면 캐시 비중 1%까지 정의를 가려냈다. | 합성 호출 기록, 실제 지표 정의는 미확인 |
| [034 · 측정 비용](experiments/034-observability-cost/README.md) | 사용자 ID 차원 지표는 집계 지표의 92.6배였다. 디바이스별 지표 300개(90 USD)가 같은 데이터를 EMF 로그로 남기는 수집 요금(5.50 USD)의 16배였다. 무기한 보관의 월 저장 요금은 25개월째에야 수집 요금을 넘었다(가설 기각). 다만 36개월 누적은 30일 보관의 18.5배였다. | 로그 저장 압축 미확인(상한) |
| [035 · 캐시 축출 정책](experiments/035-cache-eviction-policy/README.md) | 로컬 Redis 10 MB에서 allkeys-lru 0.785, volatile-lru 0.757, volatile-ttl 0.720(3회 범위 ≤ 0.0008)이었다. 원본이 LLM 호출이면 요청 100만 건당 약 228 USD 차이다. TTL 키만 반복 축출돼 OOM은 나지 않았다(가설 기각). | 로컬 실측 1회, Zipf 접근, 여유 메모리 3.34 GiB에서 사용자 지시로 실행 |
| [036 · 설계 단계 비용 모델](experiments/036-architecture-cost-model/README.md) | 구성 요소별 "청구 예상"과 "요율 × 실사용량"을 함께 내는 모델이 019의 1,000건당 비용 8개를 그대로 재현했다. 시나리오 ① 월 294.88 USD(1,000건당 0.0114), ② 월 888.58 USD였고 검토 표시 비중은 57%·68%였다. | 첫 달 기준, 사본에 없는 요율은 제외 목록 |

**공통 결론.** 작은 작업량에서는 사용량보다 **최소치·상시 시간·과금 단위**가 비용을 정했고(026·029·030·032·036), 요청·크기를 줄이는 권고의 효과는 서비스마다 다른 계단 함수였다(026·031). 서비스 이름이 아니라 이 구조를 패턴으로 묶으면, InfraFit은 패턴 규칙(일반식 + 판단 자료)과 서비스 팩(단위·최소치·중지 방식·요율 행 이름)으로 나눠 확장할 수 있다. 규칙 후보 20여 개와 근거 수준은 [InfraFit 적용 메모](experiments/infrafit-pipeline-ai-rules.md#확장-범위-규칙-후보-026036)에 있다. **모두 미구현**이며 구현은 InfraFit 저장소에서 한다.

**확인하지 못한 것.** NextGen OCU 요율, KB 관리형 저장 요율, Glue Python Shell 요율·최소 과금, CloudWatch `InputTokenCount` 정의, EKS AMI 예약량, ECR 레이어 중복 제거, 로그 저장 압축은 미확인으로 남겼다. 실제 흐름 로그·지표 차원 수·캐시 접근 패턴으로 다시 확인해야 한다.

## InfraFit MVP

읽기 전용 Python CLI는 청구 행, Terraform Plan JSON, 피크 관측을 명시적 자원·기간·후보 구성 매핑으로 연결한다. 결과에는 변경 검토 후보·유지·판단 보류, 판정 이유, 확인된 가상 비용과 p99가 포함된다.

| 기본 예제 | 판정 | 근거 |
|---|---|---|
| 주문 서비스 | 변경 검토 후보 | 가상 $120→$100, 피크 p99 180ms |
| 작업자 서비스 | 유지 | 가상 비용은 감소하지만 피크 p99 250ms로 기준 200ms 초과 |
| 기타 3개 주소 | 판단 보류 | 청구 충돌·누락, 관측 또는 Plan 근거 부족 |

마지막 독립 리뷰에서 종단 간 테스트 **11개**가 통과했다. 중복 청구 재입력, 지연 도착, 구성 불일치, 민감값 미출력, 복합 누락에도 보고서가 유지되는 동작을 확인했다. 비용 관련 전후 속성이 확인되는 EC2·EBS 갱신이 MVP 지원 범위다. 이후 `--workloads` 옵션으로 IoT·Firehose·Bedrock·Athena·SageMaker·일별 비용 합성 입력의 규칙 9개를 추가했다. 입력 필드 이름은 AWS 공식 API·지표 문서에서 확인했다. 테스트는 기존 11개, 워크로드 규칙 19개, 운영 규칙 28개가 모두 통과했다(운영 규칙 테스트는 처음 24개, 024 보완 때 4개 추가). 옵션을 주지 않은 기본 출력은 이전 버전과 같다. 기준값 일부는 임시값이며 실제 계정 데이터로 다시 정해야 한다. 운영 승인과 변경 적용은 검증 범위 밖이다. [MVP 문서](infrafit/README.md)

### 실제 AWS 데이터를 넣기 위한 도구 (합성 응답으로만 검증)

InfraFit을 "합성 입력으로 검증한 연구용 CLI"에서 "실제 AWS 데이터를 넣어 쓸 수 있는 읽기 전용 도구"로 넓혔다. 모두 표준 라이브러리만 쓴다. 옵션 없는 기본 출력과 기존 예제의 판정은 바이트 단위로 같다(변경 전 출력 7가지를 저장해 비교).

| 도구 | 하는 일 | 검증 | 실제 데이터로 확인하지 못한 점 |
|---|---|---|---|
| [convert.py](infrafit/convert.py) | Cost Explorer, Athena+Glue, GetMetricData, Firehose Describe, S3 Inventory CSV, SageMaker Describe, Bedrock Converse 사용량 로그 → `--workloads` 입력. 사람 입력은 운영 정보 파일에서 합친다. 필드 오류는 그 항목만 건너뛰고 경고한다. 이름은 소금값 해시로 가릴 수 있다 | 테스트 21개. 변환한 항목이 원래 예제(016·017·018·020·021·022)와 같은 판정·근거·예상 절감을 낸다 | 실제 응답 변환 미실행. IoT 토픽별 발행 수와 Firehose 스트림별 청구 GB는 API에 없어 변환 대상이 아니다 |
| [collect.py](infrafit/collect.py) | `cel-readonly` 프로필로 위 파일을 저장소 밖에 수집한다. 드라이런(호출 0건) → 무료 단계 → 상한 안에서 `--yes`일 때만 유료 호출(Cost Explorer·GetMetricData). 요약에는 자원 이름을 넣지 않는다 | 가짜 aws 명령으로 테스트 13개. 수집 결과를 변환하면 원래 예제와 같은 판정 | 실제 계정 수집 미실행(승인 필요, 실제 프로젝트 사용량 거의 없음) |
| [`--report`](infrafit/report.py) | 판정을 단일 HTML·Markdown으로 내보낸다. 요약, 규칙별 표, 이유, 기준값과 근거 수준, 보류 사유, 조사 대기열, 입력 종류, "예상 절감 ≠ 실제 청구"를 담는다 | 테스트 10개. 민감값·추가 필드 미출력, 이스케이프, 결정성 | — |
| [tf_links.py](infrafit/tf_links.py) | `terraform show -json`에서 주소·유형·`values.id`만 읽어 주소 ↔ 자원 ID 연결 후보를 만든다. 민감 ID와 데이터 소스는 제외한다 | 합성 state로 테스트 7개 | 실제 state 미확인, `cli.py`에 아직 연결 안 함([설계](experiments/terraform-state-linking-plan.md)) |

[025](experiments/025-billing-rule-probe/README.md)의 과금 규칙 판정은 청구 사용량이 반영된 뒤에 한다. 실행 후 24시간 시점까지 4회 조회(Cost Explorer 4건, 0.04 USD)했으나 아직 반영되지 않아 **반영 대기**다. 자원 삭제는 승인을 기다린다. 실제 프로젝트 데이터로 기준값을 다시 정하는 절차는 [수집·재설정 계획](experiments/real-account-calibration-plan.md) 8장에 명령 단위로 구체화했다.

## 실제 청구 자료 확보 후의 검증

1. **한 청구 기간을 읽기 전용으로 대사한다.** 비식별 청구 행, 자원 ID 매핑, 변경 시점과 관측 기간을 준비한다. 중복·누락·늦은 행을 분리하고, 매핑되지 않은 금액과 설명되지 않은 차이를 포함해 원본 청구 합계에 맞춘다.
2. **약정 반영액을 확인한다.** 적용 사용 행·상계 행·약정료를 같은 기준으로 비교하고, 남는 약정이 같은 시간대의 다른 적격 사용에 적용됐는지 확인한다.
3. **변경 전후가 비교 가능한 경우 실현 절감을 검증한다.** 업무량·품질·가격·기간을 맞추고 전환비를 포함한다. Kubernetes 노드 축소 효과를 청구 절감으로 연결하려면 실제 노드 수와 동일 기간 청구 내역도 필요하다.

실제 청구 외의 후속 검증은 AWS provider의 추가 변경 유형·버전, 독립 EBS 사례의 검토 시간, 운영 환경의 복구와 자동 롤백을 지원할 때 수행한다. [상세 연구 기록](experiments/infrafit-predevelopment-review.md)
