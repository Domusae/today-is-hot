"""기상특보 목록에서 폭염 특보를 뽑아내고, 카드에 얹을 기온을 정리한다."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from .config import Region

# "[기상특보] ... 대전, 세종 폭염주의보 발표" 처럼 제목 안에 종류/강도/동작이 들어온다.
# 응답 스키마가 개편돼도 제목 문구는 유지되므로 문자열 매칭이 가장 덜 깨진다.
HEAT_PATTERN = re.compile(r"폭염\s*(주의보|경보)")
ACTION_PATTERN = re.compile(r"(발표|해제|대치|연장|변경)")


@dataclass(frozen=True)
class HeatEvent:
    """알림 한 건."""

    kind: str  # 폭염주의보 / 폭염경보
    action: str  # 발표 / 해제 / 대치 / 연장 / 변경
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
