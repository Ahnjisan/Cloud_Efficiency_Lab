# Kubernetes 배치와 자동 확장 — Pod와 노드의 제어 루프

[Requests와 Limits](resource-management.md)를 줄였을 때 실제로 노드가 줄어드는 조건을 구분한다.

## 배치와 확장

스케줄러는 가능한 노드를 필터링하고 점수로 고른다. 자원 충족, taint/toleration, affinity, 토폴로지 분산 같은 조건이 배치를 제한한다. Bin packing은 여러 Pod를 적은 노드에 모으지만 CPU와 메모리 비율이 다르면 조각화가 생기고 장애 범위도 커질 수 있다. HPA는 지표를 보고 복제본 수를 조정하며 CPU 사용률 목표는 요청값의 영향을 받는다. VPA는 요청 권고·조정에 쓰이며 모드에 따라 재시작이나 퇴거가 필요할 수 있다. Cluster Autoscaler는 노드 그룹 용량을, Karpenter는 조건에 맞는 노드 공급·정리를 다룬다.

HPA가 자원 지표를 사용하려면 리소스 메트릭 API 등의 지표 공급이 필요하다. VPA는 별도 설치와 업데이트 모드 설정이 필요하다. 노드 오토스케일러의 공급자·클러스터 버전 지원과 중단 정책을 확인한다.

## 가상 반례

노드 두 대에 각각 1 CPU·4 GiB가 남으면 합계는 2 CPU·8 GiB다. 2 CPU·3 GiB Pod는 어느 노드에도 들어가지 못한다. CPU 목표 HPA와 VPA를 함께 변경하면 요청값 변화가 HPA 분모를 바꿔 결과를 혼동할 수 있다. Pending 이유, 지표 지연, 노드 공급 시간, PDB와 토폴로지, 축소 뒤 재배치·가용성을 확인한다.

## 이해도 확인

클러스터 전체 여유 용량은 충분한데 Pod가 Pending이면 어떤 배치 제약을 확인하는가?

## 근거와 확인 범위

- [Vertical Pod Autoscaling — Update modes](https://kubernetes.io/docs/concepts/workloads/autoscaling/vertical-pod-autoscale/) · 2026-11-08 확인
- [Node Autoscaling — Provisioning and consolidation](https://kubernetes.io/docs/concepts/cluster-administration/node-autoscaling/) · 2026-11-08 확인
- [Karpenter Disruption — Consolidation and controls](https://karpenter.sh/docs/concepts/disruption/) · 2026-11-08 확인
- [Kubernetes · Autoscaling — Horizontal, Vertical and Node autoscaling](https://kubernetes.io/docs/concepts/workloads/autoscaling/) · 2026-11-08 확인

이 문서의 예시는 설명용 가정이다. 실제 환경의 결과와 적용 가능성은 별도로 확인한다.
