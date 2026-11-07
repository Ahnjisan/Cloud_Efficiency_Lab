# 공식 데이터 예제 — FOCUS 비용·사용량

FinOps FOCUS 공식 안내는 공급자에서 자신의 청구 자료를 내보내는 방법과 학습용 샘플 생성 경로를 구분한다. 이 저장소에서는 [비용 배분](../studies/methods/cost-allocation.md)의 스키마·대사 연습에 활용할 후보로 둔다.

| 항목 | 확인 내용 |
|---|---|
| 형식·크기 | FOCUS 1.4 부록의 24시간 약정 할인 예시 CSV는 공개 요약 기준 §8.2.3.2가 25행(구매 1행, 사용 24행), §8.2.4.2가 26행(구매 2행, 사용 24행)이다. 원본 바이트 크기는 미확인 |
| 필드 | ChargePeriodStart, ServiceName, ChargeCategory, BilledCost, EffectiveCost 등 사양 열을 대조. 샘플별 구현 범위를 확인해야 함 |
| 접근 | 공식 안내 및 사양 부록은 웹 공개. 계정에서 내보낸 실제 청구 자료에는 계정 권한과 개인정보 처리 기준 적용 |
| 라이선스 | 사양 문서의 라이선스와 샘플 파일 또는 생성기 산출물의 배포 조건을 구분. 샘플 파일 별도 재배포 조건은 미확인 |
| 한계 | 할인 설명용 예시에는 운영 이상·낭비 정답 라벨이 보장되지 않는다. 24시간은 주간 계절성 평가에도 부족하다 |

샘플 원본을 내려받거나 저장소에 포함하지 않았다. 실제 운영 자료는 비용 라벨 누락·식별자 민감도·지연 정정을 확인하고, 합성 자료에서는 주입 규칙과 실제 사고 여부를 별도 열로 관리한다.

## 이해도 확인

24시간 예시 CSV가 합계 대사에는 유용해도 이상탐지 평가에 부족한 이유는 무엇인가?

## 근거와 확인 범위

- [Getting Started with FOCUS Datasets — Provider and sample dataset paths](https://focus.finops.org/docs/implementation/get-started/get-started-with-focus-datasets/) · 2026-11-08 확인
- [FOCUS 1.4 — Examples: Commitment Discounts](https://focus.finops.org/docs/specification/v1-4/sections/appendix/commitment-discounts/) · 2026-11-08 확인

이 문서의 예시는 설명용 가정이다. 실제 환경의 결과와 적용 가능성은 별도로 확인한다.
