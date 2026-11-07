# Rightsizing — 사용 분포에서 자원 후보로

[EC2](../aws/ec2/rightsizing-and-autoscaling.md)와 [Kubernetes](../platforms/kubernetes/resource-management.md)의 자원 조정을 공통 절차로 비교한다.

## 후보 규칙

같은 기간·입도의 CPU 코어 사용, 메모리 피크, I/O와 처리량, p99·오류를 모은다. 휴일·배치·배포·장애 대응을 포함하고 누락과 스로틀링을 표시한다. 포화 상태에서 측정한 사용량은 미처리 수요를 반영하지 못할 수 있다. 백분위에 여유를 더해 후보를 만들고 메모리·대역폭·아키텍처·장애 시 수용량으로 필터링한다.

가상 CPU p95가 1.4 코어이고 목표 사용률이 70%면 1.4/0.70=2 코어다. 피크 2.3 코어가 지연에 민감하거나 가상 메모리 6 GiB를 요구하면 2 vCPU·4 GiB 후보는 배제한다. p95 규칙과 Compute Optimizer 권고를 각각 기준선에 비교하며 같은 성공 처리량·p99·오류·비용을 평가한다. 노드 제거·약정 재배치 등 청구 변화가 확인돼야 실현 절감을 말할 수 있다.

## 이해도 확인

관측 p95가 낮아도 스로틀링이 많으면 후보 산정을 왜 보류해야 하는가?

## 근거와 확인 범위

- [AWS Compute Optimizer — Recommendations and utilization metrics](https://docs.aws.amazon.com/compute-optimizer/latest/ug/what-is-compute-optimizer.html) · 2026-11-08 확인
- [AWS Well-Architected Cost Optimization Pillar — Cost-effective resources](https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/welcome.html) · 2026-11-08 확인

이 문서의 예시는 설명용 가정이다. 실제 환경의 결과와 적용 가능성은 별도로 확인한다.
