# Amazon CloudWatch — 관측 범위와 비용

[AWS 서비스 목차](../README.md) · [후보별 관측과 청구 연결](../../../experiments/008-evidence-reconciliation/README.md)

관측이 있어야 [Rightsizing](../../methods/rightsizing.md)을 검증할 수 있지만 수집 설계 자체에도 비용이 든다.

## 분리할 사용량

메트릭은 숫자 시계열, 로그는 이벤트 기록, 알람은 임계·패턴 판단이다. 사용자 정의 메트릭은 이름과 차원 조합이 늘수록 시계열 수가 늘 수 있다. 로그는 수집, 보관, Logs Insights 쿼리에서 스캔한 데이터 등 별도 단위를 확인한다. 알람은 유형과 대상 메트릭 수에 따라 요금 구조가 달라질 수 있다.

수집 주기와 메트릭 해상도를 구분한다. 빠른 샘플링은 짧은 피크를 볼 수 있지만 수집 요청·고해상도 알람의 비용과 잡음이 늘 수 있다. 지표의 누락과 실제 0을 분리하고, 집계 구간은 장애 탐지에 필요한 시간보다 충분히 짧게 잡는다.

## 가상 비교

월 수집 100 GB를 가상 $0.50/GB, 쿼리 스캔 200 GB를 $0.005/GB로 두면 해당 두 항목만 $51이다. 로그 선별 후 각각 40 GB와 80 GB라면 $20.40이다. 보존 기간을 줄이는 방식은 기존 수집량을 바꾸지 않으며, 새로 남기는 보관량과 질의 범위에 영향을 준다. 모든 로그를 같은 확률로 샘플링하면 희귀 오류를 놓칠 수 있다. 오류·감사 로그의 보존 기준과 개인정보 처리를 먼저 정하고 정상 트래픽 표본, 알람 정확도, 진단 가능성을 비교한다. 실제 비용은 리전·로그 클래스·무료 범위·할인과 비용 행을 확인한다.

## 이해도 확인

수집량이 같고 쿼리에서 스캔하는 기간만 줄면 어떤 항목이 직접 바뀌는가?

## 근거와 확인 범위

- [CloudWatch · Publish custom metrics — High-resolution metrics](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/publishingMetrics.html) · 2026-11-08 확인
- [Amazon CloudWatch Pricing — Metrics, Logs, Alarms](https://aws.amazon.com/cloudwatch/pricing/) · 2026-11-08 확인

이 문서의 예시는 설명용 가정이다. 실제 환경의 결과와 적용 가능성은 별도로 확인한다.
