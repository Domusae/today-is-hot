"""기상청 공공데이터 API 클라이언트.

- 기상특보 조회서비스 (WthrWrnInfoService)  : 폭염주의보/경보 발표·해제 감지
- 단기예보 조회서비스 (VilageFcstInfoService_2.0) : 최고/최저기온 → 열대야 판정
"""
from __future__ import annotations

from datetime import datetime, timedelta

import requests

from .config import KMA_BASE

TIMEOUT = 15
# 단기예보 발표시각(정시). 발표 후 API 반영까지 시간이 걸려 45분 여유를 둔다.
FCST_BASE_HOURS = (23, 20, 17, 14, 11, 8, 5, 2)
FCST_PUBLISH_DELAY = timedelta(minutes=45)


class KmaError(RuntimeError):
    pass


def _get(path: str, service_key: str, **params) -> dict:
    res = requests.get(
        f"{KMA_BASE}/{path}",
        params={"serviceKey": service_key, "dataType": "JSON", "pageNo": 1, **params},
        timeout=TIMEOUT,
    )
    res.raise_for_status()
    try:
        body = res.json()
    except ValueError as exc:
        # 인증키 오류·트래픽 초과 시 기상청은 JSON 대신 XML 에러를 반환한다.
        raise KmaError(f"JSON 응답이 아닙니다. 인증키를 확인하세요.\n{res.text[:300]}") from exc

    header = body.get("response", {}).get("header", {})
    code = header.get("resultCode")
    if code not in ("00", "0"):
        raise KmaError(f"기상청 API 오류 {code}: {header.get('resultMsg')}")
    return body["response"]["body"]


def _items(body: dict) -> list[dict]:
    items = body.get("items")
    if not items:  # 조회 결과 0건이면 items가 빈 문자열로 오는 경우가 있다.
        return []
    item = items.get("item", [])
    return item if isinstance(item, list) else [item]


def fetch_warnings(service_key: str, stn_id: str, days: int = 2) -> list[dict]:
    """최근 며칠간 발표된 기상특보 목록을 조회한다."""
    today = datetime.now()
    body = _get(
        "WthrWrnInfoService/getWthrWrnList",
        service_key,
        numOfRows=100,
        stnId=stn_id,
        fromTmFc=(today - timedelta(days=days)).strftime("%Y%m%d"),
        toTmFc=today.strftime("%Y%m%d"),
    )
    return _items(body)


def base_datetime(now: datetime | None = None) -> tuple[str, str]:
    """현재 시각 기준으로 사용할 단기예보 발표일자/발표시각을 고른다."""
    now = (now or datetime.now()) - FCST_PUBLISH_DELAY
    for hour in FCST_BASE_HOURS:
        if now.hour >= hour:
            return now.strftime("%Y%m%d"), f"{hour:02d}00"
    prev = now - timedelta(days=1)
    return prev.strftime("%Y%m%d"), "2300"


def fetch_forecast(service_key: str, nx: int, ny: int) -> list[dict]:
    """단기예보(3일치)를 조회한다."""
    base_date, base_time = base_datetime()
    body = _get(
        "VilageFcstInfoService_2.0/getVilageFcst",
        service_key,
        numOfRows=1000,
        base_date=base_date,
        base_time=base_time,
        nx=nx,
        ny=ny,
    )
    return _items(body)
