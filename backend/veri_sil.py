# -*- coding: utf-8 -*-
"""
2026-08-18 (güvenlik denetimi madde 21): Gizlilik Politikası (bkz.
hukuki_metinler.py GIZLILIK_POLITIKASI_METIN madde 6) "tüm verilerinizin
silinmesini {ILETISIM_EPOSTA} adresinden talep edebilirsiniz" diyor, ama
buna karşılık gelen otomatik bir silme aracı yoktu -- süreç tamamen elle
(admin'in veritabanına SQL yazması) yapılması gerekiyordu. Bu script, bir
kullanıcı silme talebi geldiğinde ADMIN'İN elle çalıştırması için hazırlandı.

ÖNEMLİ: "Hesap" kavramı yok -- kullanıcıyı tanımlayan tek şey cihaz
kimliğidir (constants/api.tsx cihazKimligiGetir() -- "cihaz-xxxx" formatında,
favoriler.expo_push_token kolonunda saklanır) VE/VEYA o cihaza kayıtlı
gerçek Expo push token'ıdır (push_tokenlari tablosu). Talep sahibi genelde
sadece cihaz kimliğini bilmez -- bu yüzden script iki kimlikleyiciyi de
kabul eder, hangisi verilirse diğerini push_tokenlari.cihaz_kimligi
eşleşmesinden bulup HER İKİSİNE ait tüm kayıtları siler.

Kullanım (backend/ klasöründen):
    python veri_sil.py --cihaz-kimligi cihaz-a3f8e9d2...
    python veri_sil.py --push-token ExponentPushToken[xxxxx]
    python veri_sil.py --cihaz-kimligi cihaz-xxx --gercekten-sil

Varsayılan olarak KURU ÇALIŞTIRMA (dry-run) yapar -- sadece neyin
silineceğini gösterir, hiçbir şeyi silmez. Gerçekten silmek için
--gercekten-sil bayrağı ZORUNLU (yanlışlıkla veri kaybını önlemek için).
"""
import argparse
import os
import sys

from dosya_utils import veritabani_baglantisi, guvenli_commit

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 2026-08-19 (Render'a taşıma): bkz. main.py'deki aynı isimli sabitin notu.
VERI_DIZINI = os.environ.get("DATA_DIR", BASE_DIR)
DB_FILE = os.path.join(VERI_DIZINI, "dosyalar.db")


def _ilgili_kimlikleri_bul(cursor, cihaz_kimligi, push_token):
    """
    Verilen tek kimlikleyiciden yola çıkıp, aynı kullanıcıya ait OLASI HER
    İKİ kimlikleyiciyi de (cihaz kimliği + gerçek push token) bulur --
    aksi halde sadece biri silinir, diğerine ait kayıt (favoriler veya
    push_tokenlari'nda) unutulmuş olur.
    """
    if cihaz_kimligi and not push_token:
        cursor.execute(
            "SELECT expo_push_token FROM push_tokenlari WHERE cihaz_kimligi = ?",
            (cihaz_kimligi,),
        )
        row = cursor.fetchone()
        if row:
            push_token = row[0]
    elif push_token and not cihaz_kimligi:
        cursor.execute(
            "SELECT cihaz_kimligi FROM push_tokenlari WHERE expo_push_token = ?",
            (push_token,),
        )
        row = cursor.fetchone()
        if row and row[0]:
            cihaz_kimligi = row[0]
    return cihaz_kimligi, push_token


def kullaniciya_ait_veriyi_sil(cihaz_kimligi=None, push_token=None, gercekten_sil=False):
    if not cihaz_kimligi and not push_token:
        print("Hata: --cihaz-kimligi veya --push-token belirtmelisiniz.")
        return

    conn = veritabani_baglantisi(DB_FILE)
    cursor = conn.cursor()

    cihaz_kimligi, push_token = _ilgili_kimlikleri_bul(cursor, cihaz_kimligi, push_token)

    print("Aranan kimlikler:")
    print(f"  cihaz_kimligi = {cihaz_kimligi!r}")
    print(f"  push_token    = {push_token!r}")
    print()

    silinecekler = []

    if cihaz_kimligi:
        cursor.execute(
            "SELECT id, dosya_no, yil, otomatik_mi FROM favoriler WHERE expo_push_token = ?",
            (cihaz_kimligi,),
        )
        favori_satirlari = cursor.fetchall()
        for satir in favori_satirlari:
            silinecekler.append(f"  favoriler.id={satir[0]} dosya_no={satir[1]} yil={satir[2]} otomatik_mi={satir[3]}")

    push_tokenlari_satirlari = []
    if push_token:
        cursor.execute("SELECT id, expo_push_token FROM push_tokenlari WHERE expo_push_token = ?", (push_token,))
        push_tokenlari_satirlari = cursor.fetchall()
    elif cihaz_kimligi:
        cursor.execute("SELECT id, expo_push_token FROM push_tokenlari WHERE cihaz_kimligi = ?", (cihaz_kimligi,))
        push_tokenlari_satirlari = cursor.fetchall()
    for satir in push_tokenlari_satirlari:
        silinecekler.append(f"  push_tokenlari.id={satir[0]} expo_push_token={satir[1]}")

    if not silinecekler:
        print("Bu kimliklere ait hiçbir kayıt bulunamadı -- silinecek bir şey yok.")
        conn.close()
        return

    print(f"Silinecek {len(silinecekler)} kayıt:")
    for satir in silinecekler:
        print(satir)
    print()

    if not gercekten_sil:
        print("[KURU ÇALIŞTIRMA] Hiçbir şey silinmedi. Gerçekten silmek için --gercekten-sil ekleyin.")
        conn.close()
        return

    if cihaz_kimligi:
        cursor.execute("DELETE FROM favoriler WHERE expo_push_token = ?", (cihaz_kimligi,))
    if push_token:
        cursor.execute("DELETE FROM push_tokenlari WHERE expo_push_token = ?", (push_token,))
    elif cihaz_kimligi:
        cursor.execute("DELETE FROM push_tokenlari WHERE cihaz_kimligi = ?", (cihaz_kimligi,))

    guvenli_commit(conn)
    conn.close()
    print(f"✓ {len(silinecekler)} kayıt kalıcı olarak silindi.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bir kullanıcının tüm verilerini (favoriler + push token) siler.")
    parser.add_argument("--cihaz-kimligi", default=None, help="constants/api.tsx cihazKimligiGetir()'ın ürettiği 'cihaz-xxxx' kimliği.")
    parser.add_argument("--push-token", default=None, help="Gerçek Expo push token (ExponentPushToken[...]).")
    parser.add_argument("--gercekten-sil", action="store_true", help="Bu bayrak olmadan sadece önizleme yapılır, hiçbir şey silinmez.")
    args = parser.parse_args()

    if not args.cihaz_kimligi and not args.push_token:
        parser.print_help()
        sys.exit(1)

    kullaniciya_ait_veriyi_sil(
        cihaz_kimligi=args.cihaz_kimligi,
        push_token=args.push_token,
        gercekten_sil=args.gercekten_sil,
    )
