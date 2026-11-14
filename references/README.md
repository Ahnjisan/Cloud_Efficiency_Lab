# References

[프로젝트 README](../README.md) · [최종 연구 보고서](../FINAL-REPORT.md)

공식 자료 및 학술 참고문헌의 위치와 참고 목적을 안내하는 공간입니다.

## 포함할 자료

- AWS 공식 기술·요금·API 문서
- 클라우드 공급자의 공식 문서
- FinOps Foundation의 공식 자료
- FOCUS 등 공식 표준·사양
- Docker·Kubernetes 공식 문서
- 정식 학술 논문과 별도로 구분한 프리프린트
- 공식 공개 데이터셋

## 참고문헌 관리

자료별로 필요한 범위에서 다음을 기록합니다.

- 제목과 저자 또는 발행 기관
- 발행·개정 시점과 확인한 버전
- 원문 URL
- 실제 읽은 절 또는 페이지와 확인일
- 관련 학습 주제와 참고 목적

자료는 유형별로 구분하고 실제 확인한 절과 확인일을 남깁니다.

## 참고문헌 목록

- [공식 기술 문서](official-docs.md)
- [표준·프레임워크](standards.md)
- [학술 논문](papers.md)
- [공식 데이터 예제](datasets.md)

## 서울 리전 요율 사본

| 파일 | 확인일 | 범위 |
|---|---|---|
| [aws-price-list-apn2-2026-11-13.json](aws-price-list-apn2-2026-11-13.json) | 2026-11-13 | IoT Core, Firehose, Athena, Glue, S3, SageMaker, Bedrock (실험 016~022) |
| [aws-price-list-apn2-2026-11-15.json](aws-price-list-apn2-2026-11-15.json) | 2026-11-15 | 위 서비스 일부 + OpenSearch, ElastiCache, API Gateway, Lambda, RDS, VPC 엔드포인트·NAT, EC2, EKS, ECS Fargate, ECR, CloudWatch, Bedrock Guardrails (실험 026~036) |

두 사본 모두 AWS Price List Bulk API의 서울 오퍼 파일에서 온디맨드 공개 요율 행만 그대로 옮겼다. 무료 제공량·할인·세금은 없다. 2026-11-15 사본은 [extract-price-snapshot.py](extract-price-snapshot.py)로 만들었고, 오퍼마다 게시일(`publicationDate`)과 추출 조건(`selection`)을, 찾지 못한 요율은 `missing`에 적었다. 이전 사본은 고치지 않는다.

기존 Foundations 문서의 [확인한 자료와 해석 범위](../studies/foundations/README.md#확인한-자료와-해석-범위)도 참고합니다.

## 외부 자료 재사용

공식 참고문헌 목록에는 다른 개인의 GitHub 프로젝트나 동아리 스터디 저장소를 등록하지 않습니다. 기존에 참고 대상으로 나열했던 개인 프로젝트의 코드·데이터는 재사용하지 않았습니다.

외부 코드·데이터·독창적인 분석 방법을 실제로 재사용하면 해당 [Studies](../studies/README.md) 또는 [Experiments](../experiments/README.md) 문서에 원 출처, 확인한 버전·커밋, 라이선스, 수정 범위를 기록합니다. 라이선스와 재배포 조건을 별도로 확인하며, 외부 자료에 이 저장소의 LICENSE가 자동으로 적용되지는 않습니다.
