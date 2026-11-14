# 기준 시나리오와 공통 모듈 (실험 026~036)

[실험 목차](../README.md) · [누수 패턴 방법 노트](../../studies/methods/cost-leak-patterns.md)

실험 026~036은 같은 두 시나리오와 같은 요율 사본을 씁니다. 시나리오는 **일반화한 가상 구성**이며 특정 조직·과제를 나타내지 않습니다.

## 시나리오

| 파일 | 구성 | 주로 쓰는 실험 |
|---|---|---|
| [iot-pipeline-agent.json](iot-pipeline-agent.json) | ① 디바이스 100대가 10초마다 200 B 측정값 전송 → IoT Core → Firehose → S3, 실시간 Lambda, 시간별 Glue 작업, Athena 조회, 운영자 질문에 답하는 AI 에이전트(요청당 모델 호출 4회, Athena 질의 2회) | 026, 027, 032, 034, 036 |
| [web-llm-chatbot.json](web-llm-chatbot.json) | ② HTTP API + ECS Fargate 서비스 + RDS PostgreSQL + 서버리스 캐시, 사내 LLM 챗봇(월 5만 질문, Guardrails, OpenSearch Serverless 벡터 저장소), NAT 1개·2 AZ, 개발 환경 일정 | 028, 029, 030, 031, 032, 033, 035, 036 |

수치(디바이스 수, 질문 수, 토큰 수, 트래픽 GB 등)는 모두 가정값이며, 실험마다 README의 "실행 전 결정"에 사용한 값을 다시 적습니다.

## 공통 모듈

| 파일 | 역할 |
|---|---|
| [pricebook.py](pricebook.py) | [서울 요율 사본 2026-11-15](../../references/aws-price-list-apn2-2026-11-15.json)에서 요율을 `Decimal`로 읽는다. 사본에 없는 요율은 `KeyError` — 추정하지 않는다. 구간 요금(`tiered`), 월 730시간, UTF-8 JSON 출력(`emit`) |
| [service_pack.py](service_pack.py) | 서비스별 과금 단위·최소치(`UNITS`), 올림 식 `billed`, Fargate 허용 조합 `fargate_provision`(EKS +256 MB), `max_pods`, 노드 인스턴스 사양 |
| [test_scenarios.py](test_scenarios.py) | 요율 읽기, 구간 요금, 올림·조합·maxPods 계산 확인 |

`service_pack.py`는 InfraFit의 "서비스 팩"(서비스별 단위·최소치·요율 행 이름) 구조를 시험하는 원형입니다. 단위의 근거와 확인일은 각 학습 노트의 공식 참고 자료 표에 있습니다. 공식 문장으로 확인하지 못한 값(IoT 5 KB의 바이트 정의, ECPU의 소수 KB 올림, HTTP API 512 KB)은 `basis`에 표시했습니다.

## 실행

```powershell
cd experiments/scenarios
py -3 -B test_scenarios.py
```
