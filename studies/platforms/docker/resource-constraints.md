# Docker 자원 제한 — CPU 스로틀링과 메모리 OOM

자원을 제한하면 같은 호스트의 다른 서비스와 경쟁을 제어할 수 있다. [워크로드 성능](../../foundations/workload-performance.md) 기준으로 제한 전후를 비교한다.

## CPU와 메모리

CPU 가중치는 경쟁 시 상대 배분에, CPU 쿼터는 지정 구간에서 실행 가능한 CPU 시간 제한에 쓰인다. 쿼터를 소진하면 호스트 전체 CPU가 낮아도 스로틀링이 발생할 수 있다. 메모리 제한에서 회수가 충분하지 않으면 OOM 종료가 발생할 수 있다. JVM 힙 외에 네이티브 메모리·스택·파일 캐시 등이 제한 내 공간을 사용한다. Docker stats와 cgroup v2의 cpu.stat, memory.current, memory.events, 애플리케이션 지연·오류를 함께 본다.

컨테이너를 인식하는 HotSpot은 지원되는 Linux 환경에서 JVM의 CPU·메모리 인식에 컨테이너 설정을 반영할 수 있다. 실제 JDK와 cgroup 버전에서 인식 여부를 확인한다. cold start와 정상 구간을 나눠 같은 입력 요청률에서 성공 처리량·p95·p99·OOM을 비교한다.

## 가상 비교

100 ms 구간에 50 ms의 CPU 시간 예산이면 CPU 0.5개 상당이다. 동시에 CPU를 요구하는 스레드 두 개가 각각 25 ms 실행하면 같은 구간의 총예산을 소진한다. 메모리 제한 512 MiB에서 힙 400 MiB와 가상 기타 사용 150 MiB가 같은 시점에 제한에 잡히면 550 MiB로 38 MiB를 초과한다. 정확한 종료 여부는 회수 가능량과 환경에 달려 있다. 고정 VM에서 컨테이너 제한만 바꾸면 VM 시간료는 유지될 수 있다.

## 이해도 확인

CPU 평균이 낮아도 p99 악화와 스로틀링이 함께 관측되는 이유는 무엇인가?

## 근거와 확인 범위

- [Oracle Java · The java Command — UseContainerSupport](https://docs.oracle.com/en/java/javase/25/docs/specs/man/java.html) · 2026-11-08 확인
- [Docker Engine · Resource constraints — CPU 및 Memory](https://docs.docker.com/engine/containers/resource_constraints/) · 2026-11-08 확인
- [Linux Kernel · Control Group v2 — cpu.stat, memory.events](https://docs.kernel.org/admin-guide/cgroup-v2.html) · 2026-11-08 확인

이 문서의 예시는 설명용 가정이다. 실제 환경의 결과와 적용 가능성은 별도로 확인한다.
