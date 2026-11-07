# Kubernetes 자원 관리 — Requests·Limits·노드 압력

[클러스터 구조](README.md)에서 Pod가 배치되고 실행될 때 서로 다른 자원 기준이 쓰인다.

## 배치와 실행

스케줄러는 노드의 Allocatable과 이미 배치된 요청을 바탕으로 새 Pod를 배치할 수 있는지 본다. 실행 사용량은 계측값이다. CPU limit에 도달하면 스로틀링될 수 있고 메모리 limit은 압력에서 OOM 종료로 이어질 수 있다. QoS는 CPU·메모리 요청·제한의 구성에 따라 Guaranteed, Burstable, BestEffort로 분류한다. 노드 압력 퇴거는 kubelet이 노드 자원을 회수하는 동작이다. Pod 우선순위와 요청 대비 사용량 등을 함께 보며 컨테이너 자체 OOM과 구분한다.

## 가상 배치

Allocatable 4 CPU·8 GiB인 노드에서 기존 요청 2.5 CPU·5 GiB이면 1.5 CPU·3 GiB가 남는다. 새 Pod가 1 CPU·4 GiB를 요청하면 기존 실제 메모리가 2 GiB여도 이 요청으로는 배치되지 않는다. 실제 피크, 장애 재배치, 지연·OOM 이력을 바탕으로 요청 변경 후보를 만든다. Pod 이벤트와 CPU throttling, 종료 원인, 노드 압력을 대조한다.

## 이해도 확인

CPU 요청을 만족하지만 메모리 요청이 노드의 남은 Allocatable을 초과하면 어떤 일이 생기는가?

## 근거와 확인 범위

- [Resource Management for Pods and Containers — Requests, Limits and Scheduling](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/) · 2026-11-08 확인
- [Node-pressure Eviction — Pod selection](https://kubernetes.io/docs/concepts/scheduling-eviction/node-pressure-eviction/) · 2026-11-08 확인

이 문서의 예시는 설명용 가정이다. 실제 환경의 결과와 적용 가능성은 별도로 확인한다.
