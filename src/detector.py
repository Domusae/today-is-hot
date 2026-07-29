"""특보 목록과 단기예보에서 '더위' 관련 이벤트를 뽑아낸다."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .config import Region, TROPICAL_NIGHT_C

# "[기상특보] ... 대전, 세종 폭염주의보 발표" 처럼 제목 안에 종류/강도/동작이 들어온다.
# 응답 스키마가 개편돼도 제목 문구는 유지되므로 문자열 매칭이 가장 덜 깨진다.
HEAT_PATTERN = re.compile(r"폭염\s*(주의보|경보)")
ACTION_PATTERN = re.compile(r"(발표|해제|대치|연장|변경)")


@dataclass(frozen=True)
class HeatEvent:
    """알림 한 건."""

    kind: str  # 폭염주의보 / 폭염경보 / 열대야
    action: str  # 발표 / 해제 / 예상
    region: str
    issued_at: str  # 표시용 시각 문자열
    key: str  # 중복 발송 방지용 고유키
    detail: str = ""
    temps: dict[str, float] = field(default_factory=dict)

    @property
    def is_release(self) -> bool:
        return self.action == "해제"


def _matches_region(title: str, region: Region) -> bool:
    return any(kw in title for kw in region.keywords)


def _format_tm_fc(tm_fc: str) -> str:
    """202607291100 → '07월 29일 11시 00분'"""
    try:
        return datetime.strptime(str(tm_fc), "%Y%m%d%H%M").strftime("%m월 %d일 %H시 %M분")
    except ValueError:
        return str(tm_fc)


def detect_heat_warnings(items: list[dict], region: Region) -> list[HeatEvent]:
    """기상특보 목록에서 해당 지역의 폭염 특보만 골라낸다."""
    events: list[HeatEvent] = []
    for item in items:
        title = str(item.get("title", ""))
        heat = HEAT_PATTERN.search(title)
        if not heat or not _matches_region(title, region):
            continue

        action_match = ACTION_PATTERN.search(title)
        action = "해제" if "해제" in title else (action_match.group(1) if action_match else "발표")
        tm_fc = item.get("tmFc", "")
        events.append(
            HeatEvent(
                kind=f"폭염{heat.group(1)}",
                action=action,
                region=region.name,
                issued_at=_format_tm_fc(tm_fc),
                key=f"warn:{region.name}:{tm_fc}:{item.get('tmSeq', '')}:{heat.group(1)}:{action}",
                detail=title,
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
    """오늘 최고기온과 오늘 밤 최저기온을 뽑는다."""
    now = now or datetime.now()
    table = _parse_forecast(items)
    today = now.strftime("%Y%m%d")
    result: dict[str, float] = {}

    for time_slot in table.get(today, {}).values():
        tmx = _to_float(time_slot.get("TMX"))
        if tmx is not None:
            result["today_max"] = tmx
            break

    night_min = _night_min(table, now)
    if night_min is not None:
        result["night_min"] = night_min
    return result


def _night_min(table: dict, now: datetime) -> float | None:
    """오늘 18시 ~ 내일 09시 사이 예보 기온의 최솟값(열대야 판정 구간)."""
    start = now.replace(hour=18, minute=0, second=0, microsecond=0)
    if now.hour < 9:  # 새벽에 돌린 경우 어젯밤 구간을 본다.
        start -= timedelta(days=1)
    end = start + timedelta(hours=15)

    temps = []
    for date, slots in table.items():
        for time, values in slots.items():
            temp = _to_float(values.get("TMP"))
            if temp is None:
                continue
            try:
                at = datetime.strptime(f"{date}{time}", "%Y%m%d%H%M")
            except ValueError:
                continue
            if start <= at <= end:
                temps.append(temp)
    return min(temps) if temps else None


def detect_tropical_night(
    items: list[dict], region: Region, now: datetime | None = None
) -> HeatEvent | None:
    """열대야는 정식 기상특보가 아니므로 예보 최저기온으로 직접 판정한다."""
    now = now or datetime.now()
    temps = summarize_temps(items, now)
    night_min = temps.get("night_min")
    if night_min is None or night_min < TROPICAL_NIGHT_C:
        return None

    night_date = now if now.hour >= 9 else now - timedelta(days=1)
    return HeatEvent(
        kind="열대야",
        action="예상",
        region=region.name,
        issued_at=night_date.strftime("%m월 %d일 밤"),
        key=f"tropical:{region.name}:{night_date:%Y%m%d}",
        detail=f"밤사이 최저기온이 {night_min:.0f}℃로 예상됩니다.",
        temps=temps,
    )
