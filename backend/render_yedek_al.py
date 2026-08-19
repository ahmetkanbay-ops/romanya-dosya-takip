# -*- coding: utf-8 -*-
"""
Render'daki canlı veritabanı ve PDF'lerin bilgisayara PERİYODİK yedeğini alır.

AMAÇ (2026-08-19, kullanıcı isteği): Render'a hiç ulaşılamaz duruma gelirse
(sunucu çöker, hesap sorunu vb.) bilgisayarda GÜNCEL, Render'dan tamamen
BAĞIMSIZ bir kopya bulunsun. Render'ın kendi 03:00 yedeği KENDİ diskinde
durduğu için "Render'a hiç ulaşılamıyor" senaryosuna karşı koruma sağlamaz --
bu script tam olarak o boşluğu dolduruyor.

Nereye kaydedilir: backend/render_yedekleri/ (bu bilgisayarın kendi diski --
Render'ın Frankfurt'taki sunucusundan fiziksel olarak tamamen ayrı bir yer,
ayrıca bir bulut hesabına göndermeye GEREK YOK).

Ne yapılır:
  1) Veritabanı: Render'da SQLite'ın kendi "online backup" API'siyle
     (WAL-güvenli) taze bir kopya alınır, gzip ile sıkıştırılır, indirilir.
     Sadece son YEDEK_SAKLAMA_HAFTA kadarı saklanır, eskiler silinir.
  2) PDF'ler: Render'daki TÜM PDF dosyalarının listesi (yol+boyut) çekilir,
     yerelde ZATEN VAR olanlar atlanır -- sadece YENİ eklenen PDF'ler
     indirilir (haftada haftada aynı 750MB+'ı tekrar tekrar çekmemek için).

Çalıştırma: `python render_yedek_al.py` (yerelde, bu bilgisayarda).
SSH anahtarı: ~/.ssh/render_romanya (Render hesabına daha önce eklendi).
"""
import gzip
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YEDEK_KOK = os.path.join(BASE_DIR, "render_yedekleri")
DB_YEDEK_KLASOR = os.path.join(YEDEK_KOK, "veritabani")
PDF_YEDEK_KLASOR = os.path.join(YEDEK_KOK, "pdfs")
LOG_DOSYASI = os.path.join(YEDEK_KOK, "yedek_gecmisi.log")

YEDEK_SAKLAMA_HAFTA = 8  # DB yedeklerinden bundan eskisi otomatik silinir

SSH_ANAHTAR = os.path.expanduser("~/.ssh/render_romanya")
SSH_HEDEF = "srv-d9r91j2fngtc73crlk5g@ssh.frankfurt.render.com"
UZAK_PYTHON = "/opt/render/project/src/.venv/bin/python3"


def _log(mesaj):
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    satir = f"[{zaman}] {mesaj}"
    try:
        print(satir)
    except UnicodeEncodeError:
        print(satir.encode("ascii", "replace").decode("ascii"))
    os.makedirs(YEDEK_KOK, exist_ok=True)
    with open(LOG_DOSYASI, "a", encoding="utf-8") as f:
        f.write(satir + "\n")


def _ssh_calistir(komut, timeout=600):
    tam_komut = [
        "ssh", "-i", SSH_ANAHTAR,
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "ConnectTimeout=20",
        SSH_HEDEF, komut,
    ]
    sonuc = subprocess.run(
        tam_komut, capture_output=True, timeout=timeout,
        encoding="utf-8", errors="replace",
    )
    return sonuc.stdout, sonuc.stderr, sonuc.returncode


def veritabani_yedekle():
    _log("Veritabani yedegi baslıyor...")
    os.makedirs(DB_YEDEK_KLASOR, exist_ok=True)

    uzak_gecici = "/tmp/render_yedek_gecici.db.gz"
    komut = (
        f"{UZAK_PYTHON} -c \""
        "import sqlite3, gzip, shutil; "
        "k=sqlite3.connect('/data/dosyalar.db'); "
        "h=sqlite3.connect('/tmp/render_yedek_gecici.db'); "
        "h.__enter__(); k.backup(h); h.__exit__(None,None,None); h.close(); k.close(); "
        "f_in=open('/tmp/render_yedek_gecici.db','rb'); "
        "f_out=gzip.open('/tmp/render_yedek_gecici.db.gz','wb'); "
        "shutil.copyfileobj(f_in, f_out); f_in.close(); f_out.close()\""
    )
    out, err, kod = _ssh_calistir(komut, timeout=300)
    if kod != 0:
        _log(f"HATA: uzak DB yedegi alinamadi -- {err[:300]}")
        return False

    yerel_gz = os.path.join(DB_YEDEK_KLASOR, "_gecici_indirilen.db.gz")
    scp_komut = [
        "scp", "-i", SSH_ANAHTAR, "-o", "StrictHostKeyChecking=accept-new",
        f"{SSH_HEDEF}:{uzak_gecici}", yerel_gz,
    ]
    sonuc = subprocess.run(
        scp_komut, capture_output=True, timeout=300,
        encoding="utf-8", errors="replace",
    )
    if sonuc.returncode != 0:
        _log(f"HATA: DB indirilemedi -- {sonuc.stderr[:300]}")
        return False

    zaman_damgasi = datetime.now().strftime("%Y-%m-%d_%H-%M")
    hedef_yol = os.path.join(DB_YEDEK_KLASOR, f"dosyalar_{zaman_damgasi}.db")
    with gzip.open(yerel_gz, "rb") as f_in, open(hedef_yol, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    os.remove(yerel_gz)
    _ssh_calistir(f"rm -f {uzak_gecici}")

    boyut_mb = os.path.getsize(hedef_yol) / (1024 * 1024)
    _log(f"Veritabani yedegi tamamlandi: {hedef_yol} ({boyut_mb:.1f} MB)")

    sinir = time.time() - (YEDEK_SAKLAMA_HAFTA * 7 * 24 * 60 * 60)
    silinen = 0
    for ad in os.listdir(DB_YEDEK_KLASOR):
        tam = os.path.join(DB_YEDEK_KLASOR, ad)
        if ad.startswith("dosyalar_") and ad.endswith(".db") and os.path.getmtime(tam) < sinir:
            os.remove(tam)
            silinen += 1
    if silinen:
        _log(f"  ({silinen} eski DB yedegi silindi, {YEDEK_SAKLAMA_HAFTA} haftadan eski)")

    return True


def pdf_farkini_senkronla():
    """
    2026-08-19 DÜZELTMESİ: ilk sürüm her eksik PDF için AYRI bir SSH
    bağlantısı açıyordu -- 3428 dosyada bu, bağlantı başlangıç yükünden
    (~1-2sn) dolayı saatler sürerdi. Artık TÜM eksik dosyalar TEK bir SSH
    akışında (uzakta tar ile paketlenip gzip'lenerek) indiriliyor -- ilk
    çalıştırmada (tüm dosyalar eksik) bile birkaç dakika sürer, sonraki
    haftalık çalıştırmalarda zaten çok az yeni dosya olacağı için saniyeler
    sürer.
    """
    import io
    import tarfile

    _log("PDF senkronizasyonu basliyor (sadece yeni dosyalar)...")
    out, err, kod = _ssh_calistir(
        "cd /data/pdfs && find . -name '*.pdf' -printf '%P\\n'", timeout=60
    )
    if kod != 0:
        _log(f"HATA: uzak PDF listesi alinamadi -- {err[:300]}")
        return 0

    uzak_dosyalar = [s.strip() for s in out.splitlines() if s.strip()]
    _log(f"  Render'da toplam {len(uzak_dosyalar)} PDF var.")

    eksikler = []
    for goreli_yol in uzak_dosyalar:
        yerel_yol = os.path.join(PDF_YEDEK_KLASOR, goreli_yol)
        if not os.path.exists(yerel_yol):
            eksikler.append(goreli_yol)

    if not eksikler:
        _log("  Yeni PDF yok, senkron zaten guncel.")
        return 0

    _log(f"  {len(eksikler)} yeni PDF tek akista indirilecek...")

    # Eksik dosya listesini uzak sunucuya STDIN üzerinden gönderip orada bir
    # liste dosyasına yaz -- komut argümanına gömmek Windows'ta ~32KB komut
    # satırı sınırını aşabilir (3428 dosya adında kolayca aşılır), stdin'in
    # böyle bir sınırı yok.
    liste_metni = "\n".join(eksikler)
    yaz_komut = [
        "ssh", "-i", SSH_ANAHTAR, "-o", "StrictHostKeyChecking=accept-new",
        "-o", "ConnectTimeout=20", SSH_HEDEF,
        "cat > /tmp/eksik_pdf_listesi.txt",
    ]
    sonuc = subprocess.run(
        yaz_komut, input=liste_metni.encode("utf-8"),
        capture_output=True, timeout=60,
    )
    if sonuc.returncode != 0:
        _log(f"HATA: eksik liste uzak sunucuya yazilamadi -- {sonuc.stderr.decode('utf-8','replace')[:300]}")
        return 0

    # Tek bir tar.gz akışı olarak indir (stdout binary, text mode YOK).
    tam_komut = [
        "ssh", "-i", SSH_ANAHTAR, "-o", "StrictHostKeyChecking=accept-new",
        "-o", "ConnectTimeout=20", SSH_HEDEF,
        "cd /data/pdfs && tar -czf - -T /tmp/eksik_pdf_listesi.txt 2>/tmp/tar_hata.log",
    ]
    sonuc = subprocess.run(tam_komut, capture_output=True, timeout=1800)
    if sonuc.returncode != 0 or not sonuc.stdout:
        hata = sonuc.stderr.decode("utf-8", "replace")[:300]
        _log(f"HATA: tar akisi basarisiz -- {hata}")
        return 0

    os.makedirs(PDF_YEDEK_KLASOR, exist_ok=True)
    try:
        with tarfile.open(fileobj=io.BytesIO(sonuc.stdout), mode="r:gz") as tar:
            tar.extractall(PDF_YEDEK_KLASOR, filter="data")
            uye_sayisi = len(tar.getmembers())
    except Exception as e:
        _log(f"HATA: tar acilamadi -- {e}")
        return 0

    _ssh_calistir("rm -f /tmp/eksik_pdf_listesi.txt /tmp/tar_hata.log")
    _log(f"  Tamamlandi: {uye_sayisi} yeni PDF indirildi.")
    return uye_sayisi


def main():
    baslangic = time.time()
    _log("=" * 60)
    _log("RENDER YEDEKLEME BASLADI")
    db_basarili = veritabani_yedekle()
    yeni_pdf_sayisi = pdf_farkini_senkronla()
    sure = time.time() - baslangic
    _log(f"RENDER YEDEKLEME TAMAMLANDI ({sure:.0f} saniye)")
    _log("=" * 60)
    return db_basarili, yeni_pdf_sayisi, sure


if __name__ == "__main__":
    main()
