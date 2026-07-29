"""환경변수와 감시 지역 설정."""
import os
from dataclasses import dataclass

KMA_BASE = "https://apis.data.go.kr/1360000"

# 폭염 참고 기준: 낮 최고기온
HEAT_ADVISORY_C = 33.0
HEAT_WARNING_C = 35.0

# 특보 발효 여부를 판정할 때 며칠치 이력을 재생할지.
# 폭염경보는 며칠씩 이어지므로 당일(0)만 보면 어제 발효돼 오늘도 유효한 특보를 놓친다.
# "오늘 새로 발효된 건"은 별도로 표시되므로, 정확도를 위해 넉넉히 본다.
# 기상청 제한상 최대 6일까지만 가능하다.
WARNING_LOOKBACK_DAYS = 6


@dataclass(frozen=True)
class Region:
    """감시 대상 지역.

    특보 제목에는 지역명이 들어있지 않고 stn_id로만 구분되므로,
    지역 필터링은 전적으로 stn_id에 의존한다.

    stn_id : 기상특보 발표관서 코드 (108=서울, 133=대전, 159=부산 ...)
    nx, ny : 단기예보 격자 좌표
    """

    name: str
    stn_id: str
    nx: int
    ny: int


# 기본값: 서울 강남구 역삼동.
# nx/ny는 역삼동 위경도(37.5006, 127.0364)를 기상청 격자로 변환한 값이라 동 단위로 정확하다.
# 반면 특보는 stnId 단위(108=서울)로만 조회되어 구 단위로 좁힐 수 없다.
# 그래서 표시 이름은 실제 특보 범위에 맞춰 "서울"로 둔다.
REGIONS = (Region(name="서울", stn_id="108", nx=61, ny=125),)


@dataclass(frozen=True)
class Settings:
    kma_service_key: str
    webhook_url: str
    bot_username: str
    bot_icon: str
    dry_run: bool


def load_settings(dry_run: bool = False) -> Settings:
    key = os.environ.get("KMA_SERVICE_KEY", "")
    url = os.environ.get("MM_WEBHOOK_URL", "")
    if not key:
        raise SystemExit("KMA_SERVICE_KEY 환경변수가 없습니다. (data.go.kr 일반 인증키 - Decoding)")
    if not url and not dry_run:
        raise SystemExit("MM_WEBHOOK_URL 환경변수가 없습니다.")
    return Settings(
        kma_service_key=key,
        webhook_url=url,
        bot_username=os.environ.get("MM_BOT_NAME", "오늘도 덥습니다"),
        bot_icon=os.environ.get("MM_BOT_ICON", ":sunny:"),
        dry_run=dry_run,
    )
