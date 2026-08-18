# -*- coding: utf-8 -*-
"""
GEÇİCİ yeniden sınıflandırma betiği (2026-08-15).

stadiu klasörlerindeki (ARTICOLUL 10/11/8/8''1/8''2/NR. DOSAR) TÜM PDF'leri
gerçek kategorilerine göre yeniden düzenler:
  1) Dosya adında makale numarası varsa (art._8, art._10, art._11, art._8.1,
     art._8.2) -> o kategoriye ait tek kopya bırakılır.
  2) Makale numarası yoksa (Rezultate-interviu-*, Lista-interviu-* vb.)
     -> NR. DOSAR'a ait tek kopya bırakılır.
Her dosya ÖNCE doğru klasörde olduğundan emin olunur (yoksa herhangi bir
kaynaktan kopyalanır), SONRA yanlış klasörlerdeki kopyalar silinir --
böylece hiçbir aşamada veri kaybı riski olmaz.
"""
import os
import re
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STADIU_KOK = os.path.join(BASE_DIR, "pdfs", "stadiu")

KLASORLER = ["ARTICOLUL 10", "ARTICOLUL 11", "ARTICOLUL 8", "ARTICOLUL 8′′1", "ARTICOLUL 8′′2", "NR. DOSAR"]

DESENLER = [
    ("ARTICOLUL 11", re.compile(r"(?i)art[._-]*11(?!\d)")),
    ("ARTICOLUL 8′′2", re.compile(r"(?i)art[._-]*8[._]2(?!\d)")),
    ("ARTICOLUL 8′′1", re.compile(r"(?i)art[._-]*8[._]1(?!\d)")),
    ("ARTICOLUL 10", re.compile(r"(?i)art[._-]*10(?!\d)")),
    ("ARTICOLUL 8", re.compile(r"(?i)art[._-]*8(?!\d)")),
]


def gercek_kategori(dosya_adi):
    for kategori, desen in DESENLER:
        if desen.search(dosya_adi):
            return kategori
    return "NR. DOSAR"  # makale numarasiz -> NR. DOSAR'a ait kabul edildi


# 1) Her dosyanın hangi klasör(ler)de fiziksel olarak var olduğunu bul.
konumlar = {}  # dosya_adi -> [klasor, klasor, ...]
for klasor in KLASORLER:
    yol = os.path.join(STADIU_KOK, klasor)
    if not os.path.isdir(yol):
        continue
    for f in os.listdir(yol):
        if f.lower().endswith(".pdf"):
            konumlar.setdefault(f, []).append(klasor)

toplam_dosya = len(konumlar)
tasinan = 0
silinen_kopya = 0
zaten_dogru = 0

for dosya, bulundugu_klasorler in sorted(konumlar.items()):
    hedef = gercek_kategori(dosya)
    hedef_yol = os.path.join(STADIU_KOK, hedef, dosya)
    hedef_url_yol = hedef_yol + ".url"

    if hedef not in bulundugu_klasorler:
        # Hedefte yok -- herhangi bir kaynaktan (ilk bulunan) kopyala.
        kaynak_klasor = bulundugu_klasorler[0]
        kaynak_yol = os.path.join(STADIU_KOK, kaynak_klasor, dosya)
        kaynak_url_yol = kaynak_yol + ".url"
        os.makedirs(os.path.join(STADIU_KOK, hedef), exist_ok=True)
        shutil.copy2(kaynak_yol, hedef_yol)
        if os.path.isfile(kaynak_url_yol):
            shutil.copy2(kaynak_url_yol, hedef_url_yol)
        tasinan += 1
    else:
        zaten_dogru += 1

    # Şimdi hedef DIŞINDAKİ tüm kopyaları sil.
    for klasor in bulundugu_klasorler:
        if klasor == hedef:
            continue
        yanlis_yol = os.path.join(STADIU_KOK, klasor, dosya)
        yanlis_url_yol = yanlis_yol + ".url"
        if os.path.isfile(yanlis_yol):
            os.remove(yanlis_yol)
            silinen_kopya += 1
        if os.path.isfile(yanlis_url_yol):
            os.remove(yanlis_url_yol)

print(f"Toplam tekil dosya: {toplam_dosya}")
print(f"Zaten dogru klasorde olan: {zaten_dogru}")
print(f"Dogru klasore kopyalanan (eksikti): {tasinan}")
print(f"Yanlis klasorlerden silinen kopya sayisi: {silinen_kopya}")

print("\n=== SON DURUM: klasor basina dosya sayisi ===")
for klasor in KLASORLER:
    yol = os.path.join(STADIU_KOK, klasor)
    if os.path.isdir(yol):
        sayi = len([f for f in os.listdir(yol) if f.lower().endswith(".pdf")])
        print(f"  {klasor}: {sayi}")
