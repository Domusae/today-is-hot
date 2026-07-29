"""환경변수와 감시 지역 설정."""
import os
from dataclasses import dataclass

KMA_BASE = "https://apis.data.go.kr/1360000"

# 열대야 판정 기준: 밤(18시~익일 09시) 최저기온
TROPICAL_NIGHT_C = 25.0
# 폭염 참고 기준: 낮 최고기온
HEAT_ADVISORY_C = 33.0
HEAT_WARNING_C = 35.0


@dataclass(frozen=True)
class Region:
    """감시 대상 지역.

    stn_id : 기상특보 발표관서 코드 (108=전국/본청, 133=대전, 108 외 지역은 기상청 문서 참조)
    nx, ny : 단기예보 격자 좌표
    keywords: 특보 통보문 제목에서 이 지역을 식별할 문자열
    """

    name: str
    stn_id: str
    nx: int
    ny: int
    keywords: tuple[str, ...]


# 기본값: 대전 (SSAFY 대전캠퍼스 기준). 필요하면 여기만 고치면 됩니다.
REGIONS = (
    Region(
        name="대전",
        stn_id="133",
        nx=67,
        ny=100,
        keywords=("대전", "세종", "충남", "충청남도"),
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
