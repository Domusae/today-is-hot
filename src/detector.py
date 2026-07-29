"""통보문 현황(t6)과 단기예보에서 알림 이벤트를 만든다.

특보 판정은 전적으로 status.py(t6 파싱)에 맡긴다. 특보 목록의 제목에는
지역 정보가 없어서 구역 단위 판정이 불가능하기 때문이다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .config import Region
from .precip import DayPart
from .precip import summarize_dayparts as dayparts_of
from .status import heat_warnings_for

RELEASE = "해제"


@dataclass(frozen=True)
class HeatEvent:
    """알림 한 건."""

    kind: str  # 폭염중대경보 / 폭염경보 / 폭염주의보 / 오늘의 더위
    action: str  # 발효 중 / 해제 / 예보
    region: str
    issued_at: str  # 표시용 시각 문자열
    key: str  # 중복 발송 방지용 고유키 (하루 1회 발송되도록 날짜 포함)
    detail: str = ""
    temps: dict[str, float] = field(default_factory=dict)
    dayparts: tuple[DayPart, ...] = ()  # 오전/오후/저녁 하늘 상태
    started_today: bool = False  # 오늘 새로 발효된 특보인지

    @property
    def is_release(self) -> bool:
        return self.action == RELEASE

    @property
    def is_warning(self) -> bool:
        return self.kind.startswith("폭염")


def format_tm_fc(tm_fc) -> str:
    try:
        return datetime.strptime(str(tm_fc), "%Y%m%d%H%M").strftime("%m월 %d일 %H시 %M분")
    except (ValueError, TypeError):
        return str(tm_fc)


def build_events(
    current_t6: str,
    previous_t6: str | None,
    region: Region,
    tm_fc=None,
    now: datetime | None = None,
) -> list[HeatEvent]:
    """지금 발효 중인 특보와, 어제 대비 해제된 특보로 이벤트를 만든다.

    previous_t6가 없으면(어제 통보문을 못 구한 경우) 신규 여부를 알 수 없으므로
    모두 '이어지는 특보'로 취급한다. 없는 정보를 지어내지 않는다.
    """
    now = now or datetime.now()
    today = now.strftime("%Y%m%d")
    stamp = format_tm_fc(tm_fc) if tm_fc else now.strftime("%m월 %d일")

    current = heat_warnings_for(current_t6, region.warn_area, region.sub_area)
    previous = (
        heat_warnings_for(previous_t6, region.warn_area, region.sub_area)
        if previous_t6
        else None
    )

    events: list[HeatEvent] = []
    for kind in current:
        is_new = previous is not None and kind not in previous
        events.append(
            HeatEvent(
                kind=kind,
                action="발효 중",
                region=region.name,
                issued_at=stamp,
                key=f"{today}:active:{region.name}:{kind}",
                detail=f"{kind} {'신규 발효' if is_new else '발효 중'}",
                started_today=is_new,
            )
        )

    for kind in previous or []:
        if kind in current:
            continue
        events.append(
            HeatEvent(
                kind=kind,
                action=RELEASE,
                region=region.name,
                issued_at=stamp,
                key=f"{today}:release:{region.name}:{kind}",
                detail=f"{kind} 해제",
            )
        )
    return events


def forecast_event(
    region: Region, temps: dict[str, float], now: datetime | None = None
) -> HeatEvent:
    """특보가 없는 날에도 내보낼 '오늘의 더위' 카드.

    등급과 문구는 표현 계층(card.py)이 기온을 보고 정한다.
    """
    now = now or datetime.now()
    return HeatEvent(
        kind="오늘의 더위",
        action="예보",
        region=region.name,
        issued_at=now.strftime("%m월 %d일"),
        key=f"{now:%Y%m%d}:daily:{region.name}",
        temps=temps,
    )


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
    """오늘 예보에서 카드에 실을 값을 뽑는다.

    **여기서 새 수치를 만들지 않는다.** 기상청이 준 값을 그대로 고르기만 한다.

    - today_max / today_min : TMX / TMN 그대로. 없으면 넣지 않는다.
      (시간별 TMP의 최대·최소로 대신하면 일최고/최저와 달라져 거짓이 된다.)
    - humidity : 낮 최고기온 시각의 REH 그대로.
    """
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

    humidity = _humidity_at_hottest_hour(today)
    if humidity is not None:
        result["humidity"] = humidity
    return result


def summarize_dayparts(items: list[dict], now: datetime | None = None) -> list[DayPart]:
    """오늘을 오전·오후·저녁으로 나눈 하늘 상태."""
    now = now or datetime.now()
    table = _parse_forecast(items)
    return dayparts_of(table.get(now.strftime("%Y%m%d"), {}))


def _humidity_at_hottest_hour(day: dict[str, dict[str, str]]) -> float | None:
    """가장 더운 시각의 상대습도. 값 자체는 API가 준 REH 그대로다."""
    best: tuple[float, float] | None = None  # (기온, 그 시각 습도)
    for slot in day.values():
        temp = _to_float(slot.get("TMP"))
        humidity = _to_float(slot.get("REH"))
        if temp is None or humidity is None:
            continue
        if best is None or temp > best[0]:
            best = (temp, humidity)
    return best[1] if best else None
