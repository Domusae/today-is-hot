"""특보 통보문의 t6(현재 발효 현황)를 읽어 우리 지역의 특보를 판정한다.

t6는 전국의 현재 발효 현황을 한 덩어리로 준다.

    o 폭염중대경보 : 경상남도(양산, 김해, 밀양, 의령, 창녕)
    o 폭염경보 : 경기도(고양, 남양주, ...), 서울(서울서북권 제외), 인천(인천북부)
    o 폭염주의보 : 경기도(광명, 과천, ...), 서울(서울서북권)
    o 열대야주의보 : ..., 서울, ...

지역 표기는 세 가지 형태다.

    서울                      → 서울 전역
    서울(서울서북권)          → 그 구역만
    서울(서울서북권 제외)     → 그 구역만 빼고 전역

괄호가 중첩되므로(예: `완도(여서도 제외)`) 쉼표 분리는 괄호 깊이를 세면서 해야 한다.
"""
from __future__ import annotations

import re

# "o 폭염경보 : 경기도(...), 서울(...)" 한 줄
STATUS_LINE = re.compile(r"^o\s*([^:]+?)\s*:\s*(.+)$")
EXCLUDE_SUFFIX = "제외"


def split_top_level(text: str) -> list[str]:
    """괄호 안의 쉼표는 무시하고 최상위 쉼표로만 나눈다."""
    parts: list[str] = []
    depth = 0
    buffer: list[str] = []
    for char in text:
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        if char == "," and depth == 0:
            parts.append("".join(buffer).strip())
            buffer = []
        else:
            buffer.append(char)
    if buffer:
        parts.append("".join(buffer).strip())
    return [p for p in parts if p]


def parse_status(t6: str) -> dict[str, str]:
    """t6 전문을 {특보명: 지역 표기} 로 만든다."""
    status: dict[str, str] = {}
    for raw_line in str(t6).replace("\r\n", "\n").split("\n"):
        match = STATUS_LINE.match(raw_line.strip())
        if not match:
            continue
        name, areas = match.group(1).strip(), match.group(2).strip()
        if areas == "없음":
            continue
        status[name] = areas
    return status


def is_included(areas: str, area: str, sub_area: str | None = None) -> bool:
    """지역 표기 안에 우리 지역이 포함되는지 본다."""
    for token in split_top_level(areas):
        if token == area:
            return True
        if not (token.startswith(f"{area}(") and token.endswith(")")):
            continue

        inner = token[len(area) + 1 : -1].strip()
        if sub_area is None:
            # 하위 구역이 없는 지역(대전 등)은 괄호가 붙어도 해당으로 본다.
            return True
        if inner.endswith(EXCLUDE_SUFFIX):
            excluded = split_top_level(inner[: -len(EXCLUDE_SUFFIX)].strip())
            return sub_area not in excluded
        return sub_area in split_top_level(inner)
    return False


def heat_warnings_for(t6: str, area: str, sub_area: str | None = None) -> list[str]:
    """우리 지역에 발효 중인 폭염 계열 특보 이름을 강한 순으로 돌려준다."""
    found = [
        name
        for name, areas in parse_status(t6).items()
        if name.startswith("폭염") and is_included(areas, area, sub_area)
    ]
    return sorted(found, key=severity, reverse=True)


def severity(name: str) -> int:
    """폭염중대경보 > 폭염경보 > 폭염주의보"""
    if "중대경보" in name:
        return 3
    if "경보" in name:
        return 2
    if "주의보" in name:
        return 1
    return 0
