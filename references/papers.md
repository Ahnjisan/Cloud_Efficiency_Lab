# 학술 논문 — 구성 탐색과 자동 확장

현재 범위는 학회 페이지 또는 저자 공개본의 서지·초록을 확인하고 읽을 질문을 정리하는 것이다.

| 논문 | 저자·발표 | 확인 범위와 학습 연결 |
|---|---|---|
| CherryPick: Adaptively Unearthing the Best Cloud Configurations for Big Data Analytics | Omid Alipourfard 외, USENIX NSDI 2017 | 학회 서지와 초록. 분석 작업 구성 탐색에 베이지안 최적화를 적용했다는 저자 설명을 [구성 최적화](../studies/methods/configuration-optimization.md)에 연결 |
| Autopilot: workload autoscaling at Google | Krzysztof Rzadca 외, ACM EuroSys 2020 | 저자 공개본 초록과 서지. 동시 작업 수와 개별 작업의 CPU·메모리 한도를 함께 조정하는 문제를 [배치와 확장](../studies/platforms/kubernetes/scheduling-and-autoscaling.md)과 비교 |

본문 검토 시 후보 범위, 기준선, 워크로드, 평가 환경과 지표를 먼저 발췌한다. 다른 실행 환경에서 논문 결과를 그대로 기대하기 어렵다. 원문 전체 검토·실험 및 재현은 기록되지 않았다.

## 이해도 확인

논문의 최저 비용 결과를 다른 워크로드에 옮기기 전에 어떤 가정을 확인해야 하는가?

## 근거와 확인 범위

- [USENIX · CherryPick — Abstract, Open Access and BibTeX](https://www.usenix.org/conference/nsdi17/technical-sessions/presentation/alipourfard) · 2026-11-08 확인
- [EuroSys · Autopilot 저자 공개본 — Abstract와 ACM Reference Format](https://john.e-wilkes.com/papers/2020-EuroSys-Autopilot.pdf) · 2026-11-08 확인

이 문서의 예시는 설명용 가정이다. 실제 환경의 결과와 적용 가능성은 별도로 확인한다.
