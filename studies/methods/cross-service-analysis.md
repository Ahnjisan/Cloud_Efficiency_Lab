# 서비스 간 비용 분석 — 경로와 순효과

[네트워크 경로](../foundations/network-and-data-flow.md)와 [AWS 비용 행](../aws/cost-data/README.md)을 결합해 한 자원의 비용 감소가 다른 항목으로 이전되는지 본다.

## 의존성 분석

호출 서비스를 노드, 호출 횟수·전송량·AZ 경계를 간선으로 표시한다. 팬아웃·재시도·중복 저장·로그가 기본 요청을 증폭한다. 배포 식별자, 리소스 ID와 시간창을 매핑하고 미연결 EBS·LB 등 잔존 리소스를 확인한다. 상태 변경이 겹치면 대조군 또는 변경 전후의 트래픽·가격·배포 차이를 기록한다.

가상 캐시 도입으로 DB가 월 $80 감소하고 캐시가 $35, 추가 전송이 $10 늘면 순 추정 차이는 $35다. DB 권고와 캐시 권고가 같은 DB $80 감소를 설명하면 두 번 더하지 않는다. 가설은 같은 성공 요청 수에서 비용과 p99가 함께 개선된다는 것으로 정하고, 장애 시 캐시 미스 폭주와 일관성 요구를 평가한다. 정확한 연결 근거가 없는 청구 항목은 별도 보류한다.

## 이해도 확인

요청량이 바뀐 주에 DB 비용이 줄었다면 어떤 분모와 비교군이 필요한가?

## 근거와 확인 범위

- [AWS Well-Architected Cost Optimization Pillar — Expenditure and usage awareness](https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/welcome.html) · 2026-11-08 확인
- [AWS Cost Optimization Hub — Aggregating recommendations](https://docs.aws.amazon.com/cost-management/latest/userguide/cost-optimization-hub.html) · 2026-11-08 확인

이 문서의 예시는 설명용 가정이다. 실제 환경의 결과와 적용 가능성은 별도로 확인한다.
