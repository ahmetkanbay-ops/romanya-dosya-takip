# -*- coding: utf-8 -*-
"""
/admin istatistik paneli -- SADECE proje sahibinin kullanması için,
şifreyle korunan (bkz. main.py'deki imzalı oturum çerezi kontrolü,
2026-08-23'te HTTP Basic Auth'un yerini aldı), salt-okunur bir
"arka ofis" görünümü. Kapsam 2026-08-19'da netleştirildi:

  1) Kullanıcı sayıları  -- toplam/yeni cihaz, favori sayıları
  2) Sistem/bot sağlığı  -- son tarama, veri dağılımı, disk kullanımı,
                            son kritik uyarılar
  3) Bildirim etkinliği  -- gönderilen push bildirimleri, favori→onay
                            dönüşüm oranı

BİLİNÇLİ OLARAK YOK: tekil arama/sorgu geçmişi. Kullanıcı, hangi dosya
numarasının arandığını kaydetmenin (kişisel veri + Gizlilik Politikası
güncellemesi gerektireceği için) İSTEMEDİĞİNE karar verdi (2026-08-19).
"""
import html
import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

from dosya_utils import ROMANYA_SAAT_DILIMI, kategori_yolu_goster

# 2026-08-19 DÜZELTMESİ (kullanıcı fark etti, verileri panelle çapraz
# doğruladıktan sonra sordu): rakamların KENDİSİ hep doğruydu ama "bugün/
# hafta/ay yeni cihaz" eşiği ve olay zaman damgaları UTC ile
# gösteriliyordu (SQLite'ın CURRENT_TIMESTAMP'ı HER ZAMAN UTC'dir) --
# Romanya saatiyle karşılaştırıldığında birkaç saatlik bir kaymaya
# (görsel, matematiksel değil) yol açıyordu. Artık her yerde tutarlı
# şekilde Romanya saatine çevriliyor.
_UTC = ZoneInfo("UTC")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 2026-08-19 (Render'a taşıma): bkz. main.py'deki aynı isimli sabitin notu.
VERI_DIZINI = os.environ.get("DATA_DIR", BASE_DIR)
PDF_KOK_KLASOR = os.path.join(VERI_DIZINI, "pdfs")

LACIVERT_KOYU = "#0f1a2e"
LACIVERT = "#16233d"
ALTIN = "#e3a83b"

# 2026-08-19: PDF klasörünün toplam boyutunu hesaplamak (os.walk ile
# binlerce dosyayı tek tek ölçmek) birkaç saniye sürebiliyor -- admin
# panelini her açışta bunu tekrar hesaplamamak için 10 dakikalık basit bir
# önbellek (main.py'deki _genel_istatistik_onbellek ile aynı desen).
_disk_boyutu_onbellek = {"veri": None, "zaman": 0.0}
_ONBELLEK_SURESI_SN = 600

# ---------------------------------------------------------------------------
# "BUGÜNÜN DURUMU" -- 2026-08-22, kullanıcının isteğiyle eklendi
# ---------------------------------------------------------------------------
# Kullanıcı, Render/Sentry/GitHub/Backblaze panelleri arasında tek tek
# gezmek yerine hepsinin GÜNLÜK durumunu TEK pencerede görmek istedi.
# Buradaki 4 fonksiyon, ilgili servise KENDİ API'si üzerinden anlık bir
# sorgu atıp tek satırlık bir özet döndürüyor. Her biri kendi ortam
# değişkenlerine bakıyor -- biri eksikse (ör. yerel geliştirmede) o servis
# sessizce "yok" durumuna düşer, panelin geri kalanını bozmaz (SENTRY_DSN
# ile aynı desen). Ağ çağrıları paralel (ThreadPoolExecutor) çalıştırılıyor
# ki 4 servisin toplam bekleme süresi, en yavaş TEKİNİNKİ kadar olsun
# (art arda 4x8sn değil). Sonuç 5 dakika önbelleğe alınıyor -- panel art
# arda birkaç kez yenilense bile dış servislere gereksiz yük binmesin diye
# (yukarıdaki disk boyutu önbelleğiyle aynı desen).
RENDER_API_ANAHTARI = os.environ.get("RENDER_API_ANAHTARI")
RENDER_SERVIS_ID = os.environ.get("RENDER_SERVIS_ID")
SENTRY_AUTH_TOKEN = os.environ.get("SENTRY_AUTH_TOKEN")
SENTRY_ORG_SLUG = os.environ.get("SENTRY_ORG_SLUG")
SENTRY_PROJECT_SLUG = os.environ.get("SENTRY_PROJECT_SLUG")
GITHUB_REPO = "ahmetkanbay-ops/romanya-dosya-takip"  # herkese açık repo, anahtar gerekmiyor

_dis_servis_onbellek = {"veri": None, "zaman": 0.0}
_DIS_SERVIS_ONBELLEK_SURESI_SN = 300  # 5 dakika
_AG_ZAMAN_ASIMI_SN = 6


def _render_durumu_getir():
    if not (RENDER_API_ANAHTARI and RENDER_SERVIS_ID):
        return {"ikon": "🖥️", "ad": "Render (sunucu)", "durum": "yok", "mesaj": "API anahtarı ayarlı değil"}
    try:
        yanit = requests.get(
            f"https://api.render.com/v1/services/{RENDER_SERVIS_ID}/deploys?limit=1",
            headers={"Authorization": f"Bearer {RENDER_API_ANAHTARI}"},
            timeout=_AG_ZAMAN_ASIMI_SN,
        )
        yanit.raise_for_status()
        deploy = yanit.json()[0]["deploy"]
        basarili = deploy.get("status") == "live"
        commit_kisa = deploy.get("commit", {}).get("id", "")[:7]
        return {
            "ikon": "🖥️", "ad": "Render (sunucu)",
            "durum": "iyi" if basarili else "uyari",
            "mesaj": f"Ayakta, son deploy: {deploy.get('status')} ({commit_kisa})" if basarili
                     else f"Son deploy durumu: {deploy.get('status')} ({commit_kisa})",
        }
    except Exception as e:
        return {"ikon": "🖥️", "ad": "Render (sunucu)", "durum": "hata", "mesaj": f"Kontrol edilemedi: {e}"}


def _sentry_durumu_getir():
    if not (SENTRY_AUTH_TOKEN and SENTRY_ORG_SLUG and SENTRY_PROJECT_SLUG):
        return {"ikon": "🐞", "ad": "Sentry (hatalar)", "durum": "yok", "mesaj": "API anahtarı ayarlı değil"}
    try:
        yanit = requests.get(
            f"https://sentry.io/api/0/projects/{SENTRY_ORG_SLUG}/{SENTRY_PROJECT_SLUG}/issues/",
            headers={"Authorization": f"Bearer {SENTRY_AUTH_TOKEN}"},
            params={"statsPeriod": "24h", "query": "is:unresolved"},
            timeout=_AG_ZAMAN_ASIMI_SN,
        )
        yanit.raise_for_status()
        sayi = len(yanit.json())
        return {
            "ikon": "🐞", "ad": "Sentry (hatalar)",
            "durum": "iyi" if sayi == 0 else "uyari",
            "mesaj": "Son 24 saatte yeni hata yok" if sayi == 0 else f"Son 24 saatte {sayi} yeni/açık hata",
        }
    except Exception as e:
        return {"ikon": "🐞", "ad": "Sentry (hatalar)", "durum": "hata", "mesaj": f"Kontrol edilemedi: {e}"}


def _github_durumu_getir():
    try:
        esik = (datetime.now(_UTC) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
        yanit = requests.get(
            f"https://api.github.com/repos/{GITHUB_REPO}/commits",
            params={"since": esik},
            timeout=_AG_ZAMAN_ASIMI_SN,
        )
        yanit.raise_for_status()
        sayi = len(yanit.json())
        return {
            "ikon": "💻", "ad": "GitHub",
            "durum": "iyi",
            "mesaj": f"Son 24 saatte {sayi} commit" if sayi else "Son 24 saatte commit yok",
        }
    except Exception as e:
        return {"ikon": "💻", "ad": "GitHub", "durum": "hata", "mesaj": f"Kontrol edilemedi: {e}"}


def _b2_durumu_getir():
    b2_key_id = os.environ.get("B2_KEY_ID")
    b2_anahtar = os.environ.get("B2_APPLICATION_KEY")
    b2_bucket = os.environ.get("B2_BUCKET_ADI")
    b2_endpoint = os.environ.get("B2_ENDPOINT")
    if not (b2_key_id and b2_anahtar and b2_bucket and b2_endpoint):
        return {"ikon": "☁️", "ad": "Backblaze (yedek)", "durum": "yok", "mesaj": "B2 ayarlı değil"}
    try:
        import boto3
        from botocore.config import Config
        # boto3'ün VARSAYILAN zaman aşımı çok uzun (bağlantı için ~60sn) --
        # B2 herhangi bir sebeple yavaş/erişilemez olursa bu, TÜM admin
        # panelini dakikalarca kilitleyebilirdi (yerel testte tam bunu
        # yaşadık -- bkz. 2026-08-22 B2 entegrasyonu sırasındaki ağ engeli
        # notu). Diğer 3 servisle (requests, timeout=6sn) tutarlı olsun diye.
        s3 = boto3.client(
            "s3", endpoint_url=b2_endpoint,
            aws_access_key_id=b2_key_id, aws_secret_access_key=b2_anahtar,
            config=Config(connect_timeout=_AG_ZAMAN_ASIMI_SN, read_timeout=_AG_ZAMAN_ASIMI_SN, retries={"max_attempts": 1}),
        )
        yanit = s3.list_objects_v2(Bucket=b2_bucket, Prefix="veritabani-yedekleri/")
        nesneler = yanit.get("Contents", [])
        if not nesneler:
            return {"ikon": "☁️", "ad": "Backblaze (yedek)", "durum": "uyari", "mesaj": "Hiç yedek bulunamadı"}
        en_yeni = max(nesneler, key=lambda n: n["LastModified"])
        yas_saat = (datetime.now(_UTC) - en_yeni["LastModified"]).total_seconds() / 3600
        boyut_mb = en_yeni["Size"] / (1024 * 1024)
        if yas_saat <= 30:  # gece 03:00 yedeklemesi + cömert pay (main.py'deki SON_TARAMA_TAZELIK_ESIGI_SAAT ile aynı mantık)
            return {"ikon": "☁️", "ad": "Backblaze (yedek)", "durum": "iyi",
                     "mesaj": f"Son yedek {yas_saat:.0f} saat önce, {boyut_mb:.1f} MB"}
        return {"ikon": "☁️", "ad": "Backblaze (yedek)", "durum": "uyari",
                 "mesaj": f"Son yedek {yas_saat:.0f} saat önce -- beklenenden eski"}
    except Exception as e:
        return {"ikon": "☁️", "ad": "Backblaze (yedek)", "durum": "hata", "mesaj": f"Kontrol edilemedi: {e}"}


def _bot_taramasi_durumu(son_basarili_tarama, son_tarama_detay):
    if not son_basarili_tarama:
        return {"ikon": "🤖", "ad": "Günlük Tarama", "durum": "uyari", "mesaj": "Hiç tarama kaydı yok"}
    try:
        ayristirilan = datetime.fromisoformat(son_basarili_tarama)
        if ayristirilan.tzinfo is not None:
            # Yeni kayıtlar saat dilimi bilgisiyle yazılıyor (bot.py).
            ayristirilan = ayristirilan.astimezone(ROMANYA_SAAT_DILIMI)
        else:
            # Eski kayıt, saat dilimsiz -- zaten Romanya yerel saatiyle yazılmıştı.
            ayristirilan = ayristirilan.replace(tzinfo=ROMANYA_SAAT_DILIMI)
        yas_saat = (datetime.now(ROMANYA_SAAT_DILIMI) - ayristirilan).total_seconds() / 3600
    except Exception:
        yas_saat = 999
    detay = f" — {son_tarama_detay}" if son_tarama_detay else ""
    if yas_saat <= 30:
        return {"ikon": "🤖", "ad": "Günlük Tarama", "durum": "iyi", "mesaj": f"{yas_saat:.0f} saat önce çalıştı{detay}"}
    return {"ikon": "🤖", "ad": "Günlük Tarama", "durum": "uyari", "mesaj": f"{yas_saat:.0f} saattir çalışmadı{detay}"}


def bugunun_durumunu_getir(son_basarili_tarama, son_tarama_detay):
    """4 dış servisi PARALEL sorgulayıp + bot'un kendi tarama durumunu
    birlikte tek bir liste olarak döndürür. 5 dakika önbelleğe alınır."""
    onbellek = _dis_servis_onbellek
    if onbellek["veri"] is not None and (time.time() - onbellek["zaman"]) < _DIS_SERVIS_ONBELLEK_SURESI_SN:
        return onbellek["veri"]

    bot_durumu = _bot_taramasi_durumu(son_basarili_tarama, son_tarama_detay)
    with ThreadPoolExecutor(max_workers=4) as havuz:
        sonuclar = list(havuz.map(
            lambda fn: fn(),
            [_render_durumu_getir, _sentry_durumu_getir, _b2_durumu_getir, _github_durumu_getir],
        ))

    sonuc = [bot_durumu] + sonuclar
    onbellek["veri"] = sonuc
    onbellek["zaman"] = time.time()
    return sonuc


def bugunun_durumu_verisini_getir(conn, son_basarili_tarama):
    """bugunun_durumunu_getir() icin son_tarama_detay'i veritabanindan
    okuyup ham liste (HTML'e SARILMAMIS) olarak dondurur -- hem
    bugunun_durumu_html_getir (admin sayfasi) hem de Gece Nobeti'nin
    /api/admin/saglik-kontrolu ucu (main.py, 2026-08-30 EKLENTISI) bunu
    ortak kullaniyor, DB sorgusu iki yerde tekrarlanmasin diye."""
    c = conn.cursor()
    c.execute(
        "SELECT detay FROM sistem_olaylari WHERE olay_tipi='tarama_tamamlandi' "
        "ORDER BY zaman DESC LIMIT 1"
    )
    satir = c.fetchone()
    son_tarama_detay = satir[0] if satir else None
    return bugunun_durumunu_getir(son_basarili_tarama, son_tarama_detay)


def bugunun_durumu_html_getir(conn, son_basarili_tarama):
    """2026-08-22: /admin sayfasının kendisi ARTIK bunu çağırmıyor -- 4 dış
    servise (Render/Sentry/B2/GitHub) atılan canlı istekler onlarca saniye
    sürebiliyor (Render'ın bu bölgeden bazı servislere erişimi yavaş
    kalabiliyor), bu da TÜM admin panelini bloke ediyordu. Artık sayfa
    ANINDA açılıyor, bu fonksiyon ayrı bir uç noktadan (/api/admin/
    bugunun-durumu) sayfa yüklendikten SONRA, tarayıcıdan JS ile çağrılıyor
    -- kullanıcı bekleme hissetmiyor, veri geldiğinde yerine oturuyor."""
    durumlar = bugunun_durumu_verisini_getir(conn, son_basarili_tarama)
    return _bugunun_durumu_html(durumlar)


def _boyutu_okunabilir_yap(byte_sayisi):
    for birim in ["B", "KB", "MB", "GB", "TB"]:
        if byte_sayisi < 1024:
            return f"{byte_sayisi:.1f} {birim}"
        byte_sayisi /= 1024
    return f"{byte_sayisi:.1f} PB"


def _klasor_boyutu(yol):
    toplam = 0
    for kok, _, dosyalar in os.walk(yol):
        for ad in dosyalar:
            try:
                toplam += os.path.getsize(os.path.join(kok, ad))
            except OSError:
                pass
    return toplam


def _disk_kullanimini_hesapla(db_dosyasi):
    onbellek = _disk_boyutu_onbellek
    if onbellek["veri"] is not None and (time.time() - onbellek["zaman"]) < _ONBELLEK_SURESI_SN:
        return onbellek["veri"]

    db_boyutu = os.path.getsize(db_dosyasi) if os.path.exists(db_dosyasi) else 0
    pdf_boyutu = _klasor_boyutu(PDF_KOK_KLASOR) if os.path.isdir(PDF_KOK_KLASOR) else 0

    # 2026-08-19 (disk kotası izleme): db_boyutu + pdf_boyutu sadece BİZİM
    # dosyalarımızın boyutu -- diskteki GERÇEK doluluk oranını (Render'daki
    # kalıcı diskin toplam kapasitesine göre) göstermiyordu. shutil.disk_usage
    # VERI_DIZINI'nin bağlı olduğu dosya sisteminin gerçek toplam/kullanılan/
    # boş alanını veriyor -- Render'da bu, /data'ya bağlı kalıcı disk (10GB).
    try:
        disk_toplam, disk_kullanilan, disk_bos = shutil.disk_usage(VERI_DIZINI)
        disk_yuzde = (disk_kullanilan / disk_toplam * 100) if disk_toplam else 0.0
    except OSError:
        disk_toplam = disk_kullanilan = disk_bos = 0
        disk_yuzde = 0.0

    sonuc = {
        "db_boyutu": _boyutu_okunabilir_yap(db_boyutu),
        "pdf_boyutu": _boyutu_okunabilir_yap(pdf_boyutu),
        "toplam_boyutu": _boyutu_okunabilir_yap(db_boyutu + pdf_boyutu),
        "disk_toplam": _boyutu_okunabilir_yap(disk_toplam),
        "disk_bos": _boyutu_okunabilir_yap(disk_bos),
        "disk_yuzde": disk_yuzde,
    }
    onbellek["veri"] = sonuc
    onbellek["zaman"] = time.time()
    return sonuc


_metrikler_onbellek = {"veri": None, "zaman": 0.0}
_METRIK_ONBELLEK_SURESI_SN = 300  # 5 dakika


def metrikleri_hesapla(conn, db_dosyasi, son_basarili_tarama):
    """metrikleri_hesapla()'nın ÖNBELLEKLİ dış yüzü -- 2026-08-22: canlıda
    ölçüldü, `dosyalar` tablosundaki (~1,3 milyon satır) COUNT/GROUP BY
    sorguları Render'ın kalıcı diskinde (ağ üzerinden bağlı depolama,
    yerel SSD'den çok daha yüksek gecikmeli) TEK BAŞINA 30-45 saniye
    sürebiliyor -- disk boyutu zaten ayrı önbelleğe alınıyordu (aşağıdaki
    _disk_kullanimini_hesapla) ama asıl maliyet SQL sorgularıymış, hiç
    önbelleklenmiyordu. Gerçek hesap _metrikleri_hesapla_ham()'a taşındı,
    burada sadece 5 dakikalık bir önbellek katmanı var (diğer önbelleklerle
    aynı desen). Admin paneli haftada bir bakılan bir sayfa -- 5 dakikalık
    bayatlık kabul edilebilir bir bedel, 30-45 saniyelik bekleme değil."""
    onbellek = _metrikler_onbellek
    if onbellek["veri"] is not None and (time.time() - onbellek["zaman"]) < _METRIK_ONBELLEK_SURESI_SN:
        return onbellek["veri"]
    sonuc = _metrikleri_hesapla_ham(conn, db_dosyasi, son_basarili_tarama)
    onbellek["veri"] = sonuc
    onbellek["zaman"] = time.time()
    return sonuc


def _metrikleri_hesapla_ham(conn, db_dosyasi, son_basarili_tarama):
    """Tüm admin paneli metriklerini tek bir sözlükte toplar. `conn`,
    main.py'nin zaten kullandığı row_factory=sqlite3.Row bağlantısıdır."""
    c = conn.cursor()
    simdi = datetime.now(ROMANYA_SAAT_DILIMI)

    # --- 1) Kullanıcı sayıları -------------------------------------------
    c.execute("SELECT COUNT(*) FROM push_tokenlari")
    toplam_cihaz = c.fetchone()[0]

    yeni_cihaz = {}
    for etiket, gun in [("bugun", 1), ("hafta", 7), ("ay", 30)]:
        # Eşik Romanya saatine göre hesaplanıp, SQLite'ın kendi sakladığı
        # formata (UTC, boşluklu, "YYYY-MM-DD HH:MM:SS") çevrilerek
        # karşılaştırılıyor -- ikisi de aynı ANI temsil etsin diye.
        esik_utc = (simdi - timedelta(days=gun)).astimezone(_UTC)
        esik = esik_utc.strftime("%Y-%m-%d %H:%M:%S")
        c.execute("SELECT COUNT(*) FROM push_tokenlari WHERE olusturma_tarihi >= ?", (esik,))
        yeni_cihaz[etiket] = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM favoriler WHERE otomatik_mi = 0")
    toplam_favori = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM favoriler WHERE otomatik_mi = 1")
    toplam_otomatik_takip = c.fetchone()[0]

    # --- 2) Sistem / bot sağlığı ------------------------------------------
    c.execute(
        "SELECT detay, zaman FROM sistem_olaylari WHERE olay_tipi='tarama_tamamlandi' "
        "ORDER BY zaman DESC LIMIT 1"
    )
    son_tarama_satiri = c.fetchone()
    son_tarama_detay = son_tarama_satiri[0] if son_tarama_satiri else None

    c.execute("SELECT COUNT(*) FROM dosyalar")
    toplam_kayit = c.fetchone()[0]

    # 2026-09-03 EKLENTİSİ (kullanıcı isteği): "Toplam kayıt" tek başına
    # bir referans noktası olmadan anlamsız (kullanıcı: "geçen haftaki
    # sayıyı ben tutmuyorum ki artışı görebileyim"). tarama_gecmisi
    # tablosundan (bkz. dosya_utils.tarama_gecmisine_kaydet) son 7 günde
    # eklenen TOPLAM yeni kayıt sayısı buradan hesaplanıp ayrı bir kart
    # olarak gösteriliyor -- kullanıcının hiçbir şey not almasına gerek
    # kalmadan "bu hafta ne kadar arttı" sorusuna direkt cevap. Bu sütun
    # (tarama_zamani) ROMANYA yerel saatiyle yazılıyor (bkz. bot.py) --
    # sistem_olaylari'nın aksine burada UTC çevrimi YAPILMAMALI.
    esik_yerel = (simdi - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    c.execute(
        "SELECT COALESCE(SUM(yeni_kayit_sayisi), 0) FROM tarama_gecmisi WHERE tarama_zamani >= ?",
        (esik_yerel,),
    )
    bu_hafta_eklenen = c.fetchone()[0]

    c.execute("SELECT ana_kategori, COUNT(*) FROM dosyalar GROUP BY ana_kategori")
    kategori_dagilimi = dict(c.fetchall())

    c.execute("SELECT durum, COUNT(*) FROM dosyalar GROUP BY durum")
    durum_dagilimi = dict(c.fetchall())

    # sistem_olaylari.zaman de SQLite'ın kendi CURRENT_TIMESTAMP'ı (UTC) --
    # aynı çevrim burada da gerekiyor.
    esik_7gun = (simdi - timedelta(days=7)).astimezone(_UTC).strftime("%Y-%m-%d %H:%M:%S")
    c.execute(
        "SELECT COUNT(*) FROM sistem_olaylari WHERE olay_tipi='kritik_uyari' AND zaman >= ?",
        (esik_7gun,),
    )
    kritik_uyari_7gun = c.fetchone()[0]

    c.execute(
        "SELECT detay, zaman FROM sistem_olaylari WHERE olay_tipi='kritik_uyari' "
        "ORDER BY zaman DESC LIMIT 5"
    )
    son_kritik_uyarilar = c.fetchall()

    disk = _disk_kullanimini_hesapla(db_dosyasi)

    # --- 3) Bildirim etkinliği ---------------------------------------------
    c.execute(
        "SELECT COUNT(*) FROM sistem_olaylari WHERE olay_tipi='push_gonderildi' AND zaman >= ?",
        (esik_7gun,),
    )
    push_gonderim_7gun = c.fetchone()[0]

    c.execute(
        "SELECT detay, zaman FROM sistem_olaylari WHERE olay_tipi='push_gonderildi' "
        "ORDER BY zaman DESC LIMIT 5"
    )
    son_push_gonderimler = c.fetchall()

    # Favori -> onay dönüşüm oranı: kullanıcının elle favorilediği (dosya_no_norm,
    # yil) çiftlerinden kaçının 'ordine' tarafında durum='ONAYLANDI' olarak
    # göründüğü.
    c.execute("""
        SELECT
            COUNT(DISTINCT f.dosya_no_norm || '|' || f.yil) AS toplam,
            COUNT(DISTINCT CASE WHEN d.durum = 'ONAYLANDI'
                                 THEN f.dosya_no_norm || '|' || f.yil END) AS onaylanan
        FROM favoriler f
        LEFT JOIN dosyalar d
            ON d.dosya_no_norm = f.dosya_no_norm
           AND d.yil = f.yil
           AND d.ana_kategori = 'ordine'
        WHERE f.otomatik_mi = 0
    """)
    donusum_satiri = c.fetchone()
    favori_toplam, favori_onaylanan = donusum_satiri[0] or 0, donusum_satiri[1] or 0
    donusum_orani = (favori_onaylanan / favori_toplam * 100) if favori_toplam else 0.0

    return {
        "olusturma_zamani": simdi.strftime("%d.%m.%Y %H:%M"),
        "kullanicilar": {
            "toplam_cihaz": toplam_cihaz,
            "yeni_bugun": yeni_cihaz["bugun"],
            "yeni_hafta": yeni_cihaz["hafta"],
            "yeni_ay": yeni_cihaz["ay"],
            "toplam_favori": toplam_favori,
            "toplam_otomatik_takip": toplam_otomatik_takip,
        },
        "sistem": {
            "son_basarili_tarama": son_basarili_tarama,
            "son_tarama_detay": son_tarama_detay,
            "toplam_kayit": toplam_kayit,
            "bu_hafta_eklenen": bu_hafta_eklenen,
            "kategori_dagilimi": kategori_dagilimi,
            "durum_dagilimi": durum_dagilimi,
            "kritik_uyari_7gun": kritik_uyari_7gun,
            "son_kritik_uyarilar": son_kritik_uyarilar,
            "disk": disk,
        },
        "bildirimler": {
            "push_gonderim_7gun": push_gonderim_7gun,
            "son_push_gonderimler": son_push_gonderimler,
            "favori_toplam": favori_toplam,
            "favori_onaylanan": favori_onaylanan,
            "donusum_orani": donusum_orani,
        },
    }


def _e(deger):
    """HTML'e basmadan önce güvenli şekilde kaçış yapar (bkz. hukuki_metinler.py
    sayfa_html'deki aynı gerekçe -- kullanıcı girdisi burada yok ama savunma
    katmanı olarak tutarlı tutuluyor)."""
    return html.escape(str(deger)) if deger is not None else "—"


def _olay_satirlari_html(olaylar, bos_mesaj):
    if not olaylar:
        return f'<p class="bos">{bos_mesaj}</p>'
    satirlar = []
    for detay, zaman in olaylar:
        try:
            ayristirilan = datetime.fromisoformat(zaman)
            if ayristirilan.tzinfo is None:
                # sistem_olaylari.zaman SQLite'ın CURRENT_TIMESTAMP'ı -- UTC, saat dilimsiz.
                ayristirilan = ayristirilan.replace(tzinfo=_UTC)
            zaman_okunabilir = ayristirilan.astimezone(ROMANYA_SAAT_DILIMI).strftime("%d.%m.%Y %H:%M")
        except Exception:
            zaman_okunabilir = _e(zaman)
        satirlar.append(
            f'<li><span class="olay-zaman">{zaman_okunabilir}</span>'
            f'<span class="olay-detay">{_e(detay)}</span></li>'
        )
    return f'<ul class="olay-listesi">{"".join(satirlar)}</ul>'


_DURUM_RENGI = {"iyi": "#2e9e5b", "uyari": "#e3a83b", "hata": "#d9534f", "yok": "#9aa3b2"}
_DURUM_SIMGESI = {"iyi": "✅", "uyari": "⚠️", "hata": "❌", "yok": "⚪"}


def _bugunun_durumu_html(durumlar):
    satirlar = []
    for d in durumlar:
        renk = _DURUM_RENGI.get(d["durum"], "#9aa3b2")
        simge = _DURUM_SIMGESI.get(d["durum"], "⚪")
        satirlar.append(f"""
        <div class="durum-satir" style="border-left-color:{renk}">
          <span class="durum-ikon">{d['ikon']}</span>
          <span class="durum-ad">{_e(d['ad'])}</span>
          <span class="durum-mesaj">{simge} {_e(d['mesaj'])}</span>
        </div>""")
    return "".join(satirlar)


def tarama_gecmisi_verisini_getir(conn, limit=30):
    """
    2026-09-02 EKLENTİSİ (kullanıcı isteği): "Tarama Geçmişi" sayfası için
    -- her taramanın özeti + yeni bulunan kayıtların hangi kategori/PDF'ten
    geldiği (bkz. dosya_utils.tarama_gecmisine_kaydet). En yeni tarama en
    üstte, en fazla `limit` tarama gösterilir (sayfa çok uzamasın diye).
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT tarama_zamani, tur, toplam_pdf_bulunan, kaydedilen_kayit, yeni_kayit_sayisi, yeni_pdf_sayisi "
        "FROM tarama_gecmisi ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    taramalar = cursor.fetchall()

    sonuc = []
    for zaman, tur, toplam, kayit, yeni_sayi, yeni_pdf in taramalar:
        gruplar = []
        if yeni_sayi:
            cursor.execute(
                "SELECT dosya_no, ana_kategori, alt_kategori, pdf_dosya FROM tarama_yeni_kayitlar "
                "WHERE tarama_zamani = ? ORDER BY ana_kategori, alt_kategori, pdf_dosya",
                (zaman,),
            )
            # (kategori_yolu, pdf_dosya) -> [dosya_no, ...] şeklinde grupla --
            # aynı PDF'ten gelen kayıtlar bir arada gösterilsin.
            grup_sozlugu = {}
            grup_sirasi = []
            for dosya_no, ana_kategori, alt_kategori, pdf_dosya in cursor.fetchall():
                anahtar = (kategori_yolu_goster(ana_kategori, alt_kategori), pdf_dosya)
                if anahtar not in grup_sozlugu:
                    grup_sozlugu[anahtar] = []
                    grup_sirasi.append(anahtar)
                grup_sozlugu[anahtar].append(dosya_no)
            gruplar = [
                {"kategori_yolu": k[0], "pdf_dosya": k[1], "dosya_nolari": grup_sozlugu[k]}
                for k in grup_sirasi
            ]
        sonuc.append({
            "zaman": zaman, "tur": tur, "toplam_pdf": toplam, "kayit": kayit,
            "yeni_sayi": yeni_sayi, "yeni_pdf": yeni_pdf, "gruplar": gruplar,
        })
    return sonuc


def _tarama_gecmisi_zamani_goster(zaman_metni):
    # tarama_gecmisi.tarama_zamani zaten ROMANYA_SAAT_DILIMI ile yazılıyor
    # (bkz. bot.py) -- sistem_olaylari.zaman'ın aksine burada AYRICA
    # UTC->Romanya çevirisi YAPILMAMALI (zaten yerel), sadece biçimlendirilir.
    try:
        return datetime.strptime(zaman_metni, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y %H:%M")
    except Exception:
        return _e(zaman_metni)


def tarama_gecmisi_html(taramalar):
    """2026-09-02: /admin/tarama-gecmisi sayfasının tam HTML'i -- her
    taramayı bir kart olarak, yeni kayıtları kategori/PDF'e göre gruplu
    gösterir. admin_sayfa_html ile AYNI görsel dil (renkler/sınıflar)."""
    if not taramalar:
        govde = '<p class="bos">Henüz kayıtlı tarama yok.</p>'
    else:
        kartlar = []
        for t in taramalar:
            baslik = f"{_tarama_gecmisi_zamani_goster(t['zaman'])} — {_e(t['tur']).upper()}"
            ozet = (
                f"{t['toplam_pdf']} PDF bulundu, {t['kayit']} kayıt işlendi "
                f"({t['yeni_sayi']} yeni, {t['yeni_pdf']} yeni PDF dosyasında)"
            )
            if t["gruplar"]:
                grup_html_parcalari = []
                for g in t["gruplar"]:
                    nolar = g["dosya_nolari"]
                    gosterilen = ", ".join(nolar[:20])
                    if len(nolar) > 20:
                        gosterilen += f" … (+{len(nolar) - 20} tane daha)"
                    grup_html_parcalari.append(f"""
                    <div class="dagilim-satir" style="flex-direction:column;align-items:flex-start;gap:3px;padding:8px 0">
                      <span><b>{_e(g['kategori_yolu'])}</b> <span style="color:var(--metin-ikincil)">— {_e(g['pdf_dosya'])} ({len(nolar)})</span></span>
                      <span style="font-size:12px;color:var(--metin-ikincil);font-variant-numeric:tabular-nums">{_e(gosterilen)}</span>
                    </div>""")
                detay_html = "".join(grup_html_parcalari)
            else:
                detay_html = '<p class="bos">Bu taramada yeni kayıt bulunmadı.</p>'
            kartlar.append(f"""
            <div class="genis-kart">
              <h3>{baslik}</h3>
              <p style="margin:0 0 8px;font-size:13px;color:var(--metin-ikincil)">{_e(ozet)}</p>
              {detay_html}
            </div>""")
        govde = "".join(kartlar)

    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tarama Geçmişi — Romanya Dosya Takip</title>
{_ADMIN_PWA_HEAD}
<style>
  :root {{
    --lacivert-koyu: {LACIVERT_KOYU}; --lacivert: {LACIVERT}; --altin: {ALTIN};
    --zemin: #f6f7fb; --yuzey: #ffffff; --kenar: #e4e7ee;
    --metin: #1c2433; --metin-ikincil: #6b7280;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 32px 20px 60px; background: var(--zemin); color: var(--metin);
    font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
  }}
  .sayfa {{ max-width: 860px; margin: 0 auto; }}
  header.ustbilgi {{
    display: flex; justify-content: space-between; align-items: baseline;
    margin-bottom: 22px; flex-wrap: wrap; gap: 8px;
  }}
  header.ustbilgi h1 {{ font-size: 20px; margin: 0; color: var(--lacivert-koyu); }}
  header.ustbilgi a {{ font-size: 12.5px; color: var(--metin-ikincil); }}
  .genis-kart {{
    background: var(--yuzey); border: 1px solid var(--kenar); border-radius: 10px;
    padding: 16px 18px; margin-top: 12px;
  }}
  .genis-kart h3 {{ font-size: 13.5px; margin: 0 0 4px; color: var(--lacivert-koyu); }}
  .dagilim-satir {{ display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid var(--kenar); font-size: 13.5px; }}
  .dagilim-satir:last-child {{ border-bottom: none; }}
  p.bos {{ color: var(--metin-ikincil); font-size: 13px; font-style: italic; margin: 4px 0; }}
  footer.altbilgi {{ text-align: center; font-size: 11.5px; color: var(--metin-ikincil); margin-top: 30px; }}
</style>
</head>
<body>
<div class="sayfa">
  <header class="ustbilgi">
    <h1>🗂️ Tarama Geçmişi</h1>
    <a href="/admin">← Panele dön</a>
  </header>
  {govde}
  <footer class="altbilgi">Romanya Dosya Takip — en yeni {len(taramalar)} tarama gösteriliyor.</footer>
</div>
</body>
</html>"""


_ADMIN_PWA_HEAD = """
<link rel="manifest" href="/admin/manifest.json">
<meta name="theme-color" content="#0f1a2e">
<link rel="apple-touch-icon" href="/statik/admin/icon-1024.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="RDT Admin">
<meta name="mobile-web-app-capable" content="yes">
"""


def admin_giris_html(hata=False):
    """2026-08-23 EKLENTİSİ: HTTP Basic Auth'un yerini alan giriş sayfası --
    kullanıcı "her seferinde parola girmekten sıkıldım" dedi, artık başarılı
    girişte 90 günlük imzalı bir çerez bırakılıyor (bkz. main.py
    _admin_oturum_dogrula), bir daha bu formu görmesi gerekmeyecek."""
    hata_html = (
        '<p class="hata">Kullanıcı adı veya şifre hatalı.</p>' if hata else ""
    )
    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Admin Girişi — Romanya Dosya Takip</title>
{_ADMIN_PWA_HEAD}
<style>
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center;
    background: {LACIVERT_KOYU}; color: #F5F7FA;
    font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
    padding: 20px;
  }}
  form {{
    width: 100%; max-width: 340px; background: {LACIVERT}; border: 1px solid #2E3B5C;
    border-radius: 16px; padding: 32px 28px;
  }}
  h1 {{ font-size: 18px; margin: 0 0 4px; text-align: center; }}
  p.alt {{ margin: 0 0 24px; text-align: center; color: #8E9AB8; font-size: 13px; }}
  p.hata {{
    background: rgba(217,83,79,0.12); border: 1px solid rgba(217,83,79,0.4);
    color: #f2a09d; border-radius: 8px; padding: 10px 14px; font-size: 13px; margin: 0 0 18px;
  }}
  label {{ display: block; font-size: 12.5px; color: #8E9AB8; margin: 0 0 6px; }}
  input {{
    width: 100%; padding: 12px 14px; margin-bottom: 16px; border-radius: 10px;
    border: 1px solid #2E3B5C; background: {LACIVERT_KOYU}; color: #F5F7FA; font-size: 15px;
  }}
  input:focus {{ outline: none; border-color: {ALTIN}; }}
  button {{
    width: 100%; padding: 13px; border: none; border-radius: 10px; background: {ALTIN};
    color: {LACIVERT_KOYU}; font-weight: 800; font-size: 15px; cursor: pointer;
  }}
</style>
</head>
<body>
  <form method="post" action="/admin/giris">
    <h1>🔒 Admin Paneli</h1>
    <p class="alt">Romanya Dosya Takip -- sadece proje sahibi için</p>
    {hata_html}
    <label for="kullanici_adi">Admin kullanıcı adı</label>
    <input type="text" id="kullanici_adi" name="kullanici_adi" autocomplete="username" autofocus required>
    <label for="sifre">Admin şifresi</label>
    <input type="password" id="sifre" name="sifre" autocomplete="current-password" required>
    <button type="submit">Giriş Yap</button>
  </form>
</body>
</html>"""


def admin_sayfa_html(m):
    k = m["kullanicilar"]
    s = m["sistem"]
    b = m["bildirimler"]

    kategori_satirlari = "".join(
        f'<div class="dagilim-satir"><span>{_e(ad)}</span><b>{sayi}</b></div>'
        for ad, sayi in s["kategori_dagilimi"].items()
    ) or '<p class="bos">Henüz veri yok.</p>'

    durum_satirlari = "".join(
        f'<div class="dagilim-satir"><span>{_e(ad)}</span><b>{sayi}</b></div>'
        for ad, sayi in s["durum_dagilimi"].items()
    ) or '<p class="bos">Henüz veri yok.</p>'

    son_tarama_metin = "Hiç tarama kaydı yok."
    if s["son_basarili_tarama"]:
        try:
            ayristirilan = datetime.fromisoformat(s["son_basarili_tarama"])
            if ayristirilan.tzinfo is not None:
                # Yeni kayıtlar saat dilimi bilgisiyle yazılıyor (bot.py) --
                # emin olmak için Romanya saatine çevir (zaten öyleyse etkisiz).
                ayristirilan = ayristirilan.astimezone(ROMANYA_SAAT_DILIMI)
            # tzinfo yoksa: eski kayıt, zaten yerel (Romanya) saatiyle yazılmıştı -- olduğu gibi kullan.
            zaman = ayristirilan.strftime("%d.%m.%Y %H:%M")
        except Exception:
            zaman = _e(s["son_basarili_tarama"])
        son_tarama_metin = f"{zaman}"
        if s["son_tarama_detay"]:
            son_tarama_metin += f" — {_e(s['son_tarama_detay'])}"

    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Admin Paneli — Romanya Dosya Takip</title>
{_ADMIN_PWA_HEAD}
<style>
  :root {{
    --lacivert-koyu: {LACIVERT_KOYU}; --lacivert: {LACIVERT}; --altin: {ALTIN};
    --zemin: #f6f7fb; --yuzey: #ffffff; --kenar: #e4e7ee;
    --metin: #1c2433; --metin-ikincil: #6b7280;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 32px 20px 60px; background: var(--zemin); color: var(--metin);
    font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
  }}
  .sayfa {{ max-width: 860px; margin: 0 auto; }}
  header.ustbilgi {{
    display: flex; justify-content: space-between; align-items: baseline;
    margin-bottom: 22px; flex-wrap: wrap; gap: 8px;
  }}
  header.ustbilgi h1 {{
    font-size: 20px; margin: 0; color: var(--lacivert-koyu);
    display: flex; align-items: center; gap: 10px;
  }}
  header.ustbilgi h1 img.profil-avatar {{
    width: 64px; height: 64px; border-radius: 50%; object-fit: cover;
    border: 3px solid var(--altin); flex-shrink: 0;
  }}
  header.ustbilgi .zaman {{ font-size: 12.5px; color: var(--metin-ikincil); }}

  .bolum {{ margin-bottom: 26px; }}
  .bolum-baslik {{
    font-size: 12px; font-weight: 700; letter-spacing: .07em; text-transform: uppercase;
    color: var(--altin); margin: 0 0 10px;
  }}
  .kart-izgara {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }}
  .kart {{
    background: var(--yuzey); border: 1px solid var(--kenar); border-radius: 10px;
    padding: 14px 16px;
  }}
  .kart .rakam {{ font-size: 26px; font-weight: 700; color: var(--lacivert-koyu); line-height: 1.1; }}
  .kart .etiket {{ font-size: 12px; color: var(--metin-ikincil); margin-top: 3px; }}

  .genis-kart {{
    background: var(--yuzey); border: 1px solid var(--kenar); border-radius: 10px;
    padding: 16px 18px; margin-top: 12px;
  }}
  .genis-kart h3 {{ font-size: 13.5px; margin: 0 0 8px; color: var(--lacivert-koyu); }}

  .dagilim-satir {{
    display: flex; justify-content: space-between; padding: 5px 0;
    border-bottom: 1px solid var(--kenar); font-size: 13.5px;
  }}
  .dagilim-satir:last-child {{ border-bottom: none; }}
  .dagilim-satir b {{ color: var(--lacivert-koyu); }}

  .olay-listesi {{ list-style: none; margin: 0; padding: 0; }}
  .olay-listesi li {{
    display: flex; gap: 10px; padding: 6px 0; border-bottom: 1px solid var(--kenar);
    font-size: 12.8px; align-items: baseline;
  }}
  .olay-listesi li:last-child {{ border-bottom: none; }}
  .olay-zaman {{ color: var(--metin-ikincil); white-space: nowrap; font-variant-numeric: tabular-nums; }}
  .olay-detay {{ color: var(--metin); }}
  p.bos {{ color: var(--metin-ikincil); font-size: 13px; font-style: italic; margin: 4px 0; }}

  .donusum-cubuk-zemin {{ height: 8px; background: var(--kenar); border-radius: 5px; overflow: hidden; margin-top: 8px; }}
  .donusum-cubuk-dolu {{ height: 100%; background: linear-gradient(90deg, var(--altin), #f0c069); }}

  .durum-satir {{
    display: flex; align-items: center; gap: 10px; padding: 10px 14px;
    background: var(--yuzey); border: 1px solid var(--kenar); border-left: 4px solid #9aa3b2;
    border-radius: 8px; margin-bottom: 8px; font-size: 13.5px; flex-wrap: wrap;
  }}
  .durum-ikon {{ font-size: 16px; }}
  .durum-ad {{ font-weight: 700; color: var(--lacivert-koyu); min-width: 150px; }}
  .durum-mesaj {{ color: var(--metin-ikincil); }}

  .nobetci-buton {{
    padding: 9px 16px; border: none; border-radius: 8px; background: var(--altin);
    color: var(--lacivert-koyu); font-weight: 700; font-size: 13px; cursor: pointer;
  }}
  .nobetci-buton:disabled {{ opacity: .5; cursor: default; }}

  footer.altbilgi {{ text-align: center; font-size: 11.5px; color: var(--metin-ikincil); margin-top: 30px; }}
</style>
</head>
<body>
<div class="sayfa">
  <header class="ustbilgi">
    <h1><img class="profil-avatar" src="/statik/admin/profil-foto.jpg" alt=""> Admin Paneli</h1>
    <span class="zaman">Oluşturulma: {m['olusturma_zamani']} · <a href="/admin/tarama-gecmisi" style="color:var(--metin-ikincil)">Tarama Geçmişi →</a></span>
  </header>

  <div class="bolum">
    <p class="bolum-baslik">Bugünün Durumu</p>
    <div id="bugunun-durumu-icerik">
      <div class="durum-satir" style="border-left-color:#9aa3b2">
        <span class="durum-ikon">⏳</span>
        <span class="durum-ad">Yükleniyor…</span>
        <span class="durum-mesaj">Render, Sentry, Backblaze ve GitHub kontrol ediliyor (birkaç saniye sürebilir)</span>
      </div>
    </div>
  </div>
  <!-- 2026-08-22 DÜZELTMESİ: bu script SATIR İÇİYDİ ama main.py'deki CSP
       başlığı (default-src 'self', script-src için ayrı izin yok) satır içi
       script'leri sessizce engelliyordu -- "Bugünün Durumu" bu yüzden
       sonsuza kadar "Yükleniyor…"da kalıyordu. Aynı kökenden servis edilen
       ayrı bir dosyaya taşındı (bkz. statik/admin/bugunun-durumu.js). -->
  <script src="/statik/admin/bugunun-durumu.js"></script>

  <div class="bolum">
    <p class="bolum-baslik">Kullanıcılar</p>
    <p style="margin:0 0 10px;font-size:12.5px;color:var(--metin-ikincil)">
      Gerçek Play Store yükleme sayısı için <a href="https://play.google.com/console" target="_blank" style="color:var(--metin-ikincil)">Play Console → İstatistikler</a>'e bakın — buradaki sayılar sadece bildirim izni verilmiş cihazları sayar (bir kısmı hiç izin vermemiş olabilir).
    </p>
    <div class="kart-izgara">
      <div class="kart"><div class="rakam">{k['toplam_cihaz']}</div><div class="etiket">Bildirim kaydı olan cihaz</div></div>
      <div class="kart"><div class="rakam">{k['yeni_bugun']}</div><div class="etiket">Bugün yeni</div></div>
      <div class="kart"><div class="rakam">{k['yeni_hafta']}</div><div class="etiket">Bu hafta yeni</div></div>
      <div class="kart"><div class="rakam">{k['yeni_ay']}</div><div class="etiket">Bu ay yeni</div></div>
      <div class="kart"><div class="rakam">{k['toplam_favori']}</div><div class="etiket">Favori (elle eklenen)</div></div>
      <div class="kart"><div class="rakam">{k['toplam_otomatik_takip']}</div><div class="etiket">Otomatik izlenen</div></div>
    </div>
  </div>

  <div class="bolum">
    <p class="bolum-baslik">Render / Sistem / Bot Sağlığı</p>
    <div class="kart-izgara">
      <div class="kart"><div class="rakam">{s['toplam_kayit']}</div><div class="etiket">Toplam kayıt</div></div>
      <div class="kart"><div class="rakam">+{s['bu_hafta_eklenen']}</div><div class="etiket">Bu hafta eklenen</div></div>
      <div class="kart"><div class="rakam">{s['kritik_uyari_7gun']}</div><div class="etiket">Kritik uyarı (7 gün)</div></div>
      <div class="kart"><div class="rakam" style="font-size:17px">{s['disk']['db_boyutu']}</div><div class="etiket">Veritabanı boyutu</div></div>
      <div class="kart"><div class="rakam" style="font-size:17px">{s['disk']['pdf_boyutu']}</div><div class="etiket">PDF klasörü boyutu</div></div>
    </div>

    <div class="genis-kart">
      <h3>Disk kullanımı (kalıcı disk)</h3>
      <p style="margin:0 0 2px;font-size:13.5px">%{s['disk']['disk_yuzde']:.1f} dolu
        <span style="color:var(--metin-ikincil)">({s['disk']['disk_bos']} boş / {s['disk']['disk_toplam']} toplam)</span></p>
      <div class="donusum-cubuk-zemin"><div class="donusum-cubuk-dolu" style="width:{min(s['disk']['disk_yuzde'],100):.1f}%{';background:#d9534f' if s['disk']['disk_yuzde'] >= 80 else ''}"></div></div>
    </div>

    <div class="genis-kart">
      <h3>Son tarama</h3>
      <p style="margin:0;font-size:13.5px">{son_tarama_metin}</p>
    </div>

    <div class="genis-kart">
      <h3>Ana kategori dağılımı</h3>
      {kategori_satirlari}
    </div>

    <div class="genis-kart">
      <h3>Durum dağılımı</h3>
      {durum_satirlari}
    </div>

    <div class="genis-kart">
      <h3>Son kritik uyarılar</h3>
      {_olay_satirlari_html(s['son_kritik_uyarilar'], "Son dönemde kritik uyarı yok — iyi haber.")}
    </div>
  </div>

  <div class="bolum">
    <p class="bolum-baslik">Bildirimler</p>
    <div class="kart-izgara">
      <div class="kart"><div class="rakam">{b['push_gonderim_7gun']}</div><div class="etiket">Gönderim turu (7 gün)</div></div>
      <div class="kart"><div class="rakam">{b['favori_toplam']}</div><div class="etiket">Takipteki favori</div></div>
      <div class="kart"><div class="rakam">{b['favori_onaylanan']}</div><div class="etiket">Onaylanan</div></div>
    </div>

    <div class="genis-kart">
      <h3>Favori → Onay dönüşüm oranı</h3>
      <p style="margin:0 0 2px;font-size:13.5px">%{b['donusum_orani']:.1f}
        <span style="color:var(--metin-ikincil)">({b['favori_onaylanan']} / {b['favori_toplam']})</span></p>
      <div class="donusum-cubuk-zemin"><div class="donusum-cubuk-dolu" style="width:{min(b['donusum_orani'],100):.1f}%"></div></div>
    </div>

    <div class="genis-kart">
      <h3>Son bildirim gönderimleri</h3>
      {_olay_satirlari_html(b['son_push_gonderimler'], "Henüz push bildirimi gönderilmedi.")}
    </div>
  </div>

  <footer class="altbilgi">Romanya Dosya Takip — sadece proje sahibi için, salt-okunur görünüm. · <a href="/admin/cikis" style="color:var(--metin-ikincil)">Çıkış yap</a></footer>
</div>
</body>
</html>"""
