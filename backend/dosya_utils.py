# -*- coding: utf-8 -*-
"""
Ortak yardımcı fonksiyonlar.

aktar.py, bot.py ve main.py bu modülü ortak kullanır ki:
  - mobil uygulamadaki alt kategori listesi,
  - backend'in oluşturduğu klasör isimleri,
  - veritabanındaki kategori alanları
her zaman BİREBİR tutarlı olsun. Kategori isimlerini SADECE burada değiştir,
diğer dosyalara dokunman gerekmez.
"""
import re
import sqlite3
import time
import unicodedata
from zoneinfo import ZoneInfo

# 2026-08-19 DÜZELTMESİ (kullanıcı sordu: "16384 numaralı dosya neden
# Render'da hâlâ yok" -- kök neden burasıydı): scheduler, mesai saati
# kontrolü ve zaman damgaları eskiden `datetime.now()` (SUNUCUNUN yerel
# saat dilimi) kullanıyordu. Kullanıcının kendi bilgisayarında bu Türkiye
# saatiydi (kazara doğru), ama Render'ın konteynerleri VARSAYILAN olarak
# UTC kullanıyor -- yani "09:00'da tara" komutu Render'da GERÇEKTE 12:00
# Türkiye/Romanya saatinde (UTC+3, yaz saati) çalışıyordu, mesai saati
# kontrolü de aynı şekilde kaymıştı. cetatenie.just.ro Romanya'da
# barındığı için artık saat dilimi AÇIKÇA Romanya'ya (Europe/Bucharest)
# sabitlendi -- sunucu nerede çalışırsa çalışsın (yerel bilgisayar,
# Render, başka bir bulut) artık hep AYNI, doğru saatte tarama yapılır.
# main.py, bot.py, admin_panel.py hepsi BURADAN import ediyor.
ROMANYA_SAAT_DILIMI = ZoneInfo("Europe/Bucharest")

# ---------------------------------------------------------------------------
# KATEGORİ TANIMLARI (mobil uygulamadaki (app/(tabs)/index.tsx) listeyle
# BİREBİR aynı olmalı)
# ---------------------------------------------------------------------------
# 2026-08-16 -- "NR. DOSAR" ve "CONSULAT / ANC" AYRI kategoriler DEĞİL:
# sitede tek bir sekme başlığı uzun olduğu için alt satıra sarıyor, biz de
# bunu iki farklı sekme sanmıştık (bkz. CONSULAT/ANC'nin her zaman NR.
# DOSAR ile birebir aynı içeriği vermesi). Kullanıcının kendi site
# ekranından doğrulamasıyla TEK kategoriye birleştirildi.
# NOT: site eşleştirmesi için (page.get_by_text ile) SADECE "NR. DOSAR"
# kullanılıyor -- "NR. DOSAR / CONSULAT / ANC" gibi tahmini bir birleşik
# metin denendi ama sitedeki gerçek satır kaydırma karakteri "/" değilmiş,
# bu yüzden eşleşme bozuldu (canlı çalıştırmada yakalandı). "NR. DOSAR"
# tek başına güvenilir şekilde eşleşiyor ve zaten Consulat/ANC içeriğini
# de kapsıyor.
STADIU_ALT_KATEGORILERI = [
    "ARTICOLUL 11", "ARTICOLUL 8", "ARTICOLUL 8″1", "ARTICOLUL 8″2",
    "ARTICOLUL 10", "NR. DOSAR",
    "REZULTATE INTERVIU ART. 8", "INVITATII INTERVIU ART. 8",
    "REZULTATE INTERVIU ART. 8.1", "INVITATII INTERVIU ART. 8.1",
]

ORDINE_ALT_KATEGORILERI = [
    "Ordine articolul 11", "Ordine articolul 8", "Ordine articolul 8”1",
    "Ordine articolul 10", "Ordine articolul 27",
    "Ordine minori",
]

DIGER_KATEGORI = "DİĞER / EŞLEŞMEYEN BAŞLIK"

# Ana kategoriye göre mobilde gösterilecek sabit sonuç mesajı ve durum etiketi.
# (İstenen tam metinler burada.) NOT: mobil tarafta (index.tsx, favorilerim.tsx)
# bu metin DEĞİL, constants/i18n.tsx'teki dile göre çevrilmiş karşılığı
# gösteriliyor -- burası sadece veritabanına yazılan ham 'mesaj' sütunu için
# (2026-08-16: kullanıcı isteğiyle stadiu mesajı bir sonraki adımı (ORDINE)
# işaret edecek şekilde güncellendi, bkz. i18n.tsx sonucMesaji.stadiu notu).
MESAJ_STADIU = (
    "Vatandaşlık başvurunuza ait dosyanız 1. aşama olarak sisteme kabul "
    "edilmiştir. Başvurunuzun onay durumunu (2. aşama) takip etmek için "
    "sorgulamanızı ORDİNE kategorisini seçerek tekrar yapabilirsiniz."
)
MESAJ_ORDINE = "Tebrikler, vatandaşlık başvurunuz onaylanmıştır."

DURUM_STADIU = "İŞLEMDE"
DURUM_ORDINE = "ONAYLANDI"


def mesaj_ve_durum(ana_kategori):
    """ana_kategori 'stadiu' ya da 'ordine' için sabit mesaj/durum çiftini döndürür."""
    if ana_kategori == "ordine":
        return MESAJ_ORDINE, DURUM_ORDINE
    return MESAJ_STADIU, DURUM_STADIU


# ---------------------------------------------------------------------------
# METİN SADELEŞTİRME / KATEGORİ EŞLEŞTİRME
# ---------------------------------------------------------------------------
def _sadelestir(metin):
    """Karşılaştırma için metni sadeleştirir: aksan/tırnak/boşluk farklarını yok sayar."""
    if not metin:
        return ""
    metin = metin.strip().upper()
    metin = unicodedata.normalize("NFKD", metin)
    metin = "".join(ch for ch in metin if not unicodedata.combining(ch))
    for ch in ["″", "'", "’", '"', "`", "´", "”", "“"]:
        metin = metin.replace(ch, "")
    metin = re.sub(r"\s+", " ", metin).strip()
    return metin


def metni_sadelestir(metin):
    """_sadelestir'in dışarıdan (bot.py gibi diğer modüllerden) çağrılabilen hali."""
    return _sadelestir(metin)


def kategori_eslestir(sayfa_basligi, aday_liste):
    """
    Web sayfasından okunan kategori başlığını (sayfa_basligi), sabit alt
    kategori listesiyle (aday_liste) eşleştirir. Tam eşleşme yoksa,
    sadeleştirilmiş metinler birbirini içeriyorsa eşleştirir.
    Hiçbir şey eşleşmezse None döner (çağıran taraf DIGER_KATEGORI kullanabilir).
    """
    hedef = _sadelestir(sayfa_basligi)
    if not hedef:
        return None

    for aday in aday_liste:
        if _sadelestir(aday) == hedef:
            return aday

    for aday in aday_liste:
        aday_sade = _sadelestir(aday)
        if aday_sade and (aday_sade in hedef or hedef in aday_sade):
            return aday

    return None


def klasor_adi_guvenli(metin):
    """Bir kategori adını, işletim sisteminde güvenle klasör adı olarak kullanılabilecek hale getirir."""
    if not metin:
        return "DIGER"
    metin = unicodedata.normalize("NFKD", metin)
    metin = "".join(ch for ch in metin if not unicodedata.combining(ch))
    metin = re.sub(r'[\\/:*?"<>|]', "_", metin)
    metin = re.sub(r"\s+", " ", metin).strip()
    return metin[:80] if metin else "DIGER"


# ---------------------------------------------------------------------------
# DOSYA ADINDAN GERÇEK KATEGORİ DOĞRULAMASI (2026-08-15)
# ---------------------------------------------------------------------------
# İKİNCİ KEZ tespit edilen bulaşma sorunu: bot.py bir kategoriyi (ör.
# "ARTICOLUL 11") tıklayıp sayfayı ayrıştırdığında, site zaman zaman BAŞKA
# kategorilere ait PDF bağlantılarını da AYNI sayfa içeriğinde gösteriyor --
# tıklama/DOM ayrıştırması bunu güvenilir şekilde ayırt edemiyor. Bunu
# kaynağında (site davranışını düzelterek) çözmek mümkün değil; bunun
# yerine dosya ADI zaten kararlı bir sinyal (ör. "Art-11-..." kesinlikle
# Article 11'e ait) -- bu yüzden bot.py artık BİR DOSYAYI KAYDETMEDEN ÖNCE
# adından tahmin ettiği kategoriyle o an işlenen kategori UYUŞMUYORSA
# kaydetmeyi REDDEDİYOR (bkz. bot.py kullanım yeri). Böylece yanlış
# kategoriye yazma artık DOM/tıklama davranışından bağımsız olarak
# engelleniyor -- dosya, kendi gerçek kategorisinin işlendiği turda zaten
# doğru şekilde kaydedilecek.
_STADIU_DOSYA_KATEGORI_DESENLERI = [
    ("ARTICOLUL 11", re.compile(r"(?i)art[._-]*11(?!\d)")),
    ("ARTICOLUL 8″2", re.compile(r"(?i)art[._-]*8[._]2(?!\d)")),
    ("ARTICOLUL 8″1", re.compile(r"(?i)art[._-]*8[._]1(?!\d)")),
    ("ARTICOLUL 10", re.compile(r"(?i)art[._-]*10(?!\d)")),
    ("ARTICOLUL 8", re.compile(r"(?i)art[._-]*8(?!\d)")),
]


_ARTICOLUL_ALT_KATEGORILERI = {kategori for kategori, _ in _STADIU_DOSYA_KATEGORI_DESENLERI}


def stadiu_dosya_kategorisi_uyusuyor_mu(dosya_adi, alt_kategori):
    """
    STADIU dosyaları için: dosya adı bir makale numarası deseni (art._8,
    art._10, art._11, art._8.1, art._8.2) içeriyorsa VE bu desen o an
    işlenen 'alt_kategori' ile UYUŞMUYORSA False döner -- çağıran taraf
    (bot.py) bu durumda dosyayı KAYDETMEMELİ (yanlış kategoriye bulaşma).
    Dosya adında hiçbir makale numarası deseni yoksa (ör. "Rezultate-
    interviu-*.pdf" gibi CONSULAT/ANC, NR. DOSAR, interview-tipi dosyalar)
    karar veremeyiz -- bu durumda güvenle True (uyuşuyor kabul et) döner,
    çünkü bu dosyalar için siteye güvenmekten başka güvenilir bir sinyal yok.

    2026-08-16 -- DÜZELTME: bu desenler SADECE 5 ARTICOLUL kategorisi
    (11/8/8″1/8″2/10) arasındaki karışmayı önlemek için var. REZULTATE/
    INVITATII INTERVIU ART. 8 ve ART. 8.1 gibi diğer 6 kategorinin
    dosyalarının adında da doğal olarak "art.8.1" gibi ifadeler geçiyor
    (ör. "Rezultate-interviu-art.-8.1.-27.07.2026.pdf") -- bu bir
    bulaşma değil, o kategorinin GERÇEK, BEKLENEN içeriği. Filtre bunu
    bilmediği için yanlışlıkla reddediyordu (gerçek bot.py çalıştırmasında
    yakalandı: REZULTATE/INVITATII INTERVIU ART. 8.1 bulunan TÜM dosyalar
    atlanmıştı). Bu yüzden desen kontrolünü SADECE o an işlenen alt_kategori
    kendisi de bir ARTICOLUL kategorisiyse uyguluyoruz -- diğer 6 kategori
    için (artık doğru sekmeye kapsamlanmış olan) sitenin kendisine güveniyoruz.
    """
    if alt_kategori not in _ARTICOLUL_ALT_KATEGORILERI:
        return True
    for kategori, desen in _STADIU_DOSYA_KATEGORI_DESENLERI:
        if desen.search(dosya_adi):
            return kategori == alt_kategori
    return True


# 2026-08-15: kullanıcı isteğiyle ORDINE için de aynı koruma eklendi
# ("ne olur ne olmaz"). Gerçek dosya adları incelendi (bkz. backend/pdfs/
# ordine/*) -- STADIU'nun aksine ORDINE dosyalarının ÇOĞUNDA makale
# numarası hiç geçmiyor (ör. "Ordin_nr._1691P_din_11.07.2019.pdf") --
# bunlar için karar verilemez, güvenle True (siteye güven) döner. Sadece
# adında AÇIKÇA "art" + numara ya da "minori" geçen bir azınlık için
# (ör. "ORDIN-1352-art-10-22-persoane.pdf", "Ordin-805P-Art-8-ind-1.pdf")
# gerçek kontrol yapılabiliyor. Yanlış pozitif riskini azaltmak için desen
# HER ZAMAN "art" kelimesini şart koşuyor -- salt bir rakamı (ör. sipariş
# numarasındaki "1352") asla makale numarası sanmıyor.
_ORDINE_DOSYA_KATEGORI_DESENLERI = [
    ("Ordine articolul 11", re.compile(r"(?i)art[._\s-]*11(?!\d)")),
    ("Ordine articolul 27", re.compile(r"(?i)art[._\s-]*27(?!\d)")),
    # "ind" VEYA "indice" yazımı -- gerçek dosya adlarında ikisi de var
    # (ör. "Art-8-ind-1.pdf" VE "art-8-indice-1.pdf"); sadece "ind"i
    # tanımak "indice" yazımlarının yanlışlıkla düz "Ordine articolul 8"e
    # (bir alttaki desen) düşmesine sebep oluyordu -- düzeltildi.
    ("Ordine articolul 8”1", re.compile(r"(?i)art[._\s-]*8[._\s-]*(ind(ice)?[._\s-]*)?1(?!\d)")),
    ("Ordine articolul 10", re.compile(r"(?i)art[._\s-]*10(?!\d)")),
    ("Ordine minori", re.compile(r"(?i)minori")),
    ("Ordine articolul 8", re.compile(r"(?i)art[._\s-]*8(?!\d)")),
]


def ordine_dosya_kategorisi_uyusuyor_mu(dosya_adi, alt_kategori):
    """
    ORDINE dosyaları için stadiu_dosya_kategorisi_uyusuyor_mu ile AYNI
    mantık -- bkz. o fonksiyonun ve üstteki notun açıklaması. Desen
    bulunamazsa (ORDINE'de en sık durum) güvenle True döner.
    """
    for kategori, desen in _ORDINE_DOSYA_KATEGORI_DESENLERI:
        if desen.search(dosya_adi):
            return kategori == alt_kategori
    return True


# ---------------------------------------------------------------------------
# DOSYA NUMARASI NORMALİZASYONU
# ---------------------------------------------------------------------------
# Gerçek dosya numarası örneği: "43484/RD/2023" — ayırıcı karakter ve harf
# kodu (RD, RC, vb.) değişken olabiliyor; asıl kararlı/eşsiz kısım baştaki
# rakam bloğu. Eşleştirmeyi bu rakam çekirdeği üzerinden yapıyoruz ki format
# farkları (nokta/tire/boşluk/harf kodu farkı, başındaki sıfırlar) sonucu
# etkilemesin. Bu yaklaşım "gevşek" (LIKE '%..%') aramadan farklı olarak
# YANLIŞ pozitif üretmez, çünkü karşılaştırma her zaman TAM eşitliktir.

_ILK_RAKAM_BLOGU = re.compile(r"\d+")

# 2026-08-19 DÜZELTMESİ (kullanıcı fark etti): hane aralığı önceden 3-7
# idi, bu yüzden 1-2 haneli dosya numaraları (ör. "7", "42") YANLIŞLIKLA
# hiç eşleşmiyordu. Romanya vatandaşlık başvuru numaraları 1'den
# başladığı için (kullanıcının belirttiği kural), aralık artık 1-9 hane.

# Kalıp 1: "43484/RD/2023" gibi NUMARA/HARF KODU/YIL
_TAM_DOSYA_NO_DESENI = re.compile(
    r"(\d{1,9})\s*[\/\-]\s*([A-ZĂÂÎŞȘŢȚ]{1,5})\s*[\/\-]\s*(\d{4})"
)

# Kalıp 2: gerçek PDF'lerde görülen "(41289/2021)" gibi NUMARA/YIL
_NUMARA_YIL_DESENI = re.compile(r"\(?\s*(\d{1,9})\s*\/\s*(\d{4})\s*\)?")

# Yedek kalıp: yalnızca yukarıdaki yapılandırılmış kalıplardan HİÇBİRİ
# bulunamazsa devreye girer (örn. Ordin/Anexa numarası gibi alakasız
# sayıları dosya numarasıyla karıştırmamak için). 1-2 haneli bare sayılar
# genel metinde daha sık rastlansa da, bu kalıp SADECE yapılandırılmış
# kalıpların hiç bulunamadığı belgelerde devreye giriyor -- risk düşük.
_YALIN_SAYI_DESENI = re.compile(r"\b(\d{1,9})\b")


def sayisal_cekirdek(deger):
    """
    Bir dizideki İLK rakam bloğunu döndürür, baştaki sıfırları atar.
    Bu, birincil (en güvenilir) eşleştirme anahtarıdır.
      '43484/RD/2023'   -> '43484'
      '043484'          -> '43484'
      'Dosya No: 43484' -> '43484'
    Eşleşme yoksa None.
    """
    if deger is None:
        return None
    m = _ILK_RAKAM_BLOGU.search(str(deger))
    if not m:
        return None
    cekirdek = m.group(0).lstrip("0")
    return cekirdek if cekirdek else "0"


def tum_rakamlar(deger):
    """
    String içindeki TÜM rakamları birleştirir. Yalnızca birincil anahtar
    (sayisal_cekirdek) eşleşmezse denenecek İKİNCİL/yedek anahtardır.
    """
    if deger is None:
        return None
    rakamlar = re.sub(r"\D", "", str(deger))
    return rakamlar or None


def metinden_dosya_numaralarini_cikar(tum_metin):
    """
    PDF metninden dosya numaralarını çıkarır, en güvenilirden en gevşeğe:
    1) 'NUMARA/HARF KODU/YIL'  (örn. 43484/RD/2023)
    2) 'NUMARA/YIL'            (örn. (41289/2021) — gerçek PDF'lerde görülen asıl format)
    3) Yalın 1-9 haneli sayılar — SADECE yukarıdaki iki yapılandırılmış kalıptan
       hiçbiri belgede hiç bulunamadıysa devreye girer. Bu sayede "ORDIN NR. 1138"
       gibi belge/karar numaraları, yapılandırılmış liste bulunan belgelerde
       yanlışlıkla dosya numarası sanılmaz. 1900-2100 aralığındaki sayılar yıl
       olabileceğinden bu yedek taramada eleniyor.

    ÖNEMLİ DÜZELTME (2026-08-15 -- kullanıcı testinde bulunan "603" yanlış
    eşleşme sorunu): "baştaki rakam bloğu" (sayisal_cekirdek) TEK BAŞINA eşsiz
    DEĞİL -- aynı "603" numarası farklı yıllarda/kategorilerde FARKLI kişilere
    ait olabiliyor (ör. 603/RD/2014 ile 603/RD/2026 tamamen farklı iki dosya).
    Önceki sürüm bunları bir sözlükte AYNI anahtar (cekirdek) altında
    tutuyordu -- bu hem ayırt edilemez hale getiriyordu HEM DE aynı PDF
    içinde aynı cekirdekli iki farklı yıl varsa birini sessizce SİLİYORDU
    (sözlükte üzerine yazma). Artık bir LİSTE dönüyor, her kayıt kendi
    yılını da taşıyor -- hiçbir kayıt kaybolmuyor ve main.py artık yılı da
    eşleştirme anahtarına dahil edebiliyor.

    Dönen değer: [{"cekirdek": ..., "ham_metin": ..., "yil": ... veya None}, ...]
    """
    sonuc = []
    gorulen = set()  # (cekirdek, yil) tekrarlarını (ayni PDF icinde iki kez
                      # gecen ayni numara) elemek icin -- farkli yillari DEGIL.

    for num, harf, yil in _TAM_DOSYA_NO_DESENI.findall(tum_metin):
        cekirdek = num.lstrip("0") or "0"
        anahtar = (cekirdek, yil)
        if anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        sonuc.append({"cekirdek": cekirdek, "ham_metin": f"{num}/{harf}/{yil}", "yil": yil})

    for num, yil in _NUMARA_YIL_DESENI.findall(tum_metin):
        cekirdek = num.lstrip("0") or "0"
        anahtar = (cekirdek, yil)
        if anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        sonuc.append({"cekirdek": cekirdek, "ham_metin": f"{num}/{yil}", "yil": yil})

    if not sonuc:
        for num in _YALIN_SAYI_DESENI.findall(tum_metin):
            sayi = int(num)
            if 1900 <= sayi <= 2100:
                continue
            cekirdek = num.lstrip("0") or "0"
            anahtar = (cekirdek, None)
            if anahtar in gorulen:
                continue
            gorulen.add(anahtar)
            sonuc.append({"cekirdek": cekirdek, "ham_metin": num, "yil": None})

    return sonuc


# ---------------------------------------------------------------------------
# VERİTABANI BAĞLANTISI (aktar.py, bot.py, main.py ORTAK kullanmalı)
# ---------------------------------------------------------------------------
# ÖNEMLİ (2026-08-14 tespiti -- eşleşme tutarsızlığı kök nedeni):
# API sunucusu (main.py) ve tarama botu (bot.py) AYNI 'dosyalar.db'
# dosyasına aynı anda erişiyor -- biri sorgu yaparken diğeri aynı anda
# milyonlarca satır yazabiliyor. SQLite'ın varsayılan "rollback journal"
# modunda bu durum sık sık 'database is locked' / 'disk I/O error' gibi
# GEÇİCİ hatalara yol açıyordu. bot.py'de bu hatanın yakalanmadığı bir
# noktada (bkz. bot.py'deki düzeltme) tek bir geçici hata, o an işlenmekte
# olan alt kategorideki KALAN TÜM PDF'lerin veritabanına hiç işlenmemesine
# sebep oluyordu -- diskte PDF'ler dururken sorgulamada "bulunamadı"
# çıkmasının kök nedeni tam olarak buydu.
#
# Çözüm: WAL (Write-Ahead Logging) modu -- okuyucularla TEK bir yazıcı
# artık birbirini bloklamıyor -- ve "busy_timeout" (kısa süreli çakışmada
# hemen hata vermek yerine belirli bir süre bekler).
def veritabani_baglantisi(db_dosyasi, row_factory=None):
    """Tüm modüllerin (main.py, bot.py, aktar.py) kullanması gereken ORTAK
    SQLite bağlantı fabrikası -- WAL modu + busy_timeout ile geçici
    kilit/I-O hatalarına karşı büyük ölçüde dayanıklıdır."""
    conn = sqlite3.connect(db_dosyasi, timeout=30)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA synchronous=NORMAL")
    except sqlite3.Error:
        pass
    if row_factory:
        conn.row_factory = row_factory
    return conn


# 2026-08-19 (bütün bildirimleri Türkçe e-postaya bağlama): kritik_uyari
# burada YOK -- o zaten bildirim.py'deki admin_kritik_uyari() içinde ayrı
# olarak Telegram+e-posta ile gönderiliyor; burada da göndersek çift
# e-posta olurdu. Diğer olay tipleri (tarama sonucu, push bildirimi) daha
# önce sadece admin panelinde görünüyordu, artık ayrıca Türkçe özet
# e-postasıyla da bildiriliyor.
_OLAY_EPOSTA_BASLIKLARI = {
    "tarama_tamamlandi": "📋 Romanya Dosya Takip - Tarama Tamamlandı",
    "push_gonderildi": "📲 Romanya Dosya Takip - Bildirim Gönderildi",
}


def sistem_olayi_kaydet(conn, olay_tipi, detay=None):
    """
    2026-08-19 (admin istatistik paneli): işletimsel bir olayı (tarama
    tamamlandı, bildirim gönderildi, kritik uyarı vb.) 'sistem_olaylari'
    tablosuna kaydeder. Kişisel veri (dosya numarası, cihaz kimliği)
    İÇERMEMELİDİR -- sadece "ne zaman ne oldu" özeti. Kayıt başarısız
    olsa bile (ör. DB kilitli) ana işlemi ASLA durdurmaz, hatayı yutar --
    istatistik kaydı, uygulamanın çalışması için kritik değildir.

    DB kaydından sonra, _OLAY_EPOSTA_BASLIKLARI'nda tanımlı olay tipleri
    için ayrıca Türkçe bir özet e-postası da admin'e gönderilir (SMTP
    ayarlanmamışsa bildirim.py.eposta_gonder zaten sessizce atlar). Bu
    adım DB commit'inden SONRA, ayrı bir try/except içinde çalışır --
    e-posta gönderimi başarısız olsa bile olay kaydı etkilenmez.
    """
    try:
        conn.execute(
            "INSERT INTO sistem_olaylari (olay_tipi, detay) VALUES (?, ?)",
            (olay_tipi, detay),
        )
        guvenli_commit(conn)
    except Exception as e:
        print(f"  ✗ sistem_olayi_kaydet başarısız ({olay_tipi}): {str(e)[:80]}")
        return

    konu = _OLAY_EPOSTA_BASLIKLARI.get(olay_tipi)
    if konu:
        try:
            # Döngüsel import'tan kaçınmak için lazy import (bildirim.py
            # zaten dosya_utils'ten import ediyor -- bkz. main.py'deki
            # admin_kritik_uyari lazy import'u, aynı gerekçe).
            from bildirim import eposta_gonder
            eposta_gonder(konu, detay or "(detay yok)")
        except Exception as e:
            print(f"  ✗ Olay e-postası gönderilemedi ({olay_tipi}): {str(e)[:80]}")


def pdf_zaten_islenmis_mi(conn, ana_kategori, alt_kategori, pdf_dosya):
    """
    Verilen PDF dosya adı, bu ana/alt kategoride veritabanında en az bir
    kayıtta zaten var mı? Varsa bu PDF daha önce başarıyla içeri aktarılmış
    demektir -- bot.py bunu, diskte zaten mevcut olan (yeniden indirilmeyen)
    PDF'leri her taramada gereksiz yere yeniden açıp metin taramaması için
    kullanır (2026-08-15: site IP banına yol açan gereksiz yükü azaltmak
    ve tarama süresini kısaltmak amacıyla eklendi).
    """
    cur = conn.execute(
        "SELECT 1 FROM dosyalar WHERE pdf_dosya = ? AND ana_kategori = ? AND alt_kategori = ? LIMIT 1",
        (pdf_dosya, ana_kategori, alt_kategori),
    )
    return cur.fetchone() is not None


def guvenli_commit(conn, deneme=4):
    """conn.commit()'i, geçici 'database is locked' / 'disk I/O error'
    durumlarında artan bekleme süreleriyle birkaç kez yeniden dener.
    Tüm denemeler tükenirse hatayı normal şekilde yükseltir (çağıran taraf
    zaten try/except ile bunu yakalayıp devam edecek şekilde güncellendi)."""
    for deneme_no in range(1, deneme + 1):
        try:
            conn.commit()
            return
        except sqlite3.OperationalError:
            if deneme_no == deneme:
                raise
            time.sleep(1.5 * deneme_no)


# ---------------------------------------------------------------------------
# VERİTABANI ŞEMASI (aktar.py ve main.py ortak kullanır)
# ---------------------------------------------------------------------------
GEREKLI_KOLONLAR = {
    "dosya_no", "dosya_no_norm", "dosya_no_tum_rakam", "yil", "ana_kategori",
    "alt_kategori", "durum", "mesaj", "pdf_dosya", "pdf_kaynak_url",
    "liste_url", "eslesti",
}


def tabloyu_hazirla(conn):
    """
    'dosyalar' tablosunu oluşturur / gerekirse günceller.
    Eski (uyumsuz) şema tespit edilirse veriyi SİLMEZ, 'dosyalar_eski_yedek'
    adıyla yedekler ve sıfırdan doğru şemayla yeni tabloyu oluşturur.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dosyalar'")
    tablo_var_mi = cursor.fetchone() is not None

    if tablo_var_mi:
        cursor.execute("PRAGMA table_info(dosyalar)")
        mevcut_kolonlar = {row[1] for row in cursor.fetchall()}
        if not GEREKLI_KOLONLAR.issubset(mevcut_kolonlar):
            yedek_adi = "dosyalar_eski_yedek"
            cursor.execute(f"DROP TABLE IF EXISTS {yedek_adi}")
            cursor.execute(f"ALTER TABLE dosyalar RENAME TO {yedek_adi}")
            print(f"! Eski/uyumsuz veritabanı şeması tespit edildi -> '{yedek_adi}' olarak yedeklendi.")

    # ÖNEMLİ (2026-08-15 -- "603" yanlış eşleşme düzeltmesi): UNIQUE kısıtına
    # 'yil' eklendi. Öncesinde (dosya_no_norm, ana_kategori, alt_kategori)
    # tek başına eşsizdi -- ama aynı baştaki numara (ör. "603") FARKLI
    # yıllarda AYNI kategoride de geçebiliyor (ör. 603/RD/2014 ile
    # 603/RD/2020 ikisi de ARTICOLUL 10'da olabilir). Eski kısıt bu
    # durumda ikinci yılın kaydını INSERT OR REPLACE ile SESSİZCE
    # SİLİYORDU -- gerçek bir veri kaybıydı. Artık yıl da anahtarın
    # parçası, hiçbir yıl diğerinin üzerine yazmıyor.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dosyalar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dosya_no TEXT NOT NULL,
            dosya_no_norm TEXT NOT NULL,
            dosya_no_tum_rakam TEXT,
            yil TEXT,
            ana_kategori TEXT NOT NULL,
            alt_kategori TEXT NOT NULL,
            durum TEXT,
            mesaj TEXT,
            pdf_dosya TEXT,
            pdf_kaynak_url TEXT,
            liste_url TEXT,
            eslesti BOOLEAN,
            UNIQUE(dosya_no_norm, yil, ana_kategori, alt_kategori)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_dosya_no_norm ON dosyalar(dosya_no_norm)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_dosya_no_tum_rakam ON dosyalar(dosya_no_tum_rakam)")

    # --- Bildirim / Favoriler (Faz 1) -------------------------------------
    # 2026-08-17 KRİTİK DÜZELTME: Bu tablo eskiden SADECE expo_push_token
    # tutuyordu, hangi CİHAZA ait olduğunu bilmiyordu. Bu yüzden
    # 'favoriler' tablosundaki 'expo_push_token' kolonu (ki o kolon aslında
    # GERÇEK bir push token değil, constants/api.tsx'teki
    # cihazKimligiGetir()'ın ürettiği RASTGELE bir cihaz kimliği, ör.
    # "cihaz-a3f8e9d2xxx") bot.py tarafından DOĞRUDAN expo_push_gonder()'e
    # gerçek bir token gibi gönderiliyordu -- Expo'nun API'si bu sahte
    # kimliği tanımadığı için "favori dosyanız onaylandı" bildirimi HİÇBİR
    # ZAMAN GERÇEKTEN ULAŞMIYORDU (hata try/except ile sessizce yutuluyordu).
    # Artık push_tokenlari, cihaz_kimligi ile GERÇEK expo_push_token'ı
    # eşleştiriyor -- bot.py artık favoriler.expo_push_token (=cihaz
    # kimliği) üzerinden BU tabloya bakıp gerçek token'ı bulabiliyor
    # (bkz. bot.py _favori_sahiplerini_bul).
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS push_tokenlari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expo_push_token TEXT NOT NULL UNIQUE,
            cihaz_kimligi TEXT UNIQUE,
            olusturma_tarihi TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("PRAGMA table_info(push_tokenlari)")
    push_token_kolonlari = {row[1] for row in cursor.fetchall()}
    if "cihaz_kimligi" not in push_token_kolonlari:
        cursor.execute("ALTER TABLE push_tokenlari ADD COLUMN cihaz_kimligi TEXT")
        print("! 'push_tokenlari' tablosuna 'cihaz_kimligi' kolonu eklendi (mevcut veri korunuyor).")

    # ÖNEMLİ (2026-08-16 -- kullanıcı testinde bulunan hata): önceden
    # favoriler SADECE dosya_no_norm (çıplak rakam) ile kaydediliyordu --
    # kullanıcının favorilediği KARTIN hangi yıla ait olduğu unutuluyordu.
    # Sonuç: "Favorilerim" ekranı, aynı çıplak numarayla eşleşen TÜM
    # yıllardaki/kategorilerdeki kayıtları dökerdi (numaralar farklı
    # yıllarda tekrar kullanılabildiği için -- bkz. dosyalar tablosundaki
    # aynı düzeltme). 'yil' eklendi. 'ana_kategori'/'alt_kategori' BİLEREK
    # eklenmedi/kullanılmadı -- bir dosya STADIU'dan ORDINE'ye geçtiğinde bu
    # ikisi DEĞİŞİR (aynı gerçek başvurunun farklı aşamadaki görünümüdür),
    # ama dosya_no_norm+yil aynı kalır (doğrulandı: aynı numara+yıl hem
    # stadiu hem ordine'de görülüyor). Eşleştirmeyi kategoriye göre yapmak
    # "favori onaylandı" bildirimini KIRARDI (stadiu'da favorilenen bir kayıt
    # ordine'ye geçtiğinde artık kategorisi eşleşmez).
    FAVORI_GEREKLI_KOLONLAR = {
        "id", "expo_push_token", "dosya_no", "dosya_no_norm", "yil", "olusturma_tarihi",
    }
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='favoriler'")
    favoriler_tablo_var_mi = cursor.fetchone() is not None
    if favoriler_tablo_var_mi:
        cursor.execute("PRAGMA table_info(favoriler)")
        favoriler_mevcut_kolonlar = {row[1] for row in cursor.fetchall()}
        if not FAVORI_GEREKLI_KOLONLAR.issubset(favoriler_mevcut_kolonlar):
            yedek_adi = "favoriler_eski_yedek"
            cursor.execute(f"DROP TABLE IF EXISTS {yedek_adi}")
            cursor.execute(f"ALTER TABLE favoriler RENAME TO {yedek_adi}")
            print(f"! Eski/uyumsuz 'favoriler' şeması tespit edildi -> '{yedek_adi}' olarak yedeklendi.")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS favoriler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expo_push_token TEXT NOT NULL,
            dosya_no TEXT NOT NULL,
            dosya_no_norm TEXT NOT NULL,
            yil TEXT,
            olusturma_tarihi TEXT DEFAULT CURRENT_TIMESTAMP,
            otomatik_mi INTEGER NOT NULL DEFAULT 0,
            UNIQUE(expo_push_token, dosya_no_norm, yil)
        )
    """)
    cursor.execute("PRAGMA table_info(favoriler)")
    favoriler_kolonlari_son = {row[1] for row in cursor.fetchall()}
    if "otomatik_mi" not in favoriler_kolonlari_son:
        # 2026-08-17 EKLENTİSİ (kullanıcı isteği): "favori" artık bildirim
        # almanın ŞARTI değil -- kullanıcı bir dosya numarasını sorgulayıp
        # eşleşme bulduğunda (henüz onaylanmamışsa) sistem OTOMATİK olarak
        # bu kaydı arka planda izlemeye alır (otomatik_mi=1). Bu kayıtlar
        # "Favorilerim" ekranında GÖRÜNMEZ (bkz. /api/favorilerim'in
        # otomatik_mi=0 filtresi) -- sadece kullanıcı BİLEREK "Favorilere
        # Ekle" derse otomatik_mi=0'a çevrilip görünür/kalıcı favori olur.
        # Ama HER İKİ türde de (otomatik veya elle) kayıt "onaylandı"
        # bildirimini almaya hak kazanır (bkz. bot.py
        # _favori_sahiplerini_bul -- otomatik_mi ayrımı yapmaz).
        cursor.execute("ALTER TABLE favoriler ADD COLUMN otomatik_mi INTEGER NOT NULL DEFAULT 0")
        print("! 'favoriler' tablosuna 'otomatik_mi' kolonu eklendi (mevcut veri korunuyor).")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_favori_norm ON favoriler(dosya_no_norm)")

    # 2026-08-19 EKLENTİSİ (admin istatistik paneli): tarama/bildirim gibi
    # işletimsel OLAYLARI (kişisel veri İÇERMEZ -- hangi dosya numarasının
    # arandığı gibi bir bilgi burada yok, sadece "ne zaman ne oldu" özeti)
    # kaydeder. Amaç: /admin panelinde "son tarama kaç PDF buldu",
    # "kaç bildirim gönderildi", "son 7 günde kaç kritik uyarı oldu" gibi
    # soruları cevaplayabilmek -- bunlar öncesinde hiç kalıcı tutulmuyordu,
    # sadece anlık gönderilip unutuluyordu.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sistem_olaylari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            olay_tipi TEXT NOT NULL,
            detay TEXT,
            zaman TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sistem_olay_tipi_zaman ON sistem_olaylari(olay_tipi, zaman)")

    # 2026-08-20 (sıra tahmini özelliği): stadiu'da olup henüz ordine'de
    # eşleşmeyen (yani hâlâ bekleyen) başvuruların ÖNCEDEN HESAPLANMIŞ
    # listesi. dosyalar tablosu 1.3M+ satır olduğu için "hâlâ bekliyor mu"
    # sorgusunu her arama isteğinde canlı hesaplamak (NOT EXISTS ile devasa
    # bir tabloyu taramak) çok yavaş olurdu -- bunun yerine her gece tarama
    # bitince TEK SEFERLİK yeniden hesaplanıp burada saklanıyor, sorgu anında
    # sadece bu (küçük, indeksli) tablo sayılıyor. bkz. bekleme_kuyrugunu_guncelle().
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bekleyen_dosyalar (
            dosya_no_norm TEXT NOT NULL,
            dosya_no_norm_int INTEGER NOT NULL,
            yil TEXT NOT NULL,
            alt_kategori TEXT NOT NULL,
            PRIMARY KEY (dosya_no_norm, yil, alt_kategori)
        )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_bekleyen_kuyruk "
        "ON bekleyen_dosyalar(alt_kategori, yil, dosya_no_norm_int)"
    )
    # dosyalar tablosunda ana_kategori+dosya_no_norm+yil üzerinden hızlı
    # "eşleşme var mı" kontrolü için (bekleme_kuyrugunu_guncelle'nin NOT
    # EXISTS sorgusu bu indeksi kullanıyor).
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_dosya_ana_norm_yil "
        "ON dosyalar(ana_kategori, dosya_no_norm, yil)"
    )

    conn.commit()


# 2026-08-20 (sıra tahmini özelliği): "İşlemde" durumundaki maddeler --
# görüşme/mülakat listeleri (REZULTATE/INVITATII) bir "bekleme kuyruğu"
# değil, ayrı bir süreç (davet/sonuç listesi) olduğu için kasıtlı olarak
# DIŞARIDA bırakıldı.
_BEKLEME_KUYRUGU_ALT_KATEGORILERI = [
    "ARTICOLUL 11", "ARTICOLUL 8", "ARTICOLUL 8″1", "ARTICOLUL 8″2",
    "ARTICOLUL 10", "NR. DOSAR",
]


def bekleme_kuyrugunu_guncelle(conn):
    """
    'bekleyen_dosyalar' tablosunu SIFIRDAN yeniden hesaplar: stadiu'da
    kayıtlı olup, AYNI numara+yıl ile ordine'nin HERHANGİ bir alt
    kategorisinde eşleşmesi bulunmayan (yani henüz onaylanmamış) tüm
    kayıtları listeler.

    Neden ordine'nin HERHANGİ bir alt kategorisi (belirli bir eşleşme
    değil)? -- main.py /api/sorgula'daki (2026-08-19'da doğrulanmış) aynı
    ilke: aynı dosya_no_norm + yıl ikilisi neredeyse her zaman TEK bir
    kişiye ait, hangi madde altında yayınlandığından bağımsız olarak.

    Bu fonksiyon HAFİF DEĞİL (900K+ satırlık stadiu tablosunu tarıyor) --
    her sorguda değil, sadece bot.py'nin günlük taramasının SONUNDA bir
    kez çağrılmalı. Süre birkaç saniye ile birkaç dakika arasında olabilir,
    veritabanı boyutuna bağlı.
    """
    yer_tutucular = ",".join("?" * len(_BEKLEME_KUYRUGU_ALT_KATEGORILERI))
    cursor = conn.cursor()
    cursor.execute("DELETE FROM bekleyen_dosyalar")
    cursor.execute(
        f"""
        INSERT INTO bekleyen_dosyalar (dosya_no_norm, dosya_no_norm_int, yil, alt_kategori)
        SELECT DISTINCT s.dosya_no_norm, CAST(s.dosya_no_norm AS INTEGER), s.yil, s.alt_kategori
        FROM dosyalar s
        WHERE s.ana_kategori = 'stadiu'
          AND s.yil IS NOT NULL
          AND s.alt_kategori IN ({yer_tutucular})
          AND NOT EXISTS (
              SELECT 1 FROM dosyalar o
              WHERE o.ana_kategori = 'ordine'
                AND o.dosya_no_norm = s.dosya_no_norm
                AND o.yil = s.yil
          )
        """,
        _BEKLEME_KUYRUGU_ALT_KATEGORILERI,
    )
    eklenen = cursor.rowcount
    guvenli_commit(conn)
    return eklenen


def sira_tahmini_hesapla(conn, dosya_no_norm, yil, alt_kategori):
    """
    Belirli bir (dosya_no_norm, yil, alt_kategori) için 'bekleyen_dosyalar'
    kuyruğundaki konumunu hesaplar. Dönen değer None ise, bu kayıt kuyrukta
    yok -- ya zaten onaylanmış (ordine'de eşleşmiş) ya da hiç stadiu'da
    kayıtlı değil ya da bu madde kuyruk kapsamında değil (interview/sonuç
    listeleri gibi).

    ÖNEMLİ (dürüstlük): dosya_no_norm_int TEK BAŞINA yıllar arası kronolojik
    değil -- Romanya'nın numaralandırması HER YIL yeniden başlıyor (bugün
    canlı veriyle doğrulandı, ör. '100' numarası 2018-2025 arası her yılda
    farklı bir kişiye ait). Bu yüzden "tüm zamanlar" sıralaması (yıl, numara)
    ikilisine göre KRONOLOJİK yapılıyor, sadece numaraya göre DEĞİL.
    """
    if not (alt_kategori in _BEKLEME_KUYRUGU_ALT_KATEGORILERI and yil):
        return None

    try:
        numara_int = int(dosya_no_norm)
    except (TypeError, ValueError):
        return None

    cursor = conn.cursor()

    # Bu kayıt gerçekten kuyrukta mı? (zaten onaylanmışsa ya da hiç
    # kayıtlı değilse sıra tahmini yapmanın hiçbir anlamı yok.)
    cursor.execute(
        "SELECT 1 FROM bekleyen_dosyalar WHERE dosya_no_norm = ? AND yil = ? AND alt_kategori = ?",
        (dosya_no_norm, yil, alt_kategori),
    )
    if cursor.fetchone() is None:
        return None

    # -- Kendi yılına göre --
    cursor.execute(
        "SELECT COUNT(*) FROM bekleyen_dosyalar WHERE alt_kategori = ? AND yil = ? AND dosya_no_norm_int < ?",
        (alt_kategori, yil, numara_int),
    )
    onundeki_yil = cursor.fetchone()[0]
    cursor.execute(
        "SELECT COUNT(*) FROM bekleyen_dosyalar WHERE alt_kategori = ? AND yil = ?",
        (alt_kategori, yil),
    )
    toplam_yil = cursor.fetchone()[0]

    # -- Tüm zamanlar (kronolojik: önce yıl, sonra numara) --
    cursor.execute(
        "SELECT COUNT(*) FROM bekleyen_dosyalar WHERE alt_kategori = ? "
        "AND (yil < ? OR (yil = ? AND dosya_no_norm_int < ?))",
        (alt_kategori, yil, yil, numara_int),
    )
    onundeki_tum = cursor.fetchone()[0]
    cursor.execute(
        "SELECT COUNT(*) FROM bekleyen_dosyalar WHERE alt_kategori = ?",
        (alt_kategori,),
    )
    toplam_tum = cursor.fetchone()[0]

    # -- Onay yüzdesi (kendi yılı+maddesi için) --
    # 2026-08-20 (kullanıcının mockup'ında "%25 onaylandı" halkası vardı):
    # o yıl+maddede toplam kaç başvuru vardı (dosyalar tablosunda stadiu
    # tarafında kayıtlı olan TÜM numaralar, onaylanmış olsun olmasın) --
    # bekleyen sayısı çıkarılınca onaylanan sayısı bulunuyor.
    cursor.execute(
        "SELECT COUNT(DISTINCT dosya_no_norm) FROM dosyalar WHERE ana_kategori = 'stadiu' AND alt_kategori = ? AND yil = ?",
        (alt_kategori, yil),
    )
    yil_toplam_basvuru = cursor.fetchone()[0]
    yil_onaylanan = max(yil_toplam_basvuru - toplam_yil, 0)
    onay_yuzdesi = (yil_onaylanan / yil_toplam_basvuru * 100) if yil_toplam_basvuru else 0.0

    # -- En yakın onaylanmış komşu numaralar (2026-08-20, rakip uygulama
    # ilhamı: "sıra bize ne kadar yaklaştı") --
    # ÖNEMLİ (dürüstlük): elimizde her onayın GERÇEK yayın tarihi yok
    # (dosyalar tablosunda böyle bir sütun yok), bu yüzden "X gün önce"
    # GİBİ bir iddia YOK -- sadece "en yakın numaralar hangileri, ne kadar
    # numara farkı var" gösteriliyor. Aynı yıl içinde, herhangi bir ordine
    # alt kategorisinde arıyor (bugün kurulan güvenli eşleştirme ilkesiyle
    # tutarlı).
    cursor.execute(
        "SELECT dosya_no_norm FROM dosyalar WHERE ana_kategori='ordine' AND yil=? "
        "AND CAST(dosya_no_norm AS INTEGER) < ? ORDER BY CAST(dosya_no_norm AS INTEGER) DESC LIMIT 1",
        (yil, numara_int),
    )
    _alt = cursor.fetchone()
    cursor.execute(
        "SELECT dosya_no_norm FROM dosyalar WHERE ana_kategori='ordine' AND yil=? "
        "AND CAST(dosya_no_norm AS INTEGER) > ? ORDER BY CAST(dosya_no_norm AS INTEGER) ASC LIMIT 1",
        (yil, numara_int),
    )
    _ust = cursor.fetchone()
    en_yakin_komsular = {
        "alt": {"dosya_no_norm": _alt[0], "fark": numara_int - int(_alt[0])} if _alt else None,
        "ust": {"dosya_no_norm": _ust[0], "fark": int(_ust[0]) - numara_int} if _ust else None,
    }

    return {
        "kendi_yilinda": {
            "onundeki_sayisi": onundeki_yil,
            "sirasi": onundeki_yil + 1,
            "yil_toplam_bekleyen": toplam_yil,
            "yil_toplam_basvuru": yil_toplam_basvuru,
            "yil_onaylanan": yil_onaylanan,
            "onay_yuzdesi": round(onay_yuzdesi, 1),
            "en_yakin_komsular": en_yakin_komsular,
        },
        "tum_zamanlar": {
            "onundeki_sayisi": onundeki_tum,
            "sirasi": onundeki_tum + 1,
            "toplam_bekleyen": toplam_tum,
        },
    }
