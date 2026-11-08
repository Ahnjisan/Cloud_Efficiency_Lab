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
