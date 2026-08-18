# -*- coding: utf-8 -*-
"""
dosya_utils.py'deki SAF (yan etkisiz) fonksiyonlar için birim testleri.

Bu testler rastgele seçilmedi -- her biri, bu projenin geliştirilmesi
sırasında GERÇEKTEN yaşanmış, elle test edilerek bulunmuş bir bug'ı temsil
ediyor (bkz. her test grubunun üstündeki yorum). Amaç: bu hatalardan biri
ileride bir kod değişikliğiyle YENİDEN ortaya çıkarsa, kullanıcı telefonda
fark etmeden ÖNCE `pytest` bunu yakalasın.

Çalıştırmak için (backend/ klasöründen):
    python -m pytest tests/ -v
"""
import os
import sys

# backend/ klasörünü import yoluna ekle (testler backend/tests/ altında).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dosya_utils import (
    sayisal_cekirdek,
    tum_rakamlar,
    metinden_dosya_numaralarini_cikar,
    kategori_eslestir,
    metni_sadelestir,
    klasor_adi_guvenli,
    stadiu_dosya_kategorisi_uyusuyor_mu,
    ordine_dosya_kategorisi_uyusuyor_mu,
    mesaj_ve_durum,
    STADIU_ALT_KATEGORILERI,
    ORDINE_ALT_KATEGORILERI,
)


# ---------------------------------------------------------------------------
# sayisal_cekirdek
# ---------------------------------------------------------------------------
class TestSayisalCekirdek:
    def test_ayirici_ile_ilk_blok(self):
        assert sayisal_cekirdek("43484/RD/2023") == "43484"

    def test_bastaki_sifirlar_atilir(self):
        assert sayisal_cekirdek("043484") == "43484"

    def test_metin_icinde_gomulu(self):
        assert sayisal_cekirdek("Dosya No: 43484") == "43484"

    def test_none_girdi(self):
        assert sayisal_cekirdek(None) is None

    def test_rakam_yok(self):
        assert sayisal_cekirdek("RD") is None

    def test_tamami_sifir(self):
        # Baştaki sıfırlar atılınca boş kalırsa "0" dönmeli, None değil.
        assert sayisal_cekirdek("000") == "0"


# ---------------------------------------------------------------------------
# metinden_dosya_numaralarini_cikar
# ---------------------------------------------------------------------------
# 2026-08-15'te kullanıcı testinde bulunan "603" yanlış eşleşme sorunu:
# aynı çıplak numara (603) farklı yıllarda FARKLI kişilere ait olabiliyor.
# Bu fonksiyon eskiden bunları bir sözlükte aynı anahtar altında tutup
# birini SESSİZCE SİLİYORDU. Artık liste dönüyor, hiçbiri kaybolmamalı.
class TestMetindenDosyaNumaralariniCikar:
    def test_ayni_cekirdek_farkli_yil_ikisi_de_korunur(self):
        metin = "Dosya (603/2014) onaylandı. Ayrıca (603/2026) da listede."
        sonuc = metinden_dosya_numaralarini_cikar(metin)
        yillar = {kayit["yil"] for kayit in sonuc if kayit["cekirdek"] == "603"}
        assert yillar == {"2014", "2026"}

    def test_numara_harf_kodu_yil_deseni_oncelikli(self):
        sonuc = metinden_dosya_numaralarini_cikar("Başvuru 43484/RD/2023 numaralı")
        assert len(sonuc) == 1
        assert sonuc[0]["cekirdek"] == "43484"
        assert sonuc[0]["yil"] == "2023"

    def test_numara_yil_parantezli_deseni(self):
        sonuc = metinden_dosya_numaralarini_cikar("Kayıt: (41289/2021) işlendi.")
        assert len(sonuc) == 1
        assert sonuc[0]["cekirdek"] == "41289"
        assert sonuc[0]["yil"] == "2021"

    def test_yapilandirilmis_desen_varsa_yalin_sayi_yedegi_devreye_girmez(self):
        # "ORDIN NR. 1352" gibi alakasız bir sayı, yapılandırılmış bir
        # dosya numarası (43484/RD/2023) zaten bulunduysa dosya numarası
        # sanılmamalı.
        metin = "ORDIN NR. 1352 ile 43484/RD/2023 numaralı dosya onaylandı."
        sonuc = metinden_dosya_numaralarini_cikar(metin)
        cekirdekler = {kayit["cekirdek"] for kayit in sonuc}
        assert "43484" in cekirdekler
        assert "1352" not in cekirdekler

    def test_yil_araligindaki_sayilar_yalin_taramada_elenir(self):
        # Yapılandırılmış hiçbir desen yoksa, 1900-2100 arası sayılar
        # (muhtemelen yıl) dosya numarası olarak alınmamalı.
        sonuc = metinden_dosya_numaralarini_cikar("Belge 2023 yılında, 998877 numarayla düzenlendi.")
        cekirdekler = {kayit["cekirdek"] for kayit in sonuc}
        assert "2023" not in cekirdekler
        assert "998877" in cekirdekler

    def test_bos_metin(self):
        assert metinden_dosya_numaralarini_cikar("") == []


# ---------------------------------------------------------------------------
# kategori_eslestir / metni_sadelestir
# ---------------------------------------------------------------------------
class TestKategoriEslestir:
    def test_tam_esleme(self):
        assert kategori_eslestir("ARTICOLUL 11", STADIU_ALT_KATEGORILERI) == "ARTICOLUL 11"

    def test_aksanli_karakterler_yok_sayilir(self):
        # metni_sadelestir, Türkçe/Romence aksanlı karakterleri (İ, ş, ğ
        # gibi) sadeleştiriyor -- bu, kategori_eslestir’in temelini
        # oluşturuyor.
        assert metni_sadelestir("İçişleri Bakanlığı Şartı") == "ICISLERI BAKANLIGI SARTI"

    def test_bosluk_ve_buyuk_kucuk_harf_farki_yok_sayilir(self):
        assert kategori_eslestir("  articolul   11  ", STADIU_ALT_KATEGORILERI) == "ARTICOLUL 11"

    def test_kismi_icerme_esleme(self):
        sonuc = kategori_eslestir("  articolul 11  (güncel liste)", STADIU_ALT_KATEGORILERI)
        assert sonuc == "ARTICOLUL 11"

    def test_hicbir_sey_eslesmezse_none(self):
        assert kategori_eslestir("Alakasız bir başlık", STADIU_ALT_KATEGORILERI) is None

    def test_bos_metin_none_doner(self):
        assert kategori_eslestir("", STADIU_ALT_KATEGORILERI) is None


# ---------------------------------------------------------------------------
# stadiu_dosya_kategorisi_uyusuyor_mu / ordine_dosya_kategorisi_uyusuyor_mu
# ---------------------------------------------------------------------------
class TestStadiuDosyaKategorisiUyusuyorMu:
    def test_articolul_11_kendi_kategorisiyle_uyusur(self):
        assert stadiu_dosya_kategorisi_uyusuyor_mu("Art-11-lista-2023.pdf", "ARTICOLUL 11") is True

    def test_articolul_11_baska_articolul_kategorisiyle_uyusmaz(self):
        # Bulaşma senaryosu: dosya adı Article 11'e ait ama o an
        # Article 8 sekmesi işleniyor -- reddedilmeli.
        assert stadiu_dosya_kategorisi_uyusuyor_mu("Art-11-lista-2023.pdf", "ARTICOLUL 8") is False

    def test_articolul_olmayan_kategoriler_icin_desen_kontrolu_atlanir(self):
        # 2026-08-16 bug'ı: REZULTATE/INVITATII INTERVIU ART.8.1 gibi
        # ARTICOLUL-DIŞI kategoriler için dosya adında "art.8.1" geçse
        # bile bu bir bulaşma DEĞİL -- o kategorinin doğal içeriği.
        # Eskiden yanlışlıkla reddediliyordu, artık kontrol hiç
        # uygulanmamalı (True dönmeli).
        assert stadiu_dosya_kategorisi_uyusuyor_mu(
            "Rezultate-interviu-art.-8.1.-27.07.2026.pdf",
            "REZULTATE INTERVIU ART. 8.1",
        ) is True

    def test_desen_yoksa_guvenle_true(self):
        assert stadiu_dosya_kategorisi_uyusuyor_mu("NR-Dosar-liste-2023.pdf", "NR. DOSAR") is True


class TestOrdineDosyaKategorisiUyusuyorMu:
    def test_indice_yazimi_da_taninir(self):
        # 2026-08-16 düzeltmesi: "ind" VEYA "indice" yazımı -- eskiden
        # sadece "ind" tanınıyordu, "indice" yazımı yanlışlıkla düz
        # "Ordine articolul 8"e düşüyordu.
        assert ordine_dosya_kategorisi_uyusuyor_mu(
            "art-8-indice-1-lista.pdf", "Ordine articolul 8”1"
        ) is True

    def test_ind_kisa_yazimi_da_taninir(self):
        assert ordine_dosya_kategorisi_uyusuyor_mu(
            "Art-8-ind-1.pdf", "Ordine articolul 8”1"
        ) is True

    def test_minori_deseni(self):
        assert ordine_dosya_kategorisi_uyusuyor_mu(
            "Ordin-minori-2023.pdf", "Ordine minori"
        ) is True

    def test_yalin_siparis_numarasi_makale_sanilmaz(self):
        # Desen HER ZAMAN "art" kelimesini şart koşar -- salt bir rakamı
        # (ör. "1352") asla makale numarası sanmamalı.
        assert ordine_dosya_kategorisi_uyusuyor_mu(
            "Ordin_nr._1691P_din_11.07.2019.pdf", "Ordine articolul 11"
        ) is True

    def test_articolul_11_baska_kategoriyle_uyusmaz(self):
        assert ordine_dosya_kategorisi_uyusuyor_mu(
            "ORDIN-1352-art-11-persoane.pdf", "Ordine articolul 8"
        ) is False


# ---------------------------------------------------------------------------
# klasor_adi_guvenli / mesaj_ve_durum
# ---------------------------------------------------------------------------
class TestKlasorAdiGuvenli:
    def test_gecersiz_karakterler_temizlenir(self):
        sonuc = klasor_adi_guvenli('ARTICOLUL 8"1 / TEST')
        assert '"' not in sonuc
        assert "/" not in sonuc

    def test_bos_girdi_varsayilana_duser(self):
        assert klasor_adi_guvenli("") == "DIGER"
        assert klasor_adi_guvenli(None) == "DIGER"

    def test_asiri_uzun_isim_kirpilir(self):
        assert len(klasor_adi_guvenli("A" * 200)) <= 80


class TestMesajVeDurum:
    def test_ordine_onay_mesaji(self):
        mesaj, durum = mesaj_ve_durum("ordine")
        assert durum == "ONAYLANDI"
        assert "onaylanmıştır" in mesaj

    def test_stadiu_islemde_mesaji(self):
        mesaj, durum = mesaj_ve_durum("stadiu")
        assert durum == "İŞLEMDE"
