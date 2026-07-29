"""기상특보 목록에서 현재 발효 중인 폭염 특보를 판정한다.

실제 특보 제목은 이런 형태다.

    [특보] 제07-100호 : 2026.07.29.10:00 / 폭염경보 변경 (*)
    [특보] 제07-92호 : 2026.07.24.16:00 / 폭염주의보 변경·폭염주의보 해제·열대야주의보 발표 (*)

제목에 지역명은 없다(지역은 stnId로 구분된다). 한 건에 여러 특보가
가운뎃점으로 묶여 오므로 조각별로 나눠 읽어야 한다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .config import Region

# "/" 뒤가 실제 특보 내용, 끝의 "(*)"는 잘라낸다.
TITLE_BODY = re.compile(r"/\s*(.+?)\s*(?:\(\*\))?\s*$")
# "폭염경보 변경" 같은 조각 하나. 열대야는 이 캠페인 범위 밖이라 잡지 않는다.
SEGMENT = re.compile(r"폭염(주의보|경보)\s*(발표|변경|대치|연장|해제)")

# 해제 외의 동작은 모두 '발효 중'으로 본다.
RELEASE = "해제"


@dataclass(frozen=True)
class HeatEvent:
    """알림 한 건."""

    kind: str  # 폭염주의보 / 폭염경보
    action: str  # 발효 중 / 해제
    region: str
    issued_at: str  # 표시용 시각 문자열
    key: str  # 중복 발송 방지용 고유키 (하루 1회 발송되도록 날짜 포함)
    detail: str = ""
    temps: dict[str, float] = field(default_factory=dict)

    @property
    def is_release(self) -> bool:
        return self.action == RELEASE


def _parse_tm_fc(tm_fc) -> datetime | None:
    try:
        return datetime.strptime(str(tm_fc), "%Y%m%d%H%M")
    except (ValueError, TypeError):
        return None


def parse_segments(title: str) -> list[tuple[str, str]]:
    """제목에서 (폭염주의보|폭염경보, 동작) 조각을 모두 뽑는다."""
    body = TITLE_BODY.search(str(title))
    if not body:
        return []
    return [
        (f"폭염{level}", action) for level, action in SEGMENT.findall(body.group(1))
    ]


def current_warnings(items: list[dict]) -> dict[str, datetime]:
    """발표 이력을 시간순으로 재생해 지금 발효 중인 특보를 남긴다.

    반환: {특보종류: 마지막으로 발효된 시각}
    """
    timed = [(at, item) for item in items if (at := _parse_tm_fc(item.get("tmFc")))]
    active: dict[str, datetime] = {}
    for at, item in sorted(timed, key=lambda pair: pair[0]):
        for kind, action in parse_segments(item.get("title", "")):
            if action == RELEASE:
                active.pop(kind, None)
            else:
                active.setdefault(kind, at)
    return active


def recent_releases(items: list[dict], now: datetime, within_hours: int = 24) -> dict[str, datetime]:
    """최근 N시간 안에 해제된 특보. 해제 카드를 하루 한 번 보내기 위해 쓴다."""
    cutoff = now - timedelta(hours=within_hours)
    released: dict[str, datetime] = {}
    for item in items:
        at = _parse_tm_fc(item.get("tmFc"))
        if at is None or at < cutoff:
            continue
        for kind, action in parse_segments(item.get("title", "")):
            if action == RELEASE:
                released[kind] = at
    # 해제 후 다시 발표된 경우는 해제 카드를 보내지 않는다.
    return {k: v for k, v in released.items() if k not in current_warnings(items)}


def build_events(
    items: list[dict], region: Region, now: datetime | None = None
) -> list[HeatEvent]:
    """오늘 아침 기준으로 알릴 이벤트를 만든다."""
    now = now or datetime.now()
    today = now.strftime("%Y%m%d")
    events: list[HeatEvent] = []

    for kind, at in sorted(current_warnings(items).items()):
        events.append(
            HeatEvent(
                kind=kind,
                action="발효 중",
                region=region.name,
                issued_at=at.strftime("%m월 %d일 %H시 %M분 발효"),
                key=f"{today}:active:{region.name}:{kind}",
                detail=f"{region.name}에 {kind}가 발효 중입니다.",
            )
        )

    for kind, at in sorted(recent_releases(items, now).items()):
        events.append(
            HeatEvent(
                kind=kind,
                action=RELEASE,
                region=region.name,
                issued_at=at.strftime("%m월 %d일 %H시 %M분 해제"),
                key=f"{today}:release:{region.name}:{kind}",
                detail=f"{region.name}의 {kind}가 해제되었습니다.",
            )
        )
    return events


def _parse_forecast(items: list[dict]) -> dict[str, dict[str, dict[str, str]]]:
    """예보 항목을 {날짜: {시각: {카테고리: 값}}} 으로 정리한다."""
    table: dict[str, dict[str, dict[str, str]]] = {}
    for item in items:
        date = str(item.get("fcstDate", ""))
        time = str(item.get("fcstTime", ""))
        table.setdefault(date, {}).setdefault(time, {})[str(item["category"])] = str(
            item["fcstValue"]
        )
    return table


def _to_float(value: str | None) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def summarize_temps(items: list[dict], now: datetime | None = None) -> dict[str, float]:
    """카드에 함께 보여줄 오늘의 최고/최저기온을 뽑는다."""
    now = now or datetime.now()
    table = _parse_forecast(items)
    today = table.get(now.strftime("%Y%m%d"), {})
    result: dict[str, float] = {}

    for category, label in (("TMX", "today_max"), ("TMN", "today_min")):
        for time_slot in today.values():
            value = _to_float(time_slot.get(category))
            if value is not None:
                result[label] = value
                break
    return result
