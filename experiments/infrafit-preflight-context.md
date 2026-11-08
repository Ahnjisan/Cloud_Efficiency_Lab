# InfraFit 연구 실행 환경

사전점검은 읽기 전용으로 수행했다. 호스트는 Windows 11 Home 10.0.26200, 논리 CPU 12개, Python 3.14.7이다. C 드라이브 여유는 68.7 GiB였다.

| 항목 | 읽기 전용 확인 |
|---|---|
| 메모리 | 최초 2.53 GiB, 도구 재점검 2.46 GiB, 후속 2.71 GiB 및 2.33 GiB. 모두 Docker 시작 하한인 5 GiB 미만 |
| Docker | `desktop-linux`, Server 29.8.2, Compose v5.6.0. 기존 컨테이너는 전체 86개, 실행 중 3개로 확인했으며 후속 확인의 집계도 동일 |
| Kubernetes | kubectl client v1.36.1, Minikube v1.39.0, 현재 컨텍스트 `minikube`. kind 미설치. 기존 컨텍스트의 API 서버에는 접속하지 않음 |
| 워크로드 도구 | Java 17.0.19, k6 v2.3.0. Maven·Gradle 미설치 |
| Terraform | CLI 미설치. 004는 Python의 JSON 분석만 실행 |

확인 명령은 `Get-CimInstance Win32_OperatingSystem`, `[Environment]::ProcessorCount`, `[IO.DriveInfo]::new('C').AvailableFreeSpace`, `Get-Command`, `py -3 --version`, `docker context show`, `docker version`, `docker compose version`, `docker ps` / `docker ps -a`, `kubectl config current-context`, `kubectl version --client`, `minikube version`, `java -version`, `k6 version`이다. 컨테이너 식별자와 개발 환경의 절대 경로는 공개용 기록에서 제외했다.

최초 실행에서 005는 메모리 하한으로 시작을 차단했고, 006은 정적 계산만 했다. 이 시도에는 정리 대상이 없었다. [Python 실행 로그](infrafit-execution-log.json)

후속 점검에서는 불필요한 데스크톱 앱을 종료한 뒤 여유 메모리를 최대 4.49 GiB로 확인했다. Docker 단독 벤치마크는 5 GiB 미만으로 계속 차단했다. 별도 메모리 제한을 둔 Minikube에서 실제 배치를 부분 확인했고 생성한 자원을 정리했다. [후속 실측과 시도별 원본](006-kubernetes-resource-efficiency/live.md)

추가 요청 이후에는 기존 프로그램을 더 종료할 필요 없이, 시작 하한을 Docker 2.25 GiB와 전용 Minikube 3.25 GiB로 설정해 순차 실험을 완료했다. 두 실행의 중단 하한은 1.5 GiB였고, 모든 전용 자원을 정리했다. [Docker 실측](005-container-resource-efficiency/README.md) · [최종 Kubernetes 실측](006-kubernetes-resource-efficiency/live.md#저메모리-후속-실행)
