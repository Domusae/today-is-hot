"""Mattermost 메시지 카드(attachment) 생성.

캠페인: 오늘도 덥습니다
"""
from __future__ import annotations

from .detector import HeatEvent

CAMPAIGN = "오늘도 덥습니다"

COLORS = {
    "폭염경보": "#D0021B",
    "폭염주의보": "#F5A623",
    "해제": "#2FA84F",
}

ICONS = {
    "폭염경보": "🔥",
    "폭염주의보": "🌡️",
}

ACTION_GUIDE = {
    "폭염경보": [
        "낮 12시~17시 야외 활동·실외 작업은 **중단**하세요.",
        "갈증을 느끼지 않아도 **15분마다 물 한 컵**.",
        "어지럼·메스꺼움·근육경련은 온열질환 초기 신호입니다. 즉시 그늘로.",
        "혼자 있는 동료가 없는지 확인하고, 2인 1조로 움직이세요.",
    ],
    "폭염주의보": [
        "가장 더운 시간대(14시 전후) 외출은 피하세요.",
        "물을 자주 마시고, 카페인·알코올 음료는 줄이세요.",
        "실내는 26~28℃를 유지하고 주기적으로 환기하세요.",
        "얇고 밝은 색의 헐렁한 옷이 체온을 덜 올립니다.",
    ],
}

RELEASE_GUIDE = [
    "특보는 해제됐지만 누적된 피로는 남아 있습니다.",
    "수분 보충과 충분한 수면으로 회복하세요.",
]


def _title(event: HeatEvent) -> str:
    icon = ICONS.get(event.kind, "☀️")
    if event.is_release:
        return f"✅ {event.region} {event.kind} 해제"
    return f"{icon} {event.region} {event.kind} {event.action}"


def _color(event: HeatEvent) -> str:
    return COLORS["해제"] if event.is_release else COLORS.get(event.kind, "#F5A623")


def _fields(event: HeatEvent) -> list[dict]:
    fields = [
        {"title": "특보", "value": event.kind, "short": True},
        {"title": "지역", "value": event.region, "short": True},
        {"title": "발표", "value": event.issued_at, "short": True},
    ]
    today_max = event.temps.get("today_max")
    today_min = event.temps.get("today_min")
    if today_max is not None:
        fields.append({"title": "낮 최고", "value": f"{today_max:.0f}℃", "short": True})
    if today_min is not None:
        fields.append({"title": "아침 최저", "value": f"{today_min:.0f}℃", "short": True})
    return fields


def build_attachment(event: HeatEvent) -> dict:
    """Mattermost message attachment 한 장을 만든다."""
    guide = RELEASE_GUIDE if event.is_release else ACTION_GUIDE.get(event.kind, [])
    body = [event.detail] if event.detail else []
    if guide:
        body.append("")
        body.append("**이렇게 하세요**")
        body.extend(f"- {line}" for line in guide)

    return {
        "fallback": _title(event),
        "color": _color(event),
        "title": _title(event),
        "text": "\n".join(body),
        "fields": _fields(event),
        "footer": f"{CAMPAIGN} · 기상청 제공",
    }


def build_payload(events: list[HeatEvent], username: str, icon: str) -> dict:
    """여러 이벤트를 한 번의 웹훅 호출로 보낸다."""
    headline = "#### 오늘도 덥습니다 ☀️"
    if all(e.is_release for e in events):
        headline = "#### 오늘도 덥습니다 — 특보가 해제되었습니다 🌤"

    return {
        "username": username,
        "icon_emoji": icon,
        "text": headline,
        "attachments": [build_attachment(e) for e in events],
    }
