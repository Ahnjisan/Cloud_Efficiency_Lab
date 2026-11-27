# 037 — 측정지 1장당 구조화 비용

[실험 목차](../README.md) · [019 파이프라인 단위 비용](../019-pipeline-unit-cost/README.md) · [036 설계 단계 비용 모델](../036-architecture-cost-model/README.md) · [rates_manual.json](rates_manual.json)

**재현 PASS. H1·H2 지지, H3 기각.** 실행 전 결정은 2026-11-27에 먼저 쓰고 그 뒤 실행했다. 실행 후 가설·판정 기준을 바꾸지 않았다.

Fac:Hub v4 구조화 파이프라인(촬영 사진·CSV 업로드 → S3 → SQS → structurer-worker → Textract → Bedrock → 초안)에서 측정지 한 장이 기록이 되기까지의 비용을 단계별로 나눈다. AWS를 호출하지 않는 계산 실험이다. 모든 작업량·크기·토큰 수는 **가정값**이며 측정값이 아니다.

## 실행 전 결정

| 항목 | 내용 |
|---|---|
| 질문 | 측정지 한 장의 구조화 비용은 어느 단계가 정하는가? Textract 종류와 Bedrock 모델 선택이 얼마나 바꾸는가? |
| 가설 H1 | 기본 구성에서 S3·SQS 합계는 장당 비용의 1% 미만이다. 작업량 세 단계 모두에서 성립해야 지지. |
| 가설 H2 | 기본 구성(AnalyzeDocument Tables + Claude Haiku 4.5, 토큰 보통, 사진 70%)에서 장당 평균 Textract 비용이 Bedrock 비용보다 크다. 작업량 세 단계 모두에서 성립해야 지지. |
| 가설 H3 | 기본 구성에서 모델만 Claude Sonnet 4.5로 바꾸면 장당 비용이 3배 이상이 된다. |
| 기준선 | Tables + Haiku 4.5 + 토큰 보통(입력 3,000·출력 600) + 사진 70% |
| 바꿀 변수 | Textract: DetectDocumentText / AnalyzeDocument Tables / Tables+Forms. 모델: Claude Haiku 4.5 / Sonnet 4.5. 토큰: 작게 1,500·300 / 보통 3,000·600 / 크게 5,000·1,000. 작업량: 작게 하루 20장·장당 1페이지 / 보통 100장·1.3페이지 / 크게 500장·1.3페이지(평일 22일). 사진 비율 30% / 70% / 100% |
| 통제 조건 | 장마다 Bedrock 구조화 1회(사진·CSV 모두). Textract는 사진 페이지마다 1회(동기 API). 사진 1페이지 = 이미지 1개 = S3 객체 1개, CSV 1장 = 객체 1개. 워커는 객체마다 S3 GET 1회. SQS는 장마다 SendMessage·ReceiveMessage·DeleteMessage 3요청(메시지 64 KB 이하) |
| 가정 크기 | 사진 1페이지 2 MB, CSV 50 KB. 원본은 S3 Standard에 한 달 보관 |
| 제외 | 결과 저장(RDS는 고정비라 장당 비용에서 제외), 무료 제공량, 세금, 데이터 전송, KMS, 로그. 워커·KEDA의 빈 폴링 요청은 장당 비용이 아니라 월 고정 항목으로 따로 적는다(워커 1개 롱 폴링 20초, KEDA GetQueueAttributes 30초 간격, 30일 = 720시간) |
| 요율 | S3·Bedrock: [2026-11-15 사본](../../references/aws-price-list-apn2-2026-11-15.json). Textract·SQS: [rates_manual.json](rates_manual.json)(서울 Price List 오퍼, 2026-11-27 확인). Tables+Forms 결합 요율 행은 오퍼에 없어 Tables + Forms 합(0.065 USD/페이지)으로 계산(공식 요금 페이지 예시 4가 둘을 따로 청구) |
| Bedrock 처리 위치 | 서울 오퍼에 Haiku·Sonnet 4.5는 Global(교차 리전) 요율만 있다. Global 프로필은 요청을 전 세계 상용 리전에서 처리할 수 있다. 국내 처리(리전 내·지역 프로필) 요율은 **확인 필요** — 데이터 위치 요구가 있으면 이 실험의 Bedrock 금액에 기댄 결론은 보류 |
| 금액 | USD, Decimal. 월 = 평일 22일(작업량), 고정 항목은 30일 |
| 시드·반복 | 계산 실험이라 난수 없음 |

## 실행

```powershell
cd experiments/037-measurement-sheet-unit-cost
py -3 -B calculate.py > result.json
py -3 -B test_calculate.py
```

## 결과

**기준 구성 (Tables + Haiku 4.5 + 토큰 보통 + 사진 70%)**

| 작업량 | 장당 USD | 1,000장당 | 월(평일 22일) | Textract | Bedrock | S3 | SQS |
|---|---:|---:|---:|---:|---:|---:|---:|
| 작게 (440장/월, 1페이지) | 0.01654 | 16.54 | 7.28 | 63.5% | 36.3% | 0.24% | 0.01% |
| 보통 (2,200장/월, 1.3페이지) | 0.01970 | 19.70 | 43.34 | 69.3% | 30.5% | 0.26% | 0.01% |
| 크게 (11,000장/월, 1.3페이지) | 0.01970 | 19.70 | 216.72 | 69.3% | 30.5% | 0.26% | 0.01% |

**설계 선택별 장당 USD (작업량 보통, 토큰 보통, 사진 70%)**

| Textract / 모델 | Haiku 4.5 | Sonnet 4.5 |
|---|---:|---:|
| DetectDocumentText | 0.00742 (Bedrock 81%) | 0.01942 (Bedrock 93%) |
| AnalyzeDocument Tables | **0.01970** (Textract 69%) | 0.03170 (Bedrock 57%) |
| Tables + Forms | 0.06520 (Textract 91%) | 0.07720 (Textract 77%) |

월 고정 항목: 워커 1개 롱 폴링(129,600요청) + KEDA 큐 확인(86,400요청) = 0.0864 USD/월(30일). 장당 비용에 넣지 않았다.

- **H1 지지**: S3·SQS 합계는 장당 비용의 0.25~0.26%였다.
- **H2 지지**: 기준 구성에서 장당 평균 Textract가 Bedrock보다 컸다(보통 0.01365 대 0.00600 USD).
- **H3 기각**: Sonnet 4.5로 바꾸면 장당 비용은 1.61~1.73배였다. 토큰 요율은 3배지만 Textract가 그대로라 전체는 3배가 되지 않았다.
- **가장 큰 단계가 바뀌는 조건**(162개 조합 중 Textract 80, Bedrock 82): DetectDocumentText를 쓰면 항상 Bedrock이 가장 크다. Tables에서는 Sonnet이면 토큰 보통 이상에서(토큰 작게는 사진 30%일 때만), Haiku면 사진 30%·토큰 보통 이상에서 Bedrock이 크다. Tables+Forms에서는 Sonnet·토큰 크게·사진 30%일 때만 Bedrock이 크다.
- 장당 비용의 폭은 모델(최대 1.7배)보다 **Textract 종류(Detect 대비 Tables+Forms 8.8배)** 가 더 크게 바꿨다.

## 해석

- 장당 비용은 "어떤 Textract 기능으로 읽느냐"가 먼저 정하고, 모델은 그다음이다. Forms(키-값 추출)를 켜면 페이지당 0.05 USD가 더해져 Bedrock 비용이 거의 의미 없어진다. 측정지가 표 위주라면 Tables만으로 충분한지, 아예 DetectDocumentText + Bedrock으로 구조를 맞출 수 있는지가 비용상 가장 큰 결정이다. 정확도는 [040](../040-ocr-vs-multimodal-plan/README.md)에서 다룬다(계획, 미실행).
- S3·SQS는 1%에도 못 미쳐 최적화 대상이 아니다. 고정 폴링 비용도 월 0.1 USD 미만이다.
- 월 비용은 작업량에 비례한다(크게 216.72 USD/월). 고정비(EKS 노드·RDS)는 [039](../039-worker-scale-to-zero/README.md)와 별도 검토 대상이다.

## 가정·제외·한계

- 하루 장수, 장당 페이지, 사진 크기, 토큰 수는 모두 가정값이다. 실제 Textract 페이지 수(사진 한 장에 측정지 여러 장이 찍히는 경우 등)와 Bedrock 토큰은 측정하지 않았다.
- Bedrock 요율은 Global 교차 리전 행이다. 국내 처리 요율은 확인 필요이며, 데이터 위치 요구가 있으면 Bedrock 금액과 H3 판정은 보류한다.
- Tables+Forms는 두 요율의 합으로 계산했다(결합 요율 행 없음).
- 재시도·중복 처리는 [038](../038-retry-duplicate-cost/README.md)에서 따로 계산한다. 무료 제공량, 세금, 데이터 전송, RDS 쓰기는 제외했다.

## 테스트

`test_calculate.py` 5개: 수동 요율 값과 Tables+Forms 합, Bedrock 1회 비용, CSV만이면 Textract 0, 사진 1.3페이지 Textract, `result.json` 재현.
