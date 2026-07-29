"""Mattermost 메시지 카드(attachment) 생성.

캠페인: 오늘도 덥습니다

카드는 두 종류다.
- 특보 카드 : 폭염주의보/경보가 발효 중이거나 방금 해제됐을 때
- 예보 카드 : 특보가 없는 날에도 매일 아침 나가는 가벼운 더위 안내
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

# 특보가 없는 날, 낮 최고기온으로 정하는 등급.
# (최저 기준온도, 등급명, 아이콘, 색상, 한 줄 멘트, 안내 문구)
FORECAST_LEVELS = (
    (
        35.0,
        "가마솥",
        "🫠",
        "#D0021B",
        "오늘도 덥습니다. 아니, 오늘은 좀 심하게 덥습니다.",
        [
            "특보는 없지만 체감은 특보급입니다. 한낮 외출은 미루세요.",
            "물통을 책상에 올려두세요. 눈에 보여야 마십니다.",
        ],
    ),
    (
        33.0,
        "한여름",
        "🥵",
        "#F5A623",
        "네, 오늘도 덥습니다. 예상하셨겠지만요.",
        [
            "점심 산책은 그늘로. 아스팔트는 생각보다 뜨겁습니다.",
            "커피 말고 물도 한 잔씩 챙기세요.",
        ],
    ),
    (
        30.0,
        "더움",
        "😮‍💨",
        "#F8B94B",
        "오늘도 덥습니다. 놀랍지 않으시죠.",
        [
            "실내외 온도차가 큰 날입니다. 겉옷 하나쯤은 챙기세요.",
            "에어컨 바람을 직접 맞으면 오히려 더 피곤해집니다.",
        ],
    ),
    (
        28.0,
        "살짝 더움",
        "😌",
        "#7FB069",
        "오늘은 좀 덜 덥습니다. 그래도 덥긴 합니다.",
        [
            "이런 날 창문 열고 환기 한 번 해두면 좋습니다.",
        ],
    ),
    (
        -99.0,
        "선선",
        "🍃",
        "#2FA84F",
        "오늘은… 안 덥습니다. 이런 날도 있습니다.",
        [
            "모처럼 시원합니다. 밀린 산책 하기 좋은 날이에요.",
        ],
    ),
)

UNKNOWN_LEVEL = (
    "기온 미확인",
    "🌤",
    "#8A8A8A",
    "오늘도 덥습니다. 아마도요.",
    ["기상청 예보에서 오늘 최고기온을 가져오지 못했습니다.", "그래도 물은 챙겨 드세요."],
)


def _forecast_level(temps: dict[str, float]):
    """낮 최고기온으로 등급 튜플을 고른다. 기온이 없으면 미확인 등급."""
    today_max = temps.get("today_max")
    if today_max is None:
        return UNKNOWN_LEVEL
    for threshold, *level in FORECAST_LEVELS:
        if today_max >= threshold:
            return tuple(level)
    return UNKNOWN_LEVEL


def _title(event: HeatEvent) -> str:
    if event.is_release:
        return f"✅ {event.region} {event.kind} 해제"
    if event.is_warning:
        icon = ICONS.get(event.kind, "☀️")
        badge = " · 오늘 발효" if event.started_today else ""
        return f"{icon} {event.region} {event.kind} 발효 중{badge}"

    name, icon, _, _, _ = _forecast_level(event.temps)
    return f"{icon} 오늘의 {event.region} — {name}"


def _color(event: HeatEvent) -> str:
    if event.is_release:
        return COLORS["해제"]
    if event.is_warning:
        return COLORS.get(event.kind, "#F5A623")
    return _forecast_level(event.temps)[2]


def _body(event: HeatEvent) -> str:
    if event.is_release:
        lines = [event.detail, ""] + [f"- {line}" for line in RELEASE_GUIDE]
    elif event.is_warning:
        lines = [event.detail, "", "**이렇게 하세요**"]
        lines += [f"- {line}" for line in ACTION_GUIDE.get(event.kind, [])]
    else:
        _, _, _, headline, guide = _forecast_level(event.temps)
        lines = [headline, ""] + [f"- {line}" for line in guide]
    return "\n".join(line for line in lines if line is not None)


def _fields(event: HeatEvent) -> list[dict]:
    fields = []
    if event.is_warning:
        fields.append({"title": "특보", "value": event.kind, "short": True})
    fields.append({"title": "지역", "value": event.region, "short": True})

    today_max = event.temps.get("today_max")
    today_min = event.temps.get("today_min")
    if today_max is not None:
        fields.append({"title": "낮 최고", "value": f"{today_max:.0f}℃", "short": True})
    if today_min is not None:
        fields.append({"title": "아침 최저", "value": f"{today_min:.0f}℃", "short": True})
    if event.is_warning or event.is_release:
        fields.append({"title": "발표", "value": event.issued_at, "short": True})
    return fields


def build_attachment(event: HeatEvent) -> dict:
    """카드 한 장을 만든다."""
    return {
        "fallback": _title(event),
        "color": _color(event),
        "title": _title(event),
        "text": _body(event),
        "fields": _fields(event),
        "footer": f"{CAMPAIGN} · 기상청 제공",
    }


def _headline(events: list[HeatEvent]) -> str:
    if any(e.started_today for e in events):
        return "#### 오늘도 덥습니다 — 방금 특보가 발효됐습니다 🔥"
    if any(e.is_warning for e in events):
        return "#### 오늘도 덥습니다 ☀️"
    if any(e.is_release for e in events):
        return "#### 오늘도 덥습니다 — 특보가 해제되었습니다 🌤"
    return "#### 오늘도 덥습니다 ☀️"


def build_payload(events: list[HeatEvent], username: str, icon: str) -> dict:
    """여러 이벤트를 한 번의 웹훅 호출로 보낸다."""
    return {
        "username": username,
        "icon_emoji": icon,
        "text": _headline(events),
        "attachments": [build_attachment(e) for e in events],
    }
