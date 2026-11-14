# Amazon ECR — 이미지 저장·전송·정리

[AWS 서비스 목차](../README.md)

ECR은 컨테이너 이미지를 보관하고 배포 환경에 전달하는 레지스트리다. [Docker 이미지 최적화](../../platforms/docker/image-optimization.md)의 크기 변경을 청구 항목과 연결한다.

## 비용과 삭제 순서

이미지 레이어 저장과 조건별 데이터 전송을 구분한다. Pull 횟수만으로 전송량을 알 수 없다. 동일 레이어의 캐시 적중, 대상 리전과 서비스, 경로의 NAT·Endpoint를 확인한다. 라이프사이클 정책은 태그와 나이 또는 이미지 수 조건에 따라 정리 후보를 고른다. 미태그 이미지가 실행 중인 digest나 롤백에 필요할 수 있으므로 정책 미리보기로 후보를 확인하고 다중 아키텍처 매니페스트, 복구·배포 정책을 함께 검토한다.

## 가상 비교

평균 청구 저장량 80 GB-월과 유료 전송 30 GB에 가상 $0.10/GB-월·$0.09/GB를 적용하면 $10.70이다. 저장만 50 GB-월로 낮추면 $7.70이다. 다른 구간의 NAT 요금은 별도다. 신규 이미지 크기가 작아졌어도 보존된 과거 레이어가 남으면 청구 저장량은 즉시 같은 폭으로 줄지 않는다.

## 이해도 확인

미태그 이미지를 지우기 전에 어떤 배포·롤백 참조를 찾아야 하는가?

## 근거와 확인 범위

- [Amazon ECR · Lifecycle policies — Preview 및 정책 평가](https://docs.aws.amazon.com/AmazonECR/latest/userguide/LifecyclePolicies.html) · 2026-11-08 확인
- [Amazon ECR Pricing — Storage 및 Data Transfer](https://aws.amazon.com/ecr/pricing/) · 2026-11-08 확인

이 문서의 예시는 설명용 가정이다. 실제 환경의 결과와 적용 가능성은 별도로 확인한다.

## 추가(2026-11-15) — 저장, 수명 주기, 이미지 크기와 시작 시간

> 이미지가 크면 저장 요금 말고 어디서 돈이 새는가?

**과금 단위.** 저장 0.10 USD/GB-월, 아카이브 0.04 USD/GB-월(서울, [2026-11-15 사본](../../../references/aws-price-list-apn2-2026-11-15.json)). 수명 주기 정책으로 태그 없는 이미지나 오래된 이미지를 자동으로 만료시킬 수 있습니다. 같은 저장소 안에서 공통 레이어를 한 번만 저장하는지는 이번에 문서로 확인하지 못했습니다(**미확인**). 아래 계산은 중복 제거가 없다고 보는 상한입니다.

**가상 예시.**

| 누수 | 계산 | 월 비용 |
|---|---|---:|
| 수명 주기 없이 300 MB 이미지 300개 누적 | 300 × 0.3 × 0.10 | 9.00 USD (상한) |
| 사설 서브넷 태스크가 **NAT를 거쳐** 1 GB 이미지를 월 1만 번 받음 | 10,000 × 0.059 | 590.00 USD |
| 이미지 다운로드가 15초 더 걸림(1 GB vs 200 MB), 하루 1만 태스크(0.25 vCPU · 0.5 GB) | 15초 × 30만 회 × 0.0000039431 USD/초 | 17.74 USD |

저장 요금보다 **전송 경로(NAT 처리 요금)와 Fargate가 다운로드 시간부터 과금하는 규칙**이 큽니다. ECR용 인터페이스 엔드포인트(api·dkr)와 레이어가 저장되는 S3용 게이트웨이 엔드포인트를 두면 NAT 처리 요금을 피할 수 있습니다([VPC 노트](../vpc/README.md)).

**낭비 판단 자료.** 저장소별 이미지 수·크기와 수명 주기 정책 유무, 태스크 시작 횟수, 이미지 다운로드 시간(태스크 메타데이터의 `PullStartedAt`·`PullStoppedAt`), 서브넷의 라우팅(NAT/엔드포인트).

**확인 문제.** 이미지 크기를 줄이면 줄어드는 비용 세 가지는? **해설.** ECR 저장 요금, NAT를 거칠 때의 처리 요금, Fargate의 다운로드 시간 과금입니다.

| 공식 자료 (확인일 2026-11-15) | 확인 범위 |
|---|---|
| [Amazon ECR pricing](https://aws.amazon.com/ecr/pricing/) · [Price List — AmazonECR](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonECR/current/ap-northeast-2/index.json) | 저장·아카이브 서울 요율, 게시일 2026-11-13 |
| [Lifecycle policies in Amazon ECR](https://docs.aws.amazon.com/AmazonECR/latest/userguide/LifecyclePolicies.html) | 태그 없음·개수·기간 기준 만료 |
| [AWS Fargate pricing](https://aws.amazon.com/fargate/pricing/) | 이미지 다운로드 시작부터 과금 |
| [Amazon VPC pricing](https://aws.amazon.com/vpc/pricing/) | NAT 처리 요금, 게이트웨이 엔드포인트로 S3 트래픽 처리 요금 회피 |
