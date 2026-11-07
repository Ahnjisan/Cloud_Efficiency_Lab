# EC2 — Rightsizing과 Auto Scaling

[EC2 실행 비용](README.md)에서 사용 시간의 효과를 보았다. 여기서는 인스턴스 크기와 대수를 함께 조정한다.

## 자원과 후보 선택

범용·컴퓨팅·메모리 최적화 계열은 vCPU와 RAM의 비율이 다르다. 아키텍처, 네트워크, EBS 대역폭, 버스트 기준도 확인한다. 수직 조정은 인스턴스 사양을 바꾸고 수평 확장은 인스턴스 수를 바꾼다. Auto Scaling 그룹의 최소·희망·최대 용량과 대상 추적 정책은 기동·등록·워밍업 지연 및 AZ 장애 여유를 고려해 정한다. CPU만으로 메모리나 연결 병목을 판별하기 어려워 에이전트 지표와 서비스 SLO를 결합한다.

Scale-out은 대수 추가, scale-in은 대수 축소다. 축소 시 연결 드레이닝과 종료 정책을 확인한다. RI는 적격 EC2 사용에 대한 기간 약정 할인이고, Savings Plans는 시간당 일정한 사용 금액을 약정하여 적격 사용에 할인을 적용하는 방식이다. 적용 범위와 잔여 약정은 별도 비용 데이터로 확인한다.

## 가상 비교

고정 4대×24시간×$0.20/시간=$19.20/일이다. 가변 2대×16시간과 4대×8시간은 합계 64대·시간, $12.80/일이다. 차이 $6.40은 같은 품질과 가상 On-Demand 단가에서의 추정치다. 2대로 피크 직전의 요청이나 AZ 장애를 버티지 못하면 최소 용량·사전 확장을 바꿔 다시 계산한다. EBS, 데이터 전송 및 할인은 별도로 본다.

Compute Optimizer로 사용량 기반 후보를 좁힌 뒤 피크·메모리 계측 범위와 호환성을 확인한다. RI나 Savings Plans 약정이 남으면 사용량 감소가 약정 미사용분으로 옮겨갈 수 있다. 실현 절감은 같은 업무량의 실제 비용과 약정 활용을 비교해야 판단할 수 있다.

## 이해도 확인

스케일아웃에 5분이 걸리고 피크가 2분 이내에 도달할 때 어떤 지표와 대안이 필요한가?

## 근거와 확인 범위

- [AWS · What are Savings Plans? — Usage commitment](https://docs.aws.amazon.com/savingsplans/latest/userguide/what-is-savings-plans.html) · 2026-11-08 확인
- [AWS Compute Optimizer — What is Compute Optimizer?](https://docs.aws.amazon.com/compute-optimizer/latest/ug/what-is-compute-optimizer.html) · 2026-11-08 확인
- [Amazon EC2 Auto Scaling — What is Amazon EC2 Auto Scaling?](https://docs.aws.amazon.com/autoscaling/ec2/userguide/what-is-amazon-ec2-auto-scaling.html) · 2026-11-08 확인

이 문서의 예시는 설명용 가정이다. 실제 환경의 결과와 적용 가능성은 별도로 확인한다.
