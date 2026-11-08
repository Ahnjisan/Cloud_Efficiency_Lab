# 006 — Kubernetes 자원 효율 · 정적 검증

**정적 검증 PASS · 실제 클러스터 검증 PASS.** 격리된 Minikube에서 큰·작은 Requests 배치를 비교하고, CPU Limits 1,000m와 500m에서 HTTP 부하를 완료했다. 초기 부분 실행과 최종 측정의 범위는 [실측 기록과 원본 로그](live.md)에 구분했다. [환경 기록](../infrafit-preflight-context.md)

가설은 Requests를 줄이면 같은 Allocatable에서 배치 가능성이 달라지지만, 그 사실만으로 실제 사용량이나 노드 청구가 줄지는 않는다는 것이다. [합성 Pod manifest](pods.json)는 기준 A(700m), B(400m), C(B와 같은 요청, CPU limit 1000m→600m)를 담는다. 메모리 요청은 각 512 MiB이며 가상 복제본은 4개다.

| 가상 노드 | Allocatable | A의 최소 노드 수 및 720시간 비용 | B·C |
|---|---|---|---|
| Small · $0.12/시간 | 1,800m / 3,072 MiB | 2대 · $172.80 | 1대 · $86.40 |
| Large · $0.22/시간 | 3,600m / 7,168 MiB | 1대 · $158.40 | 1대 · $158.40 |

Small 한 대의 경우 A의 CPU 요청 합계 2,800m는 배치 불가이고, B·C의 1,600m는 메모리 2,048 MiB와 함께 수용된다. 또한 전체 메모리 합계가 충분해도 노드 한 대에 맞지 않는 단일 Pod는 배치할 수 없는 반례를 검사했다. B와 C의 동일 배치 결과는 모델에서 Limits가 달라도 Requests가 동일하기 때문이다.

Windows 11, Python 3.14.7에서 `py -3 -B experiments/006-kubernetes-resource-efficiency/placement.py`를 실행했다. 종료 코드 0. [정적 출력 원본](result.json) · [실행 로그](../infrafit-execution-log.json). manifest에서 정수 m·Mi와 요청이 제한을 넘지 않는 조건을 읽었으며, API 검증은 수행하지 않았다.

이 정적 모델은 CPU와 메모리만 보는 소규모 배치 가능성 검사다. DaemonSet, 장애 도메인, Pod 오버헤드는 모델에 포함하지 않았다. 실제 Pending과 부하 지표는 [후속 실측](live.md)에 따로 기록했다. 가용성 요건과 실제 노드 축소는 후속 검증 범위다. [Kubernetes 공식 자원 관리](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/) · [기존 학습 자료](../../studies/platforms/kubernetes/resource-management.md)
