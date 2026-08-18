# -*- coding: utf-8 -*-
"""GEÇİCİ temizlik betiği (2026-08-15, İKİNCİ bulaşma olayı sonrası).
Mantık, ilk seferkiyle (_yeniden_siniflandir.py, artık silinmiş) BİREBİR
aynı -- 6 stadiu klasörünün birleşimini alıp, her dosyayı adına göre GERÇEK
kategorisine taşır/tekilleştirir."""
import os
import shutil
from dosya_utils import _STADIU_DOSYA_KATEGORI_DESENLERI, klasor_adi_guvenli

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STADIU_KOK = os.path.join(BASE_DIR, "pdfs", "stadiu")

# ÖNEMLİ (2026-08-15 -- ikinci temizlikte bulunan hata): klasör adlarını
# elle/sabit yazmak riskli -- "8''1" (U+2032 iki kez) ile "8"1" (U+2033 tek
# karakter) görsel olarak neredeyse ayırt edilemiyor, elle yazınca kolayca
# karışıyor (tam olarak bu betiğin bir önceki sürümünde olan hata). Bunun
# yerine klasörler DİSKTEN OTOMATİK keşfediliyor -- hangi Unicode varyantı
# kullanılmış olursa olsun, var olan HER klasör dahil ediliyor.
KLASORLER = [
    d for d in os.listdir(STADIU_KOK)
    if os.path.isdir(os.path.join(STADIU_KOK, d))
]
print("Bulunan klasorler:", KLASORLER)


def gercek_kategori(dosya_adi):
    # klasor_adi_guvenli() ile normalize ediyoruz -- bot.py'nin klasör
    # oluştururken kullandığı TAM AYNI fonksiyon, böylece Unicode
    # varyantı (′′ vs ″) farkından kaynaklanan yeni bir hataya asla
    # düşmüyoruz (bkz. üstteki 2026-08-15 notu).
    for kategori, desen in _STADIU_DOSYA_KATEGORI_DESENLERI:
        if desen.search(dosya_adi):
            return klasor_adi_guvenli(kategori)
    return klasor_adi_guvenli("NR. DOSAR")


konumlar = {}
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

print("\n=== SON DURUM: klasor basina PDF sayisi ===")
for klasor in KLASORLER:
    yol = os.path.join(STADIU_KOK, klasor)
    if os.path.isdir(yol):
        sayi = len([f for f in os.listdir(yol) if f.lower().endswith(".pdf")])
        print(f"  {klasor}: {sayi}")
