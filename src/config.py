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

    특보 제목에는 지역명이 없다. 대신 통보문 t6(현재 발효 현황)에 구역 단위로
    적혀 있으므로 warn_area/sub_area로 골라낸다.

    stn_id   : 통보문 발표관서 코드. 108은 본청이고 t6에 전국 현황이 담긴다.
    nx, ny   : 단기예보 격자 좌표 (동 단위로 정확)
    warn_area: t6의 최상위 지역 표기 (예: "서울", "대전")
    sub_area : t6 괄호 안의 구역 표기. 하위 구역이 없는 지역은 None.
    """

    name: str
    stn_id: str
    nx: int
    ny: int
    warn_area: str
    sub_area: str | None = None


# 기본값: 서울 강남구 역삼동.
# nx/ny는 역삼동 위경도(37.5006, 127.0364)를 기상청 격자로 변환한 값이다.
# 강남구는 기상청 특보 구역상 '서울동남권'(서초·강남·송파·강동)에 속한다.
REGIONS = (
    Region(
        name="서울 강남구",
        stn_id="108",
        nx=61,
        ny=125,
        warn_area="서울",
        sub_area="서울동남권",
    ),
)


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
