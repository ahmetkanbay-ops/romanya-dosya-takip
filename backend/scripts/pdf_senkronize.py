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
import re
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


def _guncel_yil_dosyasi_mi(ana_kategori, dosya_adi):
    """2026-09-06 KÖK NEDEN DÜZELTMESİ (kullanıcı canlı testte YİNE
    yakaladı -- bu sefer bot.py'de DEĞİL, bu scriptte): bot.py'deki AYNI
    isimli fonksiyonun (2026-08-31) burada hiç karşılığı yoktu. Site,
    içinde bulunulan yıla ait bazı STADIU PDF'lerini AYNI dosya adında
    YERİNDE güncelliyor (dosya büyüyor, adı değişmiyor) -- bu script
    "zaten var, atla" dediği için (satır ~97), yerel kopya production'da
    çoktan düzeltilmiş/büyümüş olsa bile SONSUZA KADAR eski/eksik
    kalıyordu. Kanıt: "Art-10-2026-update-07.08.2026.pdf" yerelde 102'den
    başlıyordu (production'da 3'ten başlıyor) -- tam olarak bot.py'deki
    31 Ağustos notundaki senaryonun kendisi, sadece bu script o düzeltmeyi
    hiç almamıştı. ORDINE dosyaları (tek seferlik kararname, adında yayın
    tarihi var, yıl kategorisi değil) bu kapsamda DEĞİL -- onlar için
    eskisi gibi "zaten var, atla" davranışı korunuyor."""
    if ana_kategori != "stadiu":
        return False
    # 2026-09-06 EK DÜZELTMESİ: bot.py'deki aynı isimli notla birebir aynı
    # sebep -- "Art-11-2018-update-07.08.2026.pdf" gibi adlarda BİRDEN
    # FAZLA "20XX" deseni var, İLK eşleşme ("2018") yerine TÜMÜ kontrol
    # edilmeli.
    yillar = re.findall(r"\b(20\d{2})\b", dosya_adi)
    if not yillar:
        return False
    return str(datetime.now().year) in yillar
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


def _bildir_basarisiz(neden):
    """Senkronizasyon HİÇ BAŞLAYAMADAN durduğunda da (ör. anahtar eksik,
    sunucuya ulaşılamıyor) admin'e haber verir -- 'çözemese de bildirmeli'
    ilkesi (bkz. calistir() sonundaki bildirim notu)."""
    try:
        from bildirim import admin_kritik_uyari
        admin_kritik_uyari(f"📦 Haftalık PDF senkronu BAŞLAYAMADI: {neden}")
    except Exception as e:
        _log(f"✗ Bildirim gönderilemedi (senkronu etkilemez): {str(e)[:100]}")


def calistir():
    _log(f"\n{'='*60}")
    _log(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] PDF senkronizasyonu başladı")

    if not NOBETCI_ANAHTARI:
        _log("✗ PROD_NOBETCI_ANAHTARI .env'de tanımlı değil, durduruluyor.")
        _bildir_basarisiz("PROD_NOBETCI_ANAHTARI .env'de tanımlı değil.")
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
        _bildir_basarisiz(f"PDF listesi alınamadı: {str(e)[:150]}")
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

        if os.path.isfile(hedef_yol) and not _guncel_yil_dosyasi_mi(ana_kategori, dosya_adi):
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

    # 2026-09-06 EKLENTİSİ (kullanıcı isteği -- "sistem sadece bulduğumuz
    # hataya değil, kendi sağlığına odaklanmalı, bize haber vermeli"):
    # önceden bu özet SADECE yerel bir log dosyasına yazılıyordu, kimse
    # okumuyordu. Artık Gece Nöbeti'yle AYNI kanaldan (Telegram+e-posta)
    # size de gidiyor -- haftalık senkronun sessizce mi geçtiğini, yoksa
    # hata mı verdiğini görmek için log dosyası aramanıza gerek kalmıyor.
    try:
        from bildirim import admin_kritik_uyari
        if hatali > 0:
            admin_kritik_uyari(
                f"📦 Haftalık PDF senkronu TAMAMLANDI ama {hatali} dosya "
                f"indirilemedi ({indirilen} yeni indirildi, {atlanan} zaten "
                f"vardı) -- log dosyasını (pdf_senkron_log.txt) kontrol et."
            )
        else:
            admin_kritik_uyari(
                f"📦 Haftalık PDF senkronu tamamlandı: {indirilen} yeni PDF "
                f"indirildi, {atlanan} zaten günceldi, hata yok."
            )
    except Exception as e:
        _log(f"✗ Bildirim gönderilemedi (senkronu etkilemez): {str(e)[:100]}")


if __name__ == "__main__":
    calistir()
