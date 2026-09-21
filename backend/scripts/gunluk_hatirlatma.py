# -*- coding: utf-8 -*-
"""Gunluk hatirlatma: docs/gunluk-hatirlatma.txt icerigini Telegram'dan gonderir.
Windows Gorev Zamanlayici ile her gun 09:00 (bkz. gorev adi RomanyaDosyaTakip-GunlukHatirlatma)."""
import os
import sys
from datetime import datetime

import requests

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LISTE = os.path.join(os.path.dirname(KOK), "docs", "gunluk-hatirlatma.txt")


def env_oku():
    degerler = {}
    with open(os.path.join(KOK, ".env"), encoding="utf-8") as f:
        for satir in f:
            if "=" in satir and not satir.lstrip().startswith("#"):
                k, v = satir.strip().split("=", 1)
                degerler[k] = v.strip("\"'")
    return degerler


def main():
    env = env_oku()
    token, chat = env.get("TELEGRAM_BOT_TOKEN"), env.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("TELEGRAM ayarlari yok")
        return 1
    with open(LISTE, encoding="utf-8") as f:
        liste = f.read().strip()
    mesaj = f"Gunluk hatirlatma ({datetime.now():%d.%m.%Y})\n\n{liste}"
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat, "text": mesaj[:4000]},
        timeout=20,
    )
    print("Telegram:", r.status_code)
    return 0 if r.status_code == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
