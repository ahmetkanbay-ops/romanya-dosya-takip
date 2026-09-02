# -*- coding: utf-8 -*-
"""
Haftalık PDF senkronizasyon scripti (2026-09-03, kullanıcı isteği).

GEREKÇE: Backblaze'e sadece veritabanı (dosyalar.db) yedekleniyor -- PDF
dosyalarının kendisi (backend/pdfs/) hiçbir yerde ayrıca yedeklenmiyor,
sadece Render'ın kalıcı diskinde duruyor. Bu script, bu riski kapatmak
için Render'daki TÜM bilinen PDF'lerin listesini çeker
(/api/admin/pdf-listesi), yerel backend/pdfs/ klasörüyle karşılaştırır,
SADECE eksik olanları indirir -- zaten var olanlar tekrar indirilmez
(ilk çalıştırmada yerelde zaten 3400+ PDF vardı, sadece o zamandan beri
eklenen fark indirilir).

Çalıştırma (backend/ klasöründen):
    python scripts/pdf_senkronize.py

Haftalık otomatik çalıştırma için Windows Görev Zamanlayıcı kurulumu
proje hafızasında (pdf-senkron-kurulumu.md) belgelenmiştir -- "kaçırılan
görevi bilgisayar açılır açılmaz çalıştır" seçeneği AKTİF olmalı
(bilgisayar o gün kapalıysa görev iptal olmasın diye).

Gereken ortam değişkeni (.env'de): PROD_NOBETCI_ANAHTARI -- canlı
sunucunun NOBETCI_ANAHTARI'si (yereldeki NOBETCI_ANAHTARI'den BİLİNÇLİ
olarak farklı, proje kuralı gereği yerel/canlı sırlar ayrı tutuluyor).
"""
import os
import sys
import time
from datetime import datetime
from urllib.parse import quote

import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # backend/
sys.path.insert(0, BASE_DIR)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))
except ImportError:
    pass

from dosya_utils import klasor_adi_guvenli  # noqa: E402

SUNUCU_ADRESI = "https://romanya-dosya-takip.onrender.com"
NOBETCI_ANAHTARI = os.environ.get("PROD_NOBETCI_ANAHTARI")
PDF_KOK_KLASOR = os.path.join(BASE_DIR, "pdfs")
LOG_DOSYASI = os.path.join(BASE_DIR, "pdf_senkron_log.txt")


def _log(satir):
    print(satir)
    try:
        with open(LOG_DOSYASI, "a", encoding="utf-8") as f:
            f.write(satir + "\n")
    except Exception:
        pass  # log yazılamasa bile senkronizasyonu durdurmaz


def calistir():
    _log(f"\n{'='*60}")
    _log(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] PDF senkronizasyonu başladı")

    if not NOBETCI_ANAHTARI:
        _log("✗ PROD_NOBETCI_ANAHTARI .env'de tanımlı değil, durduruluyor.")
        return

    try:
        _log("Sunucudan PDF listesi çekiliyor...")
        yanit = requests.get(
            f"{SUNUCU_ADRESI}/api/admin/pdf-listesi",
            headers={"X-Nobetci-Anahtar": NOBETCI_ANAHTARI},
            timeout=30,
        )
        yanit.raise_for_status()
        pdfler = yanit.json()["pdfler"]
    except Exception as e:
        _log(f"✗ PDF listesi alınamadı: {str(e)[:150]}")
        return

    _log(f"Sunucuda toplam {len(pdfler)} PDF kayıtlı.")

    indirilen = 0
    atlanan = 0
    hatali = 0
    for kayit in pdfler:
        ana_kategori = kayit.get("ana_kategori")
        alt_kategori = kayit.get("alt_kategori")
        dosya_adi = kayit.get("pdf_dosya")
        if not (ana_kategori and alt_kategori and dosya_adi):
            continue

        alt_klasor = klasor_adi_guvenli(alt_kategori)
        hedef_klasor = os.path.join(PDF_KOK_KLASOR, ana_kategori, alt_klasor)
        hedef_yol = os.path.join(hedef_klasor, dosya_adi)

        if os.path.isfile(hedef_yol):
            atlanan += 1
            continue

        # /pdfs/... zaten herkese açık statik olarak servis ediliyor,
        # ayrı bir indirme ucu gerekmiyor.
        url = f"{SUNUCU_ADRESI}/pdfs/{quote(ana_kategori)}/{quote(alt_klasor)}/{quote(dosya_adi)}"
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == 200:
                os.makedirs(hedef_klasor, exist_ok=True)
                with open(hedef_yol, "wb") as f:
                    f.write(r.content)
                indirilen += 1
                if indirilen % 50 == 0:
                    _log(f"  ... {indirilen} yeni PDF indirildi")
            else:
                _log(f"  ✗ {dosya_adi}: HTTP {r.status_code}")
                hatali += 1
        except Exception as e:
            _log(f"  ✗ {dosya_adi}: {str(e)[:80]}")
            hatali += 1

        time.sleep(0.05)  # sunucuya nazik davran

    _log(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] TAMAMLANDI: "
         f"{indirilen} yeni indirildi, {atlanan} zaten vardı, {hatali} hatalı.")
    _log(f"{'='*60}")


if __name__ == "__main__":
    calistir()
