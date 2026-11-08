# 006 후속 실행 — Minikube 실제 배치 부분 검증

**최종 실측 상태 · PASS.** 4차 시도에서 큰·작은 CPU Requests 배치와 두 CPU Limits의 부하를 완료했다. 아래에 초기 부분 실행과 최종 결과를 구분해 기록한다.

현재 실행기는 지원하는 로컬 Windows named pipe에 Docker와 Minikube 연결을 고정한다. `DOCKER_HOST`가 설정되어 있거나 컨텍스트가 원격이면 시작을 중단한다. 전용 프로필의 삭제를 시도한 뒤에도 실행·프로필 라벨 및 전용 볼륨을 사용하는 보조 컨테이너를 조회해 정리한다. 잔존 여부를 확인할 수 없으면 실패로 기록한다.

호스트 여유 메모리는 Windows `GlobalMemoryStatusEx`로 감시 대상 명령의 시작 직전과 실행 중 약 2초마다 샘플링한다. 1.5 GiB 미만을 관측하면 해당 명령을 시작하지 않거나 중단한다. 로그의 최저값은 샘플 중 최저값이다. 명령 사이, 포트 포워딩 준비 및 HTTP 조회 중에는 연속 감시가 없고, 정리 명령에는 메모리 중단 기준을 적용하지 않는다.

실행 PASS에는 Requests 배치 결과와 두 Limits 구간의 유효한 측정값이 필요하다. 성공 요청, 유효한 지연·처리량, 설정과 일치하는 CPU quota, 전후 cgroup 카운터와 메모리 표본을 확인한다. 목표 부하 충족은 `target_load_met`으로 별도 기록한다. 보존한 원본과 모의 실패를 검증하려면 저장소 루트에서 `py -3 -B experiments/006-kubernetes-resource-efficiency/test_live_safety.py`를 실행한다.

## 실행 조건

Windows 11, Docker Desktop, Minikube v1.39.0, Kubernetes v1.37.0, kubectl v1.36.1, Python 3.14.7을 사용했다. 기존 로컬 이미지와 Minikube 캐시를 활용했다. 프로필·Docker 네트워크는 전용 이름으로 만들었고 Minikube 상태와 kubeconfig는 임시 디렉터리에 분리했다. Minikube 시작에 CPU 2개와 메모리 2,048 MiB를 지정했다. Kubernetes 후속 시도의 호스트 시작 기준은 3.75 GiB였으며, 실행 중 여유 메모리 1.5 GiB 미만에서 중단하는 조건을 두었다. Docker 단독 벤치마크의 5 GiB 시작 기준은 유지했다.

| 시도 | 호스트 시작 여유 | 결과 |
|---|---:|---|
| [1차 원본](live-attempt-1.json) | 3.91 GiB | 당시 Kubernetes 시작 기준 4.25 GiB에 미달해 프로필을 만들지 않음 |
| [2차 원본](live-attempt-2.json) | 3.93 GiB | 전용 프로필이 기동했고 큰 Requests 사례를 관찰. Pod 삭제 대기가 10초 안에 끝나지 않아 뒤의 비교를 중단 |

## 실제 관찰

노드 API가 보고한 Capacity와 Allocatable은 CPU 12개와 메모리 7,969,996 Ki였다. 이 값은 Minikube 시작에 지정한 자원 값과 다르다. 배치 요청은 **API의 Allocatable**을 기준으로 두 Pod 각각 6,050m 및 64 MiB로 구성했다. 두 Pod의 CPU 요청 합계는 12,100m다.

| Pod | 노드 배정 | 관측된 상태 |
|---|---|---|
| large1 | 배정됨 | 조회 시점에는 Pending. 서비스 준비는 확인하지 않았다. |
| large2 | 미배정 | PodScheduled=False, Unschedulable. Scheduler 메시지에서 `Insufficient cpu` 확인. |

이 결과는 두 큰 요청이 한 노드에 모두 배정되지 않았다는 관측이다. 작은 Requests로 줄인 경우의 실제 차이, 컨테이너 CPU·메모리·throttling, p95·p99, 처리량·오류율, 재시작·OOM은 미측정이다. 노드 API에 표시된 자원과 실제 컨테이너 제한의 차이도 후속 확인이 필요하다. 가상 배치 및 노드 비용 계산은 [정적 실험](README.md)에 별도로 보존했다.

## 정리와 재현

2차 시도의 전용 클러스터, 네트워크, 볼륨을 제거했고 잔존 리소스가 없는 것을 확인했다. 기존 `minikube` 컨텍스트와 정지된 기존 프로필을 유지했다. 기존 Docker 컨테이너 수는 전후 전체 86개, 실행 중 3개로 같았다.

후속 재시도용 [실행 코드](run_live.py)는 테스트 Pod의 종료 유예를 1초로 지정했다. 정리 뒤 호스트 여유가 약 2.5 GiB로 내려가 변경한 절차를 클러스터에서 재실행하지 못했다. 충분한 자원이 있는 같은 도구 환경에서 저장소 루트 기준 다음 명령으로 재시도한다.

```powershell
py -3 -B experiments/006-kubernetes-resource-efficiency/run_live.py
```

실행 코드는 [HTTP 워크로드](workload.py)와 [제한된 k6 부하](load.js)를 사용한다. 해당 부하 경로는 이번 시도에서 실행되지 않았다. [Minikube start 옵션](https://minikube.sigs.k8s.io/docs/commands/start/)

## 재시도 전 메모리 확인

2026-11-08에 Windows CIM의 여유 메모리는 3.518 GiB였다. 실행 코드와 같은 Windows 메모리 API로 다시 확인한 표본은 05:49:56, 05:50:01, 05:50:13 UTC에 각각 3.488, 3.497, 3.498 GiB였다. 당시 Docker 단독 실측의 5 GiB와 전용 Kubernetes의 3.75 GiB 기준에 미달해 실행을 보류했다. 기존 `minikube` 프로필은 정지 상태였고, Docker 컨테이너는 전체 86개 중 3개가 실행 중이었다.

## 저메모리 후속 실행

사용자 요청 후 전용 노드를 1,800 MiB로 제한하고 호스트 시작 하한을 3.25 GiB로 조정했다. 실행 중 중단 하한 1.5 GiB와 전용 상태 디렉터리·kubeconfig·네트워크 격리를 유지했다. 기존 프로필과 별도로 다음 명령을 사용했다.

```powershell
py -3 -B experiments/006-kubernetes-resource-efficiency/run_live.py --low-memory
```

| 시도 | 시작 여유 | 관측 |
|---|---:|---|
| [3차 원본](live-attempt-3.json) | 3.43 GiB | 작은 요청·큰 요청 배치 비교와 1,000m 부하 완료. 500m는 부하 전에 HTTP 연결이 끊겼다. |
| [4차 원본](live-attempt-4.json) | 3.53 GiB | HTTP startup probe와 제한된 준비 재확인을 추가해 배치와 두 CPU Limits 부하를 모두 완료. k6 중 최저 호스트 여유 3.05 GiB. |

두 시도에서 API가 보고한 Allocatable은 CPU 12개였다. 각 4,000m를 요청한 두 Pod는 모두 노드에 배정됐고, 각 6,050m를 요청한 두 Pod는 한 개만 배정됐다. 다른 Pod는 `Unschedulable / Insufficient cpu`였다. API의 Allocatable과 Minikube 시작 시 지정한 CPU 2개는 서로 다른 관측값이다. 이 비교는 Scheduler가 보고된 요청과 용량을 사용한 배치 결과이며, Pod가 그만큼 실제 CPU를 썼다는 뜻은 아니다.

### 4차 CPU Limits 부하

같은 100m CPU Requests·128 MiB 메모리 한도·HTTP 입력에서 CPU Limits만 바꿨다. 25회/초를 목표로 30초간 최대 3 VU로 실행했다. 아래 p95·p99는 전송된 요청 기준이다.

| CPU 한도 | p95 / p99 (ms) | 성공 req/s | 시작하지 못한 반복 | CPU 사용 (CPU초) | throttling 구간 수 | cgroup 최고 메모리 (MiB) |
|---|---:|---:|---:|---:|---:|---:|
| 1000m | 56.08 / 110.15 | 24.77 | 7 | 20.15 | 8 | 16.7 |
| 500m | 430.21 / 484.99 | 9.35 | 468 | 15.14 | 302 | 16.7 |

전송된 요청의 HTTP 오류율은 두 조건 모두 0%, 재시작과 OOM kill도 0건이었다. 500m에서 throttling과 꼬리 지연이 늘었고 처리량이 감소했다. 시작하지 못한 반복은 HTTP 오류와 별도로 집계했다. 완료된 4차 비교는 조건당 한 번이므로 반복 편차는 판단할 수 없다. 포트 포워딩과 공유 호스트 조건이 포함돼 있으며 Docker 수치와 직접 합산하지 않는다. 전용 클러스터와 Docker 자원을 정리했다. 노드 수나 실제 AWS 청구 변화는 측정하지 않았다.
