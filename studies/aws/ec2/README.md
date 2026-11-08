# EC2 비용 산정 01 — 인스턴스 실행 상태와 컴퓨팅 비용

[AWS 서비스 목차](../README.md) · [EC2·EBS 비용 실험](../../../experiments/003-aws-cost-simulation/README.md)

## 1. 학습 질문

> EC2 인스턴스를 중지하면 비용은 모두 사라지는가?

모두 사라지지는 않습니다. 이 문서에서 다루는 EBS 기반 On-Demand 인스턴스는 중지하면 컴퓨팅 사용료가 중단되지만, 유지한 EBS 볼륨의 저장 비용은 남습니다. 따라서 인스턴스의 컴퓨팅 요금과 연결된 자원의 비용을 구분해야 합니다. [AWS 상태별 과금 설명](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-lifecycle.html)

여기서는 일반적인 중지와 재시작을 중심으로 살펴봅니다. 사용량·사용률·낭비의 공통 정의는 [Foundations](../../foundations/README.md)를 참고하고, 이번에는 상태 변화와 비용 계산에 집중합니다.

## 2. EC2의 기본 구조

EC2 인스턴스는 애플리케이션을 실행할 컴퓨팅 환경입니다. 인스턴스 타입은 CPU·메모리·스토리지·네트워크 용량의 구성을 결정합니다. 같은 애플리케이션이라도 어떤 타입과 크기를 선택하는지에 따라 사용할 수 있는 자원과 성능 조건이 달라집니다. [Amazon EC2 instance types — 도입부·Available instance types](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instance-types.html)

EBS 기반 인스턴스는 운영체제가 있는 루트 볼륨으로 EBS를 사용하며, 별도 EBS 데이터 볼륨을 연결할 수도 있습니다. 컴퓨팅을 멈추는 것과 저장 공간을 없애는 것은 별개입니다. EBS 루트 볼륨을 가진 인스턴스는 중지·재시작할 수 있지만, instance store 루트 볼륨 인스턴스에는 같은 중지·재시작 방식을 적용할 수 없습니다. [Stop and start Amazon EC2 instances — 도입부·Manually stop and start](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Stop_Start.html)

인스턴스는 시작 준비, 실행, 중지 등의 상태를 거칩니다. 생성 후 경과한 전체 시간 대신, 상태별 과금 조건에 따른 실행 시간을 구분해야 컴퓨팅 비용을 계산할 수 있습니다.

## 3. EC2 On-Demand 비용

On-Demand는 장기 약정 없이 컴퓨팅 용량 사용 시간에 따라 지불하는 방식입니다. 이 문서의 계산은 **해당 과금 조건을 적용할 수 있는 Linux On-Demand 인스턴스의 컴퓨팅 사용료**를 가정합니다. [Amazon EC2 On-Demand Pricing — On-Demand Pricing](https://aws.amazon.com/ec2/pricing/on-demand/)

`running`이면 접속하지 않거나 작업이 없어도 컴퓨팅 요금이 발생합니다. 이 비용은 CPU가 실제 작업한 비율이 아니라 실행 중인 인스턴스의 컴퓨팅 용량을 사용하는 시간에 대응하기 때문입니다. CPU 사용률이 10%라고 컴퓨팅 기본 요금도 10%가 되지는 않습니다. [Amazon EC2 instance state changes — Pending instances](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-lifecycle.html)

### 60초 최소 과금과 초 단위 과금

공식 On-Demand 요금 페이지는 Linux, Windows, Windows with SQL Enterprise·Standard·Web, RHEL, Ubuntu Pro의 부분 실행 시간을 초 단위로 과금한다고 설명하고, SLES는 부분 시간도 한 시간으로 과금한다고 구분합니다. 이 문서의 Linux 가정에서는 **각 시작마다 최소 60초**, 그 이후 초 단위 과금을 적용합니다. 중지 후 다시 시작하면 최소 과금이 다시 적용됩니다. 예를 들어 20초만 실행한 한 번의 시작도 20초분만 청구되는 것은 아닙니다. [On-Demand 요금 조건](https://aws.amazon.com/ec2/pricing/on-demand/), [Stopped instances의 재시작 과금](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-lifecycle.html)

이 규칙을 모든 운영체제·라이선스 요금, 다른 구매 옵션, EBS·네트워크 등 별도 항목에 일괄 적용하지 않습니다. 특히 RHEL 등의 별도 가격 정의와 실제 선택한 상품 조건을 확인해야 합니다. 이번에는 Spot·RI·Savings Plans의 비용 계산을 다루지 않습니다. [On-Demand Pricing의 운영체제·RHEL 안내](https://aws.amazon.com/ec2/pricing/on-demand/)

## 4. EC2 실행 상태와 비용

아래는 **인스턴스 컴퓨팅 사용료**의 구분입니다. 별도 자원 비용과 이미 발생한 최소 과금까지 없어지는 뜻은 아닙니다. [Amazon EC2 instance state changes — Billing by instance state](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-lifecycle.html)

| 상태 | 의미 | 컴퓨팅 사용료 |
|---|---|---|
| `pending` | 시작 또는 재시작을 준비하는 상태 | 비과금 |
| `running` | 실행 중인 상태 | 과금 |
| `stopping` | 중지 처리 중인 상태 | 일반 중지는 비과금; 최대 절전 모드는 이 구간도 과금 |
| `stopped` | 중지되어 사용할 수 없으며 다시 시작할 수 있는 상태 | 비과금 |
| `terminated` | 영구 종료되어 같은 인스턴스를 다시 시작할 수 없는 상태 | 비과금 |

일반 중지는 `running → stopping → stopped`로 진행하며 `stopping`부터 컴퓨팅 과금이 중단됩니다. 종료 과정에는 `shutting-down`이 있으며 이 상태부터 컴퓨팅 과금이 중단됩니다. 최대 절전 모드는 일반 중지와 다른 동작이므로 위 예외를 구분합니다. [Differences between instance states](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-lifecycle.html)

### 중지와 종료의 데이터·가용성 차이

중지 중에는 서비스 제공이 끊깁니다. 일반 중지는 RAM과 instance store 데이터를 보존하지 않으며, 재시작 시 호스트나 자동 할당 공인 IPv4가 바뀔 수 있습니다. 필요한 데이터를 영속 저장소로 옮겼는지, 정상 종료·재기동이 가능한지 확인해야 합니다. 강제 종료나 정상 종료 절차 생략은 데이터 무결성 위험도 있습니다. [Stop and start — 도입부·중지 주의사항](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Stop_Start.html)

종료는 되돌려 시작할 수 없습니다. EBS 삭제 여부는 `DeleteOnTermination` 설정에 달려 있으며, 기본적으로 루트 볼륨은 삭제되고 다른 EBS 볼륨은 보존됩니다. 실제 설정과 백업을 먼저 확인해야 하며, 비용을 없애려고 무조건 종료·삭제해서는 안 됩니다. [Terminated instances](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-lifecycle.html)

## 5. EBS 비용이 남는 이유

EC2 컴퓨팅은 프로그램을 실행하는 자원이고 EBS는 데이터를 유지하는 저장 공간입니다. 인스턴스가 `stopped`여도 유지된 EBS 볼륨에는 저장 비용이 발생합니다. [Stopped instances](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-lifecycle.html)

EBS 저장 비용은 볼륨 안에 실제 파일이 얼마나 있는지만으로 결정되지 않고, **프로비저닝한 저장 용량과 유지 기간**에 따라 발생합니다. 볼륨 유형에 따라 IOPS·Throughput 등 별도 성능 비용 항목도 확인해야 합니다. 예를 들어 공식 gp3 예제는 저장 용량과 기본 제공 범위를 넘는 IOPS·Throughput 비용을 구분합니다. [Amazon EBS pricing — Overview·Example 1](https://aws.amazon.com/ebs/pricing/)

따라서 인스턴스를 덜 실행해도 같은 EBS를 같은 기간 유지하면 그 저장 비용은 줄지 않습니다. 모든 EBS 유형과 성능 요금의 상세 비교는 후속 학습으로 남깁니다.

## 6. 비용 계산 예제

**아래는 사용자가 지정한 가상 단가입니다. 실제 AWS의 특정 리전·인스턴스 타입·EBS 유형 가격이나 견적이 아닙니다.**

| 조건 | 가정 |
|---|---|
| EC2 컴퓨팅 단가 | 0.10 USD/시간 |
| EBS 할당 용량 | 50 GiB |
| EBS 저장 단가 | 0.08 USD/(GiB·월) |
| 계산 기간 | 30일을 1개월로 가정 |
| 변경 전 실행 시간 | 하루 24시간 |
| 변경 후 실행 시간 | 하루 8시간, 나머지는 일반 중지 |
| EBS 유지 기간 | 두 구성 모두 전체 30일 |

하루 실행 시간은 실제 과금 대상 실행 시간으로 가정하며, 각 실행은 최소 60초보다 충분히 깁니다. 가격 페이지의 표기 단위를 그대로 실측 가격에 대입한 예제가 아니라, 위 GiB 기준의 가상 단가를 일관되게 사용하는 계산입니다.

### 변경 전: 하루 24시간 실행

- EC2 실행 시간: `24시간/일 × 30일 = 720시간`
- EC2 비용: `720시간 × 0.10 USD/시간 = 72 USD`
- EBS 비용: `50 GiB × 0.08 USD/(GiB·월) × 1개월 = 4 USD`
- 합계: `72 USD + 4 USD = 76 USD`

### 변경 후: 하루 8시간 실행

- EC2 실행 시간: `8시간/일 × 30일 = 240시간`
- EC2 비용: `240시간 × 0.10 USD/시간 = 24 USD`
- EBS 비용: `50 GiB × 0.08 USD/(GiB·월) × 1개월 = 4 USD`
- 합계: `24 USD + 4 USD = 28 USD`

### 두 구성의 차이

- 실행 시간 차이: `(24 − 8)시간/일 × 30일 = 480시간`
- EC2 비용 차이: `480시간 × 0.10 USD/시간 = 48 USD`
- EBS 비용 차이: `4 USD − 4 USD = 0 USD`
- 합계 차이: `76 USD − 28 USD = 48 USD`

컴퓨팅 비용은 3분의 1이 되지만, EBS가 남아 합계가 3분의 1이 되는 것은 아닙니다. 여기서 48 USD는 **정해진 가정 안에서 계산한 비용 차이**이며 실제 절감 성과가 아닙니다. 서비스가 하루 8시간만 실행돼도 되는지는 확인되지 않았습니다.

이 계산에서는 다음을 제외했습니다.

- 다른 스토리지·네트워크·공인 IPv4 비용
- 추가적인 성능 및 운영 관련 비용
- 할인·크레딧·세금
- 중지·시작에 따른 운영상 영향

실제 적용에서는 재시작 시간과 서비스 중단 등 제외한 영향도 검토해야 하므로, 이 합계를 실제 청구 총액이나 곧바로 적용 가능한 절감액으로 사용하지 않습니다.

## 7. 낭비 판단과 적용 조건

다음은 이 문서의 적용 검토 기준입니다. 공식 자료의 과금 설명으로부터 모든 환경에 중지를 권고하는 것은 아닙니다.

| 질문 | 판단에 필요한 조건 |
|---|---|
| 실행 중인데 CPU 사용률이 낮으면 낭비인가? | CPU만으로 확정하지 않습니다. 피크·메모리·I/O·대기 업무·장애 대응 역할과 필요한 품질을 확인합니다. |
| 개발·테스트 환경은 야간 중지를 검토할 수 있는가? | 야간 사용자·배치·CI 작업·외부 의존성이 없거나 허용된 중단으로 처리할 수 있고, 아침 재기동과 상태 복구를 확인할 수 있을 때 검토합니다. |
| 24시간 서비스에도 같은 방법을 적용할 수 있는가? | 서비스 중단을 허용하지 않는 요구와 충돌합니다. 이 예제를 그대로 적용하지 않고 서비스 요구에 맞는 다른 구성·운영 방식을 별도로 검토해야 합니다. |
| 중지 전에 무엇을 확인해야 하는가? | 서비스 담당자의 허용 시간, 정상 종료·데이터 영속화·백업, 배치·연결 의존성, 주소 변경 영향, 재시작 소요 시간·실패 대응, 중지와 종료의 구분을 확인합니다. |
| EBS가 남으면 실제 절감액은 어떻게 달라지는가? | 줄어드는 컴퓨팅 항목과 남는 저장·기타 항목을 분리합니다. 이 예제에서는 EBS 4 USD가 남아 합계가 0이 되지 않습니다. 실제 효과는 전체 과금 조건과 추가 운영 비용까지 확인해야 합니다. |

운영 조건이 확인되지 않으면 중지를 권고하거나 낭비·절감액을 확정하지 않습니다.

## 8. 학습 확인 문제

1. 같은 가상 단가로 하루 12시간씩 30일 실행하고 EBS를 계속 유지한다면 EC2·EBS·합계 비용과 24시간 구성 대비 차이는 얼마인가?
2. 인스턴스를 30일 내내 일반 중지 상태로 두되 EBS 50 GiB를 유지하면, 이 예제에 포함된 비용은 얼마인가? 왜 실제 AWS 전체 청구액이라고 단정할 수 없는가?
3. CPU 평균 사용률이 5%인 24시간 서비스에 대해 “야간에 중지하면 48 USD 절감”이라고 결론 내려도 되는가? 추가로 확인할 운영 조건 두 가지를 설명하라.

정답과 해설은 문서 마지막에 제공합니다.

## 9. 현재 확인 범위와 한계

| 구분 | 이번 문서의 범위 |
|---|---|
| 공식 문서로 확인한 사실 | 인스턴스 타입의 자원 구성, EBS 기반 중지·재시작, 상태별 컴퓨팅 과금과 최대 절전 예외, On-Demand의 과금 단위·최소 시간 조건, EBS 유지·저장 과금 및 일부 성능 비용, 중지·종료의 데이터 차이 |
| 가상 단가로 계산한 결과 | 30일 동안 24시간/일과 8시간/일 구성의 합계 76 USD·28 USD, 차이 48 USD |
| 실제 AWS에서 측정하지 않은 항목 | 청구액·과금 경계 시각·부팅 시간·성능·데이터 복구·서비스 중단 영향; 실제 자원 생성·중지·종료를 수행하지 않음 |
| 추가 확인이 필요한 운영 조건 | 중단 허용 시간, 피크·배치·의존성, 재기동·복구, 실제 리전·타입·OS·상품·할인 조건과 전체 부가 비용 |

이 자료를 작성했다는 사실은 사용자의 학습 완료나 실험 성공을 뜻하지 않습니다. 여기서 직접 확인한 것은 아래 공식 페이지의 표시한 설명과 가상 산술이며, 실제 AWS 비용을 줄였다는 의미가 아닙니다.

## 10. 다음 학습 질문

> EC2와 연결된 EBS 볼륨은 용량, 볼륨 유형, IOPS, Throughput에 따라 어떻게 과금되는가?

이번에는 질문만 남기고 별도 EBS 학습 문서는 만들지 않습니다.

## 공식 참고 자료와 확인 범위

확인일은 모두 **2026-11-07**입니다. 페이지 전체와 연결된 모든 하위 문서를 읽었다는 뜻은 아니며, 실제 확인 범위를 아래에 한정합니다.

| 공식 자료 | 실제 확인한 관련 절 |
|---|---|
| [Amazon EC2 instance state changes](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-lifecycle.html) | Billing by instance state, Pending instances, Stopped instances, Hibernated instances, Terminated instances, Differences between instance states |
| [Amazon EC2 On-Demand Pricing](https://aws.amazon.com/ec2/pricing/on-demand/) | On-Demand Pricing의 시간·초 단위, 60초 최소 과금, OS별 구분과 RHEL 별도 가격 안내 |
| [Amazon EBS pricing](https://aws.amazon.com/ebs/pricing/) | Overview, Pricing examples의 Example 1 – General Purpose SSD (gp3) Volumes: 프로비저닝 용량과 추가 성능 항목 구분 |
| [Stop and start Amazon EC2 instances](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Stop_Start.html) | 도입부, Manually stop and start your instances의 EBS 기반 조건·instance store 데이터·정상 종료 관련 주의사항 |
| [Amazon EC2 instance types](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instance-types.html) | 도입부, Available instance types의 자원 구성 설명 |

[AWS 학습 목차](../README.md) · [전체 학습 목차](../../README.md) · [전체 커리큘럼](../../curriculum.md)

## 학습 확인 문제 — 정답과 해설

1. EC2는 `12시간/일 × 30일 × 0.10 USD/시간 = 36 USD`, EBS는 `50 GiB × 0.08 USD/(GiB·월) × 1개월 = 4 USD`입니다. 합계는 `40 USD`, 24시간 구성 대비 차이는 `76 − 40 = 36 USD`입니다. EBS는 실행 시간에 비례해 줄지 않습니다.
2. 예제에 포함된 컴퓨팅 비용은 `0 USD`, EBS는 `4 USD`, 합계는 `4 USD`입니다. 실제 환경에서는 다른 자원·상품 조건·세금 등이 있을 수 있으므로 이 값이 전체 청구액이라는 뜻은 아닙니다.
3. 결론 내릴 수 없습니다. 낮은 평균 CPU는 야간 중단 허용의 근거가 아니며, 하루 8시간 운영 가능 여부도 미확인입니다. 예를 들어 야간 요청·배치·복구 역할과 재시작 시간·데이터 보존을 확인해야 합니다. 48 USD는 제시한 가상 조건의 차이이며 이 서비스에서 관측한 절감액이 아닙니다.
