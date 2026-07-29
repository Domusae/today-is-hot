"""오늘도 덥습니다 — 폭염 특보 감지 후 Mattermost 카드 발송.

사용:
    python main.py                # 감지 → 신규 이벤트만 발송
    python main.py --dry-run      # 전송하지 않고 페이로드만 출력
    python main.py --force        # 중복 방지 무시 (카드 디자인 확인용)
    python main.py --demo         # API 호출 없이 샘플 카드 미리보기
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import replace

from src import card, detector, kma, notifier, state
from src.config import REGIONS, load_settings
from src.detector import HeatEvent


def collect_events(service_key: str) -> list[HeatEvent]:
    events: list[HeatEvent] = []
    for region in REGIONS:
        forecast = kma.fetch_forecast(service_key, region.nx, region.ny)
        temps = detector.summarize_temps(forecast)

        warnings = kma.fetch_warnings(service_key, region.stn_id, days=6)
        for event in detector.build_events(warnings, region):
            # 특보 카드에도 기온을 같이 실어 보여준다.
            events.append(replace(event, temps=temps))
    return events


def demo_events() -> list[HeatEvent]:
    return [
        HeatEvent(
            kind="폭염경보",
            action="발효 중",
            region="서울 강남구",
            issued_at="07월 29일 10시 00분 발효",
            key="demo:1",
            detail="서울 강남구에 폭염경보가 발효 중입니다.",
            temps={"today_max": 36.0, "today_min": 26.0},
        ),
        HeatEvent(
            kind="폭염주의보",
            action="해제",
            region="서울 강남구",
            issued_at="07월 28일 16시 00분 해제",
            key="demo:2",
            detail="서울 강남구의 폭염주의보가 해제되었습니다.",
            temps={"today_max": 34.0, "today_min": 25.0},
        ),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="오늘도 덥습니다 알림 봇")
    parser.add_argument("--dry-run", action="store_true", help="전송하지 않고 출력만")
    parser.add_argument("--force", action="store_true", help="중복 방지 무시")
    parser.add_argument("--demo", action="store_true", help="API 없이 샘플 카드 미리보기")
    args = parser.parse_args()

    if args.demo:
        payload = card.build_payload(demo_events(), "오늘도 덥습니다", ":sunny:")
        print(notifier.preview(payload))
        return 0

    settings = load_settings(dry_run=args.dry_run)
    events = collect_events(settings.kma_service_key)
    if not events:
        print("발효 중인 폭염 특보가 없습니다.")
        return 0

    sent = state.prune(state.load())
    new_events = events if args.force else state.filter_new(events, sent)
    if not new_events:
        print(f"신규 이벤트 없음 (감지 {len(events)}건, 모두 발송 완료 상태)")
        return 0

    payload = card.build_payload(new_events, settings.bot_username, settings.bot_icon)
    if args.dry_run:
        print(notifier.preview(payload))
        return 0

    notifier.send(settings.webhook_url, payload)
    if not args.force:
        state.save(state.mark(new_events, sent))
    print(f"발송 완료: {len(new_events)}건")
    for event in new_events:
        print(f"  - {event.kind} {event.action} ({event.region})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
