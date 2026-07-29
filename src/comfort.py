"""기온과 습도로 여름철 체감온도를 계산한다.

기상청은 2023년 5월 15일부터 폭염특보를 **체감온도 기준**으로 운영한다.
(통보문에도 명시돼 있다: 최고기온이 33℃ 미만이어도 습도가 높으면 특보가
발표될 수 있고, 33℃ 이상이어도 건조하면 발표되지 않을 수 있다.)

그래서 카드의 더위 등급도 기온이 아니라 체감온도로 매긴다.

산식은 기상청 여름철 체감온도(2020 개정)이며, 습구온도는 Stull 근사식을 쓴다.
여름철(5~9월) 기준이라 겨울 기온에는 의미가 없다.
"""
from __future__ import annotations

import math


def wet_bulb(ta: float, rh: float) -> float:
    """Stull 근사식에 의한 습구온도(℃). ta=기온(℃), rh=상대습도(%)."""
    return (
        ta * math.atan(0.151977 * math.sqrt(rh + 8.313659))
        + math.atan(ta + rh)
        - math.atan(rh - 1.67633)
        + 0.00391838 * rh**1.5 * math.atan(0.023101 * rh)
        - 4.686035
    )


def apparent_temperature(ta: float, rh: float) -> float:
    """여름철 체감온도(℃)."""
    tw = wet_bulb(ta, rh)
    return (
        -0.2442
        + 0.55399 * tw
        + 0.45535 * ta
        - 0.0022 * tw**2
        + 0.00278 * tw * ta
        + 3.0
    )


# (최저 습도, 등급명, [멘트들])
HUMIDITY_BANDS = (
    (
        80.0,
        "매우 습함",
        [
            "습도가 {rh:.0f}%예요. 이건 공기가 아니라 국물입니다 🍜",
            "습도 {rh:.0f}%… 숨쉬기가 수영 같은 날이에요",
            "땀이 아예 안 마르는 습도예요. 여벌 티셔츠 챙기세요 👕",
        ],
    ),
    (
        70.0,
        "습함",
        [
            "습도 {rh:.0f}%. 땀이 잘 안 마르는 그 느낌이에요 😓",
            "끈적한 하루가 예상됩니다. 습도 {rh:.0f}%예요",
            "선풍기보다 제습이 더 급한 날이에요",
        ],
    ),
    (
        55.0,
        "약간 습함",
        [
            "습도 {rh:.0f}%. 살짝 눅눅한 정도예요",
            "습도는 애매하게 높아요. 그늘 들어가면 괜찮습니다",
            "그늘에서는 견딜 만한 습도예요",
        ],
    ),
    (
        -1.0,
        "쾌적",
        [
            "습도 {rh:.0f}%. 그나마 건조해서 다행이에요 🍃",
            "습도가 낮아 그늘만 들어가면 살 만해요",
            "끈적하진 않은 더위예요. 이게 어디예요",
        ],
    ),
)


def humidity_band(rh: float) -> tuple[str, list[str]]:
    """습도 등급명과 멘트 후보를 돌려준다."""
    for threshold, name, notes in HUMIDITY_BANDS:
        if rh >= threshold:
            return name, notes
    return HUMIDITY_BANDS[-1][1], HUMIDITY_BANDS[-1][2]
