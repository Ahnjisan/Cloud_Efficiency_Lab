# 010 — CPU 한도별 품질 기준 재검증

[실험 목차](../README.md) · [최종 연구 보고서](../../FINAL-REPORT.md)

**010 보존 로그 분석 PASS.** [Docker 원본](../005-container-resource-efficiency/live-result.json)과 [Kubernetes 원본](../006-kubernetes-resource-efficiency/live-attempt-4.json)을 환경별로 집계했다. 새 Kubernetes 반복 실측은 [015](../015-kubernetes-rollback/README.md)에 기록했다. 실험용 품질 기준은 p99 200ms 이하, 전송 요청 HTTP 오류율 1% 이하, 제공된 부하 대비 성공률 99% 이상이다. 제공된 부하는 이 단일 요청 워크로드의 HTTP 요청 건수와 시작하지 못한 반복의 합이다.

저장소 루트에서 `py -3 -B experiments/010-cpu-quality-envelope/analyze.py`를 실행한다. [결과 원본](result.json)

k6 요약에 미시작 반복 항목이 없으면 0건으로 처리한다. 음수·비유한 지연, 범위를 벗어난 오류율, 성공 건수와 모순되는 오류율, 잘못된 반복 건수는 분석 오류로 처리한다. 반례는 `py -3 -B experiments/010-cpu-quality-envelope/test_analyze.py`로 재현할 수 있다.

| 환경 | 500m 기준 통과 | 1,000m 기준 통과 | 반복 편차 |
|---|---:|---:|---|
| Docker | 0/2 | 2/2 | p99 범위 폭은 각각 34.62ms, 28.74ms |
| Kubernetes | 0/1 | 1/1 | 각 조건 1회로 미확인 |

### 전용 환경에서의 반복 절차

동일 이미지, Requests, 메모리 한도, 부하 스크립트로 500m·1,000m 쌍을 최소 세 차례 수집한다. [006 실행기](../006-kubernetes-resource-efficiency/run_live.py)를 순차 호출하고 매회 다른 파일에 stdout을 저장한다. 실행 전 호스트 여유와 부하 발생기의 CPU 여유를 확인하고, 실행 후 정리 확인과 종료 코드를 기록한다. 저메모리 모드와 일반 모드의 결과는 따로 집계한다.

```powershell
py -3 -B experiments/006-kubernetes-resource-efficiency/run_live.py > pair-1.json
# Repeat with distinct paths and keep each exit code.
py -3 -B experiments/010-cpu-quality-envelope/analyze.py --kubernetes pair-1.json pair-2.json pair-3.json
```

조건별 p99 범위, 제공 부하 대비 성공률, 미시작 반복, 오류율, throttling을 원본과 대조한다. 현재 실행기는 한도 순서가 고정돼 있다. 순서 효과를 분리하거나 제공 부하 수준별 경계를 찾으려면 순서와 부하량을 별도 변수로 두고 비교해야 한다. 이 실험은 노드 수나 AWS 청구 변화를 추정하지 않는다.
