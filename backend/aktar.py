# -*- coding: utf-8 -*-
"""
PDF -> veritabanı aktarım modülü.

PDF'ler artık şu klasör yapısında bekleniyor (bot.py bu yapıyı oluşturur):

    backend/pdfs/stadiu/<ALT KATEGORİ ADI>/*.pdf
    backend/pdfs/ordine/<ALT KATEGORİ ADI>/*.pdf

Alt klasör adı, dosya_utils.py içindeki STADIU_ALT_KATEGORILERI /
ORDINE_ALT_KATEGORILERI listesinden biriyle eşleşir. Bu sayede mobil
uygulamadaki alt kategori filtresi ile veritabanındaki kayıtlar birebir
örtüşür.
"""
import os
import sqlite3

from pypdf import PdfReader

from dosya_utils import (
    tabloyu_hazirla,
    mesaj_ve_durum,
    sayisal_cekirdek,
    tum_rakamlar,
    metinden_dosya_numaralarini_cikar,
    veritabani_baglantisi,
    guvenli_commit,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 2026-08-19 (Render'a taşıma): bkz. main.py'deki aynı isimli sabitin notu.
VERI_DIZINI = os.environ.get("DATA_DIR", BASE_DIR)
DB_FILE = os.path.join(VERI_DIZINI, "dosyalar.db")
PDF_KOK_KLASOR = os.path.join(VERI_DIZINI, "pdfs")


def tabloyu_olustur():
    conn = veritabani_baglantisi(DB_FILE)
    tabloyu_hazirla(conn)
    conn.close()


def _kaynak_url_oku(pdf_yolu):
    """
    bot.py her indirdiği PDF'in yanına '<dosya>.pdf.url' adında, PDF'in web
    sitesindeki gerçek adresini içeren küçük bir eşlik dosyası bırakır.
    Bu sayede aktar.py sonradan (bot.py çalışmadan, yalnızca yerel PDF'lere
    bakarak) çalıştırılsa bile, mobil uygulamada "Resmi Belgeyi Görüntüle"
    butonunun gideceği gerçek adres kaybolmaz.
    """
    yol = pdf_yolu + ".url"
    if os.path.exists(yol):
        try:
            with open(yol, "r", encoding="utf-8") as f:
                return f.read().strip() or None
        except Exception:
            return None
    return None


def pdf_verilerini_ice_aktar(pdf_yolu, ana_kategori, alt_kategori, kaynak_url=None):
    """
    Tek bir PDF'i okuyup içindeki dosya numaralarını veritabanına ekler.

    ana_kategori: 'stadiu' ya da 'ordine'
    alt_kategori: dosya_utils.STADIU_ALT_KATEGORILERI / ORDINE_ALT_KATEGORILERI
                  içindeki kanonik başlıklardan biri (ya da DIGER_KATEGORI)
    kaynak_url: PDF'in web sitesindeki gerçek adresi (mobilde "Resmi Belgeyi
                Görüntüle" butonu için). Verilmezse '<dosya>.pdf.url' eşlik
                dosyasından okunmaya çalışılır, o da yoksa genel liste
                sayfasına düşer.

    Dönen değer: (eklenen_kayit_sayisi, yeni_kayitlar) tuple'ı.
    yeni_kayitlar: bu PDF'te bulunan ve veritabanında DAHA ÖNCE hiç
    olmayan (dosya_no_norm, ana_kategori, alt_kategori) kombinasyonlarının
    listesi -- bot.py bunu "yeni dosya eklendi" bildirimleri için kullanır.
    """
    if not os.path.exists(pdf_yolu):
        print(f"Hata: {pdf_yolu} dosyası bulunamadı!")
        return 0, []

    if not kaynak_url:
        kaynak_url = _kaynak_url_oku(pdf_yolu) or "https://cetatenie.just.ro/"

    print(f"'{os.path.basename(pdf_yolu)}' taranıyor... [{ana_kategori} / {alt_kategori}]")

    try:
        reader = PdfReader(pdf_yolu)
    except Exception as e:
        print(f"✗ Geçersiz PDF: {os.path.basename(pdf_yolu)} - {str(e)[:80]}")
        return 0, []

    tum_metin = ""
    for sayfa in reader.pages:
        metin = sayfa.extract_text()
        if metin:
            tum_metin += metin + "\n"

    mesaj, durum = mesaj_ve_durum(ana_kategori)

    bulunanlar = metinden_dosya_numaralarini_cikar(tum_metin)
    print(f"--> {len(bulunanlar)} dosya numarası bulundu")

    if not bulunanlar:
        print("✗ Dosya numarası bulunamadı.\n")
        return 0, []

    dosya_adi = os.path.basename(pdf_yolu)

    conn = veritabani_baglantisi(DB_FILE)
    cursor = conn.cursor()
    eklenen = 0
    yeni_kayitlar = []
    # 2026-08-15 düzeltmesi: 'bulunanlar' artık {cekirdek: ham} sözlüğü değil,
    # her biri kendi yılını da taşıyan bir KAYIT LİSTESİ -- aynı cekirdeğin
    # farklı yıllardaki kayıtları artık birbirinin üzerine yazılmıyor (bkz.
    # dosya_utils.metinden_dosya_numaralarini_cikar üstündeki not).
    for kayit in bulunanlar:
        cekirdek = kayit["cekirdek"]
        ham = kayit["ham_metin"]
        yil = kayit["yil"]

        cursor.execute(
            "SELECT 1 FROM dosyalar WHERE dosya_no_norm = ? AND yil IS ? AND ana_kategori = ? AND alt_kategori = ?",
            (cekirdek, yil, ana_kategori, alt_kategori),
        )
        yeni_mi = cursor.fetchone() is None

        cursor.execute(
            """
            INSERT OR REPLACE INTO dosyalar
            (dosya_no, dosya_no_norm, dosya_no_tum_rakam, yil, ana_kategori, alt_kategori,
             durum, mesaj, pdf_dosya, pdf_kaynak_url, liste_url, eslesti)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ham,
                cekirdek,
                tum_rakamlar(ham),
                yil,
                ana_kategori,
                alt_kategori,
                durum,
                mesaj,
                dosya_adi,
                kaynak_url,
                "https://cetatenie.just.ro/",
                True,
            ),
        )
        eklenen += 1
        if yeni_mi:
            yeni_kayitlar.append({
                "dosya_no": ham,
                "dosya_no_norm": cekirdek,
                "yil": yil,
                "ana_kategori": ana_kategori,
                "alt_kategori": alt_kategori,
                "pdf_dosya": dosya_adi,
            })
    guvenli_commit(conn)
    conn.close()
    print(f"✓ {eklenen} dosya kaydedildi ({len(yeni_kayitlar)} yeni).\n")

    # 2026-09-06 EKLENTİSİ (kullanıcı isteği -- "Articolul 10" 1-2 haneli
    # numara sorununun bir daha SESSİZCE yaşanmaması için): bu PDF'ten
    # BİRAZ ÖNCE çıkarılan numaraların gerçekten veritabanında (bir sonraki
    # gerçek kullanıcı sorgusunun kullanacağı AYNI sorgu şekliyle)
    # bulunabildiğini kendi kendine doğrular. Öncelik 1-2 haneli (kısa)
    # numaralara verilir -- geçmişte kırılan tam olarak bu grup. Bir
    # uyuşmazlık bulunursa (extraction "var" diyor ama DB'den okunamıyor)
    # admin'e ANINDA Telegram uyarısı gider -- kullanıcının "sistem kendi
    # mantığını bilmeli, bize otomatik haber vermeli" isteği budur.
    _ice_aktarma_tutarliligini_dogrula(bulunanlar, ana_kategori, alt_kategori, dosya_adi)

    return eklenen, yeni_kayitlar


def _ice_aktarma_tutarliligini_dogrula(bulunanlar, ana_kategori, alt_kategori, dosya_adi):
    """Bir PDF'ten çıkarılan numaraların GERÇEKTEN sorgulanabilir olduğunu
    kendi kendine test eder -- yeni bir bağlantıyla, gerçek bir kullanıcı
    sorgusuyla BİREBİR aynı şekilde (dosya_no_norm + yil + ana_kategori +
    alt_kategori TAM eşleşme) okur. Sadece uyarı amaçlı: burada bir hata
    olsa bile ana aktarım işlemini ASLA bozmaz/durdurmaz (try/except ile
    tamamen izole)."""
    try:
        if not bulunanlar:
            return
        # Kısa (1-2 haneli) numaralar önceliklidir -- en fazla 5 örnek,
        # bulunamazsa rastgele diğerlerinden tamamlanır (hiç kısa numara
        # yoksa da genel bir tutarlılık kontrolü yine yapılmış olur).
        kisalar = [k for k in bulunanlar if len(k["cekirdek"]) <= 2]
        digerleri = [k for k in bulunanlar if len(k["cekirdek"]) > 2]
        ornekler = (kisalar + digerleri)[:5]

        conn = veritabani_baglantisi(DB_FILE)
        cursor = conn.cursor()
        eksikler = []
        for kayit in ornekler:
            cursor.execute(
                "SELECT 1 FROM dosyalar WHERE dosya_no_norm = ? AND yil IS ? "
                "AND ana_kategori = ? AND alt_kategori = ?",
                (kayit["cekirdek"], kayit["yil"], ana_kategori, alt_kategori),
            )
            if cursor.fetchone() is None:
                eksikler.append(kayit["ham_metin"])
        conn.close()

        if eksikler:
            from bildirim import admin_kritik_uyari
            admin_kritik_uyari(
                f"⚠️ TUTARLILIK HATASI: '{dosya_adi}' ({ana_kategori}/{alt_kategori}) "
                f"dosyasından çıkarılan {len(eksikler)} numara, aktarımdan hemen sonra "
                f"veritabanında sorgulanamadı: {', '.join(eksikler)}. Bu, kullanıcıların "
                f"gerçekte veritabanında OLAN bir numarayı 'bulunamadı' olarak görebileceği "
                f"anlamına gelir -- acil incelenmeli."
            )
    except Exception as e:
        print(f"✗ Tutarlılık doğrulaması başarısız (aktarımı etkilemez): {str(e)[:100]}")


def klasordeki_tum_pdfleri_ice_aktar():
    """
    backend/pdfs/<ana_kategori>/<alt_kategori>/*.pdf yapısındaki TÜM PDF'leri
    tarayıp veritabanına işler. bot.py çalıştırılmadan, elle indirilmiş
    PDF'leri de bu fonksiyonla içeri aktarabilirsin.
    """
    toplam_pdf = 0
    toplam_kayit = 0

    if not os.path.exists(PDF_KOK_KLASOR):
        print(f"Uyarı: '{PDF_KOK_KLASOR}' klasörü yok, önce bot.py çalıştırılmalı.")
        return

    for ana_kategori in sorted(os.listdir(PDF_KOK_KLASOR)):
        ana_yol = os.path.join(PDF_KOK_KLASOR, ana_kategori)
        if not os.path.isdir(ana_yol):
            continue
        for alt_kategori in sorted(os.listdir(ana_yol)):
            alt_yol = os.path.join(ana_yol, alt_kategori)
            if not os.path.isdir(alt_yol):
                continue
            for dosya in sorted(os.listdir(alt_yol)):
                if dosya.lower().endswith(".pdf"):
                    toplam_pdf += 1
                    tam_yol = os.path.join(alt_yol, dosya)
                    eklenen, _yeni = pdf_verilerini_ice_aktar(tam_yol, ana_kategori, alt_kategori)
                    toplam_kayit += eklenen

    if toplam_pdf == 0:
        print("Uyarı: PDF dosyası bulunamadı!")
    else:
        print(f"\n{'='*60}")
        print(f"[İŞLEM TAMAM] {toplam_pdf} PDF tarandı, {toplam_kayit} kayıt eklendi/güncellendi!")
        print(f"{'='*60}")


def tabloyu_temizle():
    """
    Veritabanı DOSYASINI SİLMEZ, sadece 'dosyalar' tablosundaki kayıtları
    boşaltır. PDF dosyalarının kendisine hiçbir şekilde dokunmaz -- diskteki
    PDF'ler olduğu gibi kalır, sadece üzerlerinden yeniden taranıp veritabanı
    baştan (temiz) doldurulur.
    """
    conn = veritabani_baglantisi(DB_FILE)
    tabloyu_hazirla(conn)
    conn.execute("DELETE FROM dosyalar")
    guvenli_commit(conn)
    conn.close()


if __name__ == "__main__":
    print("Veritabanı kayıtları temizleniyor (PDF dosyalarına dokunulmuyor)...")
    tabloyu_temizle()
    klasordeki_tum_pdfleri_ice_aktar()
