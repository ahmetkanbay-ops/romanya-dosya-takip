# -*- coding: utf-8 -*-
"""
Play Store'un zorunlu kıldığı Gizlilik Politikası ve uygulama içi
Kullanım Şartları / Sorumluluk Reddi metinleri.

main.py bu metinleri hem web sayfası (Play Store başvurusunda istenen
gizlilik politikası URL'si) olarak, hem de mobil uygulamanın ilk açılış
onay ekranında göstermesi için düz metin olarak sunar.

NOT: Bu metinler bir hukuk danışmanının incelemesinin YERİNE GEÇMEZ,
başlangıç noktası olarak hazırlanmıştır. Yayına almadan önce bir avukata
göstermen tavsiye edilir.

2026-08-17 DÜZELTMESİ (kod taraması sırasında bulundu, 2 gerçek hata):
1) GIZLILIK_POLITIKASI_METIN, Favorilerim/push bildirimi özelliklerini
   hâlâ "ileride eklenecek" gibi GELECEK ZAMANDA anlatıyordu -- oysa bu
   özellikler artık gerçekten çalışıyor (bkz. favoriler tablosu,
   push_tokenlari tablosu, bot.py'deki _bildirimleri_gonder). Metin
   şimdiki zamana güncellendi.
2) Her iki metinde de e-posta yer tutucusu YANLIŞLIKLA ÇİFT SÜSLÜ PARANTEZ
   ("{{ILETISIM_EPOSTA}}") ile yazılmıştı -- Python f-string'lerinde çift
   süslü parantez LİTERAL (kaçış) anlamına gelir, yani hiçbir zaman gerçek
   bir e-postayla değiştirilmiyordu; sayfayı ziyaret eden biri kelimenin
   tam anlamıyla "{ILETISIM_EPOSTA}" yazısını görüyordu. Artık gerçek
   ILETISIM_EPOSTA sabiti tek süslü parantezle (gerçek f-string
   interpolasyonu) kullanılıyor.

Bu metin, uygulama içindeki (constants/i18n.tsx -- disclaimerMetin/
gizlilikMetin) 3 dilli sürümle İÇERİK OLARAK tutarlı tutulmaya çalışılıyor
-- birebir aynı olması şart değil (biri TR-tek-dil web sayfası, diğeri
uygulama içi 3 dilli metin) ama aynı gerçekleri anlatmalı.
"""
import html

UYGULAMA_ADI = "Romanya Dosya Takip"
# 2026-08-17: kullanıcı isteğiyle iletişim e-postası bu Gmail'e taşındı
# (Outlook'un artık SMTP temel kimlik doğrulamasını desteklememesiyle aynı
# gerekçe -- tüm iletişim tek bir yerde toplandı).
ILETISIM_EPOSTA = "ahmet.knby.25@gmail.com"

SORUMLULUK_REDDI_KISA = (
    "Bu uygulama resmi bir Romanya devlet kurumu değildir ve Romanya "
    "İçişleri Bakanlığı, Konsolosluk ya da Autoritatea Națională pentru "
    "Cetățenie ile herhangi bir bağlantısı yoktur. Uygulama, "
    "cetatenie.just.ro adresinde kamuya açık olarak yayınlanan PDF "
    "listelerini otomatik olarak tarayıp size kolaylık sağlamak amacıyla "
    "geliştirilmiştir; resmi ve bağlayıcı olan tek kaynak Romanya "
    "makamlarının resmi web sitesidir. Resmi hak kayıpları yaşamamak "
    "adına konsolosluk duyurularını mutlaka bizzat da takip etmeniz "
    "önerilir."
)

KULLANIM_SARTLARI_METIN = f"""
{UYGULAMA_ADI} — Kullanım Şartları ve Sorumluluk Reddi

Son güncelleme: 17 Ağustos 2026

1. Uygulamanın Amacı
{UYGULAMA_ADI}, Romanya vatandaşlık başvuru sürecini takip eden kişilere
kolaylık sağlamak amacıyla, cetatenie.just.ro adresinde kamuya açık olarak
yayınlanan PDF listelerini (Stadiu Dosar ve Ordine sayfaları) otomatik
olarak tarayıp dosya numarası bazında arama imkânı sunan bağımsız,
resmi olmayan bir bilgilendirme aracıdır.

2. Resmi Kurum Değildir
{UYGULAMA_ADI}, Romanya İçişleri Bakanlığı, herhangi bir Romanya
konsolosluğu veya Autoritatea Națională pentru Cetățenie (ANC) ile
bağlantılı, onlar tarafından desteklenen veya onaylanan bir uygulama
DEĞİLDİR. Uygulama içindeki hiçbir bilgi resmi bir belge veya beyan
niteliği taşımaz.

3. Sorumluluk Reddi
{SORUMLULUK_REDDI_KISA}
Uygulama kaynaklı gecikme, eksik/hatalı veri gösterimi, teknik aksaklık
veya PDF tarama sürecindeki olası hatalardan doğabilecek hiçbir zarardan
geliştirici sorumlu tutulamaz. Uygulama "olduğu gibi" (as-is) sunulur,
kesintisiz veya hatasız çalışacağına dair hiçbir garanti verilmez.

4. Kullanıcının Sorumluluğu
Kullanıcı, uygulamada gördüğü her sonucu resmi kaynaktan (uygulama
içindeki "Resmi Belgeyi Görüntüle" bağlantısı veya doğrudan
cetatenie.just.ro adresi) teyit etmekle yükümlüdür. Başvuru sürecinizle
ilgili nihai ve bağlayıcı bilgi yalnızca resmi Romanya makamlarından
alınabilir.

5. Değişiklikler
Bu şartlar önceden haber verilmeksizin güncellenebilir. Uygulamayı
kullanmaya devam etmeniz güncel şartları kabul ettiğiniz anlamına gelir.

6. İletişim
Sorularınız için: {ILETISIM_EPOSTA}
""".strip()

GIZLILIK_POLITIKASI_METIN = f"""
{UYGULAMA_ADI} — Gizlilik Politikası

Son güncelleme: 17 Ağustos 2026

1. Topladığımız Veriler
{UYGULAMA_ADI}, çalışması için hesap oluşturmanızı istemez. Uygulama
sınırlı miktarda teknik veri toplar:
- Bildirim izni verirseniz, cihazınıza ait anonim bir bildirim belirteci
  (Expo/Apple/Google push token).
- Cihazınıza özel, rastgele üretilmiş anonim bir kimlik.
- Favorilerinize eklediğiniz dosya numaraları ve yıl bilgisi.
- Sorgulama sırasında girdiğiniz dosya numarası/yıl/kategori bilgileri.
Onaylanmamış bir dosya numarası sorguladığınızda, favorilere eklemeseniz
bile, onaylandığında bildirim gönderebilmemiz için bu numara arka planda
otomatik olarak da kaydedilir.
Ad, soyad, TC/CNP kimlik numarası, adres, e-posta, telefon, konum,
kamera/mikrofon erişimi gibi kimlik bilgileri ASLA TALEP EDİLMEZ ve
SAKLANMAZ.

2. Verilerin Kullanım Amacı
Saklanan bildirim belirteci, yalnızca sizin kaydettiğiniz dosya
numarasının durumu değiştiğinde (örn. onaylandığında) size bildirim
gönderebilmek amacıyla kullanılır. Favori listeniz, cihazlar arasında
hatırlanabilmesi için saklanır. Hiçbir veri üçüncü taraflarla pazarlama
amacıyla paylaşılmaz veya satılmaz.

3. Üçüncü Taraf Hizmetler
Bildirimlerin telefonunuza ulaşabilmesi için bildirim belirteciniz
Expo'nun push bildirim altyapısı ile (ve o altyapı üzerinden Apple/
Google'ın kendi bildirim servisleriyle) paylaşılır. Bunun dışında
verileriniz hiçbir reklam, analitik veya pazarlama şirketiyle
paylaşılmaz.

4. Veri Kaynağı Hakkında
Uygulamada gösterilen dosya durumu bilgileri, Romanya makamlarının
resmi web sitesi cetatenie.just.ro'da halka açık olarak yayınlanan PDF
listelerinden otomatik olarak derlenir -- bu veriler zaten kamuya
açıktır.

5. Güvenlik
Veriler, sunucumuzla şifreli bağlantı (HTTPS) üzerinden iletilir.

6. Verilerin Saklanma Süresi ve Silinmesi
Favori dosyalarınızı istediğiniz zaman uygulama içindeki "Favorilerim"
sekmesinden kaldırabilirsiniz. Bildirim iznini telefonunuzun Ayarlar
kısmından her zaman kapatabilirsiniz. Tüm verilerinizin tamamen
silinmesini talep etmek için {ILETISIM_EPOSTA} adresinden bize
ulaşabilirsiniz.

7. Çocuklar
Bu uygulama çocuklara yönelik değildir, bilerek 13 yaş altı
kullanıcılardan veri toplamaz.

8. Değişiklikler
Bu politika güncellenirse, güncel hali her zaman bu sayfada ve uygulama
içi "Yasal Bilgiler" sekmesinde yer alacaktır.

9. İletişim
Sorularınız için: {ILETISIM_EPOSTA}
""".strip()


def sayfa_html(baslik, metin):
    # 2026-08-18 (güvenlik denetimi madde 16): metin escape edilmeden
    # doğrudan HTML'e basılıyordu. Şu an bu fonksiyon SADECE sabit,
    # kod içinde tanımlı metinlerle çağrılıyor (kullanıcı girdisi asla
    # buraya ulaşmıyor), bu yüzden bugün için gerçek bir XSS riski yok --
    # ama fonksiyon ileride farklı bir amaçla (ör. kullanıcı içeriği
    # göstermek için) yeniden kullanılırsa oluşacak riski baştan söndüren
    # bir savunma katmanı. ÖNEMLİ: html.escape() ÖNCE, \n->HTML dönüşümü
    # SONRA yapılmalı -- aksi halde escape() az önce eklenen <br>/<p>
    # etiketlerini de (yanlışlıkla) kaçırıp bozar.
    govde = html.escape(metin).replace("\n\n", "</p><p>").replace("\n", "<br>")
    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{baslik}</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif;
          max-width: 720px; margin: 40px auto; padding: 0 20px; line-height: 1.6; color: #222; }}
  h1 {{ font-size: 22px; }}
  p {{ margin: 14px 0; white-space: pre-wrap; }}
</style>
</head>
<body>
<p>{govde}</p>
</body>
</html>"""
