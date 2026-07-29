"""Mattermost 메시지 카드(attachment) 생성.

캠페인: 오늘도 덥습니다

카드는 두 종류다.
- 특보 카드 : 폭염중대경보/경보/주의보가 발효 중이거나 어제 대비 해제됐을 때
- 예보 카드 : 특보가 없는 날에도 매일 아침 나가는 가벼운 더위 안내

멘트는 등급마다 여러 개를 두고 날짜로 돌려가며 고른다.
같은 등급이 며칠 이어져도 매일 다른 문장이 나온다.
"""
from __future__ import annotations

from datetime import date, datetime

from .detector import HeatEvent

CAMPAIGN = "오늘도 덥습니다"

COLORS = {
    "폭염중대경보": "#8B0000",
    "폭염경보": "#D0021B",
    "폭염주의보": "#F5A623",
    "해제": "#2FA84F",
}

ICONS = {
    "폭염중대경보": "🚨",
    "폭염경보": "🔥",
    "폭염주의보": "🌡️",
}

# 특보 등급별 한 줄 멘트. 날짜로 돌아가며 하나가 뽑힌다.
WARNING_HEADLINES = {
    "폭염중대경보": [
        "오늘은 덥다는 말로 부족합니다. 생존 모드로 가시죠.",
        "오늘도 덥습니다 — 사상 최고 수준입니다. 농담 아닙니다.",
        "오늘은 밖에 나가지 않는 것이 최선입니다.",
    ],
    "폭염경보": [
        "오늘도 덥습니다. 그것도 아주 많이요.",
        "폭염경보입니다. 오늘 하루는 실내에서 버티시죠.",
        "오늘은 에어컨과 친해지셔야 합니다.",
    ],
    "폭염주의보": [
        "오늘도 덥습니다. 방심하면 훅 갑니다.",
        "폭염주의보입니다. 물병 챙기셨나요?",
        "오늘은 그늘이 최고의 친구입니다.",
    ],
}

ACTION_GUIDE = {
    "폭염중대경보": [
        "**중단** — 지금 즉시 모든 야외활동을 멈추세요.",
        "**이동** — 냉방 없는 실내는 위험합니다. 무더위쉼터·그늘로 이동하세요.",
        "**확인** — 가족, 이웃, 차 안에 남은 사람이 없는지 확인하세요.",
        "어지럼·두통이 오면 즉시 119에 신고하고 시원한 곳으로 옮기세요.",
    ],
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

RELEASE_HEADLINES = [
    "특보가 풀렸습니다. 오늘은 좀 숨통이 트이겠네요.",
    "드디어 해제입니다. 그동안 고생하셨습니다.",
    "특보 해제 — 그래도 방심은 이릅니다.",
]

RELEASE_GUIDE = [
    "특보는 해제됐지만 누적된 피로는 남아 있습니다.",
    "수분 보충과 충분한 수면으로 회복하세요.",
]

# 특보가 없는 날, 낮 최고기온으로 정하는 등급.
# (최저 기준온도, 등급명, 아이콘, 색상, [멘트들], [안내])
FORECAST_LEVELS = (
    (
        35.0,
        "가마솥",
        "🫠",
        "#D0021B",
        [
            "오늘도 덥습니다. 아니, 오늘은 좀 심하게 덥습니다.",
            "특보는 없는데 기온은 특보급입니다. 이게 무슨 일이죠.",
            "오늘의 목표는 생산성이 아니라 생존입니다.",
            "35도입니다. 더 설명이 필요할까요.",
        ],
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
        [
            "네, 오늘도 덥습니다. 예상하셨겠지만요.",
            "오늘도 덥습니다. 이쯤 되면 놀랍지도 않네요.",
            "여름이 제 할 일을 아주 성실히 하고 있습니다.",
            "오늘은 아이스아메리카노가 필수재입니다.",
        ],
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
        [
            "오늘도 덥습니다. 놀랍지 않으시죠.",
            "적당히 덥습니다. 그러니까 덥습니다.",
            "오늘은 그럭저럭 견딜 만한 더위입니다.",
            "30도는 이제 기본값이 된 것 같습니다.",
        ],
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
        [
            "오늘은 좀 덜 덥습니다. 그래도 덥긴 합니다.",
            "선방한 날씨입니다. 이 정도면 감사하죠.",
            "오늘은 에어컨을 잠깐 쉬게 해줘도 되겠습니다.",
            "덥긴 한데, 화나는 정도는 아닙니다.",
        ],
        ["이런 날 창문 열고 환기 한 번 해두면 좋습니다."],
    ),
    (
        -99.0,
        "선선",
        "🍃",
        "#2FA84F",
        [
            "오늘은… 안 덥습니다. 이런 날도 있습니다.",
            "캠페인 이름이 무색한 날입니다. 반갑네요.",
            "오늘만큼은 제목이 거짓말입니다.",
            "시원합니다. 이런 날은 기록해둡시다.",
        ],
        ["모처럼 시원합니다. 밀린 산책 하기 좋은 날이에요."],
    ),
)

UNKNOWN_LEVEL = (
    "기온 미확인",
    "🌤",
    "#8A8A8A",
    ["오늘도 덥습니다. 아마도요."],
    ["기상청 예보에서 오늘 기온을 가져오지 못했습니다.", "그래도 물은 챙겨 드세요."],
)


def _pick(pool: list[str], when: datetime | date | None = None) -> str:
    """날짜로 문구를 돌린다. 같은 날은 항상 같은 문구가 나온다."""
    if not pool:
        return ""
    day = (when or datetime.now())
    if isinstance(day, datetime):
        day = day.date()
    return pool[day.toordinal() % len(pool)]


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


def _body(event: HeatEvent, when: datetime | None = None) -> str:
    if event.is_release:
        lines = [_pick(RELEASE_HEADLINES, when), "", event.detail, ""]
        lines += [f"- {line}" for line in RELEASE_GUIDE]
    elif event.is_warning:
        headline = _pick(WARNING_HEADLINES.get(event.kind, []), when)
        lines = [headline, "", event.detail, "", "**이렇게 하세요**"]
        lines += [f"- {line}" for line in ACTION_GUIDE.get(event.kind, [])]
    else:
        _, _, _, headlines, guide = _forecast_level(event.temps)
        lines = [_pick(headlines, when), ""] + [f"- {line}" for line in guide]
    return "\n".join(lines)


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
        fields.append({"title": "기준", "value": event.issued_at, "short": True})
    return fields


def build_attachment(event: HeatEvent, when: datetime | None = None) -> dict:
    """카드 한 장을 만든다."""
    return {
        "fallback": _title(event),
        "color": _color(event),
        "title": _title(event),
        "text": _body(event, when),
        "fields": _fields(event),
        "footer": f"{CAMPAIGN} · 기상청 제공",
    }


def _headline(events: list[HeatEvent]) -> str:
    if any(e.started_today for e in events):
        return "#### 오늘도 덥습니다 — 특보가 새로 발효됐습니다 🔥"
    if any(e.is_release for e in events) and not any(e.is_warning for e in events):
        return "#### 오늘도 덥습니다 — 특보가 해제되었습니다 🌤"
    return "#### 오늘도 덥습니다 ☀️"


def build_payload(
    events: list[HeatEvent], username: str, icon: str, when: datetime | None = None
) -> dict:
    """여러 이벤트를 한 번의 웹훅 호출로 보낸다."""
    return {
        "username": username,
        "icon_emoji": icon,
        "text": _headline(events),
        "attachments": [build_attachment(e, when) for e in events],
    }
