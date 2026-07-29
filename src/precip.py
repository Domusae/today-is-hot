"""하루를 오전·오후·저녁으로 나눠 강수와 하늘 상태를 정리한다.

여기서도 새 수치를 만들지 않는다. 기상청이 준 PTY(강수형태), POP(강수확률),
SKY(하늘상태)를 시간대별로 모아 분류만 한다. 기온은 다루지 않는다.
시간대별 기온을 뽑아 쓰면 일최고와 다른 값이 생겨 혼란을 준다.
"""
from __future__ import annotations

from dataclasses import dataclass

# 기상청 단기예보 코드값
PTY_NAMES = {"0": "", "1": "비", "2": "비/눈", "3": "눈", "4": "소나기"}
SKY_NAMES = {"1": "맑음", "3": "구름많음", "4": "흐림"}

# (구간명, 시작시, 끝시) — 끝시는 포함하지 않는다.
DAYPARTS = (("오전", 6, 12), ("오후", 12, 18), ("저녁", 18, 24))

# 강수형태는 없지만 이 확률을 넘으면 "올 수도 있다"고 말한다.
MAYBE_POP = 60


@dataclass(frozen=True)
class DayPart:
    """한 시간대의 하늘 상태."""

    name: str  # 오전 / 오후 / 저녁
    rain: str  # "" | 비 | 비/눈 | 눈 | 소나기
    sky: str  # 맑음 / 구름많음 / 흐림 / ""
    pop: int  # 그 구간의 최대 강수확률(%)

    @property
    def label(self) -> str:
        """카드에 쓸 짧은 표기. 비가 오면 비를, 아니면 하늘 상태를 쓴다."""
        return self.rain or self.sky or "-"


def _to_int(value: str | None) -> int | None:
    try:
        return int(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def summarize_dayparts(day: dict[str, dict[str, str]]) -> list[DayPart]:
    """{시각: {카테고리: 값}} 을 시간대별로 접는다. 자료가 없는 구간은 뺀다."""
    parts: list[DayPart] = []
    for name, start, end in DAYPARTS:
        rains: list[str] = []
        skies: list[str] = []
        pops: list[int] = []
        for time, values in day.items():
            hour = _to_int(time[:2]) if len(time) >= 2 else None
            if hour is None or not start <= hour < end:
                continue
            rain = PTY_NAMES.get(str(values.get("PTY", "0")), "")
            if rain:
                rains.append(rain)
            sky = SKY_NAMES.get(str(values.get("SKY", "")), "")
            if sky:
                skies.append(sky)
            pop = _to_int(values.get("POP"))
            if pop is not None:
                pops.append(pop)

        if not (rains or skies or pops):
            continue
        parts.append(
            DayPart(
                name=name,
                # 소나기가 섞여 있으면 소나기를 대표로 삼는다(대비가 다르다).
                rain=("소나기" if "소나기" in rains else rains[0]) if rains else "",
                sky=max(set(skies), key=skies.count) if skies else "",
                pop=max(pops) if pops else 0,
            )
        )
    return parts


def rain_pattern(parts: list[DayPart]) -> str:
    """강수 패턴을 하나의 키로 요약한다. 멘트 풀을 고르는 데 쓴다."""
    if not parts:
        return ""

    rainy = [p.name for p in parts if p.rain]
    if not rainy:
        return "가능성" if max(p.pop for p in parts) >= MAYBE_POP else ""
    if any(p.rain == "소나기" for p in parts):
        return "소나기"
    if len(rainy) == len(parts):
        return "종일"
    return "+".join(rainy)


def max_pop(parts: list[DayPart]) -> int:
    return max((p.pop for p in parts), default=0)
