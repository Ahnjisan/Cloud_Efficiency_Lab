# Docker — 이미지에서 컨테이너까지

[Linux 자원](../../foundations/linux-resources.md)의 격리와 자원 제어를 애플리케이션 배포에 적용한다. VM은 보통 별도 게스트 커널을 사용한다. Linux 컨테이너는 실행 환경의 커널을 공유하며 Docker Desktop에서는 그 커널이 VM 안에 있을 수 있다.

## 구성과 생명 주기

CLI는 Docker Engine에 명령을 전달한다. Engine은 레지스트리에서 이미지 매니페스트와 레이어를 가져와 실행 환경을 구성하고 컨테이너 런타임을 통해 프로세스를 시작한다. 이미지는 읽기 전용 배포 입력이고 컨테이너에는 실행 상태와 쓰기 계층이 생긴다. 영속 데이터는 볼륨 등 별도 저장 위치와 백업 정책을 고려한다. 네임스페이스로 보이는 자원을 분리하고 cgroup으로 CPU·메모리 등을 계측·제어한다.

## 가상 의사결정

600 MB 이미지에서 400 MB 레이어를 이미 가진 노드가 새 이미지의 200 MB를 가져온다고 가정한다. 같은 캐시를 가진 노드 5대라면 본문 전송량은 1,000 MB다. 새 노드 5대에서는 3,000 MB다. 이미지 크기만으로 시작 시간을 예측하려면 다운로드 속도, 압축 해제, 앱 초기화가 빠져 있다. Docker inspect·history·stats로 이미지, 설정, 런타임 관측을 구분한다. 다음은 [이미지 최적화](image-optimization.md)와 [자원 제한](resource-constraints.md)이다.

## 이해도 확인

컨테이너를 다시 만들 때 이미지, 쓰기 계층, 외부 볼륨은 각각 어떤 상태가 되는가?

## 근거와 확인 범위

- [Docker overview — Docker architecture, images and containers](https://docs.docker.com/get-started/docker-overview/) · 2026-11-08 확인
- [Linux Kernel · Control Group v2 — Introduction](https://docs.kernel.org/admin-guide/cgroup-v2.html) · 2026-11-08 확인

이 문서의 예시는 설명용 가정이다. 실제 환경의 결과와 적용 가능성은 별도로 확인한다.
