# AWS 비용 데이터 — 청구·내보내기·추천

[AWS 서비스 목차](../README.md) · [청구 대사 실험](../../../experiments/008-evidence-reconciliation/README.md)

비용 변화의 원인을 관측할 때 비용 뷰의 목적, 시간 기준, 단위를 정한다. [FinOps 비용 지표](../../foundations/finops-cost-metrics.md)와 연결한다.

## 도구와 식별자

Bills는 청구 내역, Cost Explorer는 기간별 집계·필터, CUR·AWS Data Exports는 행 단위 내보내기 분석에 활용한다. AWS Data Exports 공식 문서는 AWS 확장 열을 포함한 FOCUS 1.2와 1.0 테이블을 안내한다. 아래 예제는 FOCUS 1.4 사양을 참고하므로, 실제 분석에서는 선택한 테이블의 버전과 스키마를 확인하고 표준 열과 AWS 확장 열을 구분한다. 비용 할당 태그 활성화와 적용 기간, Cost Categories 규칙, 미분류 행을 확인한다. Cost Optimization Hub는 추천을 모아 비교하는 데, Compute Optimizer는 사용량에 기반한 자원 추천에 사용한다. 추천액은 실제 청구 변화와 다르며 중복 추천을 조심한다.

## 가상 열 예제

같은 청구 계정과 통화(USD)에서 약정 적용 기간 전체를 조회한다고 가정한다. 선결제 $100은 첫 달과 둘째 달 사용에 각각 $75와 $25가 배분된다.

| 기간 | `ChargeCategory` | 내역 | `BilledCost` | `EffectiveCost` |
|---|---|---|---:|---:|
| 첫 달 | Purchase | 두 달의 적격 사용을 커버하는 약정 구매 | $100 | $0 |
| 첫 달 | Usage | 약정 적용 사용분 | $0 | $75 |
| 둘째 달 | Usage | 약정 적용 사용분 | $0 | $25 |
| 첫 달 | Usage | 약정 미적용 사용분 | $30 | $30 |
| 전체 합계 | | | $130 | $130 |

첫 달만 보면 청구 비용은 $100+$30=$130, 실효 비용은 $75+$30=$105다. 둘째 달에 실효 비용 $25가 반영되므로 전체 기간 합계는 두 열 모두 $130이다. 약정 관련 행만 보면 구매 행과 적용 사용 행을 모두 포함한 전체 기간에 두 합계가 각각 $100이다. 약정 미적용 사용 행의 두 비용 값은 같다.

기간·타임존, 계정 범위, 할인 및 청구 정정 반영 지연이 다르면 집계를 재현할 수 없다. 지표 연결 시 리소스 ID와 시간 입도를 먼저 대조하고 미매칭 비용을 남긴다.

## 이해도 확인

일별 비용이 나중에 바뀌었을 때 이상탐지 전에 어떤 갱신·정정 조건을 확인하는가?

## 근거와 확인 범위

- [AWS Data Exports — What is Data Exports?](https://docs.aws.amazon.com/cur/latest/userguide/what-is-data-exports.html) · 2026-11-08 확인
- [AWS Cost Explorer — What is AWS Cost Explorer?](https://docs.aws.amazon.com/cost-management/latest/userguide/ce-what-is.html) · 2026-11-08 확인
- [AWS Cost Optimization Hub — 개요](https://docs.aws.amazon.com/cost-management/latest/userguide/cost-optimization-hub.html) · 2026-11-08 확인
- [FOCUS Specification 1.4 — Cost and Usage](https://focus.finops.org/docs/specification/v1-4/datasets/cost-and-usage/) · 2026-11-08 확인
- [FOCUS Specification 1.4 — Effective Cost 요구사항](https://focus.finops.org/docs/specification/v1-4/columns/cost-and-usage/effective-cost/)

이 문서의 예시는 설명용 가정이다. 실제 환경의 결과와 적용 가능성은 별도로 확인한다.
