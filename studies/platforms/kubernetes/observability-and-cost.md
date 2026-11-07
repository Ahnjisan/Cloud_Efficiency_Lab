# Kubernetes 관측과 비용 — 사용·요청·유휴를 구분하기

Pod 지표, API 상태와 클라우드 비용을 연결해 [EKS 청구](../../aws/eks/README.md)를 해석한다.

## 자료의 역할

Metrics Server는 kubelet에서 수집한 CPU·메모리 지표를 리소스 메트릭 API로 제공한다. 장기 추세와 애플리케이션 지표는 Prometheus 등의 별도 저장·수집 계층이 필요하다. kube-state-metrics는 Kubernetes API 객체의 상태·설정 지표를 노출한다. 같은 시간 구간과 Pod 식별자로 요청·사용·배치 노드를 연결한다. 유휴는 노드 과금 중 워크로드에 할당되지 않은 부분으로 정의할 수 있으며 정책에 따라 일부 비용을 별도 표시한다.

Pod 사용량을 노드 용량과 비교한 뒤 소유 워크로드·네임스페이스로 집계한다. 공용 LB·관측·네트워크처럼 특정 Pod에 귀속하기 어려운 비용은 공유로 기록하고, 노드 유휴와 분리한다. 배분 규칙이 달라지면 팀 비용은 달라져도 원 청구 항목은 유지될 수 있다.

## 가상 배분

노드 CPU 비용 $30의 비교에서 A·B의 CPU 요청 비율이 2:1이면 $20·$10, 관측 사용 비율이 1:1이면 $15·$15다. 이 예는 전액 재분배이며 유휴 분리는 하지 않았다. OpenCost의 배분 사양은 CPU처럼 자원 할당 자체에 비용이 드는 항목의 워크로드 비용을 구할 때 요청량과 사용량 중 큰 값을 사용한다. AWS Split Cost Allocation Data는 vCPU·메모리의 배분 사용량인 `SplitUsage`에 예약량과 실제 사용량 중 큰 값을 사용한다. 각 방식의 가격 기준과 유휴 비용 처리 범위는 별도로 확인한다. 금액 변화를 실제 절감으로 판단하기 전에 노드 종료와 원 청구 항목을 대조한다.

## 이해도 확인

사용량만으로 배분하면 피크 대비로 요청된 공간이나 유휴 비용을 어떤 방식으로 기록할 수 있는가?

## 근거와 확인 범위

- [Resource metrics pipeline — Metrics Server](https://kubernetes.io/docs/tasks/debug/debug-cluster/resource-metrics-pipeline/) · 2026-11-08 확인
- [Prometheus Overview — Metrics collection](https://prometheus.io/docs/introduction/overview/) · 2026-11-08 확인
- [Kubernetes · Metrics for Kubernetes Object States](https://kubernetes.io/docs/concepts/cluster-administration/kube-state-metrics/) · 2026-11-08 확인
- [OpenCost Specification — Allocation and idle costs](https://opencost.io/docs/specification/) · 2026-11-08 확인
- [AWS Data Exports — Split line item details](https://docs.aws.amazon.com/cur/latest/userguide/split-line-item-columns.html)

이 문서의 예시는 설명용 가정이다. 실제 환경의 결과와 적용 가능성은 별도로 확인한다.
