# Experiments

학습 중 직접 확인할 필요가 생긴 내용을 검증하는 공간입니다. 작은 입력을 이용한 비용 계산 검증, 공개·저장 자료를 이용한 분석 방법 비교, 기존 논문·도구·모델의 전체 또는 축소 재현을 할 수 있습니다. AWS 실험은 필요한 경우에만 제한된 범위로 수행합니다.

## 분류 기준

실험은 AWS 서비스별이 아니라 연구 질문별로 독립적인 폴더에 묶습니다. 향후 폴더명은 `001-ec2-rightsizing`, `002-cost-anomaly-detection`처럼 정할 수 있습니다. 이는 이름의 예시이며 실제 실험 폴더가 아닙니다.

[커리큘럼](../studies/curriculum.md)의 어느 과정에서든 검증이 필요한 질문이 생기면 독립적인 실험으로 관리합니다. 자체 질문에 대한 실험과 기존 논문·모델의 재현을 구분합니다.

## 실험 기록 원칙

[실험 안내](experiment-guide.md)에서 실행 전 설계, 비용 비교와 재현 기록 기준을 확인할 수 있습니다.

각 실험의 README에서 필요한 범위에 따라 다음을 찾을 수 있도록 기록합니다.

- 질문과 가설 또는 확인 목표
- 데이터 출처와 실제·합성 여부
- 실행 환경과 의존성
- 비교 기준선과 변경 조건
- 측정 지표와 실행 방법
- 원본 결과와 집계 방법
- 결과 해석, 한계, 재현 범위

AWS·Docker·Kubernetes 실험은 사용한 환경·버전, 자원 구성·제한, 부하와 측정 조건을 기록합니다. 비용·성능 비교에서는 동일한 업무량과 품질 요구를 기준으로 삼고, 조건 차이가 있으면 함께 명시합니다. 자료가 부족하면 판단을 보류합니다.

모델 실험에는 필요한 경우 학습·튜닝·평가 자료의 구분과 난수 시드를 남깁니다. 기존 연구와 조건이 다르면 전체 재현이라고 부르지 않고 축소 재현 또는 방법을 참고한 별도 실험으로 구분합니다.

작은 실험은 README 하나와 최소한의 실행 파일만 사용해도 됩니다. `data/`, `scripts/`, `results/` 등의 하위 폴더는 실제 자료가 생길 때만 만듭니다.

AWS 자원 생성·실행은 필수가 아닙니다. AWS 등 유료 자원을 쓰는 실험은 실행 전에 대상, 예상 비용과 가정, 위험, 유지 시간, 중단 조건, 정리 방법을 검토하고 사용자 승인을 받은 범위에서만 수행합니다. 미측정, 실패, 효과가 없었던 결과도 그대로 기록합니다.

## 실험 목록

- [001 · EBS 낭비 탐지 규칙 로컬 검증](001-ebs-waste-rules/README.md) — 가상 볼륨 8건과 충돌 우선순위 2건 재현
- [002 · EBS 규칙 신규 반례 평가](002-ebs-rule-robustness/README.md) — 합성 11건과 보류의 영향
- [003 · EC2·EBS 비용 시뮬레이션](003-aws-cost-simulation/README.md) — 가상 비용 8가지 조건
- [004 · Terraform 변경 근거](004-terraform-evidence/README.md) — 합성 Plan 추출과 민감정보 처리
- [005 · Docker 워크로드 자원 효율 실측](005-container-resource-efficiency/README.md) — CPU 한도별 두 차례 반복
- [006 · Kubernetes 자원 검증](006-kubernetes-resource-efficiency/README.md) — 정적 비용 모형과 실제 Requests 배치·Limits 부하
- [007 · InfraFit 통합 가능성](007-infrafit-feasibility/README.md) — 품질·결측·중복 비용을 포함한 합성 판정
- [008 · 청구·변경·피크 관측 대사](008-evidence-reconciliation/README.md) — 지연 도착, 중복, 불일치와 재대사
- [009 · EBS 기록 최신성과 보류 검토 비용](009-ebs-review-cost/README.md) — 최신성 기준에 따른 오탐과 검토량
- [010 · CPU 한도별 품질 기준 재검증](010-cpu-quality-envelope/README.md) — 보존 로그 분석과 전용 환경 반복 절차
- [011 · 약정·피크 겹침·전환비 민감도](011-cost-quality-sensitivity/README.md) — 비용과 품질에 따른 채택 조건
- [012 · 실제 Terraform Plan JSON 호환성](012-terraform-plan-compatibility/README.md) — 내장 리소스의 모듈 주소·교체·민감도·미확정 값
- [013 · 피크 품질 악화 후 CPU 한도 롤백](013-peak-rollback/README.md) — 전용 로컬 컨테이너의 기준·축소·복원 실측
- [014 · AWS provider의 실제 EC2·EBS Plan](014-aws-provider-plan/README.md) — AWS API를 호출하지 않는 생성 계획과 필드 호환성
- [015 · Kubernetes 반복 부하와 Deployment 롤백](015-kubernetes-rollback/README.md) — 전용 Minikube에서 CPU 축소·복원 반복

### IoT 파이프라인·생성형 AI·모델 학습 (로컬·합성·계산, AWS 호출 없음)

서울 리전 요율은 [Price List 사본](../references/aws-price-list-apn2-2026-11-13.json)에서 읽는다. 실제 프로젝트의 비용 구조를 미리 확인하기 위한 묶음이며, 실제 계정 데이터로 다시 확인할 점은 [InfraFit 적용 메모](infrafit-pipeline-ai-rules.md)에 정리했다.

- [016 · IoT Core 메시지 묶음](016-iot-message-batching/README.md) — 5 KB 계량 단위와 묶음 크기·지연의 교환
- [017 · Firehose 버퍼와 작은 파일](017-firehose-buffer-small-files/README.md) — 버퍼 설정별 S3 객체 수·신선도 시뮬레이션
- [018 · 저장 형식·파티션별 스캔량](018-format-partition-scan/README.md) — CSV·Parquet·파티션의 읽은 바이트 대리 측정
- [019 · 파이프라인 단위 비용](019-pipeline-unit-cost/README.md) — 센서 1,000건당 비용과 데이터 신선도
- [020 · Bedrock 토큰·캐싱](020-bedrock-token-caching/README.md) — 에이전트 호출 증폭과 캐싱 손익분기
- [021 · 일별 비용 급증 탐지](021-daily-cost-spike-detection/README.md) — 단순 규칙 3개의 오탐·미탐·지연
- [022 · GPU 학습 유휴 비용 (선택)](022-gpu-training-idle-cost/README.md) — 상시 실행·스케줄·학습 작업 분리와 잔존 비용
- [023 · 실제 계정의 일별 비용으로 R-COST-1 점검](023-real-cost-spike-check/README.md) — 실제 청구 410일에서 월 경계·세금 오탐 확인, 기준값은 보류
- [024 · 비용 급증 규칙 보완과 작은 급증 재평가](024-cost-spike-rule-fixes/README.md) — 세금 분리·최소 증가액·달력 보정으로 실제 오탐 27→0건, 작은 급증 재현율 21.5%

#### 016~022 테스트 기록 (2026-11-13, Windows 11, Python 3.14.7, pyarrow 26.0.1)

| 실험 | 단위 테스트 | `result.json` 재현 |
|---|---|---|
| 016 | 8개 통과 | 테스트 안에서 재실행·일치 |
| 017 | 6개 통과 | 테스트 안에서 재실행·일치 |
| 018 | 8개 통과(소형 데이터) | **전체 재실행 미실시**(약 31분). 소형 데이터로 결정성만 테스트 |
| 019 | 4개 통과 | 테스트 안에서 재실행·일치 |
| 020 | 8개 통과 | 테스트 밖에서 전체 재실행(약 1.5분), 저장 결과와 일치 |
| 021 | 7개 통과 | 테스트 안에서 재실행·일치 |
| 022 | 5개 통과 | 테스트 안에서 재실행·일치 |
| 023 | 5개 통과(합성 데이터) | 실제 원본은 저장소 밖. 024 이전 규칙에 고정해 원본으로 재실행, 경보 수·위치 일치(비율 표시만 정밀도 수정) |
| 024 | 3개 통과(합성 데이터) | 합성 부분은 테스트 안에서 재실행·일치. 실제 부분은 원본(저장소 밖)으로 재실행해 일치 |

같은 시점에 기존 [InfraFit 종단 간 테스트](../infrafit/test_cli.py) 11개와 010 테스트 2개도 다시 실행해 통과했다. 001~015의 다른 실험 스크립트와 Docker·Kubernetes 실측은 이번에 다시 실행하지 않았다.

### InfraFit 확장 범위: 누수 패턴·컨테이너·LLM 비용·설계 단계 모델 (026~036, 로컬·합성·계산, AWS 호출 없음)

서울 리전 요율은 [2026-11-15 사본](../references/aws-price-list-apn2-2026-11-15.json)에서만 읽고 금액은 `Decimal`로 계산한다. 두 기준 시나리오와 공통 모듈(요율 읽기·서비스 팩)은 [scenarios](scenarios/README.md)에 있다. 패턴별 정리는 [누수 패턴 방법 노트](../studies/methods/cost-leak-patterns.md), 규칙 후보는 [InfraFit 적용 메모](infrafit-pipeline-ai-rules.md#확장-범위-규칙-후보-026036)에 있다.

- [026 · 과금 단위 올림의 일반식](026-billing-unit-rounding/README.md) — 평균 기반 추정은 단위 경계 바로 아래·분산이 클 때만 크게 틀림(H1 기각), 평균이 단위의 절반 미만이면 낭비율 50% 초과(H2 지지)
- [027 · 같은 데이터의 중복 전송](027-duplicate-transfer/README.md) — 바이트 과금 양이 원본의 189배, 중복 경로 제거로 37% 절감. 금액은 GB 요율이 높은 단계(NAT·로그)가 정함
- [028 · NAT vs VPC 엔드포인트 손익분기](028-nat-vs-vpc-endpoint/README.md) — 2 AZ·엔드포인트 1개 손익분기 월 387 GB, 소규모에서는 S3 게이트웨이 엔드포인트만 이득
- [029 · 상시 고정비와 일정 기반 중지](029-fixed-cost-scheduling/README.md) — 삭제만 가능한 자원 때문에 근무 시간 일정 절감 13%, NextGen 전환 시 63%. RDS 중지 후 잊으면 절감의 33%만 남음
- [030 · 숨은 최소 요금](030-hidden-minimum-charges/README.md) — 시나리오 ②에서 최소치가 정하는 비용 431 USD > 모델 토큰 175 USD, 작은 캐시는 Valkey가 Redis OSS보다 93% 저렴
- [031 · 컨테이너 실행 방식 비교](031-container-runtime-cost/README.md) — "요청 감소 → 비용 감소"는 실행 방식마다 다른 계단 함수(H0 기각). Fargate는 허용 조합 경계에서만, EKS+EC2는 노드 수가 바뀔 때만 줄고 Lambda는 무관
- [032 · LLM 요청 1건당 비용 분해와 호출 증폭](032-llm-request-cost-breakdown/README.md) — 모델 토큰은 챗봇 요청의 27%, 에이전트 호출 4회 = 5.83배, Haiku 4.5의 최소 캐시 4,096토큰 때문에 고정 앞부분 캐시 절감 0%. 모델 배분은 판단 보류
- [033 · 입력 토큰 정의 차이와 교차 확인](033-input-token-definitions/README.md) — Converse(캐시 제외)·Responses(포함)·CloudWatch(미확인). 청구 수량 비교로 캐시 비중 1%까지 정의 판별
- [034 · 측정 비용](034-observability-cost/README.md) — 고차원 지표 92.6배, 디바이스별 지표 90 USD > 같은 데이터 EMF 수집 5.50 USD, 무기한 보관 저장 > 수집은 25개월째
- [035 · 캐시 축출 정책 (로컬 Redis 실측)](035-cache-eviction-policy/README.md) — 같은 10 MB에서 allkeys-lru 0.785 > volatile-lru 0.757 > volatile-ttl 0.720, 원본 호출 23% 차이
- [036 · 설계 단계 아키텍처 비용 모델 원형](036-architecture-cost-model/README.md) — 019 1,000건당 비용 8개 완전 재현, 두 시나리오의 구성 요소별 청구·사용량 기반 금액과 패턴 표시

#### 026~036 테스트 기록 (2026-11-15, Windows 11, Python 3.14.7, Docker 29.8.2)

| 실험 | 단위 테스트 | `result.json` 재현 |
|---|---|---|
| scenarios | 8개 통과 | 해당 없음(공통 모듈) |
| 026 | 5개 통과 | 테스트 안에서 재실행·일치(약 6초) |
| 027 | 4개 통과 | 테스트 안에서 재실행·일치 |
| 028 | 4개 통과 | 테스트 안에서 재실행·일치 |
| 029 | 4개 통과 | 테스트 안에서 재실행·일치 |
| 030 | 4개 통과 | 테스트 안에서 재실행·일치 |
| 031 | 5개 통과 | 테스트 안에서 재실행·일치 |
| 032 | 5개 통과 | 테스트 안에서 재실행·일치 |
| 033 | 5개 통과 | 테스트 안에서 재실행·일치 |
| 034 | 4개 통과 | 테스트 안에서 재실행·일치 |
| 035 | 6개 통과 | Redis 측정은 Docker로 1회 실행(정책별 3회, 시작 시 여유 메모리 3.34 GiB — 기준 4 GiB 미만이지만 사용자 지시로 실행). 테스트는 저장된 측정값에서 요약 재계산(`--resummarize`)·일치. 컨테이너·이미지 삭제 확인 |
| 036 | 5개 통과 | 테스트 안에서 재실행·일치, 019 재현 8개 일치 |

[최종 연구 보고서](../FINAL-REPORT.md)에서 001~015와 [InfraFit MVP](../infrafit/README.md)의 검증 범위를 함께 볼 수 있다. [InfraFit 개발 전 연구 기록](infrafit-predevelopment-review.md)은 개별 실행과 후속 검증의 맥락을 보존한다.

미확인 과금 규칙을 작은 테스트 파이프라인으로 확인하는 [025](025-billing-rule-probe/README.md)는 실행을 마쳤다. 실행 후 24시간 시점까지 Cost Explorer를 4회 조회했으나 청구 사용량이 아직 반영되지 않아 **반영 대기**로 기록했다. 판정은 반영 후에 한다. 실험 자원은 계정 소유자의 승인을 받아 2026-11-15에 모두 삭제했다(025 README에 기록). 실제 계정 데이터로 InfraFit 기준값을 다시 정하는 [수집·재설정 계획](real-account-calibration-plan.md)은 승인됐다. 하지만 실제 프로젝트 사용량이 없어 아직 데이터를 수집하지 않았다. 계획의 8장에 수집·변환 명령을 구체적으로 적었다.

- [InfraFit 실제 AWS 출력 변환·수집·보고서](../infrafit/README.md#실제-aws-출력-변환기-convertpy) — `convert.py`(AWS 응답 → 입력 형식), `collect.py`(읽기 전용 수집, 드라이런·가짜 aws 테스트만), `--report`(HTML·Markdown). 모두 합성 응답으로만 검증했다
- [Terraform 주소 ↔ 실제 자원 ID 자동 연결 설계](terraform-state-linking-plan.md) — `terraform show -json`에서 주소와 ID만 읽는 규칙과 합성 state 테스트. 실제 state로는 미확인

실제 실행한 실험만 문서의 상대 링크와 함께 이 목록에 등록합니다. 관련 [Studies](../studies/README.md) 학습 문서와 실험 문서를 상호 연결해 학습 근거와 재현 경로를 찾을 수 있도록 합니다.
