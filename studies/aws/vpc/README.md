# VPC 비용 산정 01 — NAT Gateway·VPC Endpoint·데이터 전송

> 같은 프라이빗 서브넷에서 같은 양의 데이터를 읽고 쓸 때, 경로에 따라 어떤 비용이 달라지는가?

커리큘럼 02. AWS Infrastructure & Pricing의 학습 노트입니다. [S3 비용 산정 01](../s3/README.md)에서 구분한 요청·조회·전송 비용에 VPC 경로의 시간료와 데이터 처리료를 더해 비교합니다.

## 1. 경로별 역할과 과금 단위

| 경로 | 역할 | 시간료 | 데이터 처리료 |
|---|---|---|---|
| 퍼블릭 NAT Gateway | 프라이빗 서브넷의 IPv4 워크로드가 외부 서비스로 연결을 시작할 수 있게 합니다. 인터넷 목적지로 나갈 때는 Internet Gateway를 경유합니다. | Zonal은 가용한 Gateway 시간, Regional은 구성된 AZ별 시간. 부분 시간은 1시간으로 올림 | NAT를 통과한 GB에 적용 |
| Gateway Endpoint | 연결된 라우팅 테이블에서 같은 리전의 S3·DynamoDB 트래픽을 해당 서비스로 보냅니다. | 추가 요금 없음 | 추가 요금 없음 |
| Interface Endpoint | 지원 서비스에 AWS PrivateLink로 연결합니다. 선택한 서브넷의 엔드포인트 네트워크 인터페이스가 프라이빗 IP를 사용합니다. | 프로비저닝된 Endpoint의 AZ별 시간. 부분 시간은 1시간으로 올림 | Endpoint를 통과한 GB에 적용. 리전 내 전체 Interface Endpoint 처리량에 요금 구간 적용 |

NAT와 Interface Endpoint는 트래픽이 없어도 해당 시간료가 발생합니다. Regional NAT 하나가 3개 AZ에서 한 시간 구성돼 있으면 3 Gateway-hour입니다. Interface Endpoint도 서비스별로 필요한 Endpoint와 AZ 수를 확인합니다. Gateway Endpoint는 임의의 인터넷 목적지나 온프레미스에서의 S3 접근을 대신하지 못합니다. S3 Interface Endpoint는 지원되는 VPN·Direct Connect 경로에서 온프레미스 접근에 사용할 수 있습니다. [VPC 요금](https://aws.amazon.com/vpc/pricing/) · [PrivateLink 요금](https://aws.amazon.com/privatelink/pricing/) · [Gateway endpoints](https://docs.aws.amazon.com/vpc/latest/privatelink/gateway-endpoints.html) · [AWS PrivateLink for Amazon S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/privatelink-interface-endpoints.html)

## 2. 데이터 처리료와 데이터 전송료

- **처리료**는 NAT나 Interface Endpoint가 처리한 트래픽에 붙습니다. 요청 방향과 응답 방향의 처리량을 모두 고려합니다. 예를 들어 송신 50 GB와 응답 20 GB가 같은 NAT를 통과하면 이 예제의 처리량은 70 GB입니다. 같은 바이트를 Gateway 입구와 출구에서 두 번 더하지 않습니다. [NAT Gateway 지표](https://docs.aws.amazon.com/vpc/latest/userguide/metrics-dimensions-nat-gateway.html) · [VPC 요금](https://aws.amazon.com/vpc/pricing/) · [PrivateLink 요금](https://aws.amazon.com/privatelink/pricing/)
- **인터넷 전송료**는 과금 대상 인터넷 송신량과 무료 구간 등 요금 조건에 따라 계산합니다. NAT를 통한 인터넷 송신은 NAT 처리료와 인터넷 전송료가 함께 발생할 수 있습니다. [VPC 요금 — NAT Gateway 예제](https://aws.amazon.com/vpc/pricing/)
- **AZ 간 전송료**는 실제 경로와 서비스 조건에 따릅니다. 예를 들어 워크로드와 Zonal NAT가 서로 다른 AZ에 있으면 그 구간에 전송료가 붙습니다. 같은 AZ의 NAT로 경로를 바꾸거나 AZ마다 NAT를 두는 경우에는 줄어드는 전송료와 늘어나는 시간료를 함께 봅니다. [Pricing for NAT gateways](https://docs.aws.amazon.com/vpc/latest/userguide/nat-gateway-pricing.html)
- **리전 간 전송료**도 별도입니다. 지원되는 교차 리전 PrivateLink에서는 표준 Endpoint 시간·처리료에 더해 리전 간 전송료가 적용됩니다. [PrivateLink — Cross-Region Connectivity Pricing](https://aws.amazon.com/privatelink/pricing/)
- **서비스 요금**은 별도로 남습니다. 같은 리전 S3 트래픽의 전송료가 0이어도 NAT 처리료는 발생할 수 있습니다. Gateway Endpoint로 바꾸면 이 경로의 NAT 처리료를 피하지만, S3 저장·요청·클래스별 조회료는 각 조건에 따라 계산합니다. [VPC 요금 — NAT에서 S3로의 전송 예제](https://aws.amazon.com/vpc/pricing/) · [S3 요금](https://aws.amazon.com/s3/pricing/)

## 3. 가상 단가와 비교 범위

아래 금액은 모두 학습용 가상 값입니다. 30일 동안 **720시간**, 워크로드와 비교 대상 Zonal NAT 또는 Interface Endpoint는 **같은 AZ**에 있다고 가정합니다. S3 버킷은 같은 리전입니다. 같은 업무량에 대한 네트워크 경로 비용만 계산하며, 가상 전송량은 GB로 통일합니다.

| 항목 | 가상 단가 |
|---|---:|
| Zonal NAT 시간료 | 0.050 USD/시간 |
| NAT 처리료 | 0.040 USD/GB |
| Interface Endpoint 시간료 | 0.012 USD/(AZ·시간) |
| Interface Endpoint 처리료 | 0.015 USD/GB |
| 과금 대상 인터넷 송신료 | 0.080 USD/GB |

공인 IPv4 주소, S3 서비스 요금, 로그, 할인·크레딧·세금은 제외합니다. 실제 견적에는 리전별 단가, Endpoint 처리량 구간, NAT에 연결된 공인 IPv4 등 해당 부가 항목을 확인합니다. [VPC 요금 — Public IPv4 Address](https://aws.amazon.com/vpc/pricing/) · [PrivateLink 요금](https://aws.amazon.com/privatelink/pricing/)

## 4. 예제 A. 같은 리전 S3만 접근

프라이빗 서브넷의 워크로드가 S3와 주고받는 양방향 데이터의 합이 **200 GB**입니다. 외부 인터넷 접근은 필요 없으며, 기존 NAT가 있다면 다른 의존성이 없어 완전히 제거할 수 있다고 가정합니다. 세 경로 모두 예제 조건에서 별도 데이터 전송료를 0으로 둡니다.

| S3 경로 | 시간료 | 처리료 | 전송료 | 합계 |
|---|---:|---:|---:|---:|
| NAT Gateway | `720 × 0.050 = 36.00` | `200 × 0.040 = 8.00` | 0.00 | **44.00 USD** |
| S3 Gateway Endpoint | 0.00 | 0.00 | 0.00 | **0.00 USD** |
| S3 Interface Endpoint, AZ 1개 | `720 × 0.012 = 8.64` | `200 × 0.015 = 3.00` | 0.00 | **11.64 USD** |

이 사례에서 Gateway Endpoint의 0 USD는 비교에 포함한 경로 비용입니다. Interface Endpoint는 NAT보다 적게 들지만, 같은 VPC에서 같은 리전 S3만 접근한다면 가상 예제의 Gateway Endpoint가 더 저렴합니다. 온프레미스 접근처럼 필요한 경로가 다르면 먼저 지원 여부를 확인합니다.

## 5. 예제 B. 인터넷 때문에 NAT를 유지

같은 200 GB의 S3 트래픽에 더해, 외부 서비스로 **50 GB 송신**하고 **20 GB 수신**합니다. 외부 서비스 트래픽은 세 구성 모두 NAT를 통과합니다. 가상 예제는 인터넷 송신 50 GB 전부를 과금 대상으로, 수신의 전송료는 0으로 가정합니다. NAT는 인터넷 양방향 70 GB를 처리하며, 인터넷 전송료는 `50 × 0.080 = 4.00 USD`입니다.

| 구성 | NAT 시간료 | NAT 처리료 | Endpoint 비용 | 전송료 | 합계 |
|---|---:|---:|---:|---:|---:|
| NAT로 S3와 인터넷 접근 | 36.00 | `270 × 0.040 = 10.80` | 0.00 | 4.00 | **50.80 USD** |
| S3 Gateway Endpoint + 인터넷 NAT | 36.00 | `70 × 0.040 = 2.80` | 0.00 | 4.00 | **42.80 USD** |
| S3 Interface Endpoint + 인터넷 NAT | 36.00 | 2.80 | 11.64 | 4.00 | **54.44 USD** |

Gateway Endpoint로 S3만 우회하면 줄어드는 비용은 **8.00 USD**의 NAT 처리료입니다. NAT가 남아 시간료와 인터넷 전송료는 그대로 계산됩니다. Interface Endpoint는 같은 처리료를 피하지만 **11.64 USD**가 새로 들어, 이 가정에서는 총액이 **3.64 USD** 늘어납니다.

## 6. 실제 경로를 비교할 때 확인할 조건

1. **목적지와 지원 범위**를 확인합니다. 같은 리전의 S3·DynamoDB, PrivateLink 지원 서비스, 외부 인터넷을 구분하고 라우팅 테이블과 DNS가 실제로 어느 경로를 선택하는지 확인합니다.
2. **남을 고정비와 옮길 처리량**을 따로 계산합니다. 여러 워크로드가 NAT를 공유한다면 S3를 우회해도 NAT 전체 시간료를 절감액에 넣지 않습니다. AZ별 Endpoint 수와 송수신량을 산정합니다.
3. **전송 경로와 운영 조건**을 확인합니다. 출발·도착 AZ 및 리전, 인터넷 송신량, 공인 IP 사용, 엔드포인트 정책과 보안 그룹을 검토합니다. 비용이 낮아도 필요한 연결, AZ 장애 대응, 접근 제어를 충족하는 구성끼리 비교합니다.

[Gateway endpoints — Routing and Security](https://docs.aws.amazon.com/vpc/latest/privatelink/gateway-endpoints.html) · [Interface Endpoint — Prerequisites](https://docs.aws.amazon.com/vpc/latest/privatelink/create-interface-endpoint.html)

## 7. 확인 문제와 한계

1. 예제 B에서 S3 Gateway Endpoint를 추가해도 NAT 시간료가 남는 이유는 무엇인가요?
2. 외부 서비스와 주고받는 70 GB 전체에 NAT 처리료가 붙는데, 가상 인터넷 송신료는 왜 50 GB에만 적용하나요?

공식 문서에서 Gateway·Endpoint별 과금 단위와 전송 경로 조건을 확인했습니다. 실제 경로, 트래픽, 청구액과 가용성은 측정하지 않았습니다.

## 공식 참고 자료

확인일은 **2026-11-07**입니다.

| 자료 | 확인 범위 |
|---|---|
| [Amazon VPC pricing](https://aws.amazon.com/vpc/pricing/) · [Pricing for NAT gateways](https://docs.aws.amazon.com/vpc/latest/userguide/nat-gateway-pricing.html) | Zonal·Regional NAT 시간료, 처리료, S3·인터넷 예제와 AZ 간 전송 |
| [AWS PrivateLink pricing](https://aws.amazon.com/privatelink/pricing/) | Interface Endpoint AZ별 시간·처리료, 리전 간 전송 |
| [Gateway endpoints](https://docs.aws.amazon.com/vpc/latest/privatelink/gateway-endpoints.html) · [AWS PrivateLink for Amazon S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/privatelink-interface-endpoints.html) | 대상 서비스와 라우팅, Gateway·Interface 비교 |
| [Access an AWS service using an interface VPC endpoint](https://docs.aws.amazon.com/vpc/latest/privatelink/create-interface-endpoint.html) · [NAT gateway metrics and dimensions](https://docs.aws.amazon.com/vpc/latest/userguide/metrics-dimensions-nat-gateway.html) | 서브넷·보안 그룹, 방향별 바이트 지표 |
| [Amazon S3 pricing](https://aws.amazon.com/s3/pricing/) | Storage & requests, Data transfer |

[AWS 학습 목차](../README.md) · [전체 학습 목차](../../README.md)

## 확인 문제 정답

1. 외부 서비스 트래픽에 NAT를 계속 사용하기 때문입니다. S3 트래픽만 우회하면 NAT가 처리하던 200 GB의 처리료가 줄어듭니다.
2. 처리료는 NAT가 처리한 송수신량에 적용합니다. 가상 전송료는 인터넷으로 나간 50 GB에만 적용하므로 같은 트래픽이라도 두 항목의 과금량이 다릅니다.
