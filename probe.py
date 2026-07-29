"""기상청 API 원본 응답을 그대로 덤프한다.

공공데이터포털의 기상특보 API 문서가 개편되면서 응답 필드명이 바뀔 수 있다.
detector.py는 제목 문자열 매칭으로 동작하도록 만들어 두었지만,
실제 응답을 눈으로 확인하고 싶을 때 이 스크립트를 쓴다.

    python probe.py warn        # 기상특보 목록 원본
    python probe.py forecast    # 단기예보 원본(일부)
"""
from __future__ import annotations

import json
import sys

from src import kma
from src.config import REGIONS, load_settings


def main() -> int:
    what = sys.argv[1] if len(sys.argv) > 1 else "warn"
    settings = load_settings(dry_run=True)
    region = REGIONS[0]

    if what == "warn":
        items = kma.fetch_warnings(settings.kma_service_key, region.stn_id, days=7)
        print(f"# 기상특보 {len(items)}건 (stnId={region.stn_id}, 최근 7일)")
    elif what == "forecast":
        items = kma.fetch_forecast(settings.kma_service_key, region.nx, region.ny)[:40]
        print(f"# 단기예보 상위 40건 (nx={region.nx}, ny={region.ny})")
    else:
        print(__doc__)
        return 1

    print(json.dumps(items, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
