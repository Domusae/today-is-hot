"""Mattermost 메시지 카드(attachment) 생성.

캠페인: 오늘도 덥습니다

카드는 두 종류다.
- 특보 카드 : 폭염중대경보/경보/주의보가 발효 중이거나 어제 대비 해제됐을 때
- 예보 카드 : 특보가 없는 날에도 매일 아침 나가는 가벼운 더위 안내

읽는 사람이 정해져 있으므로(역삼동) 지역은 표시하지 않는다.
멘트는 등급마다 여러 개를 두고 날짜로 돌려가며 고른다.
같은 등급이 며칠 이어져도 매일 다른 문장이 나온다.
"""
from __future__ import annotations

from datetime import date, datetime

from .comfort import humidity_band
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
        "이건 진짜 위험해요. 오늘은 그냥 나가지 마세요 🚨",
        "역대급이에요. 농담 아니고 밖은 위험합니다",
        "오늘의 목표는 딱 하나, 무사히 집에 가기예요",
    ],
    "폭염경보": [
        "오늘 진짜 더워요. 에어컨 앞자리 사수하세요 🔥",
        "폭염경보 떴어요. 무리하면 훅 갑니다 진짜로",
        "밖에 나갈 일 있으면 물병은 필수예요 🧴",
    ],
    "폭염주의보": [
        "슬슬 위험해요. 물 좀 드시고요 🥤",
        "폭염주의보예요. 방심하다 훅 가는 날씨입니다",
        "오늘은 그늘만 골라 밟고 다니게 될 거예요 🌳",
    ],
}

ACTION_GUIDE = {
    "폭염중대경보": [
        "**멈추기** — 하던 야외활동 지금 바로 접으세요",
        "**옮기기** — 에어컨 없는 실내도 위험해요. 무더위쉼터나 그늘로",
        "**살피기** — 주변에 혼자 있는 사람, 차 안에 남은 사람 없는지 봐주세요",
        "어지럽거나 머리 아프면 망설이지 말고 119예요 🚑",
    ],
    "폭염경보": [
        "낮 12시~5시엔 야외활동 접어두세요. 진심입니다",
        "목마르기 전에 마셔야 해요. 15분에 한 모금씩 🥤",
        "어지럽거나 속이 울렁이면 바로 그늘로! 참지 마세요",
        "혼자 다니지 말고 친구랑 같이 움직이세요",
    ],
    "폭염주의보": [
        "제일 더운 2시쯤엔 실내에 있는 게 좋아요",
        "커피 말고 물이요. 카페인은 오히려 탈수돼요",
        "실내는 26~28도가 딱이에요. 너무 춥게 하면 더 피곤해져요",
        "밝고 헐렁한 옷이 훨씬 시원해요 👕",
    ],
}

RELEASE_HEADLINES = [
    "특보 풀렸어요! 조금은 살 것 같네요 🎉",
    "드디어 해제예요. 그동안 고생 많으셨어요",
    "한숨 돌려도 좋아요. 그래도 물은 챙기고요",
]

RELEASE_GUIDE = [
    "특보는 풀렸지만 몸은 아직 지쳐 있어요",
    "물 많이 마시고 오늘은 좀 일찍 자요 😴",
]

# 특보가 없는 날의 더위 등급. 기준은 기상청이 준 낮 최고기온(TMX)이다.
# (최저 기준온도, 등급명, 아이콘, 색상, [멘트들], [안내])
FORECAST_LEVELS = (
    (
        35.0,
        "가마솥",
        "🫠",
        "#D0021B",
        [
            "밖은 지금 프라이팬이에요 🍳 진심으로 나가지 마세요",
            "35도… 이건 날씨가 아니라 공격인 것 같아요",
            "오늘의 목표는 생산성이 아니라 생존입니다",
            "특보는 없는데 기온은 특보급이에요. 이게 무슨 일이죠",
        ],
        [
            "특보만 없지 더운 건 똑같아요. 한낮 외출은 미루세요",
            "물통을 책상에 올려두세요. 눈에 보여야 마시게 돼요",
        ],
    ),
    (
        33.0,
        "한여름",
        "🥵",
        "#F5A623",
        [
            "오늘도 덥습니다. 놀랍게도 어제보다 더요",
            "아이스아메리카노가 생존템이 되는 날이에요 🧊",
            "밖에 5분만 있어도 땀범벅 확정입니다",
            "그늘만 골라 밟기 게임, 오늘도 시작이에요 🌳",
        ],
        [
            "점심 산책은 그늘로. 아스팔트 위는 생각보다 훨씬 뜨거워요",
            "커피만 마시지 말고 물도 한 잔씩 챙겨요",
        ],
    ),
    (
        30.0,
        "더움",
        "😮‍💨",
        "#F8B94B",
        [
            "덥긴 한데 아직 화나는 정도는 아니에요",
            "여름이 슬슬 몸 푸는 중입니다 😮‍💨",
            "선풍기로 버틸 수 있는 마지노선이에요",
            "가방에 물병 하나 챙기면 딱 좋은 날",
        ],
        [
            "실내외 온도차가 큰 날이에요. 겉옷 하나 챙기면 좋아요",
            "에어컨 바람 직빵으로 맞으면 오히려 더 피곤해져요",
        ],
    ),
    (
        28.0,
        "살짝 더움",
        "😌",
        "#7FB069",
        [
            "오늘은 좀 봐주네요. 웬일이죠? 😌",
            "이 정도면 여름치곤 착한 편이에요",
            "창문 열어두기 딱 좋은 날씨예요 🪟",
            "산책 나가도 후회 안 할 것 같아요",
        ],
        ["이런 날 환기 한 번 시켜두면 하루가 쾌적해요"],
    ),
    (
        -99.0,
        "선선",
        "🍃",
        "#2FA84F",
        [
            "오늘은 안 덥습니다. 제 이름이 좀 민망하네요 🍃",
            "이런 날은 기록해둬야 해요. 캡처 각입니다",
            "여름이 잠깐 쉬어가는 중인가 봐요",
            "밖에 나가세요! 이런 날 그냥 보내면 아까워요",
        ],
        ["모처럼 시원해요. 미뤄둔 산책 하기 좋은 날이에요"],
    ),
)

UNKNOWN_LEVEL = (
    "날씨 미확인",
    "🌤",
    "#8A8A8A",
    ["오늘 날씨를 못 가져왔어요… 그래도 덥겠죠? 🤔"],
    ["기상청에서 오늘 예보를 못 받아왔어요", "그래도 물은 꼭 챙겨 드세요"],
)


def _pick(pool: list[str], when: datetime | date | None = None) -> str:
    """날짜로 문구를 돌린다. 같은 날은 항상 같은 문구가 나온다."""
    if not pool:
        return ""
    day = when or datetime.now()
    if isinstance(day, datetime):
        day = day.date()
    return pool[day.toordinal() % len(pool)]


def _forecast_level(temps: dict[str, float]):
    """더위 등급을 고른다. 기준은 기상청이 준 낮 최고기온(TMX)이다.

    기상청은 체감온도로 폭염특보를 내지만 단기예보 API는 체감온도를 주지 않는다.
    직접 계산해 쓰면 공식 값과 어긋날 수 있어 받아온 기온만 쓴다.
    """
    today_max = temps.get("today_max")
    if today_max is None:
        return UNKNOWN_LEVEL
    for threshold, *level in FORECAST_LEVELS:
        if today_max >= threshold:
            return tuple(level)
    return UNKNOWN_LEVEL


def _humidity_note(temps: dict[str, float], when: datetime | None = None) -> str:
    """습도 한 줄. 값은 기상청 REH 그대로다."""
    humidity = temps.get("humidity")
    if humidity is None:
        return ""
    return _pick(humidity_band(humidity)[1], when).format(rh=humidity)


def _title(event: HeatEvent) -> str:
    if event.is_release:
        return f"✅ {event.kind} 해제됐어요"
    if event.is_warning:
        icon = ICONS.get(event.kind, "☀️")
        badge = " · 방금 떴어요" if event.started_today else ""
        return f"{icon} {event.kind} 발효 중{badge}"

    name, icon, _, _, _ = _forecast_level(event.temps)
    return f"{icon} 오늘은 {name}"


def _color(event: HeatEvent) -> str:
    if event.is_release:
        return COLORS["해제"]
    if event.is_warning:
        return COLORS.get(event.kind, "#F5A623")
    return _forecast_level(event.temps)[2]


def _body(event: HeatEvent, when: datetime | None = None) -> str:
    humidity_note = _humidity_note(event.temps, when)

    if event.is_release:
        lines = [_pick(RELEASE_HEADLINES, when), ""]
        lines += [f"- {line}" for line in RELEASE_GUIDE]
    elif event.is_warning:
        lines = [_pick(WARNING_HEADLINES.get(event.kind, []), when)]
        if humidity_note:
            lines.append(humidity_note)
        lines += ["", "**이렇게 해요**"]
        lines += [f"- {line}" for line in ACTION_GUIDE.get(event.kind, [])]
    else:
        _, _, _, headlines, guide = _forecast_level(event.temps)
        lines = [_pick(headlines, when)]
        if humidity_note:
            lines.append(humidity_note)
        lines += [""] + [f"- {line}" for line in guide]
    return "\n".join(lines)


def _fields(event: HeatEvent) -> list[dict]:
    """지역은 늘 같으므로 표시하지 않는다.

    값이 없으면 필드를 아예 만들지 않는다. 추정치로 채우지 않는다.
    """
    fields = []
    today_max = event.temps.get("today_max")
    today_min = event.temps.get("today_min")
    humidity = event.temps.get("humidity")

    if today_max is not None:
        fields.append({"title": "낮 최고", "value": f"{today_max:.0f}℃", "short": True})
    if today_min is not None:
        fields.append({"title": "아침 최저", "value": f"{today_min:.0f}℃", "short": True})
    if humidity is not None:
        name, _ = humidity_band(humidity)
        fields.append(
            {"title": "습도", "value": f"{humidity:.0f}% · {name}", "short": True}
        )
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
        return "#### 오늘도 덥습니다 — 특보가 새로 떴어요 🔥"
    if any(e.is_release for e in events) and not any(e.is_warning for e in events):
        return "#### 오늘도 덥습니다 — 특보가 풀렸어요 🌤"
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
