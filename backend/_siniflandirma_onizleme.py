# -*- coding: utf-8 -*-
"""
GEÇİCİ önizleme betiği (2026-08-15): stadiu klasörlerindeki TÜM PDF dosya
adlarını toplar (5 klasörün birleşimi, tekrarsız), her biri için dosya
adındaki desene göre GERÇEK kategoriyi tahmin eder ve bir özet/liste basar.
HİÇBİR ŞEYİ TAŞIMAZ/SİLMEZ/DEĞİŞTİRMEZ -- sadece önizleme.
"""
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STADIU_KOK = os.path.join(BASE_DIR, "pdfs", "stadiu")

KLASORLER = ["ARTICOLUL 10", "ARTICOLUL 11", "ARTICOLUL 8", "ARTICOLUL 8′′1", "ARTICOLUL 8′′2", "NR. DOSAR"]

# Dosya adı desenlerine göre GERÇEK kategori tahmini. Sıra ÖNEMLİ: daha
# spesifik desenler (8.1, 8.2) önce, genel "8" deseni EN SONA (yoksa "8.1"
# içindeki "8" erken eşleşip yanlış sınıflandırır).
DESENLER = [
    ("ARTICOLUL 11", re.compile(r"(?i)art[._-]*11(?!\d)")),
    ("ARTICOLUL 8′′2", re.compile(r"(?i)art[._-]*8[._]2(?!\d)")),
    ("ARTICOLUL 8′′1", re.compile(r"(?i)art[._-]*8[._]1(?!\d)")),
    ("ARTICOLUL 10", re.compile(r"(?i)art[._-]*10(?!\d)")),
    ("ARTICOLUL 8", re.compile(r"(?i)art[._-]*8(?!\d)")),
]


def gercek_kategori_tahmin(dosya_adi):
    for kategori, desen in DESENLER:
        if desen.search(dosya_adi):
            return kategori
    return None  # tahmin edilemedi (ör. "Rezultate-interviu-*.pdf" gibi makale numarasız dosyalar)


# 1) Tüm klasörlerin BİRLEŞİMİNİ (tekrarsız dosya adı seti) topla.
tum_dosyalar = set()
for klasor in KLASORLER:
    yol = os.path.join(STADIU_KOK, klasor)
    if not os.path.isdir(yol):
        continue
    for f in os.listdir(yol):
        if f.lower().endswith(".pdf"):
            tum_dosyalar.add(f)

print(f"Toplam TEKRARSIZ pdf dosya adi (5 klasorun birlesimi): {len(tum_dosyalar)}\n")

tahminler = {}
tahmin_edilemeyen = []
for dosya in sorted(tum_dosyalar):
    kat = gercek_kategori_tahmin(dosya)
    if kat is None:
        tahmin_edilemeyen.append(dosya)
    else:
        tahminler.setdefault(kat, []).append(dosya)

print("=== TAHMIN EDILEN KATEGORI DAGILIMI ===")
for kat in ["ARTICOLUL 8", "ARTICOLUL 8′′1", "ARTICOLUL 8′′2", "ARTICOLUL 10", "ARTICOLUL 11"]:
    liste = tahminler.get(kat, [])
    print(f"\n--- {kat} ({len(liste)} dosya) ---")
    for d in liste[:8]:
        print("  ", d)
    if len(liste) > 8:
        print(f"   ... ve {len(liste)-8} tane daha")

print(f"\n=== TAHMIN EDILEMEYEN (makale numarasi yok, {len(tahmin_edilemeyen)} dosya) ===")
for d in tahmin_edilemeyen[:25]:
    print("  ", d)
if len(tahmin_edilemeyen) > 25:
    print(f"   ... ve {len(tahmin_edilemeyen)-25} tane daha")
