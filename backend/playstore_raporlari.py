# -*- coding: utf-8 -*-
"""
Play Store istatistik/satış raporları (2026-10-03, kullanıcı isteği):
  1) Admin panelinde günlük ziyaretçi/indirme takibi (/admin/playstore)
  2) İlk gerçek satışta Telegram'a günlük özet bildirimi

Google bu verileri UYGULAMANIN KENDİSİ İÇİN hiçbir anlık/gerçek-zamanlı API
sunmuyor (doğrulandı, bkz. karar günlüğü) -- tek kaynak, her Play Console
hesabına özel bir Google Cloud Storage "bucket"ına Google'ın kendisinin
koyduğu GÜNLÜK ama 3-7 GÜN GECİKMELİ CSV raporları. Yani bu modül ne kadar
sık çalışırsa çalışsın, en güncel birkaç gün admin panelinde HER ZAMAN boş
görünecek -- bu bir hata değil, Google'ın veri gecikmesi.

Gerekli ortam değişkeni:
  GOOGLE_PLAYSTORE_SA_JSON -- Play Console'da "Uygulama bilgilerini
  görüntüleme" + "Finansal verileri görüntüleme" (ikisi de salt-okunur)
  izniyle davet edilmiş bir Google Cloud servis hesabının JSON anahtarının
  TAM İÇERİĞİ (tek satır/çok satır fark etmez). Ayarlı değilse bu modülün
  tüm fonksiyonları sessizce hiçbir şey yapmaz (B2/Sentry ile aynı desen,
  bkz. main.py).

NOT (2026-10-03 kurulum günü): Play Console'da izin verildikten hemen sonra
Google Cloud Storage'a erişim denendiğinde 403 (storage.objects.get izni
yok) hatası alındı -- bu, başka geliştiricilerde de görülen BİLİNEN bir
gecikme (Play Console izninin bucket'a yansıması saatler sürebiliyor).
Sonraki bir denemede hâlâ 403 alınıyorsa önce bunu, sonra servis hesabı
e-postasının Play Console'da hâlâ "Etkin" göründüğünü kontrol et.
"""
import csv
import io
import json
import os
import zipfile
from datetime import datetime

from dosya_utils import veritabani_baglantisi, ROMANYA_SAAT_DILIMI

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VERI_DIZINI = os.environ.get("DATA_DIR", BASE_DIR)
DB_FILE = os.path.join(VERI_DIZINI, "dosyalar.db")

GOOGLE_PLAYSTORE_SA_JSON = os.environ.get("GOOGLE_PLAYSTORE_SA_JSON")

# 2026-10-03 kurulumunda Play Console "Raporları indir" sayfasından elle
# doğrulandı (Cloud Storage URI'si kopyalanarak) -- bu proje/hesaba özel,
# değişmez.
BUCKET_ADI = "pubsite_prod_6682485857181665012"
PAKET_ADI = "com.knby.romanyadosyatakip"


def _gcs_istemcisi():
    """GOOGLE_PLAYSTORE_SA_JSON ayarlı değilse None döner (B2/Sentry ile
    aynı 'opsiyonel özellik' deseni) -- çağıran taraf bunu kontrol eder."""
    if not GOOGLE_PLAYSTORE_SA_JSON:
        return None
    try:
        from google.cloud import storage
        from google.oauth2 import service_account
    except ImportError:
        print("⚠️  GOOGLE_PLAYSTORE_SA_JSON ayarlı ama google-cloud-storage paketi kurulu değil.")
        return None
    try:
        bilgi = json.loads(GOOGLE_PLAYSTORE_SA_JSON)
        kimlik = service_account.Credentials.from_service_account_info(bilgi)
        return storage.Client(project=bilgi.get("project_id"), credentials=kimlik)
    except Exception as e:
        print(f"✗ Play Store servis hesabı başlatılamadı: {str(e)[:120]}")
        return None


def _blob_indir(istemci, yol):
    """Belirtilen yoldaki dosyayı bytes olarak döner; yoksa (henüz
    oluşmamış ay/rapor) ya da izin hatası varsa None döner, hata fırlatmaz
    -- bu raporların bir kısmı (ör. ilk ay, ilk satış) gerçekten yok."""
    try:
        from google.api_core.exceptions import NotFound, Forbidden
    except ImportError:
        NotFound = Forbidden = Exception
    try:
        blob = istemci.bucket(BUCKET_ADI).blob(yol)
        return blob.download_as_bytes()
    except (NotFound, Forbidden):
        return None
    except Exception as e:
        print(f"✗ Play Store raporu indirilemedi ({yol}): {str(e)[:120]}")
        return None


def _csv_satirlari(veri_bytes):
    """Google'ın Play Console CSV'leri tarihsel olarak UTF-16 kodlu --
    önce onu dener, olmazsa UTF-8'e düşer. Her ihtimalde DictReader
    döndürür (boş liste = okunamadı/boş dosya)."""
    if not veri_bytes:
        return []
    for kodlama in ("utf-16", "utf-8-sig", "utf-8"):
        try:
            metin = veri_bytes.decode(kodlama)
            okuyucu = csv.DictReader(io.StringIO(metin))
            satirlar = list(okuyucu)
            if satirlar:
                return satirlar
        except (UnicodeDecodeError, UnicodeError):
            continue
    return []


def _ay_etiketleri(geriye_kac_ay=2):
    """Bugünden geriye [geriye_kac_ay] ay için 'YYYYMM' etiketleri --
    rapor geç geldiği için SADECE bu ay değil, bir önceki ay(lar) da
    kontrol edilmeli."""
    bugun = datetime.now(ROMANYA_SAAT_DILIMI)
    etiketler = []
    y, a = bugun.year, bugun.month
    for _ in range(geriye_kac_ay):
        etiketler.append(f"{y}{a:02d}")
        a -= 1
        if a == 0:
            a = 12
            y -= 1
    return etiketler


def playstore_gunluk_raporlari_guncelle():
    """Yükleme (installs) ve mağaza ziyaretçi (store_performance) CSV'lerini
    indirip günlük satırlara ayrıştırır, 'playstore_gunluk' tablosuna
    upsert eder. GOOGLE_PLAYSTORE_SA_JSON ayarlı değilse sessizce atlanır."""
    istemci = _gcs_istemcisi()
    if istemci is None:
        return {"durum": "atlandi", "sebep": "GOOGLE_PLAYSTORE_SA_JSON ayarlı değil"}

    gunluk_veri = {}  # gun -> {"yeni_yukleme":..,"kaldirma":..,"ziyaretci":..}

    for ay in _ay_etiketleri():
        yukleme_yolu = f"stats/installs/installs_{PAKET_ADI}_{ay}_overview.csv"
        veri = _blob_indir(istemci, yukleme_yolu)
        for satir in _csv_satirlari(veri):
            gun = satir.get("Date") or satir.get("date")
            if not gun:
                continue
            kayit = gunluk_veri.setdefault(gun, {"yeni_yukleme": None, "kaldirma": None, "ziyaretci": None})
            try:
                if "Daily User Installs" in satir:
                    kayit["yeni_yukleme"] = int(float(satir["Daily User Installs"] or 0))
                elif "Daily Device Installs" in satir:
                    kayit["yeni_yukleme"] = int(float(satir["Daily Device Installs"] or 0))
                if "Daily User Uninstalls" in satir:
                    kayit["kaldirma"] = int(float(satir["Daily User Uninstalls"] or 0))
                elif "Daily Device Uninstalls" in satir:
                    kayit["kaldirma"] = int(float(satir["Daily Device Uninstalls"] or 0))
            except (TypeError, ValueError):
                pass

        ziyaretci_yolu = f"stats/store_performance/store_performance_{PAKET_ADI}_{ay}_country.csv"
        veri = _blob_indir(istemci, ziyaretci_yolu)
        for satir in _csv_satirlari(veri):
            gun = satir.get("Date") or satir.get("date")
            if not gun:
                continue
            ziyaretci_sutunu = satir.get("Store listing visitors") or satir.get("Store listing visitors ")
            if ziyaretci_sutunu is None:
                continue
            try:
                deger = int(float(ziyaretci_sutunu))
            except (TypeError, ValueError):
                continue
            kayit = gunluk_veri.setdefault(gun, {"yeni_yukleme": None, "kaldirma": None, "ziyaretci": None})
            kayit["ziyaretci"] = (kayit["ziyaretci"] or 0) + deger

    if not gunluk_veri:
        return {"durum": "veri_yok", "sebep": "Henüz hiç aylık rapor oluşmamış (Google tarafı gecikmesi olabilir)"}

    simdi = datetime.now(ROMANYA_SAAT_DILIMI).strftime("%Y-%m-%d %H:%M")
    conn = veritabani_baglantisi(DB_FILE)
    try:
        for gun, k in gunluk_veri.items():
            conn.execute(
                """
                INSERT INTO playstore_gunluk (gun, yeni_yukleme, kaldirma, ziyaretci, guncelleme_zamani)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(gun) DO UPDATE SET
                    yeni_yukleme = excluded.yeni_yukleme,
                    kaldirma = excluded.kaldirma,
                    ziyaretci = excluded.ziyaretci,
                    guncelleme_zamani = excluded.guncelleme_zamani
                """,
                (gun, k["yeni_yukleme"], k["kaldirma"], k["ziyaretci"], simdi),
            )
        conn.commit()
    finally:
        conn.close()
    return {"durum": "tamam", "gun_sayisi": len(gunluk_veri)}


def playstore_satis_bildirimini_kontrol_et():
    """Satış/finansal rapor klasöründe (henüz hiç dosya yok -- ilk gerçek
    satıştan sonra oluşacak) yeni/değişmiş bir dosya var mı bakar; varsa
    daha önce bildirilmemiş kadarını Telegram'a GÜNLÜK ÖZET olarak bildirir.
    Gerçek zamanlı DEĞİL -- Google'ın verisi 3-7 gün gecikmeli (bkz. modül
    başındaki not); bu sadece en yakın ulaşılabilir alternatif."""
    istemci = _gcs_istemcisi()
    if istemci is None:
        return {"durum": "atlandi", "sebep": "GOOGLE_PLAYSTORE_SA_JSON ayarlı değil"}

    try:
        from google.api_core.exceptions import Forbidden
    except ImportError:
        Forbidden = Exception
    try:
        blob_listesi = list(istemci.list_blobs(BUCKET_ADI, prefix="sales/"))
    except Forbidden as e:
        print(f"✗ Play Store satış klasörü listelenemedi (izin): {str(e)[:120]}")
        return {"durum": "hata", "sebep": "izin"}
    except Exception as e:
        print(f"✗ Play Store satış klasörü listelenemedi: {str(e)[:120]}")
        return {"durum": "hata", "sebep": str(e)[:120]}

    if not blob_listesi:
        return {"durum": "satis_yok", "sebep": "Henüz hiç satış raporu oluşmamış (ilk siparişten sonra görünecek)"}

    en_yeni = max(blob_listesi, key=lambda b: b.name)
    veri = _blob_indir(istemci, en_yeni.name)
    if veri is None:
        return {"durum": "hata", "sebep": "en yeni rapor indirilemedi"}

    if en_yeni.name.endswith(".zip"):
        try:
            with zipfile.ZipFile(io.BytesIO(veri)) as zf:
                ic_dosyalar = [n for n in zf.namelist() if n.lower().endswith(".csv")]
                veri = zf.read(ic_dosyalar[0]) if ic_dosyalar else b""
        except zipfile.BadZipFile:
            veri = b""

    satirlar = _csv_satirlari(veri)
    satir_sayisi = len(satirlar)

    conn = veritabani_baglantisi(DB_FILE)
    try:
        onceki = conn.execute(
            "SELECT son_deger FROM playstore_satis_durumu WHERE anahtar = ?",
            (en_yeni.name,),
        ).fetchone()
        onceki_sayi = int(onceki[0]) if onceki else 0

        if satir_sayisi <= onceki_sayi:
            return {"durum": "degisiklik_yok"}

        yeni_satir_sayisi = satir_sayisi - onceki_sayi
        from bildirim import telegram_gonder
        telegram_gonder(
            f"💰 Play Store'da yeni satış verisi: \"{en_yeni.name.split('/')[-1]}\" "
            f"raporunda {yeni_satir_sayisi} yeni satır görünüyor (toplam {satir_sayisi}). "
            f"Not: bu veri Google'dan 3-7 gün gecikmeli geldiği için satışın GERÇEK tarihi "
            f"birkaç gün önce olabilir, 'şimdi oldu' anlamına gelmez. Ayrıntı için Play "
            f"Console > Raporları indirin > Finansal."
        )

        simdi = datetime.now(ROMANYA_SAAT_DILIMI).strftime("%Y-%m-%d %H:%M")
        conn.execute(
            """
            INSERT INTO playstore_satis_durumu (anahtar, son_deger, zaman) VALUES (?, ?, ?)
            ON CONFLICT(anahtar) DO UPDATE SET son_deger = excluded.son_deger, zaman = excluded.zaman
            """,
            (en_yeni.name, str(satir_sayisi), simdi),
        )
        conn.commit()
    finally:
        conn.close()
    return {"durum": "bildirildi", "yeni_satir": yeni_satir_sayisi}
