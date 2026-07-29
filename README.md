# 오늘도 덥습니다 ☀️

폭염주의보·폭염경보·열대야를 자동으로 감지해 **Mattermost 채널에 더위 안전 카드**를 올리는 캠페인 봇입니다.

```
[GitHub Actions · 30분마다]
        │
        ├─▶ 기상청 기상특보 API   ──▶ 폭염주의보 / 폭염경보 발표·해제 감지
        └─▶ 기상청 단기예보 API   ──▶ 밤 최저기온 25℃ 이상 → 열대야 판정
                    │
                    ▼
        [중복 발송 필터] ──▶ Mattermost Incoming Webhook ──▶ 메시지 카드
```

## 왜 두 갈래로 감지하나

**열대야는 기상특보가 아닙니다.** 폭염은 주의보/경보라는 정식 특보가 발령되지만,
열대야는 "밤사이(18시~익일 09시) 최저기온 25℃ 이상"이라는 통계 기준일 뿐입니다.
그래서 특보 API로는 잡히지 않고, 단기예보 기온을 직접 계산해 판정합니다.

## 준비물

### 1. 기상청 API 키

[공공데이터포털](https://www.data.go.kr/data/15000415/openapi.do)에서 아래 두 개를 활용신청합니다.

- 기상청_기상특보 조회서비스
- 기상청_단기예보 조회서비스

마이페이지에서 **일반 인증키(Decoding)** 를 복사합니다.
Encoding 키를 쓰면 이중 인코딩되어 실패하니 주의하세요.

### 2. Mattermost Incoming Webhook

통합 기능(Integrations) → Incoming Webhook → 채널 선택 → URL 복사.

## 로컬 실행

```bash
pip install -r requirements.txt
cp .env.example .env   # 값 채우기
```

```bash
python main.py --demo
```

API 호출 없이 카드 모양만 미리 봅니다. 실제 조회는 아래처럼 합니다.

```bash
python main.py --dry-run
```

전송 없이 감지 결과와 페이로드만 출력합니다. 이상 없으면 그냥 `python main.py`.

| 옵션 | 설명 |
|---|---|
| `--demo` | API 없이 샘플 카드 출력 |
| `--dry-run` | 실제 조회하되 전송은 안 함 |
| `--force` | 중복 방지 무시하고 다시 보냄 (디자인 확인용) |

응답 원본을 확인하고 싶으면:

```bash
python probe.py warn
```

## GitHub Actions 설정

레포 **Settings → Secrets and variables → Actions** 에 두 개를 등록합니다.

| 이름 | 값 |
|---|---|
| `KMA_SERVICE_KEY` | 공공데이터포털 일반 인증키(Decoding) |
| `MM_WEBHOOK_URL` | Mattermost Webhook URL |

등록 후 Actions 탭에서 `오늘도 덥습니다` → **Run workflow** 로 수동 실행해 확인하세요.

## 지역 변경

[src/config.py](src/config.py)의 `REGIONS`만 고치면 됩니다.

```python
Region(name="대전", stn_id="133", nx=67, ny=100, keywords=("대전", "세종", "충남"))
```

- `nx`, `ny`: 단기예보 격자 좌표. 기상청이 배포하는 좌표 엑셀에서 찾습니다.
- `stn_id`: 특보 발표관서 코드. `108`은 전국(본청)이라 가장 넓게 잡힙니다.
- `keywords`: 특보 제목에 이 문자열이 있어야 우리 지역으로 인정합니다.

여러 지역을 넣으면 각각 따로 감지해 카드를 만듭니다.

## 중복 발송 방지

30분마다 폴링하므로 같은 특보가 계속 다시 잡힙니다.
발송한 이벤트 키를 `state/sent.json`에 남기고, Actions가 이 파일을 레포에 다시 커밋해
실행 사이에 상태를 유지합니다. 7일이 지난 키는 자동으로 정리됩니다.

## 알려진 제약

- **GitHub Actions cron은 정시에 실행되지 않습니다.** 부하에 따라 수 분~수십 분 밀립니다.
  특보 발령 즉시 알림이 필요하면 상시 구동 서버의 cron으로 옮기세요.
- 기상특보 API의 응답 필드 스펙은 개편될 수 있어, 감지 로직은 필드명 대신
  **제목 문자열 매칭**(`폭염(주의보|경보)` + 지역 키워드)으로 구현했습니다.
  실제 응답이 예상과 다르면 `probe.py`로 확인 후 [src/detector.py](src/detector.py)의
  `HEAT_PATTERN`을 조정하세요.
- 개발계정 트래픽은 일 10,000회입니다. 30분 폴링 × 지역 2회 호출이면 하루 100회 남짓이라 여유롭습니다.

## 테스트

```bash
python -m pytest tests -q
```
