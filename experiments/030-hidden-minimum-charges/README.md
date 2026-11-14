# 030 — 숨은 최소 요금

[실험 목차](../README.md) · [누수 패턴 7](../../studies/methods/cost-leak-patterns.md#7-숨은-최소-요금) · [ElastiCache 노트](../../studies/aws/elasticache/README.md) · [OpenSearch 노트](../../studies/aws/opensearch/README.md)

**재현 PASS. H1·H2 지지.** 사용량이 적을 때 실제 사용량이 아니라 최소치가 비용을 정하는 서비스 다섯 가지의 곡선을 그리고, 시나리오 ②에서 최소치가 정하는 비용을 챗봇 모델 토큰 비용과 비교했다.

## 실행 전 결정

| 항목 | 내용 |
|---|---|
| 질문 | "요율 × 사용량"으로 추정하면 작은 작업량에서 얼마나 과소 추정하는가? 시나리오 ②에서 최소치가 정하는 비용은 어느 정도인가? |
| 지표 | 최소치 몫 = 1 − 사용량 기반 비용 / 실제 과금액 |
| 가설 H1 | 시나리오 ②에서 최소치가 정하는 월 비용(벡터 저장소 최소 OCU + 캐시 최소 저장량 초과분)이 챗봇 모델 토큰 비용보다 크다. |
| 가설 H2 | 데이터 50 MB 캐시에서 서버리스 엔진을 Redis OSS에서 Valkey로 바꾸면 저장 비용이 90% 이상 준다. |
| 최소치 | ElastiCache 서버리스 저장 Valkey 100 MB·Redis OSS 1 GB, OpenSearch Serverless Classic 2 OCU, Fargate Linux 1분, Athena 질의당 10 MB, Guardrails 텍스트 단위 1,000자 |
| 요율 | [2026-11-15 사본](../../references/aws-price-list-apn2-2026-11-15.json). 챗봇 모델은 Claude Haiku 4.5(입력 1.00·출력 5.00 USD/100만 토큰) |
| 제외 | Knowledge Base 관리형 인덱스 저장(요금 페이지에 원본 GB당 월 5 USD) — 사본 `missing` 목록에 있어 계산하지 않음 |

## 실행

```powershell
cd experiments/030-hidden-minimum-charges
py -3 -B evaluate.py > result.json
py -3 -B test_evaluate.py
```

## 결과

**최소치 몫 곡선**

| 서비스 | 사용량 → 최소치 몫 |
|---|---|
| ElastiCache 서버리스 Valkey | 10 MB 90%, 50 MB 50%, 100 MB 이상 0% |
| ElastiCache 서버리스 Redis OSS | 10 MB 99%, 50 MB 95%, 100 MB 90%, 500 MB 50%, 1 GB 이상 0% |
| OpenSearch Classic (평균 필요 OCU) | 0.1 OCU 95%, 0.5 OCU 75%, 1 OCU 50%, 2 OCU 이상 0% |
| Fargate 태스크 (0.25 vCPU·0.5 GB) | 5초 92%, 15초 75%, 30초 50%, 60초 이상 0% |
| Athena 질의 | 0.1 MB 99%, 1 MB 90%, 5 MB 50%, 10 MB 이상 0% |
| Guardrails 질문 | 30자 97%, 200자 80%, 1,000자 0%, 1,500자 25%(올림) |

**시나리오 ② 월 비용(USD)**

| 구성 요소 | 과금액 | 사용량 기반 |
|---|---:|---:|
| 벡터 저장소 OpenSearch Serverless Classic | 427.78 | 알 수 없음(원본 2 GB에 필요한 OCU 미측정) |
| 캐시 서버리스 Valkey 저장(데이터 50 MB) | 7.37 | 3.69 |
| 챗봇 모델 토큰(질문 5만 건) | 175.00 | 175.00 |

- **H1 지지**: 최소치가 정하는 비용 431.47 USD(최소 OCU 전부 + 캐시 초과분 3.68)가 모델 토큰 175.00 USD의 2.5배였다. 실제 필요한 OCU를 모르므로 최소 OCU 전부를 최소치 몫으로 셌다. 실제 필요가 평균 약 1.19 OCU 이하이면 결론이 유지된다.
- **H2 지지**: 같은 데이터에서 Redis OSS 서버리스는 110.23 USD, Valkey는 7.37 USD로 93.3% 낮았다.
- 공통 모양: 사용량이 최소치의 절반이면 최소치 몫이 50%, 10분의 1이면 90%다. 최소치보다 많이 쓰면 0이다.

## 해석

- 작은 작업량(개발 환경, 초기 서비스, 사내 도구)에서는 **사용량이 아니라 최소치가 비용을 정한다.** "요율 × 예상 사용량"으로 만든 설계 단계 추정은 이 구간에서 크게 과소 추정한다. 설계 단계 비용 모델([036](../036-architecture-cost-model/README.md))은 구성 요소마다 `max(최소치, 사용량)`을 써야 한다.
- 챗봇 비용을 줄이려고 모델·프롬프트를 먼저 보는 경우가 많지만, 이 시나리오에서는 벡터 저장소 선택(Classic → NextGen 또는 다른 저장소)이 더 크다. 단, 지연·가용성 요구를 모르면 판단 보류다.
- InfraFit 규칙 후보: "서버리스 캐시의 저장량 지표가 엔진 최소치보다 작다" → 변경 검토 후보(엔진 변경), 근거 수준 공식 자료. 엔진 호환성은 사람이 확인.

## 가정·제외·한계

- KB 관리형 인덱스 저장 요금은 사본에 없어 빠졌다. 넣으면 최소·고정 성격 비용이 더 커진다.
- NextGen 컬렉션, 다른 벡터 저장소(S3 Vectors, Aurora 등)는 비교하지 않았다.
- 시나리오의 질문 수·토큰 수·캐시 데이터 크기는 가정값이다.

## 테스트

`test_evaluate.py` 4개: 최소치 몫 식, 최소치 위에서 0, Fargate 15초 → 60초 과금, `result.json` 재현.
