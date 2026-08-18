# -*- coding: utf-8 -*-
"""
GEÇİCİ temizlik betiği (2026-08-15): "ARTICOLUL 8''2" klasörüne yanlışlıkla
karışan (başka kategorilere ait) PDF'leri temizler. Bir dosyayı SADECE
şu ikisi doğruysa siler:
  1) Dosya adı "8.2" / "8_2" içermiyorsa (yani gerçek 8^2 içeriği değilse)
  2) AYNI isimde bir kopya, diğer stadiu klasörlerinden (10/11/8/8''1/NR. DOSAR)
     birinde zaten doğru şekilde duruyorsa (yani veri kaybı olmayacaksa).
Eşleşmeyen/şüpheli durumlar SİLİNMEZ, sadece raporlanır.
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STADIU_KOK = os.path.join(BASE_DIR, "pdfs", "stadiu")
HEDEF_KLASOR = os.path.join(STADIU_KOK, "ARTICOLUL 8′′2")

DIGER_KLASORLER = [
    "ARTICOLUL 10", "ARTICOLUL 11", "ARTICOLUL 8", "ARTICOLUL 8′′1", "NR. DOSAR",
]

import re
# ÖNEMLİ DÜZELTME: ilk denemede "8.2" / "8_2" düz metin araması, tarih
# eklerini ("...-07.08.2026.pdf" -> "8.2026" içinde "8.2" geçiyor) YANLIŞ
# POZİTİF olarak "gerçek 8.2 içeriği" sanıyordu. Artık "8.2"/"8_2"den hemen
# SONRA rakam gelmemesi şartı aranıyor (yıl/tarih değil, gerçek "8.2" ibaresi).
_GERCEK_8_2_DESENI = re.compile(r"8[._]2(?!\d)")

def gercek_8_2_mi(dosya_adi):
    return bool(_GERCEK_8_2_DESENI.search(dosya_adi))

silinen = []
korunan_gercek = []
supheli = []

pdf_dosyalari = [f for f in os.listdir(HEDEF_KLASOR) if f.lower().endswith(".pdf")]

for dosya in pdf_dosyalari:
    if gercek_8_2_mi(dosya):
        korunan_gercek.append(dosya)
        continue

    # Başka bir klasörde aynı isimde dosya var mı?
    baska_yerde_var_mi = False
    for klasor in DIGER_KLASORLER:
        aday = os.path.join(STADIU_KOK, klasor, dosya)
        if os.path.isfile(aday):
            baska_yerde_var_mi = True
            break

    if baska_yerde_var_mi:
        # Güvenle silinebilir -- zaten doğru yerde bir kopyası var.
        for ek in [dosya, dosya + ".url"]:
            yol = os.path.join(HEDEF_KLASOR, ek)
            if os.path.isfile(yol):
                os.remove(yol)
        silinen.append(dosya)
    else:
        supheli.append(dosya)

print(f"Gercek 8.2 icerigi (KORUNDU): {len(korunan_gercek)}")
for d in korunan_gercek:
    print("  ", d)

print(f"\nSilinen (baska klasorde dogru kopyasi bulunan yanlis dosyalar): {len(silinen)}")
for d in silinen:
    print("  ", d)

print(f"\nSUPHELI (ne 8.2 icerigi ne de baska klasorde kopyasi var -- SILINMEDI, manuel bak): {len(supheli)}")
for d in supheli:
    print("  ", d)

kalan = [f for f in os.listdir(HEDEF_KLASOR) if f.lower().endswith(".pdf")]
print(f"\nKlasorde kalan toplam PDF: {len(kalan)}")
