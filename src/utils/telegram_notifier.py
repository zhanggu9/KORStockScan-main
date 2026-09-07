# src/utils/telegram_notifier.py
"""AI 판단 결과를 텔레그램으로 비동기 전송하는 유틸리티"""

import os
import threading
import requests

from src.utils.logger import log_error

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def _send_sync(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
            },
            timeout=5,
        )
    except Exception as e:
        log_error(f"🚨 [텔레그램 전송 실패] {e}")


def send_telegram_message(text: str):
    """호출 즉시 리턴 — 백그라운드 스레드에서 전송하므로 매매 루프를 막지 않음"""
    threading.Thread(target=_send_sync, args=(text,), daemon=True).start()