# 표준·프레임워크 — 비용 데이터와 판단 기준

표준의 스키마, 운영 프레임워크, 도구의 비용 모형을 구분한다. 예를 들어 FOCUS에서 동일한 비용 열을 쓰더라도 조직이 공통비를 배분하는 분모는 별도로 합의해야 한다.

| 자료 | 확인 범위와 용도 |
|---|---|
| FinOps Foundation, FinOps Framework | 단계와 역량. 비용 관측·최적화·운영의 협업 범위 |
| FOCUS Specification v1.4 | Cost and Usage 데이터셋. BilledCost·EffectiveCost·ServiceName 등 비교 기준. 공급자 내보내기가 동일 버전이라고 가정하지 않음 |
| AWS Well-Architected Cost Optimization Pillar | 비용 인식과 자원 선정. 개선 판단과 지속 검토의 질문 |
| OpenCost Specification | Kubernetes 자산·워크로드·유휴 배분 범위 |
| IETF RFC 9293, TCP (2022) | 연결과 순서 있는 전송. 클라우드 과금 모델과 별도 |

실제 분석에는 [비용 데이터](../studies/aws/cost-data/README.md)와 [배분 방법](../studies/methods/cost-allocation.md)을 연결한다.

## 이해도 확인

FOCUS 열을 사용해도 조직마다 유휴 비용 배분이 달라지는 이유는 무엇인가?

## 근거와 확인 범위

- [FinOps Framework — Phases and Capabilities](https://www.finops.org/framework/) · 2026-11-08 확인
- [FOCUS 1.4 — Cost and Usage](https://focus.finops.org/docs/specification/v1-4/datasets/cost-and-usage/) · 2026-11-08 확인
- [AWS Well-Architected Cost Optimization Pillar — Overview](https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/welcome.html) · 2026-11-08 확인
- [OpenCost Specification — Allocation](https://opencost.io/docs/specification/) · 2026-11-08 확인
- [RFC 9293 — Functional Specification](https://www.rfc-editor.org/rfc/rfc9293.html) · 2026-11-08 확인

이 문서의 예시는 설명용 가정이다. 실제 환경의 결과와 적용 가능성은 별도로 확인한다.
