"""Mattermost Incoming Webhook 전송."""
from __future__ import annotations

import json

import requests

TIMEOUT = 10


def send(webhook_url: str, payload: dict) -> None:
    res = requests.post(webhook_url, json=payload, timeout=TIMEOUT)
    if res.status_code >= 400:
        raise RuntimeError(f"Mattermost 전송 실패 {res.status_code}: {res.text[:300]}")


def preview(payload: dict) -> str:
    """--dry-run 용. 실제로 보내지 않고 페이로드를 보여준다."""
    return json.dumps(payload, ensure_ascii=False, indent=2)
