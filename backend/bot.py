# -*- coding: utf-8 -*-
"""
cetatenie.just.ro üzerindeki STADIU DOSAR ve ORDINE sayfalarını tarar,
her alt kategori başlığı için ayrı bir klasör açıp PDF'leri oraya indirir:

    backend/pdfs/stadiu/<ALT KATEGORİ>/*.pdf
    backend/pdfs/ordine/<ALT KATEGORİ>/*.pdf

İndirilen her PDF, indirilir indirilmez aktar.py ile veritabanına işlenir.
Tarama bittiğinde: (1) yeni kayıt varsa tüm kullanıcılara genel bildirim,
(2) favori dosyası ONAYLANDI'ya geçen kullanıcılara kişisel bildirim +
admin'e kritik uyarı, (3) site erişilemiyorsa ya da beklenen kategoriler
sayfada bulunamıyorsa admin'e uyarı gönderilir.

ÖNEMLİ: Kategori butonları sayfadaki HER buton/link taranarak değil,
doğrudan dosya_utils.py'deki sabit liste üzerinden TEK TEK aranıp
tıklanarak bulunuyor (bkz. _kategori_elementini_bul).
"""
import json
import os
import re
import sqlite3
import time
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
try:
    from urllib3.util.retry import Retry
except ImportError:  # eski urllib3 sürümleri için yedek yol
    from requests.packages.urllib3.util.retry import Retry
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

# ÖNEMLİ (2026-08-14 tespiti): elle açılan bir tarayıcıda cetatenie.just.ro
# sorunsuz yükleniyorken, Python'un `requests` kütüphanesiyle yapılan
# isteklerin AYNI ağdan bile tutarlı biçimde başarısız/zaman aşımına
# uğradığı doğrulandı. Bu, IP engeli değil -- TLS/tarayıcı "parmak izi"
# (JA3/JA4) tabanlı bir bot-engelleme (WAF) sistemine işaret ediyor: site,
# gerçek bir tarayıcının TLS el sıkışmasıyla Python `requests`in TLS el
# sıkışmasını ayırt edip ikincisini reddediyor olabilir.
#
# Çözüm: mümkünse `curl_cffi` kullanıyoruz -- bu kütüphane, requests ile
# BİREBİR aynı arayüze sahip ama gerçek bir Chrome/Firefox'un TLS parmak
# izini taklit edebiliyor (bkz. `impersonate=` parametresi). Kurulu değilse
# koda hiç dokunmadan otomatik olarak normal `requests`e geri dönüyoruz --
# uygulama HER ZAMAN çalışır, sadece `curl_cffi` kuruluysa engeli aşma
# ihtimali belirgin şekilde artar.
#
# Kurmak için (VS Code terminalinde, backend klasöründeyken):
#     pip install curl_cffi
try:
    from curl_cffi import requests as curl_cffi_requests
    _CURL_CFFI_VAR = True
except ImportError:
    _CURL_CFFI_VAR = False

# Gerçek bir Chrome tarayıcısının gönderdiği başlıklara olabildiğince
# yakın bir set -- sadece User-Agent değil, WAF'ların "bu gerçek bir
# tarayıcı mı" diye baktığı diğer başlıklar da (Accept, Sec-Fetch-*,
# Accept-Language vb.) dahil edildi.
TARAYICI_BASLIKLARI = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
}

from aktar import pdf_verilerini_ice_aktar, tabloyu_olustur, DB_FILE
from dosya_utils import (
    STADIU_ALT_KATEGORILERI,
    ORDINE_ALT_KATEGORILERI,
    klasor_adi_guvenli,
    metni_sadelestir,
    veritabani_baglantisi,
    pdf_zaten_islenmis_mi,
    stadiu_dosya_kategorisi_uyusuyor_mu,
    ordine_dosya_kategorisi_uyusuyor_mu,
    sistem_olayi_kaydet,
    bekleme_kuyrugunu_guncelle,
    ROMANYA_SAAT_DILIMI,
)
from bildirim import expo_push_gonder, admin_kritik_uyari

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 2026-08-19 (Render'a taşıma): bkz. main.py'deki aynı isimli sabitin notu --
# DATA_DIR ayarlıysa kalıcı diskten, yoksa (yerel geliştirme) eskisi gibi
# backend/ klasöründen okunur/yazılır.
VERI_DIZINI = os.environ.get("DATA_DIR", BASE_DIR)
PDF_KOK_KLASOR = os.path.join(VERI_DIZINI, "pdfs")


def _guncel_yil_dosyasi_mi(dosya_adi):
    """
    2026-08-31 KÖK NEDEN DÜZELTMESİ (kullanıcı canlı testte bulundu -- 1-2
    haneli dosya numaraları sorguda "bulunamadı" çıkıyordu, aynı PDF'teki
    3 haneli numaralar ise buluyordu): site, İÇİNDE BULUNULAN YILA ait bazı
    PDF'leri AYNI dosya adında YERİNDE güncelliyor -- yeni kayıtlar
    eklendikçe dosya büyüyor ama adı (dolayısıyla bizim "zaten indirildi"
    kısayolumuzun anahtarı) DEĞİŞMİYOR. Kanıt: "Art-10-2026-update-
    07.08.2026.pdf" veritabanımızda 102'den başlıyordu (1205 kayıt) ama
    sitenin GÜNCEL hâlinde 3'ten başlıyordu (kullanıcının bizzat indirip
    paylaştığı dosyada doğrulandı -- aynı pypdf/regex koduyla yerel testte
    3, 5, 6, 10, 13... hepsi sorunsuz çıktı). Yani içerik değişmiş ama
    "zaten var/işlendi" kontrolümüz bunu hiç yakalamıyordu -- ilk indirilen
    anlık görüntü sonsuza kadar donduruluyordu.

    Dosya adındaki "20XX" deseni içinde bulunulan yıla eşitse, bu dosya
    HÂLÂ BÜYÜYOR olabilecek "aktif" bir dosya sayılır -- çağıran kod
    "zaten var/işlendi, atla" kısayolunu bu dosyalar için atlayıp her
    taramada yeniden indirip işlemeli. ESKİ yılların (kapanmış) dosyaları
    için False döner -- onların "zaten işlendi, atla" davranışı HİÇ
    değişmez (gereksiz yük/WAF riski yok, 2019-2025 arşivi test edildi:
    toplam birkaç düzine kayıt, kapanmış).
    """
    eslesme = re.search(r"\b(20\d{2})\b", dosya_adi)
    if not eslesme:
        return False
    return eslesme.group(1) == str(datetime.now(ROMANYA_SAAT_DILIMI).year)

# TEŞHİS MODU (2026-08-15 eklendi): bazı alt kategoriler (CONSULAT / ANC,
# REZULTATE/INVITATII INTERVIU ART. 8 ve 8.1) sayfada hiç bulunamıyor --
# _kategori_elementini_bul None dönüyor, klasörleri bile açılmıyor. Kök
# nedeni görebilmek için (nested menü mü, farklı yazım mı, sayfalama mı)
# bulunamayan HER kategori için o anki sayfanın tam HTML'ini ve tam sayfa
# ekran görüntüsünü buraya kaydediyoruz. Sadece yerel teşhis içindir,
# sunucuya/git'e taşınmaz (bkz. .gitignore).
TESHIS_KLASOR = os.path.join(VERI_DIZINI, "teshis")

# NOT: Bu iki adres, kullanıcının verdiği gerçek sayfalarla BİREBİR aynı
# olmalı -- "stadiu-dosar" adresinde fazladan bir "/cetatenie/" segmenti
# olması (eski hata) sayfanın hiç açılmamasına ve o kategorinin tamamen
# atlanmasına sebep oluyordu.
URLS = [
    ("ordine", "https://cetatenie.just.ro/ordine-2/", ORDINE_ALT_KATEGORILERI),
    ("stadiu", "https://cetatenie.just.ro/stadiu-dosar/", STADIU_ALT_KATEGORILERI),
]


def _http_oturumu_olustur():
    """
    Tüm PDF indirmeleri için TEK ve tekrar kullanılan bir HTTP oturumu
    oluşturur. Önceki sürümde her PDF için ayrı bir Session açılıp hiç
    kapatılmıyordu -- yüzlerce dosyalık bir taramada bu, Windows'ta ard
    arda çok sayıda soket açılmasına (ve bir noktadan sonra
    'Max retries exceeded' hatasıyla bağlantıların reddedilmesine) yol
    açabiliyordu. Ayrıca geçici ağ/timeout hatalarında (ör. site anlık
    yavaşladığında ya da hız sınırlamasına takıldığında) otomatik olarak
    birkaç kez, artan bekleme süreleriyle yeniden dener.

    `curl_cffi` kuruluysa GERÇEK bir Chrome TLS parmak iziyle (impersonate)
    istek atan bir oturum döner -- WAF'ın "bu bir bot" diye ayırt etmesini
    büyük ölçüde zorlaştırır. Kurulu değilse, aynı arayüze sahip normal
    `requests.Session`e (artırılmış tarayıcı başlıklarıyla) geri döner.
    """
    if _CURL_CFFI_VAR:
        oturum = curl_cffi_requests.Session(impersonate="chrome124")
        oturum.headers.update(TARAYICI_BASLIKLARI)
        return oturum

    oturum = requests.Session()
    yeniden_deneme = Retry(
        total=4,
        connect=4,
        read=4,
        backoff_factor=2,  # 2sn, 4sn, 8sn, 16sn artan bekleme
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=yeniden_deneme, pool_connections=10, pool_maxsize=10)
    oturum.mount("https://", adapter)
    oturum.mount("http://", adapter)
    oturum.headers.update(TARAYICI_BASLIKLARI)
    return oturum


def _mesai_saatinde_mi():
    """Mesai saatleri: 08:00-17:59 (bkz. main.py'deki scheduler, 08-17 arası
    çalışıyor). Bu aralığın dışında resmi site planlı bakım moduna girebilir
    -- bu yüzden mesai dışı erişim sorunları "olağan dışı bir kesinti"
    sayılıp admin'e uyarı gönderilmez, sadece mesai saatleri içinde yaşanan
    kesintiler bildirilir (kullanıcının 2026-08-14 talebi)."""
    return 8 <= datetime.now(ROMANYA_SAAT_DILIMI).hour <= 17


def _site_erisilebilir_mi(page, url, deneme_sayisi=2):
    """Taramaya başlamadan önce sitenin ayakta olup olmadığını kontrol eder.

    KESİN TESPİT (2026-08-14): elle açılan bir tarayıcıda (hem ev interneti
    hem telefon hotspot'unda) https://cetatenie.just.ro/stadiu-dosar/
    sorunsuz yüklenirken, Python'un `requests` kütüphanesiyle yapılan
    AYNI istek AYNI ağdan tutarlı biçimde zaman aşımına uğruyordu. Bu artık
    "site kararsız" değil, TLS/tarayıcı parmak izi tabanlı bir bot-engelleme
    (WAF) belirtisi -- `requests`in TLS el sıkışması gerçek bir tarayıcıdan
    farklı olduğu için ayrı ayrı engelleniyor olabilir.

    ÇÖZÜM: bu kontrolü artık ayrı bir `requests` isteğiyle DEĞİL, bizzat
    tarama için zaten kullandığımız GERÇEK Playwright tarayıcı sekmesiyle
    (2026-08-25'ten beri Chromium, bkz. botu_calistir() -- bellek nedeniyle
    Firefox'tan geçildi) yapıyoruz -- gerçek bir tarayıcı motoru olduğu
    için elle açılan tarayıcıyla birebir aynı davranışı gösterir, bu
    nedenle bu engelin dışında kalır.
    """
    for deneme in range(1, deneme_sayisi + 1):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=25000)
            return True
        except Exception:
            pass
        if deneme < deneme_sayisi:
            time.sleep(deneme * 3)
    return False


def _tum_push_tokenlari():
    conn = veritabani_baglantisi(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT expo_push_token FROM push_tokenlari")
    tokenlar = [row[0] for row in cursor.fetchall()]
    conn.close()
    return tokenlar


def _favori_sahiplerini_bul(dosya_no_norm, yil):
    # 2026-08-16 düzeltmesi: 'yil' de eşleştirmeye dahil edildi -- aksi
    # halde aynı çıplak numarayı taşıyan FARKLI yıllardaki (başka kişilere
    # ait) dosyalar onaylandığında da yanlışlıkla "favori dosyanız
    # onaylandı" bildirimi giderdi. 'ana_kategori' BİLEREK filtreye dahil
    # edilmiyor -- favori, kayıt STADIU iken eklenmiş olabilir, buraya
    # ORDINE kaydıyla geliniyor (bkz. dosya_utils.py notu).
    #
    # 2026-08-17 KRİTİK DÜZELTME: favoriler.expo_push_token, GERÇEK bir
    # Expo push token DEĞİL -- constants/api.tsx'teki cihazKimligiGetir()
    # ile üretilmiş RASTGELE bir cihaz kimliği (ör. "cihaz-a3f8..."). Bu
    # sütunu doğrudan expo_push_gonder()'e vermek, Expo'nun API'sinin bu
    # sahte kimliği reddetmesine (bildirimin HİÇBİR ZAMAN ulaşmamasına)
    # yol açıyordu. Artık push_tokenlari tablosuyla cihaz_kimligi üzerinden
    # JOIN yapılıp GERÇEK expo_push_token bulunuyor -- eşleşme yoksa (ör.
    # kullanıcı bildirim iznini hiç vermemişse) o satır atlanır.
    #
    # NOT: otomatik_mi kolonuna göre HİÇBİR filtre uygulanmıyor -- hem
    # kullanıcının bilerek eklediği (otomatik_mi=0) hem sistemin sorgulama
    # sırasında sessizce oluşturduğu (otomatik_mi=1) kayıtlar AYNI şekilde
    # bildirim almaya hak kazanır (kullanıcı isteği: favori eklemek
    # bildirim şartı olmasın).
    conn = veritabani_baglantisi(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT pt.expo_push_token, f.dosya_no
        FROM favoriler f
        JOIN push_tokenlari pt ON pt.cihaz_kimligi = f.expo_push_token
        WHERE f.dosya_no_norm = ? AND f.yil IS ?
        """,
        (dosya_no_norm, yil),
    )
    satirlar = cursor.fetchall()
    conn.close()
    return satirlar


def _kategori_elementini_bul(page, alt_kategori):
    """
    Sayfada, metni verilen alt kategoriyle (aksan/tırnak/boşluk farkları göz
    ardı edilerek) en iyi eşleşen tıklanabilir elementi bulur.
    Önce TAM (sadeleştirilmiş) eşleşmeyi arar; bulamazsa en kısa "içeren"
    eşleşmeyi döndürür. Hiçbir aday yoksa None döner.
    """
    hedef = metni_sadelestir(alt_kategori)
    adaylar = page.get_by_text(alt_kategori, exact=False)

    try:
        sayi = adaylar.count()
    except Exception:
        return None

    en_iyi = None
    en_iyi_uzunluk = None

    for i in range(min(sayi, 20)):
        eleman = adaylar.nth(i)
        try:
            metin = eleman.text_content() or ""
        except Exception:
            continue
        sade = metni_sadelestir(metin)

        if sade == hedef:
            return eleman  # tam eşleşme -- hemen kullan

        if hedef in sade and (en_iyi_uzunluk is None or len(sade) < en_iyi_uzunluk):
            en_iyi = eleman
            en_iyi_uzunluk = len(sade)

    return en_iyi


# 2026-08-15 -- ÜÇÜNCÜ ve KESİN tespit (ekran görüntüsü kanıtıyla):
# stadiu-dosar sayfası basit bir SEKME (tab) arayüzü -- 11 kategori de
# (ARTICOLUL 11/8/8″1/8″2/10, NR. DOSAR, CONSULAT/ANC, REZULTATE/
# INVITATII INTERVIU ART. 8 ve 8.1) SOLDA AYNI ANDA, EŞİT SEVİYEDE
# görünüyor -- hiçbiri "ARTICOLUL 8"in çocuğu/iç içe öğesi DEĞİL. Bir
# sekmeye tıklandığında SAĞDAKİ içerik paneli o sekmenin kendi listesiyle
# değişiyor. ÖNCEKİ İKİ sürümdeki "önce ARTICOLUL 8'i aç" numarası (bkz.
# git geçmişi) YANLIŞ bir varsayıma dayanıyordu ve muhtemelen tam olarak
# BULAŞMANIN kendisine sebep oluyordu (çifte tıklama -- önce ARTICOLUL 8,
# sonra hedef sekme -- content panelinin düzgün değişmesine fırsat
# vermeden ikinci tıklamayı yapıyor olabiliyordu). O yüzden TAMAMEN
# kaldırıldı. Yerine SADECE SABIR var: sekme çubuğunun JS ile geç
# render olma ihtimaline karşı, bulunamazsa biraz daha bekleyip TEK
# SEFERLİK yeniden dener -- başka hiçbir sekmeye dokunmadan.
def _sabirla_tekrar_ara(page, alt_kategori, ekstra_bekleme_ms=4000):
    """Kategori doğrudan bulunamazsa, sayfanın (JS ile geç render olan)
    sekme çubuğunun tamamen yüklenmesi için biraz daha bekleyip TEK
    SEFERLİK tekrar arar. Başka hiçbir elemana tıklamaz."""
    page.wait_for_timeout(ekstra_bekleme_ms)
    return _kategori_elementini_bul(page, alt_kategori)


def _teshis_kaydet(page, tip, alt_kategori, url):
    """
    Bir alt kategori sayfada bulunamadığında (_kategori_elementini_bul None
    döndüğünde) çağrılır. O anki sayfanın tam HTML'ini (.html) ve tam sayfa
    ekran görüntüsünü (.png) TESHIS_KLASOR'e kaydeder -- amaç, kategorinin
    gerçekte sayfada nerede olduğunu (başka bir kategorinin içinde iç içe mi,
    farklı yazılmış mı, ayrı bir sekmede mi) sonradan inceleyebilmek.
    Teşhis kaydı başarısız olsa bile taramanın geri kalanını ENGELLEMEMELİ,
    bu yüzden tüm hatalar burada yutuluyor.
    """
    try:
        os.makedirs(TESHIS_KLASOR, exist_ok=True)
        dosya_govdesi = f"{tip}_{klasor_adi_guvenli(alt_kategori)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        html_yolu = os.path.join(TESHIS_KLASOR, dosya_govdesi + ".html")
        with open(html_yolu, "w", encoding="utf-8") as f:
            f.write(page.content())

        png_yolu = os.path.join(TESHIS_KLASOR, dosya_govdesi + ".png")
        page.screenshot(path=png_yolu, full_page=True)

        print(f"  🔎 Teşhis kaydedildi: {dosya_govdesi}.html / .png (kaynak: {url})")
    except Exception as e:
        print(f"  ✗ Teşhis kaydı alınamadı ({alt_kategori}): {str(e)[:80]}")


# =============================================================================
# "B PLANI" -- TASARIMDAN BAĞIMSIZ PDF KEŞFİ (2026-08-19, kullanıcı önerisi)
# =============================================================================
# Kök gerekçe: aynı gün canlı testte doğrulandı ki cetatenie.just.ro,
# ORDINE tarafını (tıklama/sekme yapısından ayrı sayfalara) tamamen yeniden
# yapılandırmış -- yani site tasarımı gelecekte YİNE değişebilir, bu her
# zaman bir risk. A Planı (yukarıdaki _kategori_elementini_bul + tıklama)
# sayfa YAPISINA bağımlı; bu iki fonksiyon ise WordPress'in kendi yerleşik,
# SEO amaçlı, görsel tasarımdan TAMAMEN bağımsız REST API'sini kullanıyor
# (/wp-json/wp/v2/media) -- buton/sekme/class adı ne olursa olsun çalışır.
#
# ÖNEMLİ TASARIM KARARI: B Planı SÜREKLİ paralel çalışmıyor (kullanıcının
# net isteği -- siteye gereksiz ek yük bindirmemek için). SADECE A Planı bir
# kategoriyi TAMAMEN bulamadığında (aşağıda "eleman is None" dalında) TEK
# SEFERLİK devreye giriyor. A Planı'nın kendi (yukarıdaki, iyice test
# edilmiş) indirme döngüsüne KASITLI OLARAK dokunulmadı -- bu iki fonksiyon
# tamamen izole, kendi indirme mantığını taşıyor. Amaç: B Planı'ndaki
# olası bir hata, A Planı'nın çalışan akışını hiçbir şekilde etkileyemesin.
def _wp_json_ile_pdf_kesfet(page, taban_url="https://cetatenie.just.ro", sayfa_sayisi_limit=20, sayfa_basi=50):
    """
    WordPress'in yerleşik REST API'si üzerinden site genelinde yüklenmiş
    TÜM PDF medyalarını (en yeniden eskiye) keşfeder. Sayfa tasarımıyla
    hiçbir ilgisi yok -- site menüsünü/sekmelerini değiştirse bile bu uç
    nokta (WordPress çekirdek özelliği) genelde aynı kalır.

    2026-08-19 DÜZELTMESİ (canlı testle bulundu): bu uç nokta da site
    genelindeki WAF'ın JS meydan okumasının ("Verifying your browser...")
    ARKASINDA -- düz `requests`/`curl_cffi` (JS ÇALIŞTIRMAZLAR) her zaman
    503 alır, hiçbir zaman gerçek JSON'a ulaşamaz. Bu yüzden A Planı'nın
    zaten kullandığı GERÇEK Playwright `page` nesnesi üzerinden
    (meydan okuma otomatik çözülene kadar bekleyip) istek atılıyor --
    canlı testte doğrulandı: ~4sn içinde gerçek PDF verisi geliyor.
    """
    kesfedilen = []
    for sayfa in range(1, sayfa_sayisi_limit + 1):
        istek_url = (
            f"{taban_url}/wp-json/wp/v2/media"
            f"?mime_type=application/pdf&per_page={sayfa_basi}"
            f"&orderby=date&order=desc&page={sayfa}"
        )
        try:
            page.goto(istek_url, wait_until="domcontentloaded", timeout=30000)
            # WAF meydan okumasının çözülmesini bekle (en fazla 15sn) --
            # aynı desen, projede başka yerlerde de kullanılıyor.
            for _ in range(15):
                if "verifying" not in page.content().lower():
                    break
                time.sleep(1)

            metin = page.evaluate("() => document.body.innerText")
            veri = json.loads(metin)

            # WP REST API, sayfa sayısı aşıldığında liste yerine
            # {"code": "rest_post_invalid_page_number", ...} döner --
            # bu, "daha fazla sayfa yok, dur" sinyalidir.
            if isinstance(veri, dict) and veri.get("code"):
                break
            if not veri:
                break

            for madde in veri:
                kaynak = madde.get("source_url")
                if kaynak and kaynak.lower().endswith(".pdf"):
                    kesfedilen.append(kaynak)

            time.sleep(1.5)  # siteye nazik davranmak için sayfalar arası bekleme
        except Exception as e:
            print(f"  ✗ B Planı (wp-json) keşif hatası (sayfa {sayfa}): {str(e)[:80]}")
            break
    return kesfedilen


def _b_plani_devreye_al(page, tip, alt_kategori, http_oturum, kontrol_conn):
    """
    A Planı bir kategoriyi HİÇ bulamadığında çağrılır. wp-json üzerinden
    keşfedilen TÜM PDF'ler arasından, dosya adı bu alt_kategoriyle uyuşanları
    seçip A Planı ile AYNI güvenlik kurallarına (kategori-dosya adı eşleşmesi,
    zaten-işlendi kontrolü) tabi tutarak indirir/veritabanına işler.
    Döner: (indirilen_sayısı, kaydedilen_kayıt, yeni_kayıtlar_listesi)
    """
    print(f"  🔁 B Planı devreye giriyor: '{alt_kategori}' için wp-json üzerinden keşif deneniyor...")
    try:
        tum_pdfler = _wp_json_ile_pdf_kesfet(page)
    except Exception as e:
        print(f"  ✗ B Planı tamamen başarısız oldu: {str(e)[:80]}")
        return 0, 0, []

    if not tum_pdfler:
        print("  ✗ B Planı: wp-json'dan hiç PDF keşfedilemedi (site bu API'yi desteklemiyor olabilir).")
        return 0, 0, []

    klasor_yolu = os.path.join(PDF_KOK_KLASOR, tip, klasor_adi_guvenli(alt_kategori))
    os.makedirs(klasor_yolu, exist_ok=True)

    indirilen_sayisi = 0
    kaydedilen_kayit = 0
    yeni_kayitlar = []
    eslesen_sayisi = 0

    for href in tum_pdfler:
        dosya_adi = href.split('/')[-1].split('?')[0]
        if not dosya_adi.endswith('.pdf'):
            dosya_adi += ".pdf"

        if tip == "stadiu" and not stadiu_dosya_kategorisi_uyusuyor_mu(dosya_adi, alt_kategori):
            continue
        if tip == "ordine" and not ordine_dosya_kategorisi_uyusuyor_mu(dosya_adi, alt_kategori):
            continue
        eslesen_sayisi += 1

        hedef_yol = os.path.join(klasor_yolu, dosya_adi)
        # 2026-08-31: bkz. _guncel_yil_dosyasi_mi -- aktif yılın dosyaları
        # yerinde büyüyebiliyor, "zaten var" kısayolu onlar için atlanır.
        if os.path.exists(hedef_yol) and not _guncel_yil_dosyasi_mi(dosya_adi):
            if pdf_zaten_islenmis_mi(kontrol_conn, tip, alt_kategori, dosya_adi):
                continue
            try:
                eklenen, yeni = pdf_verilerini_ice_aktar(hedef_yol, tip, alt_kategori, kaynak_url=href)
                kaydedilen_kayit += eklenen
                yeni_kayitlar.extend(yeni)
            except Exception as e:
                print(f"      ✗ (B Planı) Veritabanına işlenirken hata: {str(e)[:80]}")
            continue

        try:
            # 2026-08-25: bkz. A Planı'ndaki aynı düzeltmenin gerekçe notu --
            # ayrı http_oturum (curl_cffi) artık WAF'a takılıyor, PDF'i
            # Playwright context'inin kendi ağ istemcisiyle indiriyoruz.
            pdf_res = page.context.request.get(
                href, headers={"Referer": "https://cetatenie.just.ro/"}, timeout=45000
            )
            if pdf_res.status == 200 and len(pdf_res.body()) > 1000:
                with open(hedef_yol, 'wb') as f:
                    f.write(pdf_res.body())
                with open(hedef_yol + ".url", "w", encoding="utf-8") as f:
                    f.write(href)
                eklenen, yeni = pdf_verilerini_ice_aktar(hedef_yol, tip, alt_kategori, kaynak_url=href)
                kaydedilen_kayit += eklenen
                yeni_kayitlar.extend(yeni)
                indirilen_sayisi += 1
                print(f"      ✓ (B Planı) Kaydedildi: {dosya_adi}")
            else:
                print(f"      ✗ (B Planı) Geçersiz: {dosya_adi}")
        except Exception as e:
            print(f"      ✗ (B Planı) Hata: {str(e)[:60]}")
        time.sleep(1.5)

    print(f"  🔁 B Planı tamamlandı: {eslesen_sayisi} eşleşen PDF, {indirilen_sayisi} yeni indirildi.")
    return indirilen_sayisi, kaydedilen_kayit, yeni_kayitlar


def _bildirimleri_gonder(tum_yeni_kayitlar, bulunamayan_kategoriler, toplam_pdf_bulunan,
                          basarisiz_indirme_sayisi=0, kalici_eksik_sayisi=0):
    # 1) Genel duyuru: yeni kayıt varsa TÜM kullanıcılara bildirim.
    if tum_yeni_kayitlar:
        tokenlar = _tum_push_tokenlari()
        if tokenlar:
            expo_push_gonder(
                tokenlar,
                "Yeni dosya eklendi",
                "cetatenie.just.ro sayfası sisteme yeni dosya eklemiştir, sorgulamak için dokunun.",
                {"tip": "yeni_dosya"},
            )
            print(f"✓ Genel bildirim {len(tokenlar)} cihaza gönderildi.")

        # 2) Favori dosyası ONAYLANDI'ya (ordine) geçenlere kişisel bildirim + admin uyarısı.
        for kayit in tum_yeni_kayitlar:
            if kayit["ana_kategori"] != "ordine":
                continue
            sahipler = _favori_sahiplerini_bul(kayit["dosya_no_norm"], kayit["yil"])
            for token, gosterilen_no in sahipler:
                expo_push_gonder(
                    [token],
                    "Tebrikler!",
                    f"{gosterilen_no} numaralı dosyanız ONAYLANDI!",
                    {"tip": "favori_onay", "dosya_no": gosterilen_no},
                )
                admin_kritik_uyari(
                    f"{gosterilen_no} numaralı favori dosya ONAYLANDI "
                    f"(kategori: {kayit['alt_kategori']})."
                )

    # 3) Yapı/erişim anomali kontrolü.
    if bulunamayan_kategoriler:
        admin_kritik_uyari(
            "cetatenie.just.ro sayfa yapısı değişmiş olabilir -- şu kategoriler "
            f"bulunamadı: {', '.join(bulunamayan_kategoriler)}"
        )
    if toplam_pdf_bulunan == 0 and _mesai_saatinde_mi():
        # Mesai dışında hiç PDF bulunamaması büyük olasılıkla site bakımda
        # olduğu içindir (bkz. _mesai_saatinde_mi) -- bu durumda admin'e
        # gereksiz "kontrol et" uyarısı gönderilmez.
        admin_kritik_uyari(
            "Bu taramada hiç PDF bulunamadı. Site yapısı değişmiş ya da "
            "erişim sorunu olabilir, kontrol et."
        )

    # 2026-08-25 EKLENTİSİ: kör noktanın kapatılması -- yukarıdaki kontrol
    # SADECE "hiç PDF LİNKİ bulunamadı" durumunu yakalıyor. Bizim gerçek
    # yaşadığımız arıza farklıydı: linkler (toplam_pdf_bulunan) normal
    # şekilde bulunuyordu ama İNDİRME aşaması (WAF 503 vb.) sessizce
    # başarısız oluyordu -- hiçbir uyarı gitmiyordu, sorun günler sonra
    # kullanıcı fark edene kadar gizli kaldı. Eşik olarak 3 seçildi: tek
    # bir ara sıra ağ hatası (kullanıcıyı gereksiz yere telaşlandırmadan)
    # normal sayılır, ama art arda birden fazla başarısız GERÇEK indirme
    # denemesi artık rastgele bir hata değil, sistemik bir engel işaretidir.
    if basarisiz_indirme_sayisi >= 3:
        admin_kritik_uyari(
            f"{basarisiz_indirme_sayisi} PDF indirme denemesi başarısız oldu "
            "(dosyalar bulundu ama indirilemedi, HTTP 404 hariç) -- WAF/erişim "
            "engeli olabilir, kontrol et."
        )

    # 2026-08-26: gerçek HTTP 404'ler (WAF DEĞİL, kaynak sitede dosya kalıcı
    # olarak yok -- bkz. .404 işaret dosyası notu) admin'e panik uyarısı
    # olarak DEĞİL, bilgilendirici bir not olarak gidiyor -- her taramada
    # tekrar denenmeyecekleri için bu mesaj da SADECE İLK KEZ karşılaşıldığı
    # gün gidecek (kalici_eksik_sayisi ancak yeni bir .404 dosyası
    # OLUŞTUĞUNDA >0 olur, zaten işaretli dosyalar sessizce atlanıyor).
    if kalici_eksik_sayisi > 0:
        admin_kritik_uyari(
            f"Bilgi: {kalici_eksik_sayisi} PDF, cetatenie.just.ro'nun kendi "
            "sitesinde linki duruyor ama sunucudan kaldırılmış (gerçek HTTP "
            "404, WAF değil). Kalıcı olarak 'eksik' işaretlendi, bir daha "
            "denenmeyecek -- işlem gerekmiyor."
        )


def botu_calistir():
    tabloyu_olustur()
    indirilen = 0
    kaydedilen_kayit = 0
    tum_yeni_kayitlar = []
    bulunamayan_kategoriler = []
    toplam_pdf_bulunan = 0
    # 2026-08-25 EKLENTİSİ: kök nedeni bulunan gerçek bir kör noktaya karşı --
    # PDF LİNKLERİ bulunuyor (toplam_pdf_bulunan > 0, "hiç PDF yok" uyarısı
    # hiç tetiklenmiyor) ama İNDİRME aşamasında (ör. WAF 503 döndürünce)
    # sessizce "✗ Geçersiz"/"✗ Hata" yazılıp bir sonraki dosyaya geçiliyordu
    # -- admin'e HİÇBİR uyarı gitmiyordu, sorun günler sonra kullanıcı fark
    # edene kadar gizli kaldı. Artık her BAŞARISIZ gerçek indirme denemesi
    # (dosya diskte yoktu, indirme denendi, 200/geçerli boyut alınamadı ya da
    # exception oluştu) burada sayılıyor -- bkz. _bildirimleri_gonder.
    basarisiz_indirme_sayisi = 0
    # 2026-08-26: GERÇEK HTTP 404 (kaynak sitede dosya kalıcı olarak yok)
    # basarisiz_indirme_sayisi'nden AYRI sayılıyor -- bu bir WAF/erişim
    # sorunu değil, cetatenie.just.ro'nun kendi arşiv tutarsızlığı; admin
    # uyarısının yanlış "WAF/erişim engeli" teşhisi koymaması için.
    kalici_eksik_sayisi = 0

    http_oturum = _http_oturumu_olustur()

    # Zaten diskte olan PDF'lerin "daha önce işlendi mi" kontrolü için tek
    # bir okuma bağlantısı (her dosya için ayrı ayrı açıp kapatmak yerine).
    kontrol_conn = veritabani_baglantisi(DB_FILE)

    with sync_playwright() as p:
        # 2026-08-25 KÖK NEDEN DÜZELTMESİ (canlı Render metrikleriyle
        # kanıtlandı): Firefox headless, context+page açar açmaz TEK
        # BAŞINA ~524MB RSS'e çıkıyor (yerel ölçüm) -- Render Starter
        # planının 512MB limitini FastAPI'nin kendi ~90MB'lık idle
        # kullanımı eklenmeden bile aşıyor. Bot her tetiklendiğinde
        # (hem günlük 09:00 taraması hem manuel tetiklemeler) OOM ile
        # ÖLDÜRÜLÜYORDU -- "KATEGORİ: ORDINE, Bağlanılıyor..." print'i
        # çıktıktan saniyeler sonra instance sessizce restart oluyordu,
        # tarama hiçbir zaman ilerleyemiyordu (Render events API'sinde
        # "oomKilled": {"memoryLimit": "512Mi"} ile doğrulandı). Chromium
        # headless aynı sayfa+indirme akışında sadece ~312MB kullanıyor
        # (yerel ölçüm) -- WAF geçişi ve context.request ile PDF indirme
        # Chromium'da da AYNI şekilde çalıştığı canlı test edildi. Render
        # build komutu da "playwright install firefox"tan "playwright
        # install chromium"a güncellendi.
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        for tip, url, alt_kategori_listesi in URLS:
            print(f"\n{'='*60}")
            print(f"KATEGORİ: {tip.upper()}")
            print(f"Bağlanılıyor: {url}")
            print(f"{'='*60}")

            if not _site_erisilebilir_mi(page, url):
                print(f"✗ {url} adresine erişilemiyor, bu bölüm atlanıyor.")
                if _mesai_saatinde_mi():
                    admin_kritik_uyari(f"cetatenie.just.ro ({url}) şu anda erişilemiyor gibi görünüyor.")
                else:
                    print("  (mesai saati dışında olduğu için admin'e uyarı gönderilmedi -- site bakımda olabilir.)")
                continue

            for alt_kategori in alt_kategori_listesi:
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    time.sleep(3)

                    eleman = _kategori_elementini_bul(page, alt_kategori)
                    if eleman is None:
                        # Doğrudan bulunamadı -- HİÇBİR ŞEYE TIKLAMADAN,
                        # sadece sekme çubuğunun geç render olma ihtimaline
                        # karşı biraz daha bekleyip tekrar arıyoruz (bkz.
                        # _sabirla_tekrar_ara'daki 2026-08-15 notu).
                        eleman = _sabirla_tekrar_ara(page, alt_kategori)
                        if eleman is not None:
                            print(f"  ℹ '{alt_kategori}' ilk denemede bulunamadı, "
                                  f"biraz bekleyince bulundu.")

                    if eleman is None:
                        print(f"  ! '{alt_kategori}' sayfada bulunamadı, atlanıyor.")
                        bulunamayan_kategoriler.append(f"{tip}/{alt_kategori}")
                        _teshis_kaydet(page, tip, alt_kategori, url)

                        # B PLANI (2026-08-19): A Planı bu kategoriyi hiç
                        # bulamadı -- muhtemelen site tasarımı yine değişti
                        # (tıpkı bugün Ordine'de olduğu gibi). Tasarımdan
                        # bağımsız wp-json keşfiyle telafi etmeyi dene.
                        try:
                            b_indirilen, b_kaydedilen, b_yeni = _b_plani_devreye_al(
                                page, tip, alt_kategori, http_oturum, kontrol_conn
                            )
                            indirilen += b_indirilen
                            kaydedilen_kayit += b_kaydedilen
                            tum_yeni_kayitlar.extend(b_yeni)
                            toplam_pdf_bulunan += b_indirilen
                        except Exception as e:
                            print(f"  ✗ B Planı çağrısı başarısız: {str(e)[:80]}")

                        continue

                    print(f"\n  → Kategori açılıyor: {alt_kategori}")
                    url_tiklama_oncesi = page.url
                    eleman.click(timeout=15000)

                    # 2026-08-19 -- CANLI TESTLE DOĞRULANAN YENİ KÖK NEDEN
                    # ("Ordine minori ara sıra panel bulunamıyor" teşhisinin
                    # güncellenmiş hâli): site ORDINE tarafını tamamen yeniden
                    # yapılandırmış -- artık tek sayfada JS sekmesi DEĞİL, her
                    # kategorinin KENDİ AYRI KALICI SAYFASI var (tıklama gerçek
                    # navigasyon yapıyor: "Ordine minori" → /ordine-minori/,
                    # "Ordine articolul 8" → /ordine-articolul-8/, vb. -- 5/5
                    # test edilen ordine kategorisinde doğrulandı). STADIU
                    # tarafı hâlâ eski aynı-sayfa-sekme yapısında (ARTICOLUL 11
                    # ile doğrulandı). Bu yüzden önce GERÇEK navigasyon olup
                    # olmadığına bakıyoruz -- URL değiştiyse artık aktif panel
                    # aramanın hiç anlamı yok (o class hiç var olmayacak,
                    # aramak sadece zaman aşımına kadar boşuna beklemek olur):
                    # sayfanın TAMAMI zaten sadece bu kategoriye ait.
                    try:
                        page.wait_for_load_state("domcontentloaded", timeout=8000)
                    except Exception:
                        pass
                    gercek_navigasyon_oldu = (page.url != url_tiklama_oncesi)

                    if gercek_navigasyon_oldu:
                        time.sleep(1)  # JS ile sonradan eklenen içerik için kısa bir pay
                        content = page.content()
                        soup = BeautifulSoup(content, 'html.parser')
                        kaynak = soup
                    else:
                        # Eski (hâlâ stadiu'da geçerli) davranış: aynı sayfada
                        # JS sekmesi -- "ara sıra panel bulunamıyor" kök
                        # nedeni burada sabit 4sn bekleyip content() almaktı;
                        # Elementor'ın "active" class'ı geçmesi site yavaş
                        # yanıt verdiğinde bunu bazen aşıyordu. Sabit süre
                        # yerine, class GERÇEKTEN DOM'a işlenene kadar (en
                        # fazla 12sn) aktif olarak bekliyoruz.
                        try:
                            page.wait_for_selector(
                                "div.eael-tab-content-item.active", timeout=12000
                            )
                        except Exception:
                            pass  # zaman aşımına uğrarsa aşağıdaki eski güvenlik ağı devreye girer

                        # 2026-08-15 -- kök neden: sekmeler bir Elementor
                        # "Advanced Tabs" (eael-advance-tabs) widget'ı --
                        # TIKLANMAYAN sekmelerin panelleri DOM'dan SİLİNMİYOR,
                        # sadece "eael-tab-content-item inactive" class'ıyla
                        # gizleniyor; aktif olan "...active" class'ını alıyor.
                        # page.content() TÜM sayfayı döndürüyordu -- bu yüzden
                        # her kategori aynı devasa/duplicate listeyi alıyordu
                        # (bkz. teshis/ARTICOLUL8_TIKLAMA_SONRASI.html: tüm
                        # sayfa 165 pdf linki, aktif panel sadece 17). Artık
                        # SADECE aktif panelin içeriğini parse ediyoruz.
                        content = page.content()
                        soup = BeautifulSoup(content, 'html.parser')
                        aktif_panel = soup.find(
                            'div',
                            class_=lambda c: c and 'eael-tab-content-item' in c.split() and 'active' in c.split(),
                        )
                        if aktif_panel is not None:
                            kaynak = aktif_panel
                        else:
                            # Beklenmedik bir DOM değişikliği olursa tüm
                            # sayfaya düşüyoruz (eski davranış) -- aşağıdaki
                            # dosya adı bazlı doğrulama son bir güvenlik ağı
                            # sağlıyor. Artık bu GERÇEKTEN nadir/beklenmedik
                            # bir durum olduğu için teşhis kaydı da alınıyor.
                            print("  ⚠ Aktif sekme paneli DOM'da bulunamadı, tüm sayfaya düşülüyor.")
                            _teshis_kaydet(page, f"{tip}_PANEL_AKTIF_OLMADI", alt_kategori, url)
                            kaynak = soup
                    links = kaynak.find_all('a', href=True)

                    pdf_links = []
                    for link in links:
                        href = link['href']
                        if href and 'pdf' in href.lower():
                            if not href.startswith('http'):
                                href = "https://cetatenie.just.ro" + href
                            if href not in pdf_links:
                                pdf_links.append(href)

                    print(f"    PDF bulundu: {len(pdf_links)}")
                    toplam_pdf_bulunan += len(pdf_links)

                    klasor_yolu = os.path.join(
                        PDF_KOK_KLASOR, tip, klasor_adi_guvenli(alt_kategori)
                    )
                    os.makedirs(klasor_yolu, exist_ok=True)

                    # Çerezleri, bu kategori için BİR KEZ paylaşılan oturuma
                    # aktarıyoruz (önceden her PDF için ayrı ayrı okunuyordu).
                    for cookie in context.cookies():
                        http_oturum.cookies.set(cookie['name'], cookie['value'])

                    for href in pdf_links:
                        dosya_adi = href.split('/')[-1].split('?')[0]
                        if not dosya_adi.endswith('.pdf'):
                            dosya_adi += ".pdf"

                        # 2026-08-15 (İKİNCİ bulaşma tespiti sonrası kalıcı
                        # koruma): sayfa ayrıştırması bazen BAŞKA bir
                        # kategoriye ait PDF bağlantılarını da bu kategorinin
                        # listesine katıyor (bkz. dosya_utils.py'deki
                        # stadiu_dosya_kategorisi_uyusuyor_mu notu). Dosya adı
                        # kendi gerçek kategorisiyle UYUŞMUYORSA, bu dosya bu
                        # turda hiç indirilmez/kaydedilmez -- gerçek
                        # kategorisinin işlendiği turda zaten doğru şekilde
                        # yakalanacaktır.
                        if tip == "stadiu" and not stadiu_dosya_kategorisi_uyusuyor_mu(dosya_adi, alt_kategori):
                            print(f"      ⊘ Atlandı (başka kategoriye ait görünüyor): {dosya_adi}")
                            continue
                        # 2026-08-15: ordine için de aynı koruma (bkz.
                        # dosya_utils.py'deki ordine_dosya_kategorisi_uyusuyor_mu
                        # notu -- ORDINE dosyalarının çoğunda makale numarası
                        # adında geçmiyor, bu durumda fonksiyon zaten güvenle
                        # True döner, hiçbir şey atlanmaz).
                        if tip == "ordine" and not ordine_dosya_kategorisi_uyusuyor_mu(dosya_adi, alt_kategori):
                            print(f"      ⊘ Atlandı (başka kategoriye ait görünüyor): {dosya_adi}")
                            continue

                        hedef_yol = os.path.join(klasor_yolu, dosya_adi)
                        kalici_eksik_isareti = hedef_yol + ".404"
                        gercek_indirme_oldu = False

                        # 2026-08-26 KÖK NEDEN DÜZELTMESİ (canlı Render
                        # loglarıyla kanıtlandı): "3 PDF indirme denemesi
                        # başarısız" admin uyarısı yanlış teşhis koyuyordu --
                        # WAF/erişim engeli SANILAN 3 dosya, aslında
                        # cetatenie.just.ro'nun KENDİ sitesinde linki hâlâ
                        # duruyor ama dosyanın kendisi sunucudan kaldırılmış
                        # (gerçek HTTP 404, tarayıcıda canlı doğrulandı --
                        # WAF'ın 503 "Verifying your browser..." sayfasından
                        # FARKLI, kesin bir "kaynak sitede yok" sinyali).
                        # Bu düzeltmeden önce kod her taramada aynı 404'lük
                        # dosyayı YENİDEN deniyordu (hedef_yol hiç oluşmadığı
                        # için os.path.exists hep False kalıyordu) -- hem
                        # gereksiz ağ isteği hem her gün tekrarlayan yanlış
                        # "WAF" uyarısı üretiyordu. Artık 404 alınan dosyalar
                        # küçük bir işaret dosyasıyla (.404) kalıcı olarak
                        # işaretleniyor, bir sonraki taramada hiç denenmeden
                        # atlanıyor.
                        if os.path.exists(kalici_eksik_isareti):
                            print(f"      ⊘ Bilinen eksik (kaynak sitede 404), atlanıyor: {dosya_adi}")
                        elif not os.path.exists(hedef_yol) or _guncel_yil_dosyasi_mi(dosya_adi):
                            gercek_indirme_oldu = True
                            try:
                                print(f"      ⬇ İndiriliyor: {dosya_adi}")

                                # 2026-08-25 KÖK NEDEN DÜZELTMESİ (canlı testte
                                # bulundu): site uzun süreli kesintiden sonra
                                # yeniden açılınca WAF'ı güçlenmiş -- ayrı bir
                                # curl_cffi/requests oturumuyla (Chrome TLS
                                # parmak izi taklidi) indirme artık HER ZAMAN
                                # 503 "Verifying your browser..." JS-challenge
                                # sayfası dönüyordu (canlı doğrulandı: hem eski
                                # hem yeni PDF'ler, tutarlı biçimde). Muhtemel
                                # sebep: sayfa gezinme Firefox/Playwright ile
                                # yapılırken indirme oturumu Chrome parmak izi
                                # taklit ediyordu -- bu tutarsızlık artık
                                # yakalanıyor. Çözüm: PDF'i de AYNI Playwright
                                # context'inin kendi ağ istemcisiyle (context.
                                # request) indiriyoruz -- gerçek tarayıcı
                                # motorunun TLS/oturumunu kullandığı için WAF'ı
                                # sayfa gezintisiyle birebir aynı şekilde geçer
                                # (canlı doğrulandı: context.request.get ile
                                # 200 + gerçek PDF içeriği). http_oturum artık
                                # sadece B Planı'nda (bkz. _b_plani_devreye_al)
                                # kullanılıyor, o da aynı şekilde düzeltildi.
                                pdf_res = context.request.get(
                                    href, headers={"Referer": url}, timeout=45000
                                )

                                if pdf_res.status == 200 and len(pdf_res.body()) > 1000:
                                    with open(hedef_yol, 'wb') as f:
                                        f.write(pdf_res.body())

                                    # PDF'in gerçek web adresini küçük bir eşlik
                                    # dosyasına yazıyoruz ki mobildeki "Resmi Belgeyi
                                    # Görüntüle" butonu her zaman doğru yere gitsin.
                                    with open(hedef_yol + ".url", "w", encoding="utf-8") as f:
                                        f.write(href)

                                    eklenen, yeni = pdf_verilerini_ice_aktar(
                                        hedef_yol, tip, alt_kategori, kaynak_url=href
                                    )
                                    kaydedilen_kayit += eklenen
                                    tum_yeni_kayitlar.extend(yeni)
                                    indirilen += 1
                                    print(f"      ✓ Kaydedildi: {dosya_adi}")
                                elif pdf_res.status == 404:
                                    # 2026-08-26: gerçek HTTP 404 -- WAF değil,
                                    # kaynak sitenin KENDİSİNDE link duruyor ama
                                    # dosya sunucudan kaldırılmış. Kalıcı olarak
                                    # işaretleyip bir daha denemiyoruz (bkz.
                                    # yukarıdaki kalici_eksik_isareti notu).
                                    with open(kalici_eksik_isareti, "w", encoding="utf-8") as f:
                                        f.write(href)
                                    kalici_eksik_sayisi += 1
                                    print(f"      ⊘ Kaynak sitede 404 (kalıcı eksik işaretlendi): {dosya_adi}")
                                else:
                                    print(f"      ✗ Geçersiz (durum={pdf_res.status}): {dosya_adi}")
                                    basarisiz_indirme_sayisi += 1

                            except Exception as e:
                                print(f"      ✗ Hata: {str(e)[:60]}")
                                basarisiz_indirme_sayisi += 1
                        else:
                            # 2026-08-15: Zaten diskte olan ve veritabanında
                            # da kaydı bulunan PDF'ler artık HER TARAMADA
                            # yeniden açılıp taranmıyor -- 1500+ dosyalık bir
                            # arşivde bu, her çalıştırmada gereksiz yere
                            # binlerce PDF'i yeniden okuyup CPU/süre
                            # harcamak anlamına geliyordu (site IP banına da
                            # katkısı olan gereksiz yük/süre uzamasını
                            # azaltmak için kaldırıldı). Sadece veritabanında
                            # hiç kaydı YOKSA (örn. şema sıfırlandıysa) işlenir.
                            if pdf_zaten_islenmis_mi(kontrol_conn, tip, alt_kategori, dosya_adi):
                                print(f"      • Mevcut (zaten işli, atlanıyor): {dosya_adi}")
                            else:
                                print(f"      • Mevcut ama veritabanında yok, işleniyor: {dosya_adi}")
                                # ÖNEMLİ (2026-08-14 düzeltmesi -- eşleşme
                                # tutarsızlığının kök nedeni): bu çağrı önceden
                                # try/except İÇİNDE DEĞİLDİ. Veritabanı o an
                                # başka bir işlem tarafından meşgulken oluşan
                                # GEÇİCİ bir 'database is locked' / 'disk I/O
                                # error' hatası burada yakalanmadığı için TÜM
                                # DÖNGÜYÜ (bu alt kategorideki KALAN tüm
                                # PDF'leri) sessizce iptal ediyordu -- dışarıdaki
                                # genel except'e düşüp o alt kategori tamamen
                                # atlanıyordu. Artık indirme dalıyla AYNI
                                # korumaya sahip: bir dosyada sorun çıksa bile
                                # döngü bir sonraki PDF ile DEVAM eder.
                                try:
                                    eklenen, yeni = pdf_verilerini_ice_aktar(
                                        hedef_yol, tip, alt_kategori, kaynak_url=href
                                    )
                                    kaydedilen_kayit += eklenen
                                    tum_yeni_kayitlar.extend(yeni)
                                except Exception as e:
                                    print(f"      ✗ Veritabanına işlenirken hata: {str(e)[:80]}")

                        # 2026-08-15: siteye karşı nazik davranmak için, GERÇEK
                        # bir ağ isteği (indirme) yapıldıysa 0.5sn'den 1.5sn'ye
                        # çıkarılmış bekleme uygulanır. Dosya zaten diskteyse
                        # (indirme yoksa) hiç beklemeye gerek yok -- zaten ağa
                        # hiç istek gitmedi, boşuna beklemek taramayı
                        # uzatmaktan başka bir şey yapmaz.
                        if gercek_indirme_oldu:
                            time.sleep(1.5)

                    # 2026-08-15: bir sonraki kategori sayfasına geçmeden önce
                    # de bekleme -- önceden kategoriler arasında hiç bekleme
                    # yoktu (sadece PDF indirmeleri arasında vardı), bu da
                    # art arda çok hızlı sayfa istekleri anlamına geliyordu.
                    time.sleep(3)

                except Exception as e:
                    print(f"    ✗ '{alt_kategori}' işlenirken hata: {str(e)[:80]}")
                    continue

            time.sleep(2)

        browser.close()

    kontrol_conn.close()

    print(f"\n{'='*60}")
    print(f"[İŞLEM TAMAM] Toplam {indirilen} yeni PDF indirildi, {kaydedilen_kayit} kayıt işlendi "
          f"({len(tum_yeni_kayitlar)} tanesi yeni).")
    print(f"{'='*60}")

    # 2026-08-15: kullanıcı isteğiyle eklendi -- "servis dışı" banner'ı
    # yanında "verileriniz en son ne zaman güncellendi" bilgisini
    # gösterebilmek için, her tarama SONUNDA (başarılı biterse) zamanı
    # basit bir metin dosyasına yazıyoruz. main.py /api/durum bunu okuyup
    # mobil tarafa iletir (bkz. main.py, index.tsx).
    #
    # 2026-08-19 DÜZELTMESİ (kullanıcı sordu: "16384 numaralı dosya neden
    # Render'da hâlâ yok" -- ikinci kök neden buradaydı): dosya eskiden
    # BASE_DIR'e (kod klasörü) yazılıyordu -- Render'da BU KLASÖR KALICI
    # DEĞİL, her `git push` sonrası deploy'da SIFIRDAN indiriliyor. Yani
    # bot Render'da başarıyla tarasa bile, bir SONRAKİ deploy bu dosyayı
    # SİLİYORDU -- /api/durum hep "son_guncelleme: null" gösteriyordu.
    # Artık VERI_DIZINI'ne (DATA_DIR ayarlıysa kalıcı diske, yoksa yerelde
    # eskisi gibi backend/ klasörüne) yazılıyor.
    try:
        with open(os.path.join(VERI_DIZINI, "son_basarili_tarama.txt"), "w", encoding="utf-8") as f:
            f.write(datetime.now(ROMANYA_SAAT_DILIMI).isoformat())
    except Exception as e:
        print(f"✗ Son tarama zamanı kaydedilemedi: {str(e)[:80]}")

    # 2026-08-19 (admin istatistik paneli): tarama sonucu -- kaç PDF
    # bulundu, kaç yeni kayıt eklendi -- kalıcı olarak kaydediliyor.
    # Öncesinde bu bilgi taramanın sonunda kayboluyordu. kontrol_conn
    # yukarıda zaten kapatıldığı için (satır 634) kısa ömürlü YENİ bir
    # bağlantı açılıyor.
    try:
        _olay_conn = veritabani_baglantisi(DB_FILE)
        sistem_olayi_kaydet(
            _olay_conn,
            "tarama_tamamlandi",
            f"{toplam_pdf_bulunan} PDF bulundu, {kaydedilen_kayit} kayıt işlendi "
            f"({len(tum_yeni_kayitlar)} yeni), {indirilen} yeni PDF indirildi.",
        )
        _olay_conn.close()
    except Exception as e:
        print(f"✗ Tarama olay kaydı başarısız: {str(e)[:80]}")

    # 2026-08-20 (sıra tahmini özelliği): her taramadan sonra "hâlâ
    # bekleyen" listesi yeniden hesaplanıyor -- yeni ordine eşleşmeleri
    # kuyruktan çıkar, yeni stadiu kayıtları kuyruğa girer. Bu, taramanın
    # ANA işlevini ASLA engellememeli -- ayrı, bağımsız bir try/except.
    try:
        _kuyruk_conn = veritabani_baglantisi(DB_FILE)
        _kuyruk_sayisi = bekleme_kuyrugunu_guncelle(_kuyruk_conn)
        _kuyruk_conn.close()
        print(f"✓ Bekleme kuyruğu güncellendi: {_kuyruk_sayisi} dosya hâlâ bekliyor.")
    except Exception as e:
        print(f"✗ Bekleme kuyruğu güncellenemedi: {str(e)[:80]}")

    try:
        _bildirimleri_gonder(
            tum_yeni_kayitlar, bulunamayan_kategoriler, toplam_pdf_bulunan,
            basarisiz_indirme_sayisi, kalici_eksik_sayisi
        )
    except Exception as e:
        print(f"✗ Bildirim gönderiminde hata: {str(e)[:80]}")

    # 2026-08-17: main.py'nin (bkz. run_bot/run_bot_yeniden_deneme) "site
    # tamamen erişilemezdi mi" kararı verip GÜNDE EN FAZLA BİR EK deneme
    # zamanlayabilmesi için toplam bulunan PDF sayısı döndürülüyor.
    return toplam_pdf_bulunan


if __name__ == "__main__":
    botu_calistir()
