# Kubernetes — 제어면에서 워크로드 실행까지

[Docker 구조](../docker/README.md)의 컨테이너 실행을 클러스터로 확장한다. Kubernetes는 선언한 상태와 관측 상태를 지속적으로 맞춘다.

## 역할과 요청 흐름

API 서버가 선언을 받고 etcd에 클러스터 상태가 저장된다. 컨트롤러가 원하는 복제 수 등에 맞춰 오브젝트를 조정하며, 스케줄러가 아직 배정되지 않은 Pod의 노드를 고른다. 노드의 kubelet이 컨테이너 런타임에 Pod 실행을 요청한다. Pod는 배치 단위이고, Deployment는 교체 가능한 복제본 관리에, StatefulSet은 안정적인 식별·저장 연결이 필요한 워크로드에 쓰인다. Service는 바뀌는 Pod 뒤에 안정적인 접근점을 제공한다.

## 가상 판단

세 Pod가 각각 500m을 요청하면 합계 1.5 CPU 요청이다. 복제본을 네 개로 늘리면 2 CPU로, 노드 제약에 따라 한 Pod가 Pending일 수 있다. Service가 준비된 Pod로 요청을 보낼 수 있어도 장애 도메인에 고르게 배치됐는지는 별도 확인한다. kubectl의 객체·이벤트·상태를 대조해 선언, 배정, 기동, 준비를 구분한다. 이어서 [Requests와 Limits](resource-management.md), [배치와 확장](scheduling-and-autoscaling.md), [관측과 비용](observability-and-cost.md)을 읽는다.

## 이해도 확인

Deployment 복제 수가 3인데 Service에서 준비된 대상이 2라면 어느 단계부터 확인하는가?

## 근거와 확인 범위

- [Kubernetes Components — Control plane and node components](https://kubernetes.io/docs/concepts/overview/components/) · 2026-11-08 확인

이 문서의 예시는 설명용 가정이다. 실제 환경의 결과와 적용 가능성은 별도로 확인한다.
