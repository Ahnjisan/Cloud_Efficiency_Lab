# 비용 이상탐지 — 기준선·오탐·탐지 지연

이상탐지는 검토 후보의 우선순위를 정한다. [비용 예측](forecasting.md)의 기대값과 관측값의 차이인 잔차를 사용하면 반복 주기를 일부 제거할 수 있다.

## 방법과 가상 평가

Z-score는 평균에서의 거리를 표준편차로 나누며 극단치와 계절성에 민감하다. MAD는 중앙값에서 절대편차의 중앙값을 사용하며 0일 때 대체 기준이 필요하다. EWMA는 지속적 편이를 볼 수 있으나 학습 속도와 경보 지연이 연결된다. Isolation Forest는 무작위 분할로 쉽게 고립되는 관측을 탐색한다. scikit-learn의 `score_samples`와 `decision_function`은 값이 낮을수록 더 비정상이며, 점수만으로 원인을 알 수 없다. 예측 잔차 임계치도 배포·환율·할인 변경을 조사해야 한다.

가상 라벨에서 TP=8, FP=2, FN=4라면 Precision=8/10=80%, Recall=8/12≈66.7%, F1=16/22≈72.7%다. 경보당 조사 비용, 첫 탐지까지의 시간, 탐지하지 못한 비용 영향을 별도로 비교한다. 실제 사고 라벨과 합성 주입 라벨은 분리하고 누락·지연 청구와 조사되지 않은 사례를 정상으로 단정하지 않는다.

운영 평가에서는 정상 100개 구간 중 2개가 잘못 경보되었다면 오탐률을 2%로 기록한다. 이는 전체 경보 중 20%가 오탐인 위 예의 비율과 분모가 다르다. 실제 라벨이 불완전하면 오탐률과 미탐 비용의 평가 가능 범위를 함께 명시한다.

## 이해도 확인

Precision이 높아졌는데 평균 탐지 지연이 늘면 어떤 운영 조건에 따라 채택을 보류하는가?

## 근거와 확인 범위

- [scikit-learn · Novelty and Outlier Detection — Isolation Forest](https://scikit-learn.org/stable/modules/outlier_detection.html) · 2026-11-08 확인
- [scikit-learn · IsolationForest — 점수의 방향](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html)

이 문서의 예시는 설명용 가정이다. 실제 환경의 결과와 적용 가능성은 별도로 확인한다.
