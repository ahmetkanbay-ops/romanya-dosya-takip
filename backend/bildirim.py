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

from dosya_utils import veritabani_baglantisi, sistem_olayi_kaydet

EXPO_RECEIPTS_URL = "https://exp.host/--/api/v2/push/getReceipts"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 2026-08-19 (Render'a taşıma): bkz. main.py'deki aynı isimli sabitin notu.
VERI_DIZINI = os.environ.get("DATA_DIR", BASE_DIR)
DB_FILE = os.path.join(VERI_DIZINI, "dosyalar.db")


def _olay_kaydet_sessizce(olay_tipi, detay=None):
    """2026-08-19 (admin istatistik paneli): olay kaydı için kısa ömürlü
    bir bağlantı açar. Herhangi bir hata bildirim gönderimini ASLA
    engellememeli, bu yüzden burada da her şey sessizce yutuluyor."""
    try:
        conn = veritabani_baglantisi(DB_FILE)
        sistem_olayi_kaydet(conn, olay_tipi, detay)
        conn.close()
    except Exception as e:
        print(f"✗ Olay kaydı başarısız ({olay_tipi}): {str(e)[:80]}")

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

# app.json'daki owner+slug -- Expo'nun her push isteginde TUM token'larin
# AYNI projeye ait olmasini zorunlu kilmasi yuzunden (bkz. asagidaki
# PUSH_TOO_MANY_EXPERIENCE_IDS notu) gerekli.
EXPO_PROJE_KIMLIGI = "@kanbays-team/romanya-dosya-takip"


def _yanlis_proje_tokenlarini_sil(tokenlar):
    """2026-09-28 EKLENTISI -- bkz. expo_push_gonder'daki
    PUSH_TOO_MANY_EXPERIENCE_IDS notu. Baska bir Expo projesine ait,
    bu uygulamada ASLA calismayacak token'lari kalici siler."""
    if not tokenlar:
        return
    try:
        conn = veritabani_baglantisi(DB_FILE)
        conn.executemany(
            "DELETE FROM push_tokenlari WHERE expo_push_token = ?",
            [(t,) for t in tokenlar],
        )
        conn.commit()
        conn.close()
        print(f"✓ {len(tokenlar)} yanlis-proje token temizlendi.")
    except Exception as e:
        print(f"✗ Yanlis-proje token temizligi basarisiz: {str(e)[:80]}")


def _olu_tokenlari_sil(tokenlar):
    """2026-09-02 EKLENTİSİ (kullanıcı fark etti -- admin panelindeki
    "Toplam cihaz" sayısı uygulamayı silen kullanıcılarla da ŞİŞİYORDU,
    çünkü buraya kadar HİÇBİR temizlik yoktu): Expo'nun "DeviceNotRegistered"
    dediği (uygulama kaldırılmış/token artık geçersiz) token'ları
    push_tokenlari tablosundan kalıcı olarak siler."""
    if not tokenlar:
        return
    try:
        conn = veritabani_baglantisi(DB_FILE)
        conn.executemany(
            "DELETE FROM push_tokenlari WHERE expo_push_token = ?",
            [(t,) for t in tokenlar],
        )
        conn.commit()
        conn.close()
        print(f"✓ {len(tokenlar)} geçersiz (DeviceNotRegistered) token temizlendi.")
    except Exception as e:
        print(f"✗ Ölü token temizliği başarısız: {str(e)[:80]}")


def _expo_parca_gonder(parca, baslik, govde, veri):
    """Tek bir parça (<=100 token) icin Expo'ya istek atar, (ticket_map,
    olu_tokenlar, yanlis_proje_tokenlar, tekrar_denenecek_parca) dondurur.
    ticket_map: {ticket_id: token} -- basarili kuyruga alinanlar (henuz
    telefona ULASTIGI anlamina gelmez, bkz. receiptleri_kontrol_et).
    tekrar_denenecek_parca dolu ise cagiran taraf onu (yanlis-proje token'lari
    cikarilmis halde) tekrar bu fonksiyona vermeli."""
    mesajlar = [
        {"to": token, "title": baslik, "body": govde, "data": veri or {}}
        for token in parca
    ]
    try:
        yanit = requests.post(
            EXPO_PUSH_URL,
            json=mesajlar,
            timeout=15,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
    except Exception as e:
        print(f"✗ Expo push gonderim hatasi (ag): {str(e)[:80]}")
        return {}, [], [], []

    try:
        govde_json = yanit.json()
    except Exception:
        print(f"✗ Expo push yaniti JSON degil (HTTP {yanit.status_code}): {yanit.text[:200]}")
        return {}, [], [], []

    # 2026-09-28 DUZELTMESI: eskiden yanit gövdesi hic dogrulanmadan
    # "basarili" sayiliyordu -- Expo bir istegin TUMUNU HTTP 400 ile
    # reddedebiliyor (ornegin "PUSH_TOO_MANY_EXPERIENCE_IDS": ayni
    # istekte birden fazla Expo projesine ait token varsa). Bu durumda
    # eskiden hicbir sey fark edilmiyor, push_gonderildi olayi yine de
    # kaydediliyordu -- gercekte Expo hicbir mesaji kuyruga almiyordu.
    hatalar = govde_json.get("errors") if isinstance(govde_json, dict) else None
    if hatalar:
        for hata in hatalar:
            if hata.get("code") == "PUSH_TOO_MANY_EXPERIENCE_IDS":
                detay = hata.get("details", {}) or {}
                yanlis_proje = []
                for proje_kimligi, proje_tokenlari in detay.items():
                    if proje_kimligi != EXPO_PROJE_KIMLIGI:
                        yanlis_proje.extend(proje_tokenlari)
                if yanlis_proje:
                    print(
                        f"✗ {len(yanlis_proje)} token yanlis Expo projesine ait "
                        f"(beklenen: {EXPO_PROJE_KIMLIGI}), ayiklaniyor."
                    )
                    kalan = [t for t in parca if t not in yanlis_proje]
                    return {}, [], yanlis_proje, kalan
            print(f"✗ Expo push toplu hata: {hata.get('code')} -- {str(hata.get('message'))[:150]}")
        return {}, [], [], []

    sonuclar = govde_json.get("data", []) if isinstance(govde_json, dict) else []
    if isinstance(sonuclar, dict):
        sonuclar = [sonuclar]
    if len(sonuclar) != len(parca):
        print(f"✗ Expo push yaniti beklenmeyen formatta (HTTP {yanit.status_code}): {yanit.text[:200]}")
        return {}, [], [], []

    ticket_map = {}
    olu_tokenlar = []
    for token, sonuc in zip(parca, sonuclar):
        if not isinstance(sonuc, dict):
            continue
        if sonuc.get("status") == "ok" and sonuc.get("id"):
            ticket_map[sonuc["id"]] = token
        elif sonuc.get("details", {}).get("error") == "DeviceNotRegistered":
            olu_tokenlar.append(token)
        else:
            print(f"✗ Expo push token hatasi: {sonuc.get('message')}")
    return ticket_map, olu_tokenlar, [], []


def _ticketleri_kaydet(ticket_map):
    """Basariyla kuyruga alinan ticket'lari bekleyen_push_receiptleri'ne
    yazar -- receiptleri_kontrol_et() birkac dakika sonra bunlari
    sorgulayip GERCEKTEN telefona ulasmayanlari (DeviceNotRegistered)
    temizleyecek."""
    if not ticket_map:
        return
    try:
        conn = veritabani_baglantisi(DB_FILE)
        conn.executemany(
            "INSERT OR IGNORE INTO bekleyen_push_receiptleri (ticket_id, expo_push_token) VALUES (?, ?)",
            [(tid, token) for tid, token in ticket_map.items()],
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"✗ Ticket kaydi basarisiz: {str(e)[:80]}")


def expo_push_gonder(tokenlar, baslik, govde, veri=None):
    """
    tokenlar: 'ExponentPushToken[...]' formatında token listesi.
    Expo API tek istekte en fazla 100 mesaj kabul eder, otomatik olarak
    100'erli parçalara bölünür.
    """
    tokenlar = [t for t in (tokenlar or []) if t]
    if not tokenlar:
        return

    basarili_sayisi = 0
    olu_tokenlar = []
    yanlis_proje_tokenlar = []
    tum_ticketler = {}
    for i in range(0, len(tokenlar), 100):
        parca = tokenlar[i:i + 100]
        ticketler, olu, yanlis_proje, kalan = _expo_parca_gonder(parca, baslik, govde, veri)
        basarili_sayisi += len(ticketler)
        tum_ticketler.update(ticketler)
        olu_tokenlar.extend(olu)
        yanlis_proje_tokenlar.extend(yanlis_proje)
        if kalan:
            # Yanlis-proje token'lari ayiklandi, geri kalanlarla bir kez
            # daha dene (artik tek proje kaldigi icin basarili olmali).
            ticketler2, olu2, _, _ = _expo_parca_gonder(kalan, baslik, govde, veri)
            basarili_sayisi += len(ticketler2)
            tum_ticketler.update(ticketler2)
            olu_tokenlar.extend(olu2)

    if basarili_sayisi:
        _olay_kaydet_sessizce(
            "push_gonderildi", f"{basarili_sayisi} cihaza gönderildi: \"{baslik}\""
        )
    if tum_ticketler:
        _ticketleri_kaydet(tum_ticketler)
    if olu_tokenlar:
        _olu_tokenlari_sil(olu_tokenlar)
    if yanlis_proje_tokenlar:
        _yanlis_proje_tokenlarini_sil(yanlis_proje_tokenlar)


def receiptleri_kontrol_et():
    """2026-09-28 EKLENTISI: expo_push_gonder'in kuyruga aldigi ("ticket")
    ama telefona GERCEKTEN ulasip ulasmadigi henuz bilinmeyen gonderimleri
    kontrol eder. En az 2 dakika bekletilmis kayitlari Expo'nun receipt
    API'sinden sorgular:
      - "DeviceNotRegistered" -> uygulamayi silmis kullanicinin token'i,
        push_tokenlari'ndan kalici silinir (admin panelindeki "Toplam
        cihaz" sayisi boylece GERCEK aktif kullanici sayisini yansitir).
      - 24 saatten eski, hala cevapsiz kayitlar -- Expo bir daha
        cevap vermeyecek kabul edilip birikmesin diye silinir.
    main.py'deki zamanlayicidan periyodik cagrilir."""
    conn = veritabani_baglantisi(DB_FILE)
    try:
        c = conn.cursor()
        c.execute(
            """
            SELECT ticket_id, expo_push_token FROM bekleyen_push_receiptleri
            WHERE gonderim_zamani <= datetime('now', '-2 minutes')
            LIMIT 900
            """
        )
        bekleyenler = c.fetchall()
        c.execute(
            "DELETE FROM bekleyen_push_receiptleri WHERE gonderim_zamani <= datetime('now', '-1 day')"
        )
        conn.commit()
    finally:
        conn.close()

    if not bekleyenler:
        return

    ticket_to_token = {tid: token for tid, token in bekleyenler}
    olu_tokenlar = []
    islenen_ticketler = []
    ticket_id_listesi = list(ticket_to_token.keys())
    for i in range(0, len(ticket_id_listesi), 300):
        parca_id = ticket_id_listesi[i:i + 300]
        try:
            yanit = requests.post(
                EXPO_RECEIPTS_URL,
                json={"ids": parca_id},
                timeout=15,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
            receiptler = yanit.json().get("data", {})
        except Exception as e:
            print(f"✗ Expo receipt sorgusu basarisiz: {str(e)[:80]}")
            continue
        for rid in parca_id:
            r = receiptler.get(rid)
            if r is None:
                continue  # Expo henuz islemedi, bir sonraki turda tekrar denenir
            islenen_ticketler.append(rid)
            if isinstance(r, dict) and r.get("details", {}).get("error") == "DeviceNotRegistered":
                olu_tokenlar.append(ticket_to_token[rid])

    if islenen_ticketler:
        conn = veritabani_baglantisi(DB_FILE)
        try:
            conn.executemany(
                "DELETE FROM bekleyen_push_receiptleri WHERE ticket_id = ?",
                [(tid,) for tid in islenen_ticketler],
            )
            conn.commit()
        finally:
            conn.close()
    if olu_tokenlar:
        _olu_tokenlari_sil(olu_tokenlar)


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
    _olay_kaydet_sessizce("kritik_uyari", mesaj)
