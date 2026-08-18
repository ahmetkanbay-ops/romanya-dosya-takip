# -*- coding: utf-8 -*-
"""
GEÇİCİ test betiği (2026-08-16): 2026 içinde açıklanan (PDF'nin gerçek
yayın tarihi 2026 olan) tüm dosya numaralarını, hem STADIU hem ORDINE
tarafında, GERÇEK /api/sorgula uç noktasının kullandığı BİREBİR AYNI
eşleştirme mantığıyla (sayisal_cekirdek + tum_rakamlar + dosya_no_norm/
dosya_no_tum_rakam sorgusu) sanal olarak sorgular. Her numaranın kendi
kaydını doğru şekilde bulup bulamadığını kontrol eder, tutarsızlıkları
raporlar.

"2026'da açıklandı" tanımı: dosya adındaki tarih (varsa "-update-
DD.MM.YYYY" son eki HARİÇ tutularak, çünkü bu sadece botun dosyayı ne
zaman yeniden taradığını gösteren bir damga, içeriğin gerçek yılı değil)
2026 yılını içeriyorsa.
"""
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dosya_utils import sayisal_cekirdek, tum_rakamlar, veritabani_baglantisi

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dosyalar.db")

_UPDATE_DAMGASI = re.compile(r"-update-\d{1,2}\.\d{1,2}\.\d{4}", re.IGNORECASE)
_TARIH_DESENI = re.compile(r"(\d{1,2})[.\-](\d{1,2})[.\-](20\d{2})")
_YIL_DESENI = re.compile(r"(?<!\d)(20\d{2})(?!\d)")


def pdf_2026_mi(dosya_adi):
    """Dosya adının GERÇEK içerik tarihinin 2026 olup olmadığını belirler
    (re-tarama damgası hariç tutularak)."""
    if not dosya_adi:
        return False
    temiz = _UPDATE_DAMGASI.sub("", dosya_adi)
    tarih_eslesme = _TARIH_DESENI.search(temiz)
    if tarih_eslesme:
        return tarih_eslesme.group(3) == "2026"
    yil_eslesme = _YIL_DESENI.search(temiz)
    if yil_eslesme:
        return yil_eslesme.group(1) == "2026"
    return False


def sanal_sorgula(cursor, dosya_no, beklenen_id, ana_kategori_filtre=None):
    """/api/sorgula ile BİREBİR aynı mantık: önce dosya_no_norm, olmazsa
    dosya_no_tum_rakam ile dener. Beklenen kaydın (id) dönen sonuçlar
    arasında olup olmadığını döner."""
    birincil = sayisal_cekirdek(dosya_no)
    yedek = tum_rakamlar(dosya_no)

    if not birincil:
        return False, "GEÇERSİZ NUMARA (sayisal_cekirdek None döndü)", []

    cursor.execute("SELECT id FROM dosyalar WHERE dosya_no_norm = ?", (birincil,))
    satirlar = [r[0] for r in cursor.fetchall()]
    kullanilan_yontem = "birincil (dosya_no_norm)"

    if not satirlar and yedek and yedek != birincil:
        cursor.execute("SELECT id FROM dosyalar WHERE dosya_no_tum_rakam = ?", (yedek,))
        satirlar = [r[0] for r in cursor.fetchall()]
        kullanilan_yontem = "yedek (dosya_no_tum_rakam)"

    if not satirlar:
        return False, "HİÇBİR SONUÇ DÖNMEDİ", []

    if beklenen_id not in satirlar:
        return False, f"SONUÇ DÖNDÜ AMA KENDİ KAYDI YOK ({kullanilan_yontem}, {len(satirlar)} farklı sonuç)", satirlar

    return True, kullanilan_yontem, satirlar


def main():
    conn = veritabani_baglantisi(DB_FILE, row_factory=sqlite3.Row)
    cursor = conn.cursor()

    cursor.execute("SELECT id, dosya_no, dosya_no_norm, ana_kategori, alt_kategori, pdf_dosya, yil FROM dosyalar")
    tum_satirlar = cursor.fetchall()
    print(f"Veritabanındaki toplam kayıt: {len(tum_satirlar)}")

    hedef_satirlar = [r for r in tum_satirlar if pdf_2026_mi(r["pdf_dosya"])]
    print(f"2026'da açıklanan PDF'lerden gelen kayıt: {len(hedef_satirlar)}")

    ana_kategori_ozet = {}
    for r in hedef_satirlar:
        ana_kategori_ozet[r["ana_kategori"]] = ana_kategori_ozet.get(r["ana_kategori"], 0) + 1
    print("Ana kategori dağılımı:", ana_kategori_ozet)

    ikinci_cursor = conn.cursor()
    toplam = len(hedef_satirlar)
    eslesen = 0
    eslesmeyen = []
    kategori_bazli = {}  # ana_kategori -> [toplam, eslesen]

    for i, r in enumerate(hedef_satirlar):
        ak = r["ana_kategori"]
        kategori_bazli.setdefault(ak, [0, 0])
        kategori_bazli[ak][0] += 1

        basarili, sebep, sonuc_idler = sanal_sorgula(ikinci_cursor, r["dosya_no"], r["id"])
        if basarili:
            eslesen += 1
            kategori_bazli[ak][1] += 1
        else:
            eslesmeyen.append({
                "id": r["id"],
                "dosya_no": r["dosya_no"],
                "dosya_no_norm": r["dosya_no_norm"],
                "ana_kategori": ak,
                "alt_kategori": r["alt_kategori"],
                "pdf_dosya": r["pdf_dosya"],
                "yil": r["yil"],
                "sebep": sebep,
            })

    print("\n" + "=" * 70)
    print("SONUÇ")
    print("=" * 70)
    print(f"Test edilen toplam numara: {toplam}")
    print(f"Doğru eşleşen: {eslesen} (%{100*eslesen/toplam:.4f})" if toplam else "Test edilecek kayıt yok.")
    print(f"Eşleşmeyen: {len(eslesmeyen)}")
    print("\nKategori bazlı:")
    for ak, (t, e) in kategori_bazli.items():
        print(f"  {ak}: {e}/{t} eşleşti (%{100*e/t:.4f})")

    if eslesmeyen:
        print(f"\n=== EŞLEŞMEYEN {len(eslesmeyen)} KAYDIN DETAYI (ilk 50) ===")
        for e in eslesmeyen[:50]:
            print(f"  id={e['id']} | dosya_no={e['dosya_no']!r} | norm={e['dosya_no_norm']!r} | "
                  f"{e['ana_kategori']}/{e['alt_kategori']} | pdf={e['pdf_dosya']!r} | yil={e['yil']!r}")
            print(f"      SEBEP: {e['sebep']}")

        # sebep dagilimi
        sebep_sayaci = {}
        for e in eslesmeyen:
            anahtar = e["sebep"].split("(")[0].strip()
            sebep_sayaci[anahtar] = sebep_sayaci.get(anahtar, 0) + 1
        print("\n=== SEBEP DAĞILIMI (tüm eşleşmeyenler) ===")
        for sebep, adet in sorted(sebep_sayaci.items(), key=lambda x: -x[1]):
            print(f"  {adet} -> {sebep}")

    conn.close()


if __name__ == "__main__":
    main()
