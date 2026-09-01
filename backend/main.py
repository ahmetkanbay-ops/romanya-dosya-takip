import os
import shutil
import sys

# 2026-08-17 (canlı hata düzeltmesi): Windows'ta konsol/çıktı kod sayfası
# çoğunlukla UTF-8 DEĞİL (ör. Türkçe Windows'ta cp1254) -- bu dosyadaki
# print() ifadeleri "✓", "⚠️" gibi ASCII-dışı karakterler içerdiğinden,
# uygulama böyle bir ortamda başlarken (özellikle startup_event içindeki
# scheduler mesajında) UnicodeEncodeError ile TAMAMEN ÇÖKÜYORDU -- backend
# hiç ayağa kalkmıyor, mobil taraf da bu yüzden HER sorguda "hata" alıyordu
# (10000 portu asla dinlemeye başlamadığı için). stdout/stderr'i burada,
# en tepede, UTF-8'e zorlayarak kök nedeni ortadan kaldırıyoruz --
# reconfigure Python 3.7+'ta var, olası bir ortamda yoksa (çok eski
# yorumlayıcı) sessizce atlanır, uygulama yine de başlamayı dener.
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import time
import requests
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from types import SimpleNamespace
from urllib.parse import quote
from fastapi import BackgroundTasks, Depends, FastAPI, Form, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional
from apscheduler.schedulers.background import BackgroundScheduler

try:
    # 2026-08-15 (güvenlik testi sırasında bulundu): main.py, backend/.env
    # dosyasını ŞİMDİYE KADAR HİÇ YÜKLEMİYORDU (sadece bildirim.py
    # yüklüyordu) -- yani yerel geliştirmede .env'e APP_API_KEY yazman
    # hiçbir işe yaramıyordu, doğrulama sessizce devre dışı kalıyordu.
    # Render gibi ortamlarda değişkenler doğrudan enjekte edildiği için
    # orada sorun yoktu, ama yerel testleri/geliştirmeyi güvensiz
    # kılıyordu. python-dotenv kurulu değilse (henüz `pip install`
    # çalıştırılmadıysa) sessizce atlanır, uygulama yine ayağa kalkar.
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    _SLOWAPI_VAR = True
except ImportError:
    # slowapi henüz kurulmadıysa (pip install -r requirements.txt
    # çalıştırılmadan önce) API yine de ayağa kalksın, rate limiting
    # devre dışı kalır.
    _SLOWAPI_VAR = False

from dosya_utils import (
    tabloyu_hazirla,
    sayisal_cekirdek,
    tum_rakamlar,
    klasor_adi_guvenli,
    veritabani_baglantisi,
    guvenli_commit,
    ROMANYA_SAAT_DILIMI,
    sira_tahmini_hesapla,
)
from hukuki_metinler import (
    KULLANIM_SARTLARI_METIN,
    GIZLILIK_POLITIKASI_METIN,
    sayfa_html,
)
from pywebpush import webpush, WebPushException
from admin_panel import (
    metrikleri_hesapla, admin_sayfa_html, admin_giris_html,
    bugunun_durumu_html_getir, bugunun_durumu_verisini_getir,
    tarama_gecmisi_verisini_getir, tarama_gecmisi_html,
)
from tanitim_sayfasi import tanitim_sayfasi_html

RESMI_LISTE_URL = "https://cetatenie.just.ro/"

# Mobil uygulamanın her istekte göndereceği basit uygulama anahtarı.
# Ayarlanmazsa (yerel geliştirmede olduğu gibi) kontrol tamamen atlanır --
# bu yüzden bu değeri girmeden de sistem çalışmaya devam eder. Render'a
# taşırken bu değeri hem sunucu ortam değişkenlerine hem mobil tarafta
# EXPO_PUBLIC_APP_KEY'e aynı şekilde girmen yeterli.
APP_API_KEY = os.environ.get("APP_API_KEY")

if not APP_API_KEY:
    # 2026-08-15 (güvenlik sıkılaştırması): sessizce devam etmek yerine
    # sunucu loglarında AÇIKÇA uyarı basılıyor -- production'da (Render)
    # bu değişkenin unutulup unutulmadığı artık göz ardı edilemez.
    print(
        "\n⚠️  UYARI: APP_API_KEY ortam değişkeni ayarlanmamış -- "
        "uygulama anahtarı doğrulaması TAMAMEN DEVRE DIŞI. Bu sadece "
        "yerel geliştirmede kabul edilebilir; Render/production ortamında "
        "MUTLAKA bir değer girilmeli, aksi halde API kimliksiz herkese "
        "açık kalır.\n"
    )


def app_anahtarini_dogrula(x_app_key: Optional[str] = Header(default=None)):
    # secrets.compare_digest: düz '!=' karşılaştırması, karakter karakter
    # farkı bulduğu an durduğu için sunucunun yanıt süresinden anahtarın
    # doğru kısmının tahmin edilebildiği "zamanlama saldırısına" (timing
    # attack) açıktır -- compare_digest sabit sürede karşılaştırır.
    if APP_API_KEY and not secrets.compare_digest(x_app_key or "", APP_API_KEY):
        raise HTTPException(status_code=401, detail="Geçersiz uygulama anahtarı")
    return True


# 2026-08-30 (Gece Nobeti -- Faz 0): GitHub Actions gibi bir zamanlayici
# admin oturum cerezini TUTAMAZ (tarayici degil, giris ekranindan gecemez)
# -- bu yuzden admin_girisini_dogrula'dan AYRI, statik bir anahtar. Ayni
# app_anahtarini_dogrula deseni: fail-closed (anahtar ayarli degilse uc
# 503 doner), sabit-sureli karsilastirma.
NOBETCI_ANAHTARI = os.environ.get("NOBETCI_ANAHTARI")

# 2026-08-30 (Gece Nobeti -- Faz 1): admin panelinin (PWA) tarayici-native
# Web Push bildirimleri icin VAPID anahtar cifti. OZEL anahtar SIR (Render'da
# ayarli), GENEL anahtar tarayiciya /api/admin/push-genel-anahtar ile
# gonderilir (gizli degil, ama ikisi ESLENMIS bir cift -- ayri ayri
# degistirilmemeli, biri degisirse mevcut abonelikler gecersiz kalir).
VAPID_OZEL_ANAHTAR = os.environ.get("VAPID_OZEL_ANAHTAR")
VAPID_GENEL_ANAHTAR = os.environ.get("VAPID_GENEL_ANAHTAR")
VAPID_ILETISIM_EPOSTA = os.environ.get("VAPID_ILETISIM_EPOSTA")


def nobetci_anahtarini_dogrula(x_nobetci_anahtar: Optional[str] = Header(default=None)):
    if not NOBETCI_ANAHTARI:
        raise HTTPException(
            status_code=503,
            detail="Nobetci ucu devre disi: NOBETCI_ANAHTARI ayarlanmamis.",
        )
    if not secrets.compare_digest(x_nobetci_anahtar or "", NOBETCI_ANAHTARI):
        raise HTTPException(status_code=401, detail="Gecersiz nobetci anahtari")
    return True


# 2026-08-19 (/admin istatistik paneli): SADECE proje sahibinin göreceği,
# hiçbir mobil özelliğin çalışması için GEREKLİ OLMAYAN, isteğe bağlı bir
# yönetim sayfası. APP_API_KEY'in aksine (ayarlanmazsa "açık" kalıyor,
# çünkü mobil uygulamanın çalışması buna bağlı), burada ayarlanmazsa
# panel TAMAMEN KAPALI kalır (fail-closed) -- hassas kullanım
# istatistiklerini varsayılan olarak herkese açık bırakmanın hiçbir
# faydası yok, sadece riski var.
ADMIN_KULLANICI_ADI = os.environ.get("ADMIN_KULLANICI_ADI", "admin")
ADMIN_SIFRE = os.environ.get("ADMIN_SIFRE")

# 2026-08-23 DEĞİŞİKLİĞİ (kullanıcı isteği: "her seferinde parolayı girmekle
# uğraşmaktan sıkıldım, telefondan da uygulama gibi kullanabileyim"): HTTP
# Basic Auth'un iki pratik sorunu vardı -- (1) tarayıcı sekmesi kapanınca
# kimlik bilgisi unutuluyor, her ziyarette yeniden soruyor, (2) telefonda
# "ana ekrana ekle" ile açılan bir PWA, Basic Auth'un native tarayıcı
# popup'ını hiç göstermiyor/güvenilir çalışmıyor. Çözüm: kendi imzalı
# (HMAC-SHA256) oturum çerezimiz -- 90 gün geçerli, sunucu tarafında hiçbir
# oturum durumu SAKLAMIYOR (stateless, tıpkı JWT gibi ama harici kütüphane
# gerektirmeden) -- çerez sadece "son geçerlilik zamanı + bu sunucunun gizli
# anahtarıyla imzası"nı taşıyor, sahtesi üretilemez (bkz. _admin_oturum_dogrula).
ADMIN_OTURUM_ANAHTARI = os.environ.get("ADMIN_OTURUM_ANAHTARI")
ADMIN_OTURUM_COOKIE_ADI = "admin_oturum"
ADMIN_OTURUM_GECERLILIK_SN = 90 * 24 * 60 * 60  # 90 gün
# secure=True cerez sadece HTTPS uzerinden taraniyorsa tarayicida saklanir --
# Render'da (RENDER=true, otomatik ayarli) HTTPS var, sorun yok. Ama yerel
# gelistirmede panel http://192.168.x.x:10000 (LAN IP, duz HTTP) uzerinden
# aciliyor -- tarayici boyle bir baglantida Secure cerezi SESSIZCE reddediyor,
# giris basarili gorunuyor (303 /admin'e donuyor) ama cerez hic tutmuyor,
# /admin tekrar /admin/giris'e atiyor ("sayfaya etki etmiyor" hissi buradan
# geliyordu). Bu yuzden secure bayragini ortama gore ayarliyoruz.
ADMIN_OTURUM_COOKIE_SECURE = os.environ.get("RENDER") is not None


def _admin_oturum_imzala(son_gecerlilik_ts: int) -> str:
    mesaj = f"admin:{son_gecerlilik_ts}".encode()
    imza = hmac.new(ADMIN_OTURUM_ANAHTARI.encode(), mesaj, hashlib.sha256).hexdigest()
    return f"{son_gecerlilik_ts}.{imza}"


def _admin_oturum_dogrula(request: Request) -> bool:
    """Çerezi doğrular -- geçersiz/süresi dolmuş/imzasız/hiç yoksa False
    döner (fail-closed, tıpkı eski ADMIN_SIFRE kontrolü gibi)."""
    if not (ADMIN_SIFRE and ADMIN_OTURUM_ANAHTARI):
        return False
    cerez = request.cookies.get(ADMIN_OTURUM_COOKIE_ADI, "")
    if "." not in cerez:
        return False
    son_gecerlilik_str, imza = cerez.split(".", 1)
    try:
        son_gecerlilik_ts = int(son_gecerlilik_str)
    except ValueError:
        return False
    beklenen_imza = _admin_oturum_imzala(son_gecerlilik_ts).split(".", 1)[1]
    if not hmac.compare_digest(imza, beklenen_imza):
        return False
    return time.time() <= son_gecerlilik_ts


def admin_girisini_dogrula(request: Request):
    """/api/admin/* uçları için -- geçersizse JSON 401 döner (bu uçlar
    tarayıcıdan JS ile fetch() ile çağrılıyor, HTML sayfaya yönlendirme
    anlamsız). Sayfa uçları (/admin) kendi içinde _admin_oturum_dogrula'yı
    doğrudan kullanıp /admin/giris'e yönlendiriyor -- bkz. admin_paneli()."""
    if not (ADMIN_SIFRE and ADMIN_OTURUM_ANAHTARI):
        raise HTTPException(
            status_code=503,
            detail="Admin paneli devre dışı: ADMIN_SIFRE/ADMIN_OTURUM_ANAHTARI ayarlanmamış.",
        )
    if not _admin_oturum_dogrula(request):
        raise HTTPException(status_code=401, detail="Giriş gerekli")
    return True


# 2026-08-19 (hata izleme): SENTRY_DSN ortam değişkeni ayarlı değilse
# (ör. yerel geliştirmede) sentry_sdk.init() hiç çağrılmıyor -- SDK
# devre dışı kalır, hiçbir hata/gecikme eklemez. Ayrıca sentry-sdk paketi
# henüz kurulmamışsa (requirements.txt güncellenmiş ama pip install
# çalıştırılmamışsa) da uygulama yine ayağa kalkar, sadece izleme kapalı
# kalır -- diğer opsiyonel bağımlılıklarla (slowapi) aynı desen.
#
# 2026-08-30 DÜZELTMESİ: SENTRY_DSN yanlışlıkla yerel .env'de de tanımlıydı
# -- yukarıdaki yorumun varsaydığının aksine, bu da yerel `python main.py`
# çalıştırmalarının (bu oturumda onlarca kez oldu) canlı Sentry projesine
# RAPOR VERMESİNE yol açıyordu (kanıt: Sentry'de Windows'a özgü
# "ConnectionResetError [WinError 10054]" hatası bulundu -- Render Linux'ta
# bu hata TÜRÜ oluşamaz). Artık DSN ayarlı olsa bile RENDER ortam değişkeni
# (main.py'deki ADMIN_OTURUM_COOKIE_SECURE ile AYNI desen, Render'da
# otomatik "true") yoksa Sentry hiç başlatılmıyor -- yerel geliştirme bir
# daha canlı hata izlemeyi kirletemez.
SENTRY_DSN = os.environ.get("SENTRY_DSN")
_RENDER_ORTAMI = os.environ.get("RENDER") is not None
if SENTRY_DSN and _RENDER_ORTAMI:
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            # Kişisel veri (dosya numarası, cihaz kimliği) Sentry'ye
            # SIZMASIN diye istek gövdesi/PII gönderimi kapalı tutuluyor --
            # sadece hatanın kendisi (stack trace, istek yolu) gönderiliyor.
            send_default_pii=False,
            traces_sample_rate=0.1,
        )
        print("✓ Sentry hata izleme aktif.")
    except ImportError:
        print("⚠️  SENTRY_DSN ayarlı ama sentry-sdk paketi kurulu değil -- izleme devre dışı.")
elif SENTRY_DSN and not _RENDER_ORTAMI:
    print("ℹ️  SENTRY_DSN ayarlı ama yerel ortamdayız (RENDER yok) -- Sentry BİLEREK devre dışı, canlı hata izlemesi kirlenmesin diye.")

app = FastAPI()

if _SLOWAPI_VAR:
    # Kullanıcının istediği "korsan/kötüye kullanıma karşı üst düzey koruma"
    # kapsamında: TÜM uç noktalara varsayılan olarak dakikada 60 istek
    # sınırı uygulanır (IP bazlı). Tek başına yeterli değildir ama gündelik
    # otomatik kötüye kullanımı/botları büyük ölçüde engeller. Ayrıca
    # /api/sorgula gibi hassas uç noktalara AYRICA daha sıkı, uç noktaya
    # özel limitler uygulanıyor (bkz. ilgili endpoint tanımları) -- amaç,
    # tüm dosya numaralarını sırayla deneyip veritabanını "taramaya"
    # (enumeration) çalışan bir botu global limitten çok daha erken
    # yavaşlatmak.
    limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
else:
    # slowapi kurulu değilse bile @limiter.limit(...) süslemelerinin
    # (aşağıda /api/sorgula gibi uç noktalarda kullanılıyor) hata
    # vermeden çalışmaya devam etmesi için etkisiz (no-op) bir yedek.
    class _SahteLimiter:
        def limit(self, *args, **kwargs):
            def sarmalayici(fonk):
                return fonk
            return sarmalayici

    limiter = _SahteLimiter()

# 2026-08-18 (güvenlik denetimi madde 8): allow_origins=["*"] -> [] oldu.
# API, mobil uygulamadan (Expo/React Native) çağrılıyor -- mobil uygulama
# CORS'a hiç tabi değil (bu, sadece TARAYICI ortamında geçerli bir
# kısıtlama), bu yüzden bu değişiklik uygulamanın çalışmasını hiç
# etkilemez. Amaç, herhangi bir web sitesinin tarayıcıdan doğrudan bu
# API'ye istek atmasını (kötüye kullanım/scraping) engellemek. İleride
# bir web sürümü/yönetim paneli eklenirse, o alan adı buraya eklenmeli.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-App-Key"],
)


@app.middleware("http")
async def guvenlik_basliklari_ekle(request: Request, call_next):
    """
    Her yanıta temel güvenlik başlıkları ekler -- özellikle /kullanim-
    sartlari ve /gizlilik-politikasi gibi HTML servis eden uç noktalar için
    (clickjacking / MIME-sniffing / tarayıcı içi XSS'e karşı ek katman).
    Bir API için ağır bir önlem değil, neredeyse bedava bir sıkılaştırma.
    """
    yanit = await call_next(request)
    yanit.headers["X-Content-Type-Options"] = "nosniff"
    yanit.headers["X-Frame-Options"] = "DENY"
    yanit.headers["Referrer-Policy"] = "no-referrer"
    # 2026-08-18 (güvenlik denetimi madde 9): HSTS + basit bir CSP eklendi.
    # HSTS: tarayıcıya bu siteye bir daha asla düz HTTP ile bağlanmamasını
    # söyler (downgrade saldırılarına karşı) -- yerel geliştirmede
    # (localhost, HTTP) tarayıcılar HSTS'yi zaten yok sayar, zararsız;
    # üretimde (HTTPS) faydalı. CSP: sayfanın SADECE kendi kaynağından
    # (aynı origin) script yüklemesine izin verir -- özellikle
    # /kullanim-sartlari, /gizlilik-politikasi ve /admin gibi HTML sayfaları
    # için (dışarıdan enjekte edilebilecek script'lere karşı ek katman).
    #
    # 2026-08-19 DÜZELTMESİ (bulundu: /admin paneli test edilirken):
    # 'default-src' tek başıken 'style-src' için de fallback oluyor, bu da
    # bu üç sayfanın HEPSİNİN kendi <style> bloklarını (satır-içi CSS)
    # SESSİZCE engelliyordu -- yani gizlilik/kullanım şartları sayfaları bu
    # değişiklikten beri (18 Ağustos) hiç fark edilmeden STİLSİZ
    # görünüyordu. 'style-src' ayrıca 'unsafe-inline' ile gevşetildi --
    # bu SADECE CSS'e izin verir, script enjeksiyonuna karşı asıl koruma
    # (script-src/default-src 'self') aynen korunuyor.
    yanit.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    yanit.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' 'unsafe-inline'"
    return yanit

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 2026-08-19 (Render'a taşıma): kalıcı disk bağlıysa (Render'da DATA_DIR=/data
# ortam değişkeni ayarlanacak) veritabanı/PDF'ler/yedekler oradan okunur/
# yazılır -- disk, her yeniden başlatmada/deploy'da SIFIRLANMAYAN tek yer.
# Yerel geliştirmede DATA_DIR hiç ayarlanmadığı için davranış TAMAMEN AYNI
# kalır (VERI_DIZINI = BASE_DIR, eskisi gibi backend/ klasörünün kendisi).
VERI_DIZINI = os.environ.get("DATA_DIR", BASE_DIR)
DB_FILE = os.path.join(VERI_DIZINI, "dosyalar.db")
PDF_KOK_KLASOR = os.path.join(VERI_DIZINI, "pdfs")


def init_db():
    conn = veritabani_baglantisi(DB_FILE)
    tabloyu_hazirla(conn)
    conn.close()


init_db()

# İndirilen PDF'leri doğrudan uygulama üzerinden servis ediyoruz. Amaç:
# kullanıcı bir sonucu gördüğünde, sistemin gerçekten resmi siteden
# indirdiği PDF'i (kendi numarasının geçtiği belgeyi) kendi gözüyle
# görebilsin -- bu hem güven artırır hem de cetatenie.just.ro o an
# erişilemez olsa bile (bkz. yaşadığımız kesinti) kullanıcı yine de
# kendi indirdiğimiz kopyayı görüntüleyebilir.
#
# 2026-08-18 (güvenlik denetimi madde 3 -- BİLİNÇLİ OLARAK anahtarsız
# bırakıldı): /pdfs, diğer /api/* uçları gibi Depends(app_anahtarini_dogrula)
# ile korunmuyor. Denendi ve GERİ ALINDI: app/(tabs)/index.tsx ve
# favorilerim.tsx'teki "Yerel PDF Görüntüle" butonu bu URL'i
# Linking.openURL() ile SİSTEM TARAYICISINDA açıyor -- tarayıcı bizim
# X-App-Key header'ımızı gönderemez, anahtar kontrolü eklenirse bu buton
# her tıklandığında 401 ile kırılır. Ayrıca içerik zaten cetatenie.just.ro'da
# halka açık PDF'lerin birebir kopyası olduğu için kilitlemenin gerçek bir
# güvenlik faydası da yok -- sadece kendi özelliğimizi bozardı. Eğer
# ileride bu buton fetch+kaydet şekline dönüştürülürse (header eklenebilir
# hale gelirse) bu karar yeniden değerlendirilebilir.
os.makedirs(PDF_KOK_KLASOR, exist_ok=True)
app.mount("/pdfs", StaticFiles(directory=PDF_KOK_KLASOR), name="pdfs")

# 2026-08-20 (tanıtım web sayfası): ekran görüntüleri gibi sabit, koda
# gömülü (kullanıcı verisi İÇERMEYEN) statik varlıklar için ayrı bir
# klasör -- PDF_KOK_KLASOR'dan (kullanıcı verisiyle dolu, DATA_DIR'e
# taşınan) BİLEREK ayrı tutuluyor, bu klasör git'e commit'lenip normal
# kod gibi deploy ediliyor.
_STATIK_KLASOR = os.path.join(BASE_DIR, "statik")
if os.path.isdir(_STATIK_KLASOR):
    app.mount("/statik", StaticFiles(directory=_STATIK_KLASOR), name="statik")

# Scheduler kurulumu
scheduler = BackgroundScheduler(timezone=ROMANYA_SAAT_DILIMI)


def run_bot(yeniden_deneme_mi=False):
    """Bot'u çalıştır.

    2026-08-22 KARARI (ARTIK KISMEN GEÇERSİZ, bkz. 2026-09-02 notu):
    Günde SADECE 1 kez, 09:00'da çalışırdı -- PDF bulsun ya da bulmasın,
    aynı gün içinde tekrar denenmezdi. Eskiden (2026-08-17 - 2026-08-22
    arası) site o gün hiç PDF bulunamazsa 6 saat sonra (~15:00) tek bir ek
    deneme daha yapılıyordu; kullanıcı bunun siteyi gereksiz yere ikinci
    kez yorduğunu düşünüp kaldırılmasını istemişti. Site günde 5 kez
    (2 saatte bir) taramayı kötüye kullanım sayıp IP'yi bloke etmişti
    (bkz. 2026-08-15 notu).

    2026-09-02 KARARI: kullanıcı bilinçli olarak günde 2 keze çıkardı
    (11:00 + 15:00, bkz. lifespan() içindeki scheduler.add_job notu) --
    gerekçe: aynı gün eklenen bir PDF'in uygulamada "1 gün geç" görünmesi
    güven sarsıcı bir izlenim riski taşıyor. 5x/gün'e göre hâlâ çok daha
    ölçülü bir sıklık, ama WAF riski YAKINDAN izlenmeli (bkz. hafıza
    notu [[tarama-sikligi-2x-izleme]]) -- sorun belirtisi görülürse 1x'e
    geri dönülecek.

    yeniden_deneme_mi parametresi geriye dönük uyumluluk için duruyor
    (artık hiçbir yerden True ile çağrılmıyor, yeniden deneme
    zamanlanmıyor) -- ileride tekrar istenirse buraya eklenebilir.
    """
    try:
        from bot import botu_calistir
        print(f"\n{'='*60}")
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] BOT OTOMATİK ÇALIŞTIRILDI")
        print(f"{'='*60}")
        toplam_pdf_bulunan = botu_calistir()
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] BOT TAMAMLANDI")

        if not toplam_pdf_bulunan:
            print("  ℹ Site erişilemedi ya da hiç yeni PDF bulunamadı -- bir sonraki deneme bugün/yarın 11:00 ya da 15:00'te.")
    except Exception as e:
        print(f"✗ Bot çalıştırma hatası: {e}")


# ---------------------------------------------------------------------------
# OTOMATİK VERİTABANI YEDEĞİ (2026-08-17, kod taraması sonrası eklendi)
# ---------------------------------------------------------------------------
# dosyalar.db artık ~1GB -- bir bozulma/yanlışlıkla silinme durumunda TÜM
# geçmiş kaybolur, yeniden kurmak saatler sürer (siteyi baştan taramak
# gerekir). Her gece, bot'un ilk taramasından (11:00) ÖNCE (03:00'te),
# sqlite3'ün KENDİ "online backup" API'sini kullanarak (Connection.backup)
# tutarlı bir kopya alınıyor -- bu, DB WAL modundayken bile ÇALIŞAN
# SÜREÇTEN dosyayı elle kopyalamaktan (os.copy) çok daha güvenli, çünkü
# ortasında yazma işlemi olsa bile SQLite bunu kendi içinde senkronize
# ediyor (yarım/bozuk bir kopya riski yok).
YEDEK_KLASOR = os.path.join(VERI_DIZINI, "yedekler")
# 2026-08-23 DÜZELTMESİ: 7 gün X ~1 GB'lık veritabanı = Render'ın kalıcı
# diskinde (10 GB) tek başına ~7 GB'ı yerel yedekler yiyordu -- disk %80.3
# dolulukla kritik uyarı verdi (bkz. sistem_olaylari). B2 bulut yedeği
# (30 gün saklama, Render'dan TAMAMEN bağımsız bir depoda) artık gerçek
# felaket senaryosunu zaten karşılıyor -- yerelde uzun süre tutmanın
# değeri kalmadı. 2 gün, hızlı/basit bir geri yükleme için yine de güncel
# bir yerel kopya bırakıyor, disktekiyse ~5 GB boşaltıyor.
YEDEK_SAKLAMA_GUN_SAYISI = 2  # bundan eski yedekler otomatik silinir (B2'de 30 gün ayrıca saklanıyor)

# ---------------------------------------------------------------------------
# BULUT YEDEKLEME (Backblaze B2) -- 2026-08-22
# ---------------------------------------------------------------------------
# Yukarıdaki yerel yedek Render'ın AYNI diskinde duruyor -- disk tamamen
# kaybolursa/bozulursa yedek de gider. B2, veriyi Render'dan TAMAMEN bağımsız,
# ayrı bir sağlayıcının sunucusunda tutarak gerçek "felaket kurtarma"
# (disaster recovery) katmanı ekliyor. S3-uyumlu API'si olduğu için (boto3
# ile) entegre edildi. B2_* ortam değişkenlerinden biri bile eksikse (ör.
# yerel geliştirmede) bu adım sessizce atlanır -- yerel yedekleme hiç
# etkilenmez, tıpkı SENTRY_DSN deseninde olduğu gibi.
B2_KEY_ID = os.environ.get("B2_KEY_ID")
B2_APPLICATION_KEY = os.environ.get("B2_APPLICATION_KEY")
B2_BUCKET_ADI = os.environ.get("B2_BUCKET_ADI")
B2_ENDPOINT = os.environ.get("B2_ENDPOINT")  # ör. https://s3.us-west-004.backblazeb2.com
B2_SAKLAMA_GUN_SAYISI = 30  # bulutta yerelden daha uzun tutuyoruz -- ucuz, felaket senaryosu için


def b2_yedegini_yukle(yerel_dosya_yolu):
    """Yerel bir yedek dosyasını Backblaze B2'ye yükler, B2_SAKLAMA_GUN_SAYISI'ndan
    eski bulut yedeklerini siler. B2_* ortam değişkenleri ayarlı değilse
    sessizce atlanır -- yerel yedekleme bundan etkilenmez."""
    if not (B2_KEY_ID and B2_APPLICATION_KEY and B2_BUCKET_ADI and B2_ENDPOINT):
        return {"durum": "atlandi", "sebep": "B2_* ortam değişkenleri ayarlı değil"}
    try:
        import boto3
        from botocore.config import Config as _BotoConfig
        from boto3.s3.transfer import TransferConfig as _AktarimAyari

        # 2026-09-02 DUZELTMESI (kullanici canli testte fark etti -- 2 gece
        # ust uste ayni hata): 3 manuel deneme (5sn/15sn bekleme) hep AYNI
        # noktada -- multipart yuklemenin BIRINCI parcasinda -- "Connection
        # was closed before we received a valid response" ile basarisiz
        # oluyordu. ~1GB'lik dosyada boto3'un VARSAYILAN ayarlari (8MB'lik
        # parcalar, dusuk zaman asimi) Render'dan Backblaze'e giden baglanti
        # icin yetersiz kaliyor gibi gorunuyor -- rastgele bir ag sicramasi
        # DEGIL, sistemik bir zaman asimi sorunu (2 farkli gecede de AYNI
        # asamada basarisiz oldu). Cozum: (1) daha uzun connect/read zaman
        # asimlari + botocore'un KENDI SDK-seviyesi retry mekanizmasi
        # (bizim 3 manuel denememizin ICINDE, her denemede ekstra bir
        # guvenlik agi), (2) daha buyuk parca boyutu (25MB) -- 1GB'lik dosya
        # icin ~130 parca yerine ~40 parca, daha az round-trip/basarisizlik
        # firsati, (3) tek seferde 1 parca (concurrency yok) -- baglanti
        # rekabetinin sorunun bir parcasi olma ihtimaline karsi.
        s3 = boto3.client(
            "s3",
            endpoint_url=B2_ENDPOINT,
            aws_access_key_id=B2_KEY_ID,
            aws_secret_access_key=B2_APPLICATION_KEY,
            config=_BotoConfig(
                connect_timeout=60,
                read_timeout=180,
                retries={"max_attempts": 5, "mode": "standard"},
                # 2026-09-02 UCUNCU DUZELTME (canli testte kanitlandi --
                # ilk iki duzeltme YETMEDI): duz/imzasiz istekler ANINDA
                # basariyla donuyordu (0.7sn, dogru 403), sadece boto3'un
                # imzali PUT/POST'u takiliyordu -- bu, yeni botocore
                # surumlerinin (1.36+) S3 istekleri icin VARSAYILAN olarak
                # eklediği checksum trailer/header'larinin Backblaze B2 gibi
                # tam AWS-uyumlu OLMAYAN S3-uyumlu servislerle bilinen bir
                # uyumsuzlugu. "when_required"a dusurmek AWS disi uctan uca
                # uyumlulugu geri getiriyor.
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        )
        # 2026-09-02 IKINCI DUZELTME (canli testte kanitlandi -- ilk
        # duzeltme YETMEDI, ayni hata AYNI noktada devam etti): sorun
        # zaman asimi degil, multipart'in KENDISI gibi gorunuyor --
        # baglanti multipart'in ilk parcasinda TUTARLI sekilde reddediliyor.
        # Esik dosya boyutunun (~1GB) USTUNE cikarilip multipart TAMAMEN
        # devre disi birakildi -- tek parcalik duz PUT denenecek (S3 PUT
        # siniri 5GB, bizim icin cok rahat pay birakiyor).
        _aktarim_ayari = _AktarimAyari(
            multipart_threshold=1024 * 1024 * 1024 * 2,  # 2GB -- fiilen multipart devre disi
            max_concurrency=1,
            use_threads=True,
        )
        dosya_adi = os.path.basename(yerel_dosya_yolu)
        anahtar = f"veritabani-yedekleri/{dosya_adi}"

        # 2026-08-30 DUZELTMESI: 30 Agustos gecesi "Connection was closed
        # before we received a valid response" hatasiyla yedekleme TEK
        # denemede basarisiz oldu ve boyle raporlandi -- upload_file'da hic
        # retry yoktu, gecici bir ag kesintisi butun geceyi "basarisiz"
        # sayiyordu. Simdi 3 deneme, aralarinda artan bekleme (5sn/15sn) --
        # her Backblaze/B2 aginin GECICI bir kesintisi butun geceyi
        # kaybettirmesin diye. cetatenie.just.ro'ya sıklık artirmiyoruz
        # (o kural hala gecerli) -- bu SADECE bizim Backblaze baglantimiz.
        son_hata = None
        for deneme in range(1, 4):
            try:
                s3.upload_file(yerel_dosya_yolu, B2_BUCKET_ADI, anahtar, Config=_aktarim_ayari)
                son_hata = None
                break
            except Exception as e:
                son_hata = e
                if deneme < 3:
                    bekleme = 5 * deneme
                    print(f"⚠️  B2 yükleme denemesi {deneme}/3 başarısız ({str(e)[:80]}), {bekleme}sn sonra tekrar...")
                    time.sleep(bekleme)
        if son_hata is not None:
            raise son_hata
        print(f"✓ Bulut (B2) yedeği yüklendi: {anahtar}")

        silinen = []
        sinir_zamani = datetime.now(timezone.utc) - timedelta(days=B2_SAKLAMA_GUN_SAYISI)
        sayfalayici = s3.get_paginator("list_objects_v2")
        for sayfa in sayfalayici.paginate(Bucket=B2_BUCKET_ADI, Prefix="veritabani-yedekleri/"):
            for nesne in sayfa.get("Contents", []):
                if nesne["LastModified"] < sinir_zamani:
                    s3.delete_object(Bucket=B2_BUCKET_ADI, Key=nesne["Key"])
                    silinen.append(nesne["Key"])
                    print(f"  (eski bulut yedeği silindi: {nesne['Key']})")
        return {"durum": "basarili", "anahtar": anahtar, "silinen_eski_yedekler": silinen}
    except ImportError:
        print("⚠️  B2_* ayarlı ama boto3 paketi kurulu değil -- bulut yedekleme devre dışı.")
        return {"durum": "atlandi", "sebep": "boto3 kurulu değil"}
    except Exception as e:
        print(f"✗ Bulut (B2) yedekleme hatası: {e}")
        try:
            from bildirim import admin_kritik_uyari
            admin_kritik_uyari(f"Bulut (B2) yedeği yüklenemedi: {e}")
        except Exception:
            pass
        return {"durum": "hata", "mesaj": str(e)}


def veritabani_yedekle():
    """dosyalar.db'nin tutarlı bir kopyasını yedekler/ klasörüne alır,
    YEDEK_SAKLAMA_GUN_SAYISI'ndan eski yedekleri siler, ardından
    b2_yedegini_yukle() ile buluta yükler."""
    try:
        os.makedirs(YEDEK_KLASOR, exist_ok=True)
        zaman_damgasi = datetime.now().strftime("%Y-%m-%d_%H-%M")
        hedef_yol = os.path.join(YEDEK_KLASOR, f"dosyalar_{zaman_damgasi}.db")

        kaynak_conn = sqlite3.connect(DB_FILE)
        hedef_conn = sqlite3.connect(hedef_yol)
        with hedef_conn:
            kaynak_conn.backup(hedef_conn)
        hedef_conn.close()
        kaynak_conn.close()

        boyut_mb = os.path.getsize(hedef_yol) / (1024 * 1024)
        print(f"✓ Veritabanı yedeği alındı: {hedef_yol} ({boyut_mb:.1f} MB)")

        # 2026-08-22: Yerel yedek Render'ın AYNI diskinde -- disk tamamen
        # kaybolursa/bozulursa bu da giderdi. Ayrıca, Render'dan bağımsız,
        # bulutta ikinci bir kopya dene (B2_* ayarlı değilse sessizce atlanır).
        b2_sonucu = b2_yedegini_yukle(hedef_yol)

        # Eski yedekleri temizle (sadece son YEDEK_SAKLAMA_GUN_SAYISI günü tut).
        sinir_zamani = time.time() - (YEDEK_SAKLAMA_GUN_SAYISI * 24 * 60 * 60)
        for dosya_adi in os.listdir(YEDEK_KLASOR):
            if not dosya_adi.startswith("dosyalar_") or not dosya_adi.endswith(".db"):
                continue
            tam_yol = os.path.join(YEDEK_KLASOR, dosya_adi)
            if os.path.getmtime(tam_yol) < sinir_zamani:
                os.remove(tam_yol)
                print(f"  (eski yedek silindi: {dosya_adi})")
        return b2_sonucu
    except Exception as e:
        print(f"✗ Veritabanı yedekleme hatası: {e}")
        try:
            # run_bot()'taki gibi lazy import -- döngüsel import riskini
            # önler. admin_kritik_uyari'nin gerçek tanımı bildirim.py'de
            # (bot.py da oradan import ediyor, bkz. bot.py satır 86).
            from bildirim import admin_kritik_uyari
            admin_kritik_uyari(f"Otomatik veritabanı yedeği alınamadı: {e}")
        except Exception:
            pass  # admin uyarısı bile başarısız olursa yedekleme sürecini bozmasın


# ---------------------------------------------------------------------------
# DİSK KOTASI İZLEME (2026-08-19, Render taşıması sonrası ele alındı)
# ---------------------------------------------------------------------------
# Render'daki kalıcı disk sabit boyutlu (10GB) -- veri (DB + PDF'ler) sürekli
# büyüdüğü için bir gün doldurabilir, dolarsa yeni PDF indirilemez/DB
# yazmaları başarısız olur. Önceden hiçbir eşik-uyarı mekanizması yoktu.
# Her gün 06:00'da (yedekleme 03:00, ilk tarama 11:00 -- arada, çakışma
# yok) gerçek dosya sistemi doluluk oranı kontrol ediliyor.
DISK_UYARI_ESIK_YUZDE = 80  # bu oranın üstünde günlük kritik uyarı gönderilir


def disk_kotasi_kontrol_et():
    try:
        toplam, kullanilan, bos = shutil.disk_usage(VERI_DIZINI)
        if not toplam:
            return
        yuzde = kullanilan / toplam * 100
        bos_gb = bos / (1024 ** 3)
        if yuzde >= DISK_UYARI_ESIK_YUZDE:
            from bildirim import admin_kritik_uyari  # lazy import, bkz. veritabani_yedekle() notu
            admin_kritik_uyari(
                f"Disk kullanımı %{yuzde:.1f} -- sadece {bos_gb:.2f} GB boş alan kaldı. "
                f"Render panelinden diski büyütmeyi düşün (Disks -> Resize)."
            )
        else:
            print(f"✓ Disk kotası kontrolü: %{yuzde:.1f} dolu, {bos_gb:.2f} GB boş (eşik: %{DISK_UYARI_ESIK_YUZDE}).")
    except Exception as e:
        print(f"✗ Disk kotası kontrolü hatası: {e}")


# 2026-08-18: eski @app.on_event("startup"/"shutdown") -- FastAPI'de
# deprecated, ileride tamamen kaldırılacak (bkz. DeprecationWarning).
# Yerine önerilen "lifespan" context manager kullanılıyor. ÖNEMLİ: bu
# fonksiyon, üstünde durduğu `app = FastAPI()` satırından (yukarıda, çok
# daha erken) SONRA tanımlanıyor -- bu sorun değil, çünkü Python fonksiyon
# GÖVDESİNİ (scheduler/run_bot/veritabani_yedekle isimlerini) sadece
# fonksiyon ÇAĞRILDIĞINDA çözer, tanımlandığı anda değil. `app`'a bağlamak
# için de constructor'a taşımak yerine `app.router.lifespan_context`'e
# atama yapılıyor (Starlette'in desteklediği, dosyanın baştan aşağı
# yeniden düzenlenmesini gerektirmeyen bir yöntem).
@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Uygulama başlarken scheduler'ı kur, kapanırken durdur."""
    # 2026-08-15: cetatenie.just.ro, günde 5 kez (08-17 arası 2 saatte bir)
    # yapılan taramayı kötüye kullanım sayıp IP adresini bloke etti. Bu
    # yüzden sıklık günde SADECE 1 keze düşürülmüştü. Ayrıca bot.py artık
    # zaten indirilmiş/işlenmiş PDF'leri tekrar taramıyor (bkz. bot.py
    # "2026-08-15" notları), bu da her çalıştırmadaki toplam istek/süreyi
    # ciddi ölçüde azaltıyor.
    #
    # 2026-09-02 KARARI (kullanıcı, bilinçli): günde 2 keze çıkarıldı
    # (11:00 + 15:00) -- gerekçe: bir kullanıcı aynı gün içinde sitede yeni
    # eklenen bir PDF'i görüp uygulamada bulamazsa "uygulama geride kalıyor/
    # dandik" izlenimi oluşabilir, bu riski azaltmak öncelikli görüldü.
    # 5x/gün'e göre (banın gerçekleştiği sıklık) hâlâ çok daha ölçülü.
    # BİLİNÇLİ RİSK: ilk birkaç hafta Gece Nöbeti'nin "Günlük Tarama"
    # durumu YAKINDAN izlenmeli -- WAF/erişim sorunu belirtisi görülürse
    # (bkz. [[tarama-sikligi-2x-izleme]] hafıza notu) hemen 1x/gün'e
    # geri dönülecek.
    scheduler.add_job(
        run_bot,
        'cron',
        hour='11',
        minute='0',
        id='pdf_downloader_1',
        name='PDF Downloader Bot (1. tarama)'
    )
    scheduler.add_job(
        run_bot,
        'cron',
        hour='15',
        minute='0',
        id='pdf_downloader_2',
        name='PDF Downloader Bot (2. tarama)'
    )
    # 2026-08-17: otomatik veritabanı yedeği, taramalardan ÖNCE (03:00'te,
    # gece en sakin saat) alınıyor -- bkz. veritabani_yedekle().
    scheduler.add_job(
        veritabani_yedekle,
        'cron',
        hour='3',
        minute='0',
        id='db_yedekleme',
        name='Veritabanı Yedekleme'
    )
    # 2026-08-19: disk kotası izleme -- yedekleme (03:00) ile ilk tarama
    # (11:00) arasında, gün içinde tek sefer kontrol ediyor.
    scheduler.add_job(
        disk_kotasi_kontrol_et,
        'cron',
        hour='6',
        minute='0',
        id='disk_kota_kontrolu',
        name='Disk Kotası Kontrolü'
    )
    scheduler.start()
    print(f"\n✓ Scheduler başlatıldı!")
    print(f"✓ Bot: Her gün 11:00 ve 15:00'te çalışacak (2026-09-02 kararı, WAF riski nedeniyle yakından izleniyor)")
    print(f"✓ Yedekleme: Her gün 03:00'te otomatik veritabanı yedeği alınacak (son {YEDEK_SAKLAMA_GUN_SAYISI} gün saklanır)")
    print(f"✓ Sonraki çalışma: Zamanı gelince otomatik çalışır\n")

    yield

    scheduler.shutdown()
    print("✓ Scheduler durduruldu.")


app.router.lifespan_context = lifespan


# 2026-08-15 (güvenlik sıkılaştırması): tüm alanlara üst uzunluk sınırı
# eklendi -- öncesinde 'dosya_no' gibi alanlar sınırsızdı, kötü niyetli bir
# istemci çok büyük gövdeli istekler göndererek gereksiz iş yükü
# yaratabilirdi. Gerçek dosya numaraları en fazla birkaç düzine karakter,
# 100 payı fazlasıyla yeterli.
class SorguIstegi(BaseModel):
    dosya_no: str = Field(max_length=100)
    yil: Optional[str] = Field(default=None, max_length=10)
    ana_kategori: Optional[str] = Field(default=None, max_length=20)   # 'stadiu' | 'ordine'
    alt_kategori: Optional[str] = Field(default=None, max_length=100)
    # 2026-08-17 EKLENTİSİ (kullanıcı isteği: "favori eklemek bildirim
    # şartı olmasın"): verilirse, eşleşen ve henüz onaylanmamış sonuçlar
    # için OTOMATİK bir arka plan izleme kaydı oluşturulur -- kullanıcının
    # ayrıca "Favorilere Ekle" demesine gerek kalmadan, sorguladığı numara
    # onaylandığında bildirim alır (bkz. sorgula() fonksiyonunun sonu).
    cihaz_kimligi: Optional[str] = Field(default=None, max_length=200)


@app.get("/", response_class=HTMLResponse)
def root():
    """
    2026-08-20 (kullanıcı isteği): önceden burada sadece boş bir sağlık
    kontrolü JSON'u vardı, hiçbir işe yaramıyordu. Artık gerçek bir tanıtım
    (landing) sayfası -- Instagram'da paylaşılabilir, Play Console'un
    "web sitesi" alanına girilebilir. Mobil uygulamanın kullandığı sağlık
    kontrolü BAŞKA bir adreste (/api/durum), bu değişiklik ona dokunmuyor.

    2026-08-26 DÜZELTMESİ: Önceden bu fonksiyon önbelleği SADECE okuyordu --
    doldurma işi tamamen /api/istatistikler/genel'i çağıran mobil uygulama
    trafiğine bağlıydı. Kapalı test aşamasında mobil kullanıcı sayısı çok
    az olduğu için önbellek her sunucu yeniden başlatmasından (deploy)
    sonra SAATLERCE boş kalıyordu -- kullanıcı web sayfasını her
    yenilediğinde rakamları hiç göremiyordu. Artık /api/istatistikler/genel
    ile AYNI önbelleği, AYNI TTL mantığıyla (30dk) burada da dolduruyoruz --
    ilk istek (ya da 30dk'da bir) hafif bir DB gecikmesi (yerelde <2sn,
    ana_kategori+yil kapsayan idx_dosya_ana_norm_yil indeksi sayesinde)
    pahasına, rakamlar artık sunucu yeniden başlasa bile ilk ziyaretçide
    dolduruluyor.
    """
    simdi = time.time()
    onbellek = _genel_istatistik_onbellek
    if onbellek["veri"] is None or (simdi - onbellek["zaman"]) > _ISTATISTIK_ONBELLEK_SURESI_SN:
        onbellek["veri"] = _genel_istatistikleri_hesapla()
        onbellek["zaman"] = simdi
    veri = onbellek["veri"]
    if veri:
        return tanitim_sayfasi_html(
            toplam_stadiu=veri["toplam_stadiu"],
            toplam_onay=veri["toplam_onaylanan"],
            toplam_bekleyen=veri["toplam_bekleyen"],
        )
    return tanitim_sayfasi_html()


# 2026-08-23 EKLENTİSİ: Kullanıcı Google'da site adını aratınca hiç
# indekslenmediğimizi fark etti (rakip bir reklam çıkıyor, Google'ın "AI
# Bakışı" da bizi tanımadığı için "resmi olmayan/bireysel test projesi"
# diye tahmin yürütüyordu). Kök neden: site HİÇ Google'a bildirilmemiş --
# ne robots.txt/sitemap.xml vardı, ne Search Console'a kayıtlıydı. Bu
# ikisi, arama motorlarının siteyi keşfetmesi için asgari/standart adım --
# tek başına indekslenmeyi garanti etmez ama önkoşuludur.
_SITE_KOK = "https://romanya-dosya-takip.onrender.com"


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt():
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin\n"
        "Disallow: /api/\n"
        f"Sitemap: {_SITE_KOK}/sitemap.xml\n"
    )


@app.get("/sitemap.xml", response_class=Response)
def sitemap_xml():
    sayfalar = ["/", "/gizlilik-politikasi", "/kullanim-sartlari"]
    ogeler = "".join(f"<url><loc>{_SITE_KOK}{yol}</loc></url>" for yol in sayfalar)
    icerik = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{ogeler}</urlset>'
    return Response(content=icerik, media_type="application/xml")


def _mesai_saatinde_mi() -> bool:
    """Mesai saatleri: 08:00-17:59. Bu aralığın dışında resmi site planlı
    bakım moduna girebiliyor -- bu yüzden mesai dışı erişim sorunları
    "olağan dışı bir kesinti" sayılıp ne admin'e ne de uygulama
    kullanıcılarına bildirilmez, sadece mesai saatleri içinde yaşanan
    kesintiler bildirilir (kullanıcının 2026-08-14 talebi)."""
    return 8 <= datetime.now(ROMANYA_SAAT_DILIMI).hour <= 17


def _son_basarili_tarama_oku() -> Optional[str]:
    """
    bot.py'nin her taramanın sonunda yazdığı zaman damgasını okur (bkz.
    bot.py son satırları). 2026-08-15: kullanıcı isteğiyle eklendi --
    "servis dışı" banner'ı kaygı verici durabiliyor, yanına "verileriniz
    en son ne zaman güncellendi" bilgisini eklemek için. Dosya yoksa
    (bot hiç çalışmadıysa) None döner, mobil taraf bu durumda ek metni
    hiç göstermez.
    """
    # 2026-08-19 DÜZELTMESİ: bkz. bot.py'deki aynı isimli dosyanın notu --
    # artık VERI_DIZINI'nden (Render'da kalıcı disk) okunuyor, BASE_DIR
    # (kod klasörü, Render'da her deploy'da sıfırlanıyordu) değil.
    yol = os.path.join(VERI_DIZINI, "son_basarili_tarama.txt")
    if not os.path.isfile(yol):
        return None
    try:
        with open(yol, "r", encoding="utf-8") as f:
            return f.read().strip() or None
    except Exception:
        return None



# Bot'un günlük taraması (2026-09-02'den beri 11:00 VE 15:00, bkz. run_bot
# notu) normal koşullarda o saatlerde biter. Bu eşik, güvenli bir aralığa
# cömert bir pay ekliyor (tatil/hafta sonu gecikmeleri, sunucu yeniden
# başlatmaları vb. için) -- 2x/gün'e geçişle daha da rahat bir pay oldu.
SON_TARAMA_TAZELIK_ESIGI_SAAT = 30


@app.get("/api/durum")
def site_durumu():
    """Mobil uygulamanın ana ekranında gösterilecek küçük banner için resmi
    kaynağın (cetatenie.just.ro) erişilebilir olup olmadığını bildirir.

    2026-08-18 (canlı hata düzeltmesi -- kullanıcı bildirdi: "ben siteye
    giriyorum ama uygulama servis dışı diyor"): Bu kontrol önceden CANLI bir
    HTTP isteği (`requests.get`) atıp anlık durumu ölçüyordu. cetatenie.
    just.ro'nun bot-engelleme sistemi (bkz. bot.py "2026-08-14 tespiti"
    notu) JavaScript ÇALIŞTIRAN bir tarayıcı doğrulaması (WAF/Cloudflare
    tarzı bir "challenge") gerektiriyor -- ne düz `requests` ne de
    `curl_cffi` (TLS parmak izi taklidi) bunu geçebiliyor, sadece bot.py'nin
    zaten kullandığı GERÇEK bir tarayıcı (Playwright) geçebiliyor. Yani bu
    canlı kontrol, site TAMAMEN AÇIKKEN BİLE her zaman "servis dışı"
    gösteriyordu -- yanlış pozitifti (doğrulandı: hem düz requests hem
    curl_cffi ile elle test edildi, ikisi de site açıkken 503 aldı).
    Her istekte tam bir Playwright tarayıcısı açmak da (her uygulama
    açılışında) sunucuyu gereksiz yere çok yorar.
    Çözüm: canlı kontrol tamamen kaldırıldı. Bunun yerine, bot.py'nin GERÇEK
    (Playwright ile başarılı) son taramasının ne kadar TAZE olduğuna
    bakılıyor -- bu zaten sitenin o taramada erişilebilir olduğunun somut
    kanıtı. Tarama çok eskiyse (SON_TARAMA_TAZELIK_ESIGI_SAAT'ten fazla,
    yani günlük taramanın art arda birkaç kez başarısız olduğu anlamına
    gelir) "servis dışı" gösterilir.
    """
    son_guncelleme = _son_basarili_tarama_oku()

    if not _mesai_saatinde_mi():
        return {"servis_disi": False, "banner_mesaji": None, "son_guncelleme": son_guncelleme}

    servis_disi = True
    if son_guncelleme:
        try:
            tarama_zamani = datetime.fromisoformat(son_guncelleme)
            # bot.py artık saat dilimi BİLGİSİYLE (+03:00 gibi) yazıyor --
            # eski yedeklerden kalma saat dilimsiz (naive) bir değer
            # gelirse (ör. bu düzeltmeden önce yazılmış dosya), Romanya
            # saatiymiş gibi kabul edip devam ediyoruz, çökmüyoruz.
            if tarama_zamani.tzinfo is None:
                tarama_zamani = tarama_zamani.replace(tzinfo=ROMANYA_SAAT_DILIMI)
            gecen_saat = (datetime.now(ROMANYA_SAAT_DILIMI) - tarama_zamani).total_seconds() / 3600
            servis_disi = gecen_saat > SON_TARAMA_TAZELIK_ESIGI_SAAT
        except Exception:
            servis_disi = False  # bozuk/okunamayan zaman damgasında güvenli tarafta kal

    if not servis_disi:
        return {"servis_disi": False, "banner_mesaji": None, "son_guncelleme": son_guncelleme}
    return {
        "servis_disi": True,
        "banner_mesaji": "cetatenie.just.ro resmi web sayfası şuanda servis dışıdır.",
        "son_guncelleme": son_guncelleme,
    }


@app.get("/kullanim-sartlari", response_class=HTMLResponse)
def kullanim_sartlari():
    return sayfa_html("Kullanım Şartları", KULLANIM_SARTLARI_METIN)


@app.get("/gizlilik-politikasi", response_class=HTMLResponse)
def gizlilik_politikasi():
    return sayfa_html("Gizlilik Politikası", GIZLILIK_POLITIKASI_METIN)


@app.get("/api/hukuki-metin/kullanim-sartlari", response_class=PlainTextResponse)
def kullanim_sartlari_duz_metin():
    """Mobil uygulamanın açılış onay modalında göstermesi için düz metin."""
    return KULLANIM_SARTLARI_METIN


@app.get("/admin", response_class=HTMLResponse)
def admin_paneli(request: Request):
    """
    2026-08-19: SADECE proje sahibi için, kullanım istatistiklerini gösteren
    salt-okunur bir sayfa (bkz. admin_panel.py başındaki kapsam notu).
    Mobil uygulamanın hiçbir özelliği bu uç noktaya bağımlı değil.

    2026-08-23: Basic Auth yerine imzalı çerez kontrolü -- geçersizse
    (401 JSON döndürüp tarayıcıya çirkin bir hata göstermek yerine) düzgün
    bir giriş sayfasına yönlendiriyoruz.
    """
    if not _admin_oturum_dogrula(request):
        return RedirectResponse(url="/admin/giris", status_code=303)
    conn = veritabani_baglantisi(DB_FILE)
    try:
        metrikler = metrikleri_hesapla(conn, DB_FILE, _son_basarili_tarama_oku())
    finally:
        conn.close()
    return admin_sayfa_html(metrikler)


@app.get("/admin/tarama-gecmisi", response_class=HTMLResponse)
def admin_tarama_gecmisi(request: Request):
    """2026-09-02 (kullanıcı isteği): günlük taramalarda hangi kategoride/
    hangi PDF'te kaç yeni kayıt bulunduğunu geriye dönük gösteren sayfa."""
    if not _admin_oturum_dogrula(request):
        return RedirectResponse(url="/admin/giris", status_code=303)
    conn = veritabani_baglantisi(DB_FILE)
    try:
        taramalar = tarama_gecmisi_verisini_getir(conn)
    finally:
        conn.close()
    return tarama_gecmisi_html(taramalar)


@app.get("/admin/giris", response_class=HTMLResponse)
def admin_giris_sayfasi(hata: Optional[str] = None):
    return admin_giris_html(hata=bool(hata))


@app.post("/admin/giris")
@limiter.limit("10/minute")
def admin_giris_gonder(
    request: Request,
    kullanici_adi: str = Form(...),
    sifre: str = Form(...),
):
    if not (ADMIN_SIFRE and ADMIN_OTURUM_ANAHTARI):
        raise HTTPException(status_code=503, detail="Admin paneli devre dışı.")
    kullanici_dogru = secrets.compare_digest(kullanici_adi, ADMIN_KULLANICI_ADI)
    sifre_dogru = secrets.compare_digest(sifre, ADMIN_SIFRE)
    if not (kullanici_dogru and sifre_dogru):
        print("! Admin paneli: başarısız giriş denemesi.")
        return RedirectResponse(url="/admin/giris?hata=1", status_code=303)
    son_gecerlilik_ts = int(time.time()) + ADMIN_OTURUM_GECERLILIK_SN
    yanit = RedirectResponse(url="/admin", status_code=303)
    yanit.set_cookie(
        key=ADMIN_OTURUM_COOKIE_ADI,
        value=_admin_oturum_imzala(son_gecerlilik_ts),
        max_age=ADMIN_OTURUM_GECERLILIK_SN,
        httponly=True,
        secure=ADMIN_OTURUM_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    return yanit


@app.get("/admin/cikis")
def admin_cikis():
    yanit = RedirectResponse(url="/admin/giris", status_code=303)
    yanit.delete_cookie(ADMIN_OTURUM_COOKIE_ADI, path="/")
    return yanit


@app.get("/admin/manifest.json")
def admin_manifest():
    """2026-08-23 EKLENTİSİ: kullanıcı telefondan "Ana ekrana ekle" dediğinde
    tarayıcı çubuğu olmadan, kendi ikonuyla, uygulama gibi açılsın diye
    (PWA -- Progressive Web App). Sayfanın kendisi/tasarımı DEĞİŞMİYOR,
    sadece telefona "bunu bir uygulama gibi kur" bilgisini veriyor."""
    return {
        "name": "Romanya Dosya Takip — Admin",
        "short_name": "RDT Admin",
        "start_url": "/admin",
        "scope": "/admin",
        "display": "standalone",
        "background_color": "#0f1a2e",
        "theme_color": "#0f1a2e",
        "icons": [
            {"src": "/statik/admin/icon-1024.png", "sizes": "1024x1024", "type": "image/png", "purpose": "any"},
            {"src": "/statik/admin/icon-1024.png", "sizes": "1024x1024", "type": "image/png", "purpose": "maskable"},
        ],
    }


@app.get("/admin/sw.js")
def admin_service_worker():
    """2026-08-30 (Gece Nobeti -- Faz 1): Web Push almak icin sart olan
    service worker. /admin altinda servis ediliyor ki push kapsami (scope)
    manifest.json'daki "/admin" ile eslessin -- /statik altinda olsaydı
    varsayilan kapsami /statik/admin/ olurdu, /admin sayfasini KAPSAMAZDI.
    Sir icermez, kimlik dogrulama gerekmiyor (manifest.json ile ayni mantik).
    """
    icerik = """
self.addEventListener('push', function (olay) {
  var veri = {};
  try { veri = olay.data ? olay.data.json() : {}; } catch (e) { veri = {}; }
  var baslik = veri.baslik || 'Romanya Dosya Takip';
  var secenekler = {
    body: veri.govde || '',
    icon: '/statik/admin/icon-1024.png',
    badge: '/statik/admin/icon-1024.png',
    tag: veri.etiket || 'nobetci',
    data: { url: veri.url || '/admin' },
  };
  olay.waitUntil(self.registration.showNotification(baslik, secenekler));
});

self.addEventListener('notificationclick', function (olay) {
  olay.notification.close();
  var hedefUrl = (olay.notification.data && olay.notification.data.url) || '/admin';
  olay.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (pencereler) {
      for (var i = 0; i < pencereler.length; i++) {
        if (pencereler[i].url.indexOf(hedefUrl) !== -1 && 'focus' in pencereler[i]) {
          return pencereler[i].focus();
        }
      }
      if (clients.openWindow) return clients.openWindow(hedefUrl);
    })
  );
});
"""
    return Response(content=icerik, media_type="application/javascript")


@app.get("/api/admin/push-genel-anahtar")
def admin_push_genel_anahtar(_giris=Depends(admin_girisini_dogrula)):
    """Faz 1: tarayicinin PushManager.subscribe({applicationServerKey: ...})
    cagrisi icin VAPID genel anahtarini doner. Genel anahtar SIR degil ama
    admin oturumu arkasinda tutuluyor -- panel disina hicbir sey acik
    olmasin diye (defense in depth, zorunlu degil)."""
    if not VAPID_GENEL_ANAHTAR:
        return {"etkin": False, "genel_anahtar": None}
    return {"etkin": True, "genel_anahtar": VAPID_GENEL_ANAHTAR}


class NobetciPushAbonelikIstegi(BaseModel):
    """2026-08-30 (Gece Nobeti -- Faz 1): tarayicinin PushManager.subscribe()
    cagrisindan donen PushSubscription nesnesinin JSON hali -- endpoint
    tarayicinin push servisine ait benzersiz URL, p256dh/auth ise sifreleme
    icin gereken anahtarlar (bkz. nobetci_push_abonelikleri tablosu).
    ONEMLI: bu sinif, onu kullanan route'tan ONCE tanimli olmali -- Python
    3.14'te (PEP 649, lazy annotations) tanim SONRA gelirse FastAPI modeli
    coz(e)meyip parametreyi SESSIZCE query parametresine cevirip 422
    donuyordu (2026-08-30'da canli testte yakalandi)."""
    endpoint: str = Field(max_length=2000)
    p256dh: str = Field(max_length=300)
    auth: str = Field(max_length=300)


@app.post("/api/admin/push-abone-ol")
def admin_push_abone_ol(istek: NobetciPushAbonelikIstegi, _giris=Depends(admin_girisini_dogrula)):
    """Faz 1: tarayicidan gelen PushSubscription'i kaydeder. Ayni endpoint
    tekrar abone olursa (ör. anahtar yenilendi) INSERT OR REPLACE ile
    guncellenir -- endpoint UNIQUE oldugu icin eski satirin uzerine yazar."""
    conn = veritabani_baglantisi(DB_FILE)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO nobetci_push_abonelikleri (endpoint, p256dh, auth) "
            "VALUES (?, ?, ?)",
            (istek.endpoint, istek.p256dh, istek.auth),
        )
        conn.commit()
    finally:
        conn.close()
    return {"basarili": True}


@app.post("/api/admin/push-test-gonder")
def admin_push_test_gonder(_giris=Depends(admin_girisini_dogrula)):
    """Faz 1: kayitli tum aboneliklere bir test bildirimi gonderir --
    Faz 1'in "gercekten telefonuma ulasiyor mu" kanitidir. 410/404 donen
    (kullanici bildirimleri kapatmis/uygulamayi kaldirmis) abonelikler
    kalici olarak gecersiz sayilir ve tablodan silinir."""
    if not (VAPID_OZEL_ANAHTAR and VAPID_ILETISIM_EPOSTA):
        raise HTTPException(status_code=503, detail="VAPID anahtarlari ayarlanmamis.")

    conn = veritabani_baglantisi(DB_FILE, row_factory=sqlite3.Row)
    try:
        satirlar = conn.execute(
            "SELECT id, endpoint, p256dh, auth FROM nobetci_push_abonelikleri"
        ).fetchall()
    finally:
        conn.close()

    if not satirlar:
        return {"gonderildi": 0, "silindi": 0, "basarisiz": 0, "detay": "Kayitli abonelik yok."}

    veri = json.dumps({
        "baslik": "🔦 Gece Nöbeti — test bildirimi",
        "govde": "Bu bildirimi görüyorsanız Web Push altyapısı çalışıyor.",
        "etiket": "nobetci-test",
        "url": "/admin",
    })

    gonderildi = silindi = basarisiz = 0
    conn = veritabani_baglantisi(DB_FILE)
    try:
        for satir in satirlar:
            abonelik_bilgisi = {
                "endpoint": satir["endpoint"],
                "keys": {"p256dh": satir["p256dh"], "auth": satir["auth"]},
            }
            try:
                webpush(
                    subscription_info=abonelik_bilgisi,
                    data=veri,
                    vapid_private_key=VAPID_OZEL_ANAHTAR,
                    vapid_claims={"sub": VAPID_ILETISIM_EPOSTA},
                    # 2026-08-30: Urgency olmadan push servisi (FCM) mesaji
                    # pil tasarrufu icin erteleyebiliyor -- kullanici testte
                    # "sayfayi yenilemeden bildirim gelmiyor" diye bildirdi.
                    # "high" ile push servisine "hemen teslim et, erteleme"
                    # sinyali veriliyor (RFC 8030 Urgency header).
                    headers={"Urgency": "high"},
                    timeout=10,
                )
                gonderildi += 1
            except WebPushException as e:
                durum_kodu = e.response.status_code if e.response is not None else None
                if durum_kodu in (404, 410):
                    conn.execute("DELETE FROM nobetci_push_abonelikleri WHERE id = ?", (satir["id"],))
                    silindi += 1
                else:
                    basarisiz += 1
                    print(f"! Nobetci push gonderilemedi (id={satir['id']}): {e}")
        conn.commit()
    finally:
        conn.close()

    return {"gonderildi": gonderildi, "silindi": silindi, "basarisiz": basarisiz}


@app.get("/api/admin/bugunun-durumu", response_class=HTMLResponse)
def admin_bugunun_durumu(_giris=Depends(admin_girisini_dogrula)):
    """2026-08-22: /admin sayfasının ayrı, ASENKRON yüklenen parçası --
    bkz. bugunun_durumu_html_getir() içindeki gerekçe notu. Bu uç, sayfanın
    kendisi tamamen açıldıktan SONRA tarayıcıdan JS ile çağrılıyor, bu
    yüzden Render/Sentry/B2/GitHub'a atılan canlı isteklerin (onlarca
    saniye sürebiliyor) tüm sayfayı bloke etmesi artık mümkün değil."""
    conn = veritabani_baglantisi(DB_FILE)
    try:
        return bugunun_durumu_html_getir(conn, _son_basarili_tarama_oku())
    finally:
        conn.close()


@app.post("/api/admin/_gecici_b2_test")
def _gecici_b2_test(_yetki=Depends(nobetci_anahtarini_dogrula)):
    """2026-09-02 GECICI TESHIS UCU -- Backblaze multipart zaman asimi
    duzeltmesini gerce 03:00'i beklemeden canli dogrulamak icin. Senkron
    calisir (istek birkac dakika surebilir, ~1GB'lik DB kopyalaniyor +
    yukleniyor) -- dogrulama biter bitmez KALDIRILACAK."""
    sonuc = veritabani_yedekle()
    return {"sonuc": sonuc}


@app.post("/api/admin/_gecici_b2_ham_baglanti_testi")
def _gecici_b2_ham_baglanti_testi(_yetki=Depends(nobetci_anahtarini_dogrula)):
    """2026-09-02 GECICI TESHIS UCU -- boto3'u devre disi birakip DUZ bir
    HTTP istegiyle B2_ENDPOINT'e (TCP/TLS seviyesinde) gercekten
    ulasilabiliyor mu diye bakar."""
    import requests as _requests
    sonuclar = {}
    try:
        r = _requests.get(B2_ENDPOINT, timeout=15)
        sonuclar["duz_get"] = {"durum_kodu": r.status_code, "govde_ilk_200": r.text[:200]}
    except Exception as e:
        sonuclar["duz_get"] = {"hata": str(e)[:300]}
    try:
        r2 = _requests.head(f"{B2_ENDPOINT}/{B2_BUCKET_ADI}", timeout=15)
        sonuclar["bucket_head"] = {"durum_kodu": r2.status_code}
    except Exception as e:
        sonuclar["bucket_head"] = {"hata": str(e)[:300]}
    return sonuclar


@app.post("/api/admin/_gecici_b2_kucuk_test")
def _gecici_b2_kucuk_test(_yetki=Depends(nobetci_anahtarini_dogrula)):
    """2026-09-02 GECICI TESHIS UCU -- sorunun BUYUK dosyaya mi yoksa
    genel B2 baglantisina mi ozgu oldugunu ayirt etmek icin, sadece
    birkac baytlik minik bir test dosyasi yukler."""
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("test")
        gecici_yol = f.name
    try:
        sonuc = b2_yedegini_yukle(gecici_yol)
    finally:
        os.remove(gecici_yol)
    return {"sonuc": sonuc}


@app.get("/api/admin/saglik-kontrolu")
def admin_saglik_kontrolu(_yetki=Depends(nobetci_anahtarini_dogrula)):
    """Gece Nobeti (7/24 izleme, 2026-08-30) icin makineler-arasi saglik
    ucu -- admin oturum cerezi DEGIL, ayri bir statik anahtar
    (NOBETCI_ANAHTARI) ister, cunku GitHub Actions gibi bir zamanlayici
    tarayici oturumu tutamaz. bugunun_durumu_html_getir ile AYNI veriyi
    (bugunun_durumu_verisini_getir uzerinden) JSON olarak dondurur --
    Faz 2'de GitHub Actions bu ucu duzenli araliklarla cagirip durum
    degisikliginde (iyi -> uyari/hata) push bildirimi tetikleyecek."""
    conn = veritabani_baglantisi(DB_FILE)
    try:
        durumlar = bugunun_durumu_verisini_getir(conn, _son_basarili_tarama_oku())
    finally:
        conn.close()

    genel_durum = "iyi"
    for d in durumlar:
        if d["durum"] == "hata":
            genel_durum = "hata"
            break
        if d["durum"] == "uyari":
            genel_durum = "uyari"

    return {
        "genel_durum": genel_durum,
        "kontroller": durumlar,
        "zaman": datetime.now(ROMANYA_SAAT_DILIMI).isoformat(),
    }


_NOBETCI_DURUM_IKONU = {"iyi": "✅", "uyari": "🚨", "hata": "🚨", "yok": "ℹ️"}


@app.post("/api/admin/nobetci-kontrol-et")
def admin_nobetci_kontrol_et(_yetki=Depends(nobetci_anahtarini_dogrula)):
    """2026-08-30 (Gece Nobeti -- Faz 2): GitHub Actions'in 15 dk'da bir
    cagirdigi asil uc. saglik-kontrolu ile AYNI veriyi (bugunun_durumu_
    verisini_getir) okur ama farkli olarak SONUCU nobetci_durum_gecmisi
    ile KARSILASTIRIR -- bir kontrolun durumu bir onceki calismaya gore
    DEGISTIYSE Telegram+e-posta ile haber verir (admin_kritik_uyari),
    degismediyse SESSIZ kalir (ayni sorun her 15 dakikada tekrar tekrar
    bildirim basmasin diye). Ilk calistirmada (bir kontrol icin hic kayit
    yoksa) sessizce sadece taban durumu kaydeder, bildirim GONDERMEZ --
    aksi halde ilk calismada TUM kontroller "degisti" sayilip bildirim
    selinie yol acardi."""
    conn = veritabani_baglantisi(DB_FILE, row_factory=sqlite3.Row)
    try:
        durumlar = bugunun_durumu_verisini_getir(conn, _son_basarili_tarama_oku())
        onceki_durumlar = {
            satir["kontrol_adi"]: satir["son_durum"]
            for satir in conn.execute("SELECT kontrol_adi, son_durum FROM nobetci_durum_gecmisi")
        }

        degisenler = []
        for d in durumlar:
            ad, yeni_durum = d["ad"], d["durum"]
            eski_durum = onceki_durumlar.get(ad)
            if eski_durum is not None and eski_durum != yeni_durum:
                degisenler.append((ad, eski_durum, yeni_durum, d["mesaj"]))
            conn.execute(
                "INSERT INTO nobetci_durum_gecmisi (kontrol_adi, son_durum, son_degisim_zamani) "
                "VALUES (?, ?, CURRENT_TIMESTAMP) "
                "ON CONFLICT(kontrol_adi) DO UPDATE SET "
                "son_durum=excluded.son_durum, son_degisim_zamani=excluded.son_degisim_zamani",
                (ad, yeni_durum),
            )
        conn.commit()
    finally:
        conn.close()

    if degisenler:
        satirlar = [
            f"{_NOBETCI_DURUM_IKONU.get(yeni, 'ℹ️')} {ad}: {eski} → {yeni}\n   {mesaj}"
            for ad, eski, yeni, mesaj in degisenler
        ]
        from bildirim import admin_kritik_uyari
        admin_kritik_uyari("🔦 Gece Nöbeti -- durum değişikliği:\n\n" + "\n\n".join(satirlar))

    return {"kontrol_edilen": len(durumlar), "degisen": len(degisenler)}


def _yerel_pdf_url_olustur(request: Request, row) -> Optional[str]:
    """
    Bu sunucunun kendi indirdiği PDF kopyasının servis edilen adresini
    üretir (örn. https://.../pdfs/ordine/Ordine%20articolul%2010/xxx.pdf).
    Eşleşme yoksa ya da dosya bir sebeple diskte değilse None döner --
    mobil taraf bu durumda ilgili butonu hiç göstermez.
    """
    ana_kategori = row["ana_kategori"]
    alt_kategori = row["alt_kategori"]
    pdf_dosya = row["pdf_dosya"]
    if not (ana_kategori and alt_kategori and pdf_dosya):
        return None

    alt_klasor = klasor_adi_guvenli(alt_kategori)
    dosya_yolu = os.path.join(PDF_KOK_KLASOR, ana_kategori, alt_klasor, pdf_dosya)
    if not os.path.isfile(dosya_yolu):
        # Beklenmedik bir sebeple dosya diskten silinmiş/taşınmışsa kırık
        # bağlantı göstermemek için None dönüyoruz.
        return None

    taban = str(request.base_url).rstrip("/")
    yol = f"/pdfs/{quote(ana_kategori)}/{quote(alt_klasor)}/{quote(pdf_dosya)}"
    return taban + yol


def _satirdan_sonuc(row, request: Request):
    return {
        "ana_kategori": row["ana_kategori"],
        "alt_kategori": row["alt_kategori"],
        "durum": row["durum"],
        "mesaj": row["mesaj"],
        "dosya_no": row["dosya_no"],
        "yil": row["yil"],
        "pdf_dosya": row["pdf_dosya"],
        "resmi_pdf_url": row["pdf_kaynak_url"] or row["liste_url"] or RESMI_LISTE_URL,
        "yerel_pdf_url": _yerel_pdf_url_olustur(request, row),
        "liste_url": row["liste_url"],
        "eslesti": bool(row["eslesti"]),
    }


# 2026-08-18 (güvenlik denetimi madde 15): _sorguyu_calistir aşağıda bu
# kolon adını f-string ile SQL'e ekliyor. Bugün risk yok -- çağıran taraf
# (bu dosyadaki 4 sabit çağrı noktası) her zaman bu iki değerden birini
# sabit olarak geçiyor, kullanıcı girdisinden asla gelmiyor -- ama ileride
# biri yanlışlıkla kullanıcı girdisini bu parametreye geçirirse SQL
# injection kapısı açılırdı. Bu whitelist, o hatayı SESSİZCE ÇALIŞMAK
# yerine anında ValueError ile durdurur.
_GECERLI_ANAHTAR_KOLONLARI = {"dosya_no_norm", "dosya_no_tum_rakam"}


def _sorguyu_calistir(cursor, anahtar_kolon, anahtar_deger, veri):
    if anahtar_kolon not in _GECERLI_ANAHTAR_KOLONLARI:
        raise ValueError(f"Geçersiz anahtar_kolon: {anahtar_kolon!r} (izin verilenler: {_GECERLI_ANAHTAR_KOLONLARI})")
    sql = f"SELECT * FROM dosyalar WHERE {anahtar_kolon} = ?"
    parametreler = [anahtar_deger]

    # ÖNEMLİ (2026-08-15 -- "603" yanlış eşleşme düzeltmesi): baştaki rakam
    # bloğu (dosya_no_norm) TEK BAŞINA eşsiz değil -- aynı numara farklı
    # yıllarda farklı kişilere ait olabiliyor (bkz. dosya_utils.py notu).
    # Kullanıcı yıl girdiyse artık GERÇEKTEN filtreleniyor -- önceden bu
    # alan arayüzde vardı ama arka planda hiç kullanılmıyordu.
    if veri.yil and veri.yil.strip():
        sql += " AND yil = ?"
        parametreler.append(veri.yil.strip())
    if veri.ana_kategori:
        sql += " AND ana_kategori = ?"
        parametreler.append(veri.ana_kategori)
    if veri.alt_kategori:
        sql += " AND alt_kategori = ?"
        parametreler.append(veri.alt_kategori)

    cursor.execute(sql, parametreler)
    return cursor.fetchall()


def _otomatik_izlemeye_al(cihaz_kimligi: Optional[str], sonuclar: list):
    """2026-08-17 EKLENTİSİ (kullanıcı isteği): 'favori' artık bildirim
    almanın ŞARTI değil. Kullanıcı bir dosya numarasını sorgulayıp
    eşleşme bulduğunda, henüz ONAYLANMAMIŞ (ana_kategori='stadiu') her
    sonuç için sessizce, arka planda bir izleme kaydı oluşturulur --
    kullanıcı hiçbir şey yapmasa bile, o dosya ONAYLANDIĞINDA bildirim
    alır (bkz. bot.py _favori_sahiplerini_bul, otomatik_mi ayrımı yapmaz).

    Bu kayıtlar 'Favorilerim' ekranında GÖRÜNMEZ (bkz. /api/favorilerim'in
    otomatik_mi=0 filtresi) -- sadece kullanıcı BİLEREK "Favorilere Ekle"
    derse görünür/kalıcı favoriye yükseltilir (bkz. /api/favori-ekle).

    cihaz_kimligi verilmemişse (eski istemci sürümü, ya da bildirim izni
    hiç verilmemiş) sessizce hiçbir şey yapmaz.
    """
    cihaz_kimligi = (cihaz_kimligi or "").strip()
    if not cihaz_kimligi:
        return
    izlenecekler = [
        s for s in sonuclar
        if s.get("eslesti") and s.get("ana_kategori") == "stadiu" and s.get("dosya_no")
    ]
    if not izlenecekler:
        return
    try:
        conn = veritabani_baglantisi(DB_FILE)
        for s in izlenecekler:
            cekirdek = sayisal_cekirdek(s["dosya_no"])
            if not cekirdek:
                continue
            conn.execute(
                """
                INSERT INTO favoriler (expo_push_token, dosya_no, dosya_no_norm, yil, otomatik_mi)
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(expo_push_token, dosya_no_norm, yil) DO NOTHING
                """,
                (cihaz_kimligi, s["dosya_no"], cekirdek, s.get("yil")),
            )
        guvenli_commit(conn)
        conn.close()
    except Exception as e:
        # Otomatik izleme başarısız olsa bile SORGULAMA SONUCU asla
        # etkilenmemeli -- kullanıcı sonucu görmeye devam etmeli.
        print(f"✗ Otomatik izleme kaydı hatası: {str(e)[:80]}")


@app.post("/api/sorgula")
@limiter.limit("20/minute")
def sorgula(veri: SorguIstegi, request: Request, _anahtar=Depends(app_anahtarini_dogrula)):
    """
    Dosya numarası sorgula - bir dosya birden fazla kategoride olabilir,
    tüm eşleşmeleri döndürür (STADIU ve/veya ORDINE).

    Eşleştirme, ayırıcı karakter / harf kodu farklarından etkilenmeyen
    normalize edilmiş "rakam çekirdeği" üzerinden TAM eşitlikle yapılır
    (gevşek/joker karakterli arama YOKTUR, bu yüzden yanlış eşleşme üretmez).
    """
    ham_no = (veri.dosya_no or "").strip()
    if not ham_no:
        return {"dosya_no": ham_no, "bulundu": False, "toplam_sonuc": 0, "sonuclar": []}

    birincil_anahtar = sayisal_cekirdek(ham_no)
    yedek_anahtar = tum_rakamlar(ham_no)

    if not birincil_anahtar:
        return {
            "dosya_no": ham_no,
            "bulundu": False,
            "toplam_sonuc": 0,
            "sonuclar": [{
                "ana_kategori": None,
                "alt_kategori": None,
                "durum": "GEÇERSİZ NUMARA",
                "mesaj": "Girilen değerde bir dosya numarası tespit edilemedi. Lütfen rakamlardan oluşan dosya numaranızı kontrol edin.",
                "dosya_no": ham_no,
                "pdf_dosya": None,
                "resmi_pdf_url": RESMI_LISTE_URL,
                "yerel_pdf_url": None,
                "liste_url": RESMI_LISTE_URL,
                "eslesti": False,
            }],
        }

    conn = veritabani_baglantisi(DB_FILE, row_factory=sqlite3.Row)
    cursor = conn.cursor()

    rows = _sorguyu_calistir(cursor, "dosya_no_norm", birincil_anahtar, veri)

    # Birincil anahtar bulunamadıysa, yedek (tüm rakamlar) anahtarla dene.
    if not rows and yedek_anahtar and yedek_anahtar != birincil_anahtar:
        rows = _sorguyu_calistir(cursor, "dosya_no_tum_rakam", yedek_anahtar, veri)

    conn.close()

    if rows:
        sonuclar = [_satirdan_sonuc(row, request) for row in rows]
        _otomatik_izlemeye_al(veri.cihaz_kimligi, sonuclar)
        return {
            "dosya_no": ham_no,
            "bulundu": True,
            "toplam_sonuc": len(sonuclar),
            "sonuclar": sonuclar,
        }

    # 2026-08-16 (kullanıcı testinde bulunan UX iyileştirmesi -- İKİ KEZ
    # DÜZELTİLDİ, bkz. notlar): kullanıcı bir ana/alt kategori VE/VEYA yıl
    # FİLTRESİ girdiyse ve o filtrelerle sonuç çıkmadıysa, bu "dosya sistemde
    # hiç yok" anlamına gelmeyebilir. Kullanıcıyı yanlışlıkla "dosyam
    # sistemde yok" sanmaktan kurtarmak için, filtreler GÜVENLİ bir şekilde
    # gevşetilerek aynı numara tekrar aranıyor -- bulunursa gerçek
    # kategori(ler)/yıl(lar) "baska_kategoride_bulundu" alanında dönüyor.
    #
    # 2026-08-19 -- 3. DÜZELTME (kullanıcı canlı testte YİNE yakaladı, bu sefer
    # gerçek veriyle kanıtlandı): eski (a) adımı ("alt_kategori sabit, yılı
    # bırak") tamamen KALDIRILDI. Gerekçe: "16384" numarası test edilirken,
    # AYNI alt_kategori (Ordine articolul 11) içinde 2019, 2020 VE 2021
    # yıllarında birbirinden TAMAMEN BAĞIMSIZ, farklı kişilere ait dosyalar
    # olduğu görüldü -- yani "alt_kategori zaten yeterince dar" varsayımı
    # YANLIŞTI, tıpkı daha önce "sadece ana_kategori" için fark edildiği
    # gibi. Kullanıcının kendi sözleriyle: "en ayırt edici özellik yıl" --
    # yıl verilmeden yapılan hiçbir tahmin güvenli değil, başka bir yılda
    # açıklanmış TAMAMEN ALAKASIZ bir dosyayı "belki bu" diye göstermek
    # yanıltıcı ve kullanıcıyı gereksiz yere heyecanlandırabilir/yanlış
    # bilgilendirebilir.
    #
    # Artık TEK bir güvenli kısıtlayıcı yol var: yıl VERİLMİŞSE, onu sabit
    # tutup TÜM kategoriyi (ana+alt) bırakmak güvenli (aynı numara+yıl
    # ikilisi neredeyse hep tek kişiye ait, doğrulandı: "469/2023" ve
    # "307/RD/2017" testleri) -- bu, kullanıcının bildiği yılla ORDINE'de
    # ararken aslında henüz sadece STADIU'da olduğu durumu da doğru şekilde
    # yakalıyor (aynı numara+yıl, farklı ana_kategori). Yıl verilmemişse
    # (ya da sadece ana_kategori/alt_kategori verilmişse) hiçbir öneri
    # YAPILMIYOR -- dürüstçe "bulunamadı" deniyor.
    baska_kategoride_bulundu = []
    verilen_yil = veri.yil and veri.yil.strip()

    if verilen_yil:
        conn2 = veritabani_baglantisi(DB_FILE, row_factory=sqlite3.Row)
        cursor2 = conn2.cursor()

        # yıl sabit, TÜM kategori bırakılıyor -- "yıl doğru/biliniyor,
        # kategori yanlış/bilinmiyor" durumu (ör. stadiu'dan bilinen yılla
        # ordine'de arama).
        gevsek_veri = SimpleNamespace(yil=verilen_yil, ana_kategori=None, alt_kategori=None)
        gevsek_rows = _sorguyu_calistir(cursor2, "dosya_no_norm", birincil_anahtar, gevsek_veri)
        if not gevsek_rows and yedek_anahtar and yedek_anahtar != birincil_anahtar:
            gevsek_rows = _sorguyu_calistir(cursor2, "dosya_no_tum_rakam", yedek_anahtar, gevsek_veri)
        conn2.close()

        # 2026-08-19 DÜZELTMESİ (kullanıcı fark etti): burada eskiden sadece
        # ana_kategori/alt_kategori/yıl döndürülüyordu -- kullanıcı "stadiu'da
        # buldum" dediğimizde PDF'i de göstermemiz gerektiğini belirtti,
        # haklı: kullanıcı bunu kendi gözüyle doğrulayabilmeli. Artık
        # _satirdan_sonuc ile GERÇEK sonuçlarla AYNI tam yapı (durum, mesaj,
        # resmi_pdf_url, yerel_pdf_url dahil) dönüyor.
        gorulen = set()
        for row in gevsek_rows:
            anahtar = (row["ana_kategori"], row["alt_kategori"], row["yil"])
            if anahtar in gorulen:
                continue
            gorulen.add(anahtar)
            baska_kategoride_bulundu.append(_satirdan_sonuc(row, request))

        # 2026-08-20 DÜZELTMESİ (kullanıcı canlı testte fark etti): bu
        # "güvenli alternatif" (yıl sabit, kategori serbest) sonuçları
        # ÖNCEDEN sadece gösteriliyordu, otomatik arka plan izlemesine hiç
        # ALINMIYORDU -- yani kullanıcı tam da en çok merak edeceği anda
        # (dosyası stadiu'da bekliyor, henüz ordine'de değil) hiçbir
        # bildirim alamıyordu. Artık normal sonuçlarla AYNI muameleyi
        # görüyor -- ana_kategori='stadiu' olan her eşleşme sessizce
        # izlemeye alınıyor.
        _otomatik_izlemeye_al(veri.cihaz_kimligi, baska_kategoride_bulundu)

    return {
        "dosya_no": ham_no,
        "bulundu": False,
        "toplam_sonuc": 0,
        "sonuclar": [{
            "ana_kategori": veri.ana_kategori,
            "alt_kategori": veri.alt_kategori,
            "durum": "KAYIT YOK",
            "mesaj": f"{ham_no} numaralı dosya şu ana kadar sisteme yüklenen resmi kararname ve aşama listelerinde tespit edilemedi.",
            "dosya_no": ham_no,
            "pdf_dosya": None,
            "resmi_pdf_url": RESMI_LISTE_URL,
            "yerel_pdf_url": None,
            "liste_url": RESMI_LISTE_URL,
            "eslesti": False,
            "baska_kategoride_bulundu": baska_kategoride_bulundu,
        }],
    }


# ---------------------------------------------------------------------------
# Sıra tahmini (2026-08-20)
# ---------------------------------------------------------------------------
class SiraTahminiIstegi(BaseModel):
    dosya_no: str = Field(max_length=100)
    yil: str = Field(max_length=10)
    alt_kategori: str = Field(max_length=100)


@app.post("/api/sira-tahmini")
@limiter.limit("20/minute")
def sira_tahmini(veri: SiraTahminiIstegi, request: Request, _anahtar=Depends(app_anahtarini_dogrula)):
    """
    Bir dosyanın 'bekleyen_dosyalar' kuyruğundaki (her gece yeniden
    hesaplanan, bkz. dosya_utils.bekleme_kuyrugunu_guncelle) konumunu
    döndürür.

    ÖNEMLİ (dürüstlük): bu, BAŞVURU SIRASINA (dosya numarasına) göre
    tahmini bir konumdur -- Romanya'nın gerçek işleme sırasının numara
    sırasını birebir takip ettiğinin GARANTİSİ yoktur (bugüne kadarki
    canlı gözlemlerimizde kararnamelerin numara sırasına uymadığı
    görüldü). Mobil tarafta bu netlik korunarak sunulmalı.
    """
    dosya_no_norm = sayisal_cekirdek(veri.dosya_no)
    yil = veri.yil.strip()
    alt_kategori = veri.alt_kategori.strip()
    if not dosya_no_norm:
        raise HTTPException(status_code=400, detail="Geçersiz dosya numarası.")

    conn = veritabani_baglantisi(DB_FILE, row_factory=sqlite3.Row)
    cursor = conn.cursor()

    # 2026-08-20 DÜZELTMESİ (kullanıcı isteği: eski istatistikler/kisisel
    # ucuyla aynı 3 net durumu (onaylanmış/bekliyor/bulunamadı) versin,
    # ama madde ayrımı YAPARAK -- eski uç tüm maddeleri karıştırıyordu,
    # bu da yanlış "onaylandı" eşleşmesi riski taşıyordu). Önce ordine'de
    # AYNI numara+yıl (herhangi ordine alt kategorisinde -- bugün canlı
    # doğrulanan güvenli eşleştirme ilkesiyle tutarlı) var mı bakılıyor.
    cursor.execute(
        "SELECT COUNT(*) FROM dosyalar WHERE ana_kategori='ordine' AND dosya_no_norm=? AND yil=?",
        (dosya_no_norm, yil),
    )
    onaylanmis_mi = cursor.fetchone()[0] > 0

    if onaylanmis_mi:
        conn.close()
        return {
            "bulundu": True,
            "durum": "onaylanmis",
            "dosya_no": veri.dosya_no,
            "yil": yil,
            "alt_kategori": alt_kategori,
        }

    sonuc = sira_tahmini_hesapla(conn, dosya_no_norm, yil, alt_kategori)
    conn.close()

    if sonuc is None:
        return {
            "bulundu": False,
            "durum": "bulunamadi",
            "dosya_no": veri.dosya_no,
            "yil": yil,
            "alt_kategori": alt_kategori,
        }

    return {
        "bulundu": True,
        "durum": "bekliyor",
        "dosya_no": veri.dosya_no,
        "yil": yil,
        "alt_kategori": alt_kategori,
        **sonuc,
        "uyari": "Bu, başvuru sırasına (dosya numarasına) göre tahmini bir konumdur -- "
                 "resmi işlem sırasının garantisi değildir.",
    }


# ---------------------------------------------------------------------------
# Bildirimler / Favoriler (Faz 1)
# ---------------------------------------------------------------------------
class PushTokenKaydi(BaseModel):
    expo_push_token: str = Field(max_length=300)
    # 2026-08-17 EKLENTİSİ: cihaz kimliğiyle (constants/api.tsx
    # cihazKimligiGetir) eşleştirilebilsin diye. Opsiyonel bırakıldı ki
    # eski istemciler (bu alanı hiç göndermeyenler) kırılmasın.
    cihaz_kimligi: Optional[str] = Field(default=None, max_length=200)


class FavoriIstegi(BaseModel):
    expo_push_token: str = Field(max_length=300)
    dosya_no: str = Field(max_length=100)
    # 2026-08-16: kullanıcının favorilediği SPESİFİK kartın yılı -- aynı
    # çıplak numara farklı yıllarda farklı gerçek dosyalara ait olabildiği
    # için (bkz. dosya_utils.py tabloyu_hazirla notu), bu olmadan
    # "favorilerim" hangi kaydı kastettiğini ayırt edemiyordu.
    yil: Optional[str] = Field(default=None, max_length=10)


@app.post("/api/push-token")
@limiter.limit("20/minute")
def push_token_kaydet(veri: PushTokenKaydi, request: Request, _anahtar=Depends(app_anahtarini_dogrula)):
    """Cihazın Expo push bildirim belirtecini kaydeder (bildirim gönderebilmek için).

    2026-08-17 DÜZELTMESİ: cihaz_kimligi verildiyse, UPSERT yapılıyor --
    aynı cihazın (ör. token yenilendiğinde) eski kaydı GÜNCELLENİYOR,
    birikip duran, hiçbiri güncel olmayan çoklu satırlar oluşmuyor. Ayrıca
    bu eşleştirme, favoriler.expo_push_token (aslında cihaz kimliği,
    bkz. dosya_utils.py notu) üzerinden GERÇEK push token'ı bulabilmek
    için gerekli (bkz. bot.py _favori_sahiplerini_bul).
    """
    token = (veri.expo_push_token or "").strip()
    cihaz_kimligi = (veri.cihaz_kimligi or "").strip() or None
    if not token:
        return {"basarili": False, "hata": "Geçersiz token"}
    conn = veritabani_baglantisi(DB_FILE)
    if cihaz_kimligi:
        conn.execute(
            """
            INSERT INTO push_tokenlari (expo_push_token, cihaz_kimligi) VALUES (?, ?)
            ON CONFLICT(expo_push_token) DO UPDATE SET cihaz_kimligi = excluded.cihaz_kimligi
            """,
            (token, cihaz_kimligi),
        )
        # Aynı cihaz DAHA ÖNCE farklı bir token'la kayıtlıysa (token
        # yenilendiğinde olur), o eski satırın cihaz_kimligi'ni temizle --
        # yoksa UNIQUE(cihaz_kimligi) çakışması/iki satırda aynı cihaz
        # görünmesi riski oluşur.
        conn.execute(
            "UPDATE push_tokenlari SET cihaz_kimligi = NULL "
            "WHERE cihaz_kimligi = ? AND expo_push_token != ?",
            (cihaz_kimligi, token),
        )
    else:
        conn.execute("INSERT OR IGNORE INTO push_tokenlari (expo_push_token) VALUES (?)", (token,))
    guvenli_commit(conn)
    conn.close()
    return {"basarili": True}


@app.post("/api/favori-ekle")
@limiter.limit("20/minute")
def favori_ekle(veri: FavoriIstegi, request: Request, _anahtar=Depends(app_anahtarini_dogrula)):
    """Kullanıcı, sonuç ekranında gördüğü SPESİFİK bir kaydı (dosya numarası
    + yıl) 'Favorilerim'e ekler (pasif takip için).

    2026-08-17 DÜZELTMESİ: Bu numara için zaten OTOMATİK bir izleme kaydı
    varsa (bkz. /api/sorgula -- her sorgulanan, henüz onaylanmamış numara
    arka planda otomatik izlenir), burada onu SİLİP YENİDEN eklemek yerine
    otomatik_mi=0 yapılıyor -- yani "görünür/kalıcı favori" durumuna
    yükseltiliyor. Zaten hiç kaydı yoksa normal şekilde otomatik_mi=0
    olarak oluşturuluyor.
    """
    token = (veri.expo_push_token or "").strip()
    ham_no = (veri.dosya_no or "").strip()
    yil = (veri.yil or "").strip() or None
    cekirdek = sayisal_cekirdek(ham_no)
    if not token or not cekirdek:
        return {"basarili": False, "hata": "Geçersiz istek"}
    conn = veritabani_baglantisi(DB_FILE)
    conn.execute(
        """
        INSERT INTO favoriler (expo_push_token, dosya_no, dosya_no_norm, yil, otomatik_mi)
        VALUES (?, ?, ?, ?, 0)
        ON CONFLICT(expo_push_token, dosya_no_norm, yil) DO UPDATE SET otomatik_mi = 0
        """,
        (token, ham_no, cekirdek, yil),
    )
    guvenli_commit(conn)
    conn.close()
    return {"basarili": True}


@app.post("/api/favori-sil")
@limiter.limit("20/minute")
def favori_sil(veri: FavoriIstegi, request: Request, _anahtar=Depends(app_anahtarini_dogrula)):
    token = (veri.expo_push_token or "").strip()
    cekirdek = sayisal_cekirdek((veri.dosya_no or "").strip())
    yil = (veri.yil or "").strip() or None
    conn = veritabani_baglantisi(DB_FILE)
    conn.execute(
        "DELETE FROM favoriler WHERE expo_push_token = ? AND dosya_no_norm = ? AND yil IS ?",
        (token, cekirdek, yil),
    )
    guvenli_commit(conn)
    conn.close()
    return {"basarili": True}


@app.get("/api/favorilerim")
@limiter.limit("30/minute")
def favorilerim(
    request: Request,
    token: str = Query(max_length=300),
    _anahtar=Depends(app_anahtarini_dogrula),
):
    """Kayıtlı favori kayıtların GÜNCEL durumunu döndürür.

    2026-08-16 düzeltmesi: artık sadece çıplak numaraya (dosya_no_norm) değil,
    favorilenirken kaydedilen 'yil'a göre de filtreleniyor -- aksi halde aynı
    numarayı taşıyan FARKLI yıllardaki (ve dolayısıyla farklı kişilere ait
    olabilecek) tüm kayıtlar dönerdi. 'ana_kategori'/'alt_kategori' BİLEREK
    filtreye dahil edilmiyor -- bir dosya stadiu'dan ordine'ye geçtiğinde bu
    ikisi değişir, ama dosya_no_norm+yil aynı kalır (bkz. dosya_utils.py
    tabloyu_hazirla notu) -- bu sayede kullanıcı, dosyası onaylandığında bu
    ekranda hem eski (stadiu) hem yeni (ordine) kaydı bir arada görebiliyor.
    """
    conn = veritabani_baglantisi(DB_FILE, row_factory=sqlite3.Row)
    cursor = conn.cursor()
    # 2026-08-17: otomatik_mi=0 filtresi -- sistemin her sorgulamada
    # arka planda otomatik oluşturduğu izleme kayıtları (bkz. /api/sorgula)
    # bu ekranda GÖRÜNMEMELİ, sadece kullanıcının BİLEREK "Favorilere
    # Ekle" ile eklediği kayıtlar görünmeli.
    cursor.execute(
        "SELECT dosya_no, dosya_no_norm, yil FROM favoriler WHERE expo_push_token = ? AND otomatik_mi = 0 ORDER BY id DESC",
        (token,),
    )
    favori_satirlari = cursor.fetchall()

    sonuc = []
    for fav in favori_satirlari:
        cursor.execute(
            "SELECT * FROM dosyalar WHERE dosya_no_norm = ? AND yil IS ?",
            (fav["dosya_no_norm"], fav["yil"]),
        )
        eslesmeler = [_satirdan_sonuc(row, request) for row in cursor.fetchall()]
        sonuc.append({
            "dosya_no": fav["dosya_no"],
            "yil": fav["yil"],
            "bulundu": len(eslesmeler) > 0,
            "sonuclar": eslesmeler,
        })
    conn.close()
    return {"favoriler": sonuc}


# ---------------------------------------------------------------------------
# İstatistikler (2026-08-16, kullanıcı isteğiyle eklendi)
# ---------------------------------------------------------------------------
# ÖNEMLİ (eşleştirme doğruluğu): "stadiu'da olup ordine'de olmayan" (henüz
# onaylanmamış) dosyaları sayarken MUTLAKA dosya_no_norm + yıl ikilisiyle
# eşleştiriyoruz, ASLA çıplak numarayla değil -- bu oturumda defalarca
# kanıtladık ki çıplak numaralar yıllar arası sürekli tekrar kullanılıyor,
# sadece numarayla eşleştirmek TAMAMEN YANLIŞ istatistik üretirdi.
#
# "Sıra" hesabı bir TAHMİNDİR, resmi bir kuyruk numarası DEĞİLDİR -- elimizde
# resmi bir işlem sırası verisi yok, sadece dosya numaralarının o yıl içinde
# artan sırada verildiği varsayımıyla (numaraya göre küçükten büyüğe
# sıralama) hesaplanıyor. Mobil tarafta bu mutlaka açıkça belirtiliyor.
#
# Basit bellek-içi önbellek: bu sorgular (özellikle genel istatistik) ağır
# olabiliyor (~1-1.5sn) -- her istekte yeniden hesaplamak yerine 30 dakika
# önbellekleniyor. bot.py her taramadan sonra veriyi güncellediği için, en
# geç bir sonraki önbellek yenilenmesinde yeni PDF'ler istatistiklere yansır
# (kullanıcının "dosya eklendikçe güncellenmeli" isteği böyle karşılanıyor).
_ISTATISTIK_ONBELLEK_SURESI_SN = 1800
_genel_istatistik_onbellek = {"veri": None, "zaman": 0.0}


def _genel_istatistikleri_hesapla():
    conn = veritabani_baglantisi(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM (SELECT DISTINCT dosya_no_norm, yil FROM dosyalar "
        "WHERE ana_kategori='stadiu' AND yil IS NOT NULL)"
    )
    toplam_stadiu = cursor.fetchone()[0]
    cursor.execute(
        "SELECT COUNT(*) FROM (SELECT DISTINCT dosya_no_norm, yil FROM dosyalar "
        "WHERE ana_kategori='ordine' AND yil IS NOT NULL)"
    )
    toplam_ordine = cursor.fetchone()[0]
    cursor.execute(
        "SELECT COUNT(*) FROM ("
        "  SELECT DISTINCT dosya_no_norm, yil FROM dosyalar WHERE ana_kategori='stadiu' AND yil IS NOT NULL"
        "  INTERSECT"
        "  SELECT DISTINCT dosya_no_norm, yil FROM dosyalar WHERE ana_kategori='ordine' AND yil IS NOT NULL"
        ")"
    )
    toplam_onaylanan = cursor.fetchone()[0]

    # NOT: yıllık kırılım için makul bir aralıkla (2008-2026) filtreleniyor --
    # dosya numarası ayrıştırma sürecinden kalan nadir hatalı "yıl" değerleri
    # (ör. "1035", "8202" gibi anlamsız sayılar, muhtemelen belge/karar
    # numarasının yanlışlıkla yıl sanılması) grafiği bozmasın diye. Bu
    # filtre sadece GRAFİK için -- yukarıdaki toplam sayılara dahil (etkisi
    # ihmal edilebilir düzeyde, ~1000 kayıtta 1'den az).
    cursor.execute(
        "SELECT yil, COUNT(DISTINCT dosya_no_norm) FROM dosyalar "
        "WHERE ana_kategori='stadiu' AND yil BETWEEN '2008' AND '2026' GROUP BY yil"
    )
    stadiu_yillik = dict(cursor.fetchall())
    cursor.execute(
        "SELECT yil, COUNT(DISTINCT dosya_no_norm) FROM dosyalar "
        "WHERE ana_kategori='ordine' AND yil BETWEEN '2008' AND '2026' GROUP BY yil"
    )
    ordine_yillik = dict(cursor.fetchall())
    conn.close()

    tum_yillar = sorted(set(stadiu_yillik) | set(ordine_yillik))
    yillik_dagilim = [
        {"yil": y, "stadiu": stadiu_yillik.get(y, 0), "ordine": ordine_yillik.get(y, 0)}
        for y in tum_yillar
    ]

    # 2026-08-20 (rakip analizinden ilham): "son 7 gün aktivitesi" artık
    # sadece admin panelinde değil, kullanıcıya da açık -- "sistem gerçekten
    # çalışıyor" güvenini artırmak için (bkz. rakip uygulamanın "Son 7 gün: 4
    # PDF, 239 kişi" kutusu). sistem_olaylari.tarama_tamamlandi olaylarının
    # serbest metin 'detay' alanından (ör. "22 PDF bulundu, 5 kayıt işlendi
    # (3 yeni), ...") regex ile sayılar çıkarılıyor -- ayrı bir sütun
    # eklemek yerine zaten var olan veriyi kullanmak için.
    son_7_gun_pdf = 0
    son_7_gun_yeni_kayit = 0
    son_7_gun_tarama_sayisi = 0
    try:
        conn2 = veritabani_baglantisi(DB_FILE)
        c2 = conn2.cursor()
        esik = (datetime.now(ROMANYA_SAAT_DILIMI) - timedelta(days=7)).astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%d %H:%M:%S")
        c2.execute(
            "SELECT detay FROM sistem_olaylari WHERE olay_tipi='tarama_tamamlandi' AND zaman >= ?",
            (esik,),
        )
        for (detay,) in c2.fetchall():
            if not detay:
                continue
            son_7_gun_tarama_sayisi += 1
            pdf_eslesme = re.search(r"(\d+)\s*PDF bulundu", detay)
            if pdf_eslesme:
                son_7_gun_pdf += int(pdf_eslesme.group(1))
            yeni_eslesme = re.search(r"\((\d+)\s*yeni\)", detay)
            if yeni_eslesme:
                son_7_gun_yeni_kayit += int(yeni_eslesme.group(1))
        conn2.close()
    except Exception as e:
        print(f"✗ Son 7 gün aktivite hesabı hatası: {str(e)[:80]}")

    return {
        "toplam_stadiu": toplam_stadiu,
        "toplam_ordine": toplam_ordine,
        "toplam_onaylanan": toplam_onaylanan,
        "toplam_bekleyen": toplam_stadiu - toplam_onaylanan,
        "yillik_dagilim": yillik_dagilim,
        "son_7_gun": {
            "pdf": son_7_gun_pdf,
            "yeni_kayit": son_7_gun_yeni_kayit,
            "tarama_sayisi": son_7_gun_tarama_sayisi,
        },
        "hesaplanma_zamani": datetime.now().isoformat(),
    }


@app.get("/api/istatistikler/genel")
@limiter.limit("15/minute")
def istatistikler_genel(request: Request, _anahtar=Depends(app_anahtarini_dogrula)):
    simdi = time.time()
    onbellek = _genel_istatistik_onbellek
    if onbellek["veri"] is None or (simdi - onbellek["zaman"]) > _ISTATISTIK_ONBELLEK_SURESI_SN:
        onbellek["veri"] = _genel_istatistikleri_hesapla()
        onbellek["zaman"] = simdi
    return onbellek["veri"]


# 2026-08-20 KALDIRILDI: eski /api/istatistikler/kisisel ucu buradaydı --
# madde (alt kategori) ayrımı YAPMIYORDU (tüm stadiu/ordine kategorilerini
# aynı yıl içinde karıştırıyordu), bu da yanlış "onaylanmış" eşleşmesi
# riski taşıyordu (ör. Articolul 8'deki biri, Articolul 11'deki aynı
# numaranın onaylanmasıyla yanlışlıkla eşleşebilirdi). Yerini madde-farkında
# /api/sira-tahmini ucu aldı (yukarıda) -- istatistikler.tsx artık ona
# bağlı. _yillik_istatistik_onbellek de bununla birlikte kaldırıldı.


# 2026-08-19 (Render'a taşıma sırasında bulundu): Render, HTTPS'i kendi
# ucunda sonlandırıp bize sunucuya düz HTTP olarak iletiyor (yaygın bir
# reverse-proxy deseni) -- bu yüzden `request.base_url` (bkz.
# _yerel_pdf_url_olustur) "http://" üretiyordu, "https://" değil, halbuki
# kullanıcı tarayıcısı/uygulaması gerçekte HTTPS ile bağlanıyor. Render (ve
# benzeri proxy'ler) gerçek şemayı X-Forwarded-Proto başlığında gönderir --
# ProxyHeadersMiddleware bu başlığı okuyup request.base_url'i düzeltiyor.
# Yerel geliştirmede (proxy yok, Host doğrudan) etkisi yok, zararsız.
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
app = ProxyHeadersMiddleware(app, trusted_hosts="*")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    # 2026-08-16: reload=True iki kez denendi. İlk seferde "sunucuyu
    # yanıtsız bırakıyor" sanılmıştı -- bu YANLIŞ teşhisti (gerçek sebep,
    # /api/durum'un mesai saatinde cetatenie.just.ro'yu kontrol ederken
    # kullandığı 10sn'lik zaman aşımıydı, test çok kısa sürede vazgeçmişti).
    # İkinci denemede sunucu YANITSIZ KALMADI ama WatchFiles "değişiklik
    # algılandı, yeniden başlatılıyor" dedikten SONRA bile eski kod
    # çalışmaya devam etti -- yeniden başlatmanın gerçekten tamamlandığına
    # dair net bir log/kanıt yoktu. Bu, sessizce ESKİ KODU sunmaya devam
    # etme riski taşıyor -- manuel yeniden başlatmaktan daha KÖTÜ bir
    # durum (en azından manuel restart'ta ne zaman güncel olduğu belli).
    # Bu yüzden GERİ ALINDI. Kalıcı çözüm: her backend değişikliğinden
    # sonra Claude süreci elle durdurup (Stop-Process) yeniden başlatıyor
    # ve /api/ ile doğruluyor -- kullanıcının elle yapmasına GEREK YOK,
    # ama otomatik dosya izleme değil, Claude'un standart pratiği.
    uvicorn.run(app, host="0.0.0.0", port=port)
