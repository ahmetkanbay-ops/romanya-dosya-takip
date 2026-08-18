import os
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

import secrets
import sqlite3
import time
import requests
from datetime import datetime, timedelta
from types import SimpleNamespace
from urllib.parse import quote
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse
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
)
from hukuki_metinler import (
    KULLANIM_SARTLARI_METIN,
    GIZLILIK_POLITIKASI_METIN,
    sayfa_html,
)

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
    # (aynı origin) script/style/img yüklemesine izin verir -- özellikle
    # /kullanim-sartlari ve /gizlilik-politikasi gibi HTML sayfaları için
    # (dışarıdan enjekte edilebilecek script'lere karşı ek katman).
    yanit.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    yanit.headers["Content-Security-Policy"] = "default-src 'self'"
    return yanit

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "dosyalar.db")
PDF_KOK_KLASOR = os.path.join(BASE_DIR, "pdfs")


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

# Scheduler kurulumu
scheduler = BackgroundScheduler()


def run_bot(yeniden_deneme_mi=False):
    """Bot'u çalıştır.

    2026-08-17 EKLENTİSİ -- TEK SEFERLİK yeniden deneme: Site birkaç gün
    üst üste erişilemez olursa (daha önce yaşandı), eskiden bot bir
    sonraki günün 09:00'ına kadar hiç tekrar denemiyordu. Artık: günün
    ilk (09:00) çalışması sitenin TAMAMEN erişilemez olması yüzünden HİÇ
    PDF bulamazsa (botu_calistir'in dönüş değerine bakılıyor), 6 saat
    sonra (yaklaşık 15:00) TEK bir ek deneme otomatik zamanlanıyor.

    KASITLI SINIRLAMA: bu yeniden deneme kendi kendine BİR DAHA yeniden
    deneme ZAMANLAMAZ (yeniden_deneme_mi=True ise bu adım atlanır) --
    yani günde EN FAZLA 2 deneme (09:00 + 15:00) yapılabilir. Bunun
    nedeni: cetatenie.just.ro, günde 5 kez (2 saatte bir) yapılan
    taramayı kötüye kullanım sayıp IP'yi bloke etmişti (bkz. 2026-08-15
    notu) -- sınırsız/sık yeniden deneme aynı riski yeniden yaratır.
    """
    try:
        from bot import botu_calistir
        etiket = "YENİDEN DENEME (bugünkü ilk deneme site erişilemez bulmuştu)" if yeniden_deneme_mi else "OTOMATİK ÇALIŞTIRILDI"
        print(f"\n{'='*60}")
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] BOT {etiket}")
        print(f"{'='*60}")
        toplam_pdf_bulunan = botu_calistir()
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] BOT TAMAMLANDI")

        if not toplam_pdf_bulunan and not yeniden_deneme_mi:
            calistirma_zamani = datetime.now() + timedelta(hours=6)
            scheduler.add_job(
                run_bot,
                'date',
                run_date=calistirma_zamani,
                args=[True],
                id='pdf_downloader_yeniden_deneme',
                name='PDF Downloader Bot (yeniden deneme)',
                replace_existing=True,
            )
            print(f"  ℹ Site erişilemedi -- {calistirma_zamani.strftime('%H:%M')}'de TEK seferlik bir yeniden deneme zamanlandı.")
    except Exception as e:
        print(f"✗ Bot çalıştırma hatası: {e}")
        # Beklenmedik bir çökme (ör. ağ zaman aşımı istisna olarak
        # yükseldi) de "site erişilemedi" ile aynı muameleyi görmeli --
        # aynı tek seferlik/günde-en-fazla-2-deneme kuralı burada da geçerli.
        if not yeniden_deneme_mi:
            calistirma_zamani = datetime.now() + timedelta(hours=6)
            scheduler.add_job(
                run_bot,
                'date',
                run_date=calistirma_zamani,
                args=[True],
                id='pdf_downloader_yeniden_deneme',
                name='PDF Downloader Bot (yeniden deneme)',
                replace_existing=True,
            )
            print(f"  ℹ Çökme sonrası -- {calistirma_zamani.strftime('%H:%M')}'de TEK seferlik bir yeniden deneme zamanlandı.")


# ---------------------------------------------------------------------------
# OTOMATİK VERİTABANI YEDEĞİ (2026-08-17, kod taraması sonrası eklendi)
# ---------------------------------------------------------------------------
# dosyalar.db artık ~1GB -- bir bozulma/yanlışlıkla silinme durumunda TÜM
# geçmiş kaybolur, yeniden kurmak saatler sürer (siteyi baştan taramak
# gerekir). Her gece, bot'un 09:00'daki taramasından ÖNCE (03:00'te),
# sqlite3'ün KENDİ "online backup" API'sini kullanarak (Connection.backup)
# tutarlı bir kopya alınıyor -- bu, DB WAL modundayken bile ÇALIŞAN
# SÜREÇTEN dosyayı elle kopyalamaktan (os.copy) çok daha güvenli, çünkü
# ortasında yazma işlemi olsa bile SQLite bunu kendi içinde senkronize
# ediyor (yarım/bozuk bir kopya riski yok).
YEDEK_KLASOR = os.path.join(BASE_DIR, "yedekler")
YEDEK_SAKLAMA_GUN_SAYISI = 7  # bundan eski yedekler otomatik silinir


def veritabani_yedekle():
    """dosyalar.db'nin tutarlı bir kopyasını yedekler/ klasörüne alır,
    YEDEK_SAKLAMA_GUN_SAYISI'ndan eski yedekleri siler."""
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

        # Eski yedekleri temizle (sadece son YEDEK_SAKLAMA_GUN_SAYISI günü tut).
        sinir_zamani = time.time() - (YEDEK_SAKLAMA_GUN_SAYISI * 24 * 60 * 60)
        for dosya_adi in os.listdir(YEDEK_KLASOR):
            if not dosya_adi.startswith("dosyalar_") or not dosya_adi.endswith(".db"):
                continue
            tam_yol = os.path.join(YEDEK_KLASOR, dosya_adi)
            if os.path.getmtime(tam_yol) < sinir_zamani:
                os.remove(tam_yol)
                print(f"  (eski yedek silindi: {dosya_adi})")
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


@app.on_event("startup")
async def startup_event():
    """Uygulama başladığında scheduler'ı başlat"""
    # 2026-08-15: cetatenie.just.ro, günde 5 kez (08-17 arası 2 saatte bir)
    # yapılan taramayı kötüye kullanım sayıp IP adresini bloke etti. Bu
    # yüzden sıklık günde SADECE 1 keze düşürüldü. Ayrıca bot.py artık
    # zaten indirilmiş/işlenmiş PDF'leri tekrar taramıyor (bkz. bot.py
    # "2026-08-15" notları), bu da her çalıştırmadaki toplam istek/süreyi
    # ciddi ölçüde azaltıyor.
    scheduler.add_job(
        run_bot,
        'cron',
        hour='9',
        minute='0',
        id='pdf_downloader',
        name='PDF Downloader Bot'
    )
    # 2026-08-17: otomatik veritabanı yedeği, bot'un 09:00'daki taramasından
    # ÖNCE (03:00'te, gece en sakin saat) alınıyor -- bkz. veritabani_yedekle().
    scheduler.add_job(
        veritabani_yedekle,
        'cron',
        hour='3',
        minute='0',
        id='db_yedekleme',
        name='Veritabanı Yedekleme'
    )
    scheduler.start()
    print(f"\n✓ Scheduler başlatıldı!")
    print(f"✓ Bot: Her gün SADECE 09:00'da çalışacak (siteye aşırı yük bindirmemek için sıklık düşürüldü)")
    print(f"✓ Yedekleme: Her gün 03:00'te otomatik veritabanı yedeği alınacak (son {YEDEK_SAKLAMA_GUN_SAYISI} gün saklanır)")
    print(f"✓ Sonraki çalışma: Zamanı gelince otomatik çalışır\n")


@app.on_event("shutdown")
async def shutdown_event():
    """Uygulama kapanırken scheduler'ı durdur"""
    scheduler.shutdown()
    print("✓ Scheduler durduruldu.")


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


@app.get("/")
def root():
    return {"status": "ok", "message": "Gerçek Veri Modülü Aktif"}


def _mesai_saatinde_mi() -> bool:
    """Mesai saatleri: 08:00-17:59. Bu aralığın dışında resmi site planlı
    bakım moduna girebiliyor -- bu yüzden mesai dışı erişim sorunları
    "olağan dışı bir kesinti" sayılıp ne admin'e ne de uygulama
    kullanıcılarına bildirilmez, sadece mesai saatleri içinde yaşanan
    kesintiler bildirilir (kullanıcının 2026-08-14 talebi)."""
    return 8 <= datetime.now().hour <= 17


def _son_basarili_tarama_oku() -> Optional[str]:
    """
    bot.py'nin her taramanın sonunda yazdığı zaman damgasını okur (bkz.
    bot.py son satırları). 2026-08-15: kullanıcı isteğiyle eklendi --
    "servis dışı" banner'ı kaygı verici durabiliyor, yanına "verileriniz
    en son ne zaman güncellendi" bilgisini eklemek için. Dosya yoksa
    (bot hiç çalışmadıysa) None döner, mobil taraf bu durumda ek metni
    hiç göstermez.
    """
    yol = os.path.join(BASE_DIR, "son_basarili_tarama.txt")
    if not os.path.isfile(yol):
        return None
    try:
        with open(yol, "r", encoding="utf-8") as f:
            return f.read().strip() or None
    except Exception:
        return None


@app.get("/api/durum")
def site_durumu():
    """Mobil uygulamanın ana ekranında gösterilecek küçük banner için resmi
    kaynağın (cetatenie.just.ro) anlık erişilebilirliğini kontrol eder.
    Mesai saatleri dışındaki kesintiler bildirilmez (planlı bakım olabilir)."""
    son_guncelleme = _son_basarili_tarama_oku()

    if not _mesai_saatinde_mi():
        return {"servis_disi": False, "banner_mesaji": None, "son_guncelleme": son_guncelleme}
    try:
        yanit = requests.get(
            RESMI_LISTE_URL, timeout=10,
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"},
        )
        erisilebilir = yanit.status_code < 500
    except Exception:
        erisilebilir = False

    if erisilebilir:
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
    # 2026-08-16 -- 2. DÜZELTME (ilk düzeltme yetersiz kaldı, kullanıcı canlı
    # testte tekrar yakaladı): "kategoriyi sabit tutup sadece yılı bırak"
    # adımı, kullanıcı SADECE ana_kategori seçip (alt_kategori SEÇMEDİYSE --
    # ör. "ordine'de var mı diye bakayım" gibi çok yaygın bir kullanım)
    # aslında hâlâ GÜVENSİZDİ -- "ana_kategori=ordine, alt_kategori=YOK"
    # kısıtı, binlerce farklı dosyayı kapsayan gevşek bir kısıt, "kategori
    # zaten daraltılmış" varsayımı SADECE alt_kategori verilmişse doğruydu.
    # Artık kural netleştirildi -- İKİ BAĞIMSIZ, birbirinden ayrı güvenli
    # kısıtlayıcı var: (a) alt_kategori VERİLMİŞSE, onu sabit tutup yılı
    # bırakmak güvenli (alt_kategori zaten dar bir liste). (b) yıl
    # VERİLMİŞSE, onu sabit tutup TÜM kategoriyi bırakmak güvenli (aynı
    # numara+yıl ikilisi neredeyse hep tek kişiye ait, doğrulandı: "469/2023"
    # ve "307/RD/2017" testleri). Bu ikisi DIŞINDA (sadece ana_kategori
    # verilmiş VEYA hiçbir şey verilmemişse) hiçbir öneri YAPILMIYOR --
    # dürüstçe "bulunamadı" deniyor, çünkü ana_kategori tek başına numara
    # çakışmasını engellemeye yetecek kadar dar bir kısıt değil.
    baska_kategoride_bulundu = []
    alt_kategori_verildi = bool(veri.alt_kategori)
    verilen_yil = veri.yil and veri.yil.strip()

    if alt_kategori_verildi or verilen_yil:
        conn2 = veritabani_baglantisi(DB_FILE, row_factory=sqlite3.Row)
        cursor2 = conn2.cursor()
        gevsek_rows = []

        # (a) alt_kategori sabit, yıl bırakılıyor -- "kategori doğru,
        # sadece yıl yanlış/eksik" durumu.
        if alt_kategori_verildi:
            gevsek_veri = SimpleNamespace(yil=None, ana_kategori=veri.ana_kategori, alt_kategori=veri.alt_kategori)
            gevsek_rows = _sorguyu_calistir(cursor2, "dosya_no_norm", birincil_anahtar, gevsek_veri)
            if not gevsek_rows and yedek_anahtar and yedek_anahtar != birincil_anahtar:
                gevsek_rows = _sorguyu_calistir(cursor2, "dosya_no_tum_rakam", yedek_anahtar, gevsek_veri)

        # (b) yıl sabit, TÜM kategori bırakılıyor -- "yıl doğru/biliniyor,
        # kategori yanlış/bilinmiyor" durumu (ör. stadiu'dan bilinen yılla
        # ordine'de arama).
        if not gevsek_rows and verilen_yil:
            gevsek_veri = SimpleNamespace(yil=verilen_yil, ana_kategori=None, alt_kategori=None)
            gevsek_rows = _sorguyu_calistir(cursor2, "dosya_no_norm", birincil_anahtar, gevsek_veri)
            if not gevsek_rows and yedek_anahtar and yedek_anahtar != birincil_anahtar:
                gevsek_rows = _sorguyu_calistir(cursor2, "dosya_no_tum_rakam", yedek_anahtar, gevsek_veri)
        conn2.close()

        gorulen = set()
        for row in gevsek_rows:
            anahtar = (row["ana_kategori"], row["alt_kategori"], row["yil"])
            if anahtar in gorulen:
                continue
            gorulen.add(anahtar)
            baska_kategoride_bulundu.append({
                "ana_kategori": row["ana_kategori"],
                "alt_kategori": row["alt_kategori"],
                "yil": row["yil"],
            })

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
_yillik_istatistik_onbellek = {}  # yil -> {"zaman":..., "stadiu_set":..., "ordine_set":..., "bekleyenler":...}


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

    return {
        "toplam_stadiu": toplam_stadiu,
        "toplam_ordine": toplam_ordine,
        "toplam_onaylanan": toplam_onaylanan,
        "toplam_bekleyen": toplam_stadiu - toplam_onaylanan,
        "yillik_dagilim": yillik_dagilim,
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


class IstatistikIstegi(BaseModel):
    dosya_no: str = Field(max_length=100)
    yil: str = Field(max_length=10)


@app.post("/api/istatistikler/kisisel")
@limiter.limit("20/minute")
def istatistikler_kisisel(veri: IstatistikIstegi, request: Request, _anahtar=Depends(app_anahtarini_dogrula)):
    birincil = sayisal_cekirdek(veri.dosya_no)
    yil = (veri.yil or "").strip()
    if not birincil or not yil:
        return {"gecerli": False}

    simdi = time.time()
    onbellek = _yillik_istatistik_onbellek.get(yil)
    if onbellek is None or (simdi - onbellek["zaman"]) > _ISTATISTIK_ONBELLEK_SURESI_SN:
        conn = veritabani_baglantisi(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT dosya_no_norm FROM dosyalar WHERE ana_kategori='stadiu' AND yil = ?", (yil,)
        )
        stadiu_set = {row[0] for row in cursor.fetchall()}
        cursor.execute(
            "SELECT DISTINCT dosya_no_norm FROM dosyalar WHERE ana_kategori='ordine' AND yil = ?", (yil,)
        )
        ordine_set = {row[0] for row in cursor.fetchall()}
        conn.close()
        try:
            bekleyenler = sorted(stadiu_set - ordine_set, key=lambda x: int(x))
        except ValueError:
            bekleyenler = sorted(stadiu_set - ordine_set)
        onbellek = {"zaman": simdi, "stadiu_set": stadiu_set, "ordine_set": ordine_set, "bekleyenler": bekleyenler}
        _yillik_istatistik_onbellek[yil] = onbellek

    stadiu_set = onbellek["stadiu_set"]
    ordine_set = onbellek["ordine_set"]
    bekleyenler = onbellek["bekleyenler"]

    if birincil in ordine_set:
        return {
            "gecerli": True,
            "durum": "onaylanmis",
            "yil": yil,
            "toplam_stadiu": len(stadiu_set),
            "toplam_ordine": len(ordine_set),
            "toplam_bekleyen": len(bekleyenler),
        }
    if birincil in stadiu_set:
        sira = bekleyenler.index(birincil) + 1
        return {
            "gecerli": True,
            "durum": "bekliyor",
            "yil": yil,
            "toplam_stadiu": len(stadiu_set),
            "toplam_ordine": len(ordine_set),
            "toplam_bekleyen": len(bekleyenler),
            "sira": sira,
            "sonrasinda_kalan": len(bekleyenler) - sira,
        }
    return {
        "gecerli": True,
        "durum": "bulunamadi",
        "yil": yil,
        "toplam_stadiu": len(stadiu_set),
        "toplam_ordine": len(ordine_set),
        "toplam_bekleyen": len(bekleyenler),
    }


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
