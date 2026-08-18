# -*- coding: utf-8 -*-
"""
GEÇİCİ teşhis betiği (2026-08-15) -- sadece eksik 5 alt kategorinin kök
nedenini bulmak için bir kereliğine çalıştırılıyor, üretim kodunun parçası
DEĞİL. İş bitince silinecek.

Yaptığı: stadiu-dosar sayfasına gidip 5 eksik kategoriyi normal bot
mantığıyla (_kategori_elementini_bul) arar, bulamazsa teşhis kaydı alır.
Ayrıca "ARTICOLUL 8" elemanına tıklayıp tıklama SONRASI sayfanın tamamını
da ayrıca kaydeder (nested/accordion ihtimalini test etmek için) ve
sayfadaki TÜM görünür metin bloklarını (kategori adayı olabilecek) ayrı bir
metin dosyasına döker.
"""
import os
from playwright.sync_api import sync_playwright

from bot import _kategori_elementini_bul, _teshis_kaydet, TESHIS_KLASOR
from dosya_utils import metni_sadelestir

EKSIK_KATEGORILER = [
    "CONSULAT / ANC",
    "REZULTATE INTERVIU ART. 8",
    "INVITATII INTERVIU ART. 8",
    "REZULTATE INTERVIU ART. 8.1",
    "INVITATII INTERVIU ART. 8.1",
]

URL = "https://cetatenie.just.ro/stadiu-dosar/"

os.makedirs(TESHIS_KLASOR, exist_ok=True)

with sync_playwright() as p:
    browser = p.firefox.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    print(f"→ Bağlanılıyor: {URL}")
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3000)
    print("✓ Sayfa yüklendi.")

    # 1) Ana sayfadaki TÜM görünür metinleri dök (kategori adayları burada
    #    olmalı -- gerçek yazımlarını görmek için).
    try:
        tum_metinler = page.locator("body").inner_text()
        yol = os.path.join(TESHIS_KLASOR, "ANA_SAYFA_TUM_METIN.txt")
        with open(yol, "w", encoding="utf-8") as f:
            f.write(tum_metinler)
        print(f"✓ Ana sayfa tüm metni kaydedildi: {yol}")
    except Exception as e:
        print(f"✗ Tüm metin alınamadı: {e}")

    # 2) Ana sayfanın HTML + ekran görüntüsünü de kaydet (referans için).
    try:
        with open(os.path.join(TESHIS_KLASOR, "ANA_SAYFA.html"), "w", encoding="utf-8") as f:
            f.write(page.content())
        page.screenshot(path=os.path.join(TESHIS_KLASOR, "ANA_SAYFA.png"), full_page=True)
        print("✓ Ana sayfa HTML + ekran görüntüsü kaydedildi.")
    except Exception as e:
        print(f"✗ Ana sayfa kaydı alınamadı: {e}")

    # 3) Eksik her kategoriyi normal bot mantığıyla ara.
    for kategori in EKSIK_KATEGORILER:
        print(f"\n--- Aranıyor: '{kategori}' ---")
        eleman = _kategori_elementini_bul(page, kategori)
        if eleman is None:
            print(f"  ✗ BULUNAMADI.")
            _teshis_kaydet(page, "stadiu", kategori, URL)
        else:
            try:
                metin = eleman.text_content()
                print(f"  ✓ BULUNDU -- eşleşen eleman metni: {metin!r}")
            except Exception as e:
                print(f"  ✓ BULUNDU ama metin okunamadı: {e}")

    # 4) "ARTICOLUL 8" elemanına tıklayıp SONRASINDA sayfada bu 5 kategoriden
    #    biri belirir mi diye kontrol et (nested/accordion ihtimali).
    print("\n--- Test: 'ARTICOLUL 8' tıklanınca içinden REZULTATE/INVITATII çıkıyor mu? ---")
    try:
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)
        art8 = _kategori_elementini_bul(page, "ARTICOLUL 8")
        if art8 is not None:
            art8.click(timeout=15000)
            page.wait_for_timeout(2000)
            with open(os.path.join(TESHIS_KLASOR, "ARTICOLUL8_TIKLAMA_SONRASI.html"), "w", encoding="utf-8") as f:
                f.write(page.content())
            page.screenshot(path=os.path.join(TESHIS_KLASOR, "ARTICOLUL8_TIKLAMA_SONRASI.png"), full_page=True)
            metin_sonrasi = page.locator("body").inner_text()
            with open(os.path.join(TESHIS_KLASOR, "ARTICOLUL8_TIKLAMA_SONRASI.txt"), "w", encoding="utf-8") as f:
                f.write(metin_sonrasi)
            for kategori in EKSIK_KATEGORILER:
                var_mi = metni_sadelestir(kategori) in metni_sadelestir(metin_sonrasi)
                print(f"  '{kategori}' ARTICOLUL 8 tıklandıktan sonra sayfa metninde {'VAR' if var_mi else 'YOK'}")
        else:
            print("  ✗ 'ARTICOLUL 8' elemanı bile bulunamadı (beklenmiyordu).")
    except Exception as e:
        print(f"  ✗ Test başarısız: {e}")

    browser.close()

print("\n✓ Teşhis tamamlandı. backend/teshis/ klasörüne bak.")
