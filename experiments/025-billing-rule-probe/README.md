# 025 — 작은 테스트 파이프라인으로 미확인 과금 규칙 확인 (계획)

[실험 목차](../README.md) · [수집·재설정 계획](../real-account-calibration-plan.md) · [IoT 학습 노트](../../studies/aws/iot-core/README.md) · [Firehose 학습 노트](../../studies/aws/kinesis-firehose/README.md) · [Athena·Glue 학습 노트](../../studies/aws/athena-glue/README.md)

**상태: 실행 완료, 청구 사용량 확인 대기.** 계정 소유자의 승인을 받아 실행했다. 사용량이 Cost Explorer에 반영되면(실행 후 하루~이틀) 판정하고, 판정이 끝나면 자원을 모두 지운다. 실험용 자원은 아직 남아 있다.

## 확인할 과금 규칙

| # | 규칙 | 지금 근거 | 실험이 정하는 것 |
|---|---|---|---|
| P1 | IoT Core 메시지 5 KB 계량의 바이트 정의 | 요금 페이지는 "5 KB 단위"라고만 씀 (016에서 5,000/5,120 B 둘 다 계산) | 5,050 B 메시지 200건이 200건으로 계량되면 5,120 B, 400건이면 5,000 B |
| P1b | 토픽 이름이 계량 크기에 포함되는지 | 미확인 | 5,110 B 페이로드를 20자 토픽으로 100건 발행. 토픽이 포함되면 100건 모두 2단위(200), 아니면 100 |
| P2 | Firehose Direct PUT의 5 KB 올림과 `no-rounding` 사용 유형 | 요금 페이지는 5 KB 올림, Price List에는 `no-rounding` 행도 있음 | 200 B 레코드 1,000건을 넣고 다음 날 청구 사용 유형과 수량을 확인. 올림이면 약 0.0048 GB, 미올림이면 약 0.0002 GB |
| P3 | Athena S3 쿼리의 10 MB 최소 과금 | Glue 요금 페이지의 문장에만 근거 | 1 KB CSV에 SELECT 5회. 최소 과금이면 사용량 50 MB, 아니면 1 MB 미만 |

SageMaker 과금 단위(022의 미확인 항목)는 인스턴스 시간이 들어 이번 범위에서 뺀다.

## 실행 방법

- **장소**: AWS 콘솔의 CloudShell(서울 리전). 계정 소유자가 로그인한 앱 안 브라우저에서 Claude가 명령을 입력한다. 이 PC의 `cel-readonly` 프로필은 읽기 전용이라 쓰지 않는다.
- **IoT(P1·P1b)**: `aws iot-data publish`(HTTPS 발행)로 테스트 토픽 `cel-probe/...`에 발행한다. IoT 자원(사물·인증서·규칙)은 만들지 않는다.
- **Firehose(P2)**: 실험용 S3 버킷 1개, Firehose 스트림 1개(Direct PUT → S3, 버퍼 기본값, 변환·동적 파티셔닝 없음), 콘솔이 만드는 전달용 IAM 역할 1개를 만든다. `aws firehose put-record-batch`로 1,000건을 넣는다.
- **Athena(P3)**: 같은 버킷에 1 KB CSV와 쿼리 결과 접두사를 두고, Athena DDL로 Glue 데이터베이스·테이블을 하나씩 만든 뒤 SELECT를 5회 실행한다.
- **결과 확인**: 실행 다음 날과 그다음 날, 읽기 전용 프로필로 Cost Explorer `GetCostAndUsage`(DAILY, `GroupBy=USAGE_TYPE`, `UsageQuantity`)를 서비스별로 조회한다(요청 약 6건). 원본은 023처럼 저장소 밖에 둔다.
- **같은 날 다른 사용량과 섞이지 않게**: 이 계정은 현재 IoT·Firehose·Athena 사용량이 0이라, 그날 사용량 전체를 실험분으로 볼 수 있다.
- **P1·P1b를 같은 날 발행** (실행 직전 변경): 처음에는 두 날로 나누려 했으나, 건수를 다르게 하면 하루 합계만으로 구분된다.
  - P1: `cel-probe/a`(11자) 토픽에 5,050 B × 200건
  - P1b: `cel-probe/topic-20ch`(20자) 토픽에 5,110 B × 100건
  - 하루 계량 합계로 판정한다:

    | 하루 합계 | 결론 |
    |---:|---|
    | 300 | 5,120 B 정의, 토픽 미포함 |
    | 400 | 5,120 B 정의, 토픽 포함 |
    | 600 | 5,000 B 정의(이 경우 토픽 포함 여부는 판정 불가) |
    | 그 밖 | 판정 불가로 기록 |

- **요금 재확인 결과** (실행 직전): CloudShell은 "추가 요금 없음", Firehose Direct PUT → S3는 VPC 전달·JQ 처리 외에 시간당 요금이 없음을 공식 요금 페이지에서 확인했다.

## 예상 비용 (서울 공개 요율, Price List 2026-11-13 확인)

| 항목 | 계산 | 예상 |
|---|---|---:|
| IoT 메시지 | 최대 600건 × 1.20 USD/100만 건 | 0.001 USD 미만 |
| Firehose 수집 | 최대 0.0048 GB × 0.036 USD/GB | 0.001 USD 미만 |
| S3 저장·요청 | 1 MB 미만, 요청 수십 건 | 0.001 USD 미만 |
| Athena 스캔 | 최대 50 MB × 5 USD/TB | 0.001 USD 미만 |
| Cost Explorer 조회 | 약 6건 × 0.01 USD | 0.06 USD |
| **합계 상한** | | **0.10 USD** |

CloudShell 자체의 요금과 Firehose 스트림의 대기 요금 유무는 실행 직전에 공식 요금 페이지에서 다시 확인한다. 둘 중 하나라도 시간당 요금이 있으면 멈추고 다시 승인받는다.

## 중단·정리

- **중단 조건**: 명령이 예상과 다른 자원을 만들거나, 콘솔에 예상하지 못한 요금 안내가 나오면 즉시 멈추고 알린다.
- **정리** (마지막 확인 조회가 끝나는 날, 또는 실험 실패 시 즉시):
  1. Firehose 스트림 삭제
  2. Glue 테이블·데이터베이스 삭제
  3. S3 버킷 비우고 삭제
  4. Firehose 전달용 IAM 역할·정책 삭제
- **정리 확인**: 정리 후 S3·Firehose·Glue·IAM 화면에서 남은 것이 없는지 확인하고 기록한다. 다음 달 청구서에 이 실험 관련 항목이 있는지도 확인한다.
- **저장소 기록**: 자원 이름·계정 식별자는 저장소에 남기지 않는다. 사용량은 비율·건수로만 남긴다.

## 기록 계획

결과가 나오면 아래 항목을 확정하거나 "확정 못 함"으로 고친다.
- `iot.kb_definitions_bytes`
- R-FH-1의 `no-rounding` 보류 조건
- `athena.min_billed_mb`의 근거
- 관련 학습 노트(IoT·Firehose·Athena)의 문장

## 실행 기록

모든 명령은 서울 리전 CloudShell에서 실행했다. 시각은 CloudShell의 UTC 시계 기준이며, 청구 사용량도 UTC 날짜로 집계된다. 실행일은 실행 순서와 함께 비공개 메모로만 남기고, 아래에는 상대 시각만 적는다.

| 단계 | 내용 | 결과 |
|---|---|---|
| 요금 재확인 | CloudShell 요금 페이지("추가 요금 없음"), Firehose 요금 페이지(Direct PUT → S3에 대기 요금 없음) | 멈출 조건 없음 |
| P1 | 5,050 B 페이로드, 11자 토픽, HTTPS 발행 | 200건 성공 |
| P1b | 5,110 B 페이로드, 20자 토픽, HTTPS 발행 | 100건 성공 (P1 시작부터 약 3분 안에 둘 다 끝남, 같은 UTC 날짜) |
| P2 준비 | 실험용 S3 버킷 1개, Firehose 전달 역할 1개(S3 쓰기만 허용하는 인라인 정책), Direct PUT 스트림 1개 | 각 1개 생성, 중복 없음 확인 |
| P2 투입 | 200 B 레코드 500건짜리 `put-record-batch` | **계획과 다름: 4회 실행되어 2,000건.** 터미널 포커스가 빠진 상태에서 입력한 명령이 버퍼에 남았다가, 다시 입력한 명령과 함께 실행됐다. 실패 0건. 판정 기준은 아래와 같이 2,000건으로 바꾼다 |
| P3 | 726 B CSV 업로드, Glue 데이터베이스·테이블 생성(DDL 2회), SELECT 5회 | DDL 스캔 0 B, SELECT 각 726 B(엔진 기준) |
| 결과 조회 1차 (실행 약 15시간 뒤) | 읽기 전용 프로필로 `GetCostAndUsage` 1건(DAILY, 실행 UTC 날짜, `GroupBy=SERVICE,USAGE_TYPE`, `UsageQuantity`·`NetUnblendedCost`), 0.01 USD | **아직 미반영.** 그날 응답은 Secrets Manager 한 행뿐이고 `Estimated=true`. IoT·Firehose·Athena 행 없음. 판정·기준값 수정·정리는 하지 않고 다음 날 다시 조회한다. 원본은 저장소 밖 |

**P2 판정 기준 (2,000건 기준으로 갱신)**

| 청구 수집량 | 결론 |
|---|---|
| 약 0.0095 GB (2,000 × 5 KB) | 5 KB 올림 |
| 약 0.0004 GB (2,000 × 200 B) | 미올림 |

어느 사용 유형(`BilledBytes` 또는 `no-rounding`)으로 잡히는지도 함께 기록한다.

**P3 판정 기준**

| 청구 스캔량 | 결론 |
|---|---|
| 약 50 MB (5 × 10 MB) | 10 MB 최소 과금 |
| 1 MB 미만 | 최소 과금 없음 |

DDL이 과금되는지도 함께 본다.

## 남은 일

1. **결과 조회** (실행 다음 날부터): 읽기 전용 프로필로 Cost Explorer `GetCostAndUsage`(DAILY, 실행 UTC 날짜, `GroupBy=USAGE_TYPE`, `Metrics=UsageQuantity,NetUnblendedCost`)를 IoT·Firehose·Athena에 대해 조회한다. 하루 뒤에 사용량이 비어 있으면 하루 더 기다린다.
2. **판정 기록**: 위 기준표로 P1·P1b·P2·P3를 판정하고, `thresholds.json`과 학습 노트를 고친다.
3. **정리**: Firehose 스트림 → Glue 테이블·데이터베이스 → S3 버킷(비우고 삭제) → 전달 역할의 인라인 정책과 역할 순서로 지우고, 남은 것이 없는지 확인한다. CloudShell 홈의 임시 파일(`probe.env`, `records.json` 등)도 지운다.
