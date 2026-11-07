# VPC 비용 산정 02 — 중앙 NAT와 AZ별 NAT의 손익분기점

> NAT Gateway를 한 AZ에 모아 시간료를 아끼는 것과 AZ마다 배치해 AZ 간 전송료를 줄이는 것 중 언제 어느 쪽이 저렴한가?

[VPC 비용 산정 01](README.md)에 이어, 같은 리전의 **단일 VPC**에서 퍼블릭 **Zonal NAT Gateway**를 사용하는 두 구성을 비교합니다. 여기서 중앙 NAT는 AZ A의 NAT 하나를 여러 AZ가 공유하는 구성입니다. 별도 egress VPC나 Transit Gateway를 사용하는 설계는 이 계산 범위 밖입니다.

## 1. 같은 트래픽이 지나가는 경로

| 구성 | AZ A 워크로드 | AZ B·C 워크로드 | 장애 영향 |
|---|---|---|---|
| 중앙 NAT 1개 | 같은 AZ의 NAT A 사용 | AZ 경계를 넘어 NAT A 사용 | AZ A에 장애가 나면 다른 AZ의 워크로드도 이 경로의 인터넷 접근을 잃을 수 있음 |
| AZ별 NAT 3개 | 같은 AZ의 NAT A 사용 | 각자 같은 AZ의 NAT B·C 사용 | 정상 AZ의 송신 경로가 다른 AZ의 NAT에 의존하지 않음 |

Zonal NAT의 중복성은 해당 AZ 안에서 제공됩니다. AZ별 배치의 비용 모델은 각 서브넷의 라우팅이 같은 AZ의 NAT를 선택할 때 성립합니다. Regional NAT Gateway는 별도 옵션이며, AWS는 해당 NAT가 구성된 **AZ별**로 시간을 과금합니다. 리소스 하나라는 이유로 중앙 Zonal NAT 한 개의 시간료를 대입하면 안 됩니다. [NAT gateway basics](https://docs.aws.amazon.com/vpc/latest/userguide/nat-gateway-basics.html) · [Amazon VPC pricing — Regional NAT Gateway](https://aws.amazon.com/vpc/pricing/)

## 2. 세 비용을 따로 계산하기

| 항목 | 중앙 NAT | AZ별 NAT |
|---|---|---|
| 시간료 | NAT 한 개의 가용 시간 | 각 NAT의 가용 시간을 합산 |
| 데이터 처리료 | NAT를 지난 전체 송수신량에 적용 | 각 NAT가 처리한 송수신량을 합산. 전체 처리량과 단가가 같으면 중앙 구성과 동일 |
| AZ 간 전송료 | 워크로드와 NAT가 다른 AZ일 때 해당 구간에 적용 | 모든 워크로드가 같은 AZ의 NAT를 사용한다면 이 구간의 비용은 0 |

AWS는 NAT의 부분 시간을 한 시간으로 올림하고, 처리료는 NAT를 통과한 데이터량에 적용합니다. AZ 간 전송료는 처리료와 별도입니다. 인터넷 송신료도 별도이며, 두 구성의 인터넷 송신량과 단가가 같다면 비용 차이에서 상쇄됩니다. [Amazon VPC pricing — NAT Gateway Pricing and example](https://aws.amazon.com/vpc/pricing/) · [Pricing for NAT gateways](https://docs.aws.amazon.com/vpc/latest/userguide/nat-gateway-pricing.html)

예제에서 **교차량**은 중앙 구성의 워크로드↔NAT 구간에서 AZ 경계를 넘는 송신과 응답의 합입니다. 예를 들어 B에서 100 GB를 보내고 200 GB를 받으면 교차량은 300 GB입니다. 같은 바이트를 NAT 입구와 출구에서 각각 더하지 않습니다. 아래 가상 교차 단가는 **경계를 한 번 넘는 1 GB에 대해 청구되는 항목을 합친 유효 단가**입니다. 왕복 바이트를 합산한 뒤 방향을 이유로 두 배를 다시 곱하지 않습니다. 실제 견적에서는 방향·리소스별 청구 항목으로 유효 단가를 확인합니다. [NAT gateway metrics and dimensions](https://docs.aws.amazon.com/vpc/latest/userguide/metrics-dimensions-nat-gateway.html) · [EC2 pricing — Data Transfer within the same AWS Region](https://aws.amazon.com/ec2/pricing/on-demand/)

## 3. 가상 예제. 세 AZ에서 720시간 운영

| 조건 | 가정 |
|---|---:|
| 각 NAT의 가용 시간 | 720시간 |
| Zonal NAT 시간 단가 | 0.050 USD/Gateway-hour |
| NAT 처리 단가 | 0.040 USD/GB |
| 워크로드↔NAT 구간의 유효 AZ 간 전송 단가 | 0.020 USD/교차 GB |
| 중앙 구성에서 AZ를 넘는 비중 | 전체 NAT 송수신량의 50% |

나머지 50%는 AZ A에서 발생합니다. B·C 트래픽은 중앙 구성에서 각각 AZ 경계를 한 번 넘고, AZ별 구성에서는 모두 자기 AZ의 NAT를 사용합니다. 아래 합계에는 세 비용만 포함합니다. 인터넷 송신료는 두 구성에 동일하다고 가정해 제외했고, 공인 IPv4, 로그, 세금·할인도 제외했습니다. 공인 IPv4 사용량이 구성에 따라 달라진다면 실제 비교에는 그 차이를 포함해야 합니다. 단가는 학습용 가정입니다. [Amazon VPC pricing — Public IPv4 Address](https://aws.amazon.com/vpc/pricing/)

| 월 전체 NAT 처리량 | 중앙 · 시간 / 처리 / AZ 간 | 중앙 합계 | AZ별 · 시간 / 처리 / AZ 간 | AZ별 합계 |
|---:|---:|---:|---:|---:|
| 4,000 GB | 36 + 160 + 40 | **236 USD** | 108 + 160 + 0 | **268 USD** |
| 7,200 GB | 36 + 288 + 72 | **396 USD** | 108 + 288 + 0 | **396 USD** |
| 10,000 GB | 36 + 400 + 100 | **536 USD** | 108 + 400 + 0 | **508 USD** |

예를 들어 4,000 GB일 때 중앙 NAT는 `720 × 0.050 = 36 USD`의 시간료와 `4,000 × 0.040 = 160 USD`의 처리료를 냅니다. 그중 2,000 GB가 AZ를 넘어 `2,000 × 0.020 = 40 USD`가 추가됩니다. AZ별 NAT는 시간료가 `3 × 36 = 108 USD`로 늘고, 처리료는 같으며, 이 경로의 AZ 간 전송료는 사라집니다.

## 4. 비용이 역전되는 지점

두 구성의 처리료가 같으므로 **추가 NAT 시간료**와 **피하는 AZ 간 전송료**만 비교합니다.

- AZ별 NAT의 추가 시간료 = `(3 − 1) × 720시간 × 0.050 USD/시간 = 72 USD`
- 손익분기 교차량 = `72 USD ÷ 0.020 USD/교차 GB = 3,600 교차 GB`
- 교차 비중이 50%일 때 손익분기 전체 처리량 = `3,600 ÷ 0.50 = 7,200 GB`

이 가정에서 월 **3,600 교차 GB 미만이면 중앙 NAT**, **초과하면 AZ별 NAT**가 세 비용의 합계 기준으로 더 저렴합니다. 교차 비중이 25%라면 전체 처리량의 손익분기점은 **14,400 GB**로 올라갑니다. 교차량이 0이면 이 모델의 AZ 간 전송료 절감으로는 추가 시간료를 상쇄할 수 없습니다.

실제 비교에서는 AZ별 송수신량과 라우팅부터 확인합니다. [Gateway Endpoint](README.md)로 S3 트래픽을 우회하는 등 경로를 함께 바꾸면 NAT 처리량과 교차 비중을 다시 계산해야 합니다. 또 공인 IPv4 수나 NAT 가용 시간이 달라지면 추가 고정비도 바뀝니다. 가격이 같아지는 지점과 별개로, 공유 NAT의 장애 영향이 서비스 요구에 맞는지도 확인합니다.

## 5. 확인 문제와 한계

1. 월 전체 처리량이 10,000 GB지만 교차 비중이 25%라면 어느 구성이 저렴한가요?
2. 교차량을 줄여도 NAT 처리료가 그대로인 조건은 무엇인가요?

AWS 공식 문서로 시간료·처리료·전송료의 구분과 배치 조건을 확인했습니다. 트래픽, 단가와 비용은 가상 값입니다. 실제 송수신량, 라우팅, 청구액과 장애 영향을 측정하지 않았습니다.

## 공식 참고 자료

확인일은 **2026-11-07**입니다.

| 자료 | 확인 범위 |
|---|---|
| [Amazon VPC pricing](https://aws.amazon.com/vpc/pricing/) | Zonal·Regional NAT 시간료·처리료, 같은 AZ와 다른 AZ의 전송 차이, Public IPv4 |
| [Pricing for NAT gateways](https://docs.aws.amazon.com/vpc/latest/userguide/nat-gateway-pricing.html) · [NAT gateway basics](https://docs.aws.amazon.com/vpc/latest/userguide/nat-gateway-basics.html) | 같은 AZ로 라우팅하는 이유와 공유 NAT의 장애 영향 |
| [NAT gateway metrics and dimensions](https://docs.aws.amazon.com/vpc/latest/userguide/metrics-dimensions-nat-gateway.html) · [Amazon EC2 On-Demand Pricing](https://aws.amazon.com/ec2/pricing/on-demand/) | 방향별 바이트 지표, Data Transfer within the same AWS Region |

[AWS 학습 목차](../README.md) · [전체 학습 목차](../../README.md)

## 확인 문제 정답

1. 교차량은 `10,000 × 0.25 = 2,500 GB`이고 AZ 간 비용은 50 USD입니다. 중앙은 `36 + 400 + 50 = 486 USD`, AZ별은 `108 + 400 = 508 USD`입니다. 중앙이 22 USD 낮습니다.
2. 동일한 전체 송수신량이 여전히 NAT를 통과하고 처리 단가가 같을 때입니다. AZ별 배치로 AZ 경계를 없애도 NAT에서 처리하는 데이터는 남습니다.
