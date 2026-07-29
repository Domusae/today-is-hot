"""오늘 비 예보가 있는지만 본다.

강수는 이 캠페인의 주제가 아니다. **폭염 특보가 발효 중인데 비까지 오는**
경우에만 따로 알려주고, 그 밖에는 언급하지 않는다.

여기서도 새 수치를 만들지 않는다. 기상청이 준 PTY(강수형태)와
POP(강수확률)를 읽어 분류만 한다.
"""
from __future__ import annotations

from dataclasses import dataclass

PTY_NAMES = {"0": "", "1": "비", "2": "비/눈", "3": "눈", "4": "소나기"}


@dataclass(frozen=True)
class RainOutlook:
    """오늘 예보된 강수."""

    kind: str  # 비 / 비/눈 / 눈 / 소나기
    pop: int  # 오늘 최대 강수확률(%)


def _to_int(value: str | None) -> int | None:
    try:
        return int(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def rain_outlook(day: dict[str, dict[str, str]]) -> RainOutlook | None:
    """오늘 강수 예보. 없으면 None."""
    kinds: list[str] = []
    pops: list[int] = []
    for values in day.values():
        kind = PTY_NAMES.get(str(values.get("PTY", "0")), "")
        if kind:
            kinds.append(kind)
        pop = _to_int(values.get("POP"))
        if pop is not None:
            pops.append(pop)

    if not kinds:
        return None
    # 소나기는 대비가 다르므로 섞여 있으면 대표로 올린다.
    kind = "소나기" if "소나기" in kinds else kinds[0]
    return RainOutlook(kind=kind, pop=max(pops) if pops else 0)
