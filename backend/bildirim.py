# -*- coding: utf-8 -*-
"""
Bildirim gönderme yardımcıları:
  - Kullanıcılara: Expo Push Notification
  - Admin'e (sana): Telegram + E-posta (kritik uyarılar için ikisi birden)

Gerekli ortam değişkenleri (.env dosyasında ya da Render "Environment"
panelinde tanımlanır):
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
  SMTP_HOST, SMTP_PORT, SMTP_KULLANICI, SMTP_SIFRE, ADMIN_EPOSTA

Bunlardan biri ayarlanmamışsa ilgili gönderim SESSİZCE atlanır (hata
fırlatmaz) -- yani bu bilgileri henüz girmeden de sistemin geri kalanı
sorunsuz çalışmaya devam eder, sadece o bildirim kanalı devre dışı olur.
"""
import os
import smtplib
from email.mime.text import MIMEText

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv kurulu değilse (henüz `pip install -r requirements.txt`
    # çalıştırılmadıysa) sessizce devam et -- ortam değişkenleri yine de
    # sistem üzerinden (Render Environment paneli gibi) okunabilir.
    pass

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_KULLANICI = os.environ.get("SMTP_KULLANICI")
SMTP_SIFRE = os.environ.get("SMTP_SIFRE")
ADMIN_EPOSTA = os.environ.get("ADMIN_EPOSTA")

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


def expo_push_gonder(tokenlar, baslik, govde, veri=None):
    """
    tokenlar: 'ExponentPushToken[...]' formatında token listesi.
    Expo API tek istekte en fazla 100 mesaj kabul eder, otomatik olarak
    100'erli parçalara bölünür.
    """
    tokenlar = [t for t in (tokenlar or []) if t]
    if not tokenlar:
        return

    for i in range(0, len(tokenlar), 100):
        parca = tokenlar[i:i + 100]
        mesajlar = [
            {"to": token, "title": baslik, "body": govde, "data": veri or {}}
            for token in parca
        ]
        try:
            requests.post(
                EXPO_PUSH_URL,
                json=mesajlar,
                timeout=15,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
        except Exception as e:
            print(f"✗ Expo push gönderim hatası: {str(e)[:80]}")


def telegram_gonder(mesaj):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": mesaj}, timeout=15)
    except Exception as e:
        print(f"✗ Telegram gönderim hatası: {str(e)[:80]}")


def eposta_gonder(konu, govde):
    if not (SMTP_HOST and SMTP_KULLANICI and SMTP_SIFRE and ADMIN_EPOSTA):
        return
    try:
        msg = MIMEText(govde, "plain", "utf-8")
        msg["Subject"] = konu
        msg["From"] = SMTP_KULLANICI
        msg["To"] = ADMIN_EPOSTA
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as sunucu:
            sunucu.starttls()
            sunucu.login(SMTP_KULLANICI, SMTP_SIFRE)
            sunucu.send_message(msg)
    except Exception as e:
        print(f"✗ E-posta gönderim hatası: {str(e)[:80]}")


def admin_kritik_uyari(mesaj):
    """
    Admin'e (sana) hem Telegram hem e-posta ile kritik uyarı gönderir
    (kullanıcının tercihi: iki kanal birden).
    """
    telegram_gonder(f"🚨 {mesaj}")
    eposta_gonder("🚨 Romanya Dosya Takip - Kritik Uyarı", mesaj)
