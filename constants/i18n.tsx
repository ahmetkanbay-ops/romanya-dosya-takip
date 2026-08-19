import AsyncStorage from '@react-native-async-storage/async-storage';
import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';

// ---------------------------------------------------------------------------
// Desteklenen diller. Yeni bir dil eklemek istersen: (1) DILLER dizisine
// ekle, (2) CEVIRILER objesine o dilin tüm anahtarlarını ekle.
// ---------------------------------------------------------------------------
export type DilKodu = 'tr' | 'en' | 'ro';

export const DILLER: { kod: DilKodu; etiket: string; bayrak: string }[] = [
  { kod: 'tr', etiket: 'TR', bayrak: '🇹🇷' },
  { kod: 'en', etiket: 'EN', bayrak: '🇬🇧' },
  { kod: 'ro', etiket: 'RO', bayrak: '🇷🇴' },
];

const DIL_ANAHTARI = 'secili_dil_v1';

// ---------------------------------------------------------------------------
// Çeviriler. Kategori isimleri (ARTICOLUL 11, Ordine minori vb.) BİLEREK
// çevrilmiyor -- bunlar cetatenie.just.ro'daki resmi sayfa başlıklarıyla
// birebir eşleşmesi gereken sabit isimler, çevrilirse kullanıcı resmi
// siteyle karşılaştırırken kafası karışabilir.
// ---------------------------------------------------------------------------
const CEVIRILER = {
  tr: {
    appAdi: 'Romanya Dosya Takip',
    appSlogan: 'Detaylı Vatandaşlık ve Aşama Sorgulama',
    dosyaNoEtiket: 'Dosya Numarası *',
    dosyaNoOrnek: 'Örn: 12345',
    // 2026-08-16: "(Opsiyonel)" ibaresi kaldırıldı -- alt_kategori ile aynı
    // gerekçe (bkz. altKategoriEtiket notu): yanlış yıl girilirse artık tam
    // ekran uyarı çıkıyor, "opsiyonel" demek yanıltıcı olurdu.
    yilEtiket: 'Yıl',
    yilOrnek: 'Örn: 2023',
    anaKategoriEtiket: 'Ana Kategori',
    // 2026-08-16: "(İsteğe Bağlı Filtre)" ibaresi kaldırıldı -- yanlış alt
    // kategori seçilirse artık tam ekran bir uyarı çıkıyor (bkz.
    // index.tsx kategoriUyarisi Modal'ı), bu yüzden "opsiyonel/önemsiz"
    // izlenimi vermek yanıltıcı olurdu (kullanıcı isteği).
    altKategoriEtiket: 'Alt Kategori',
    sorgulaButon: 'Sorgula',
    hataBosNumara: 'Lütfen bir dosya numarası girin.',
    hataBaglanti: 'Sunucuya bağlanılamadı. İnternet bağlantınızı kontrol edin.',
    sonucBaslik: 'Sorgulama Sonuçları',
    durumEtiketOnEki: 'Durum:',
    resmiBelgeButon: '🔗 Resmi Web Sitesinde Görüntüle',
    yerelBelgeButon: '📄 İndirilen PDF\'i Görüntüle',
    yerelBelgeAciklama: 'Bu, sistemimizin resmi siteden indirdiği ve numaranızın geçtiği PDF\'in birebir kopyasıdır.',
    altUyari: 'Bu sonuçlar bilgilendirme amaçlıdır. Nihai ve bağlayıcı bilgi için lütfen resmi belgeyi/kaynağı kontrol edin.',
    // Bilinçli olarak çevrilmiyor: marka/güvenlik imzası, dil ne olursa
    // olsun İngilizce kalması isteniyor (kullanıcı talebi).
    footerImza: '🔒 Secured & Encrypted System · By @knby · © 2026',
    sonucBulunamadi: 'Bu numarayla eşleşen bir kayıt bulunamadı.',
    // 2026-08-16: kullanıcı bir kategori FİLTRESİ seçip aramış ama numara o
    // kategoride değilse (başka bir kategoride varsa), "sistemde hiç yok"
    // yanılgısına düşmesin diye daha yönlendirici bu mesaj gösteriliyor.
    // "{kategori}" yer tutucusu index.tsx'te gerçek kategori adıyla
    // değiştiriliyor.
    sonucBaskaKategoride: 'Bu numara sistemde var, ancak seçtiğiniz kategoride değil. Bulunduğu yer: {kategori}',
    // 2026-08-16: yanlış alt kategori seçildiğinde çıkan tam ekran uyarı modalı.
    kategoriUyariBaslik: 'Yanlış Kategori Seçimi',
    kategoriUyariMetin: 'Dosya numaranız sistemde {kategori} kategorisinde mevcut. Lütfen belirtilen kategoriyi tercih ederek tekrar sorgulama yapınız.',
    kategoriUyariUygula: 'Bu kategoriyle tekrar sorgula',
    kategoriUyariTamam: 'Tamam',
    // Mesai saatleri içinde resmi site erişilemez durumdaysa ana ekranda
    // gösterilen banner metni (bkz. backend /api/durum uç noktası).
    siteServisDisiBanner: 'cetatenie.just.ro resmi web sayfası şuanda servis dışıdır.',
    // 2026-08-15: kullanıcı isteğiyle eklendi -- yukarıdaki uyarı kaygı
    // verici durabiliyor, bu ek metin verilerin taze kaldığını hatırlatıp
    // ferahlık veriyor. "{tarih}" yer tutucusu index.tsx'te gerçek tarihle
    // değiştiriliyor.
    siteServisDisiEkAciklama: 'Sorgulamanız en son {tarih} tarihinde güncellenen veritabanından gerçekleştirilecektir.',
    // Kategoriye göre sonuç mesajı ve durum rozeti (backend'in durum
    // alanından bağımsız, dile göre burada belirleniyor).
    // 2026-08-16 (kullanıcı isteği): "işlemde" mesajı artık kullanıcıyı bir
    // sonraki adıma yönlendiriyor -- stadiu = 1. aşama (sisteme kabul),
    // ordine = 2. aşama (onay). Sadece "süreç devam ediyor" demek yerine
    // "şimdi ne yapmalı" sorusuna da cevap veriyor.
    sonucMesaji: {
      stadiu: 'Vatandaşlık başvurunuza ait dosyanız 1. aşama olarak sisteme kabul edilmiştir. Başvurunuzun onay durumunu (2. aşama) takip etmek için sorgulamanızı ORDİNE kategorisini seçerek tekrar yapabilirsiniz.',
      ordine: 'Tebrikler! Vatandaşlık başvurunuz onaylandı.',
    },
    durumRozeti: {
      stadiu: 'İŞLEMDE',
      ordine: 'ONAYLANDI',
    },
    durumBulunamadi: 'BULUNAMADI',
    // 2026-08-16 (kullanıcı isteği): aynı numara birden fazla sonuçla
    // eşleştiğinde (dosya numaraları farklı yıllarda tekrar kullanılabiliyor)
    // kullanıcıyı doğru/tekil sonuca yönlendiren bilgilendirme banner'ı.
    cokluSonucUyarisi: 'Numaranız birden fazla sonuçla eşleşti çünkü dosya numaraları farklı yıllarda tekrar kullanılabiliyor. Doğru sonuca ulaşmak için başvurunuz sırasında size verilen ana kategori, alt kategori ve yıl bilgilerini yukarıdaki alanlara girip tekrar sorgulayın.',
    // 2026-08-16: form alanlarının altında gösterilen PROAKTİF ipucu (arama
    // yapılmadan önce, her zaman görünür).
    dogruSonucIpucu: 'En isabetli sonuç için, başvurunuz sırasında size verilen ana kategori, alt kategori ve yıl bilgilerini yukarıya girmeniz önerilir.',
    // 2026-08-16 (kullanıcı isteği): stadiu<->ordine aşama geçişi için özel,
    // sakin bilgilendirme mesajları -- "yanlış kategori" uyarısından farklı,
    // bu NORMAL bir durum (henüz onaylanmadı / zaten onaylandı).
    sonucHenuzOrdineGecmedi: 'Dosya numaranız şu an STADİU (1. aşama) kısmında yayınlanmıştır. ORDİNE (2. aşama - onay) kısmında dosya numaranız henüz yayınlanmamıştır.',
    sonucZatenOrdineGecti: 'İyi haber: dosya numaranız artık ORDİNE (2. aşama - onay) kısmına geçmiştir. Güncel durumunuzu görmek için ORDİNE kategorisini seçerek tekrar sorgulayabilirsiniz.',
    // Açılış onay ekranı
    disclaimerBaslik: 'Önemli Bilgilendirme',
    disclaimerButon: 'Okudum, Anladım, Devam Et',
    disclaimerMetin: `Bu uygulama resmi bir Romanya devlet kurumu değildir ve Romanya İçişleri Bakanlığı, Konsolosluk ya da Autoritatea Națională pentru Cetățenie (ANC) ile herhangi bir bağlantısı yoktur.

Uygulama, cetatenie.just.ro adresinde kamuya açık olarak yayınlanan PDF listelerini (Stadiu Dosar ve Ordine sayfaları) otomatik olarak tarar ve size kolaylık sağlamak amacıyla dosya numarası bazında arama imkânı sunar.

Resmi ve bağlayıcı olan tek kaynak Romanya makamlarının resmi web sitesidir. Uygulama kaynaklı gecikme, eksik/hatalı veri gösterimi veya teknik aksaklıklardan geliştirici sorumlu tutulamaz.

Resmi hak kayıpları yaşamamak adına konsolosluk duyurularını bizzat da takip etmeniz önerilir. Uygulamayı kullanarak bu şartları kabul etmiş sayılırsınız.`,
    // Gizlilik Politikası (2026-08-17, Play Store zorunlu gereksinimi)
    gizlilikBaslik: 'Gizlilik Politikası',
    gizlilikMetin: `Son güncelleme: 17 Ağustos 2026

TOPLADIĞIMIZ VERİLER
Bu uygulama, bildirim gönderebilmek ve favori dosyalarınızı hatırlayabilmek için sınırlı miktarda teknik veri toplar:
• Bildirim kimliği (Expo/Apple/Google push token) -- yalnızca bildirim izni verirseniz alınır.
• Cihazınıza özel, rastgele üretilmiş anonim bir kimlik (isim/telefon numarası İÇERMEZ).
• Favorilere eklediğiniz dosya numaraları ve yıl bilgisi.
• Sorgulama sırasında girdiğiniz dosya numarası/yıl/kategori bilgileri (sunucuya, sonucu bulmak için gönderilir).
• Onaylanmamış bir dosya numarası sorguladığınızda, favorilere eklemeseniz bile, onaylandığında bildirim gönderebilmemiz için bu numara arka planda otomatik olarak da kaydedilir.

NELERİ TOPLAMIYORUZ
Adınızı, soyadınızı, e-posta adresinizi, telefon numaranızı, TC/CNP kimlik numaranızı, konumunuzu, kamera/mikrofon erişimini veya rehberinizi ASLA istemiyoruz ve toplamıyoruz.

VERİLERİ NEDEN KULLANIYORUZ
• Dosya numaranızın durumu değiştiğinde (örn. onaylandığında) size bildirim gönderebilmek.
• Favori listenizi cihazlar arası hatırlayabilmek.
• Sorgulama sonucunu doğru şekilde size gösterebilmek.

ÜÇÜNCÜ TARAFLARLA PAYLAŞIM
Bildirimlerin telefonunuza ulaşabilmesi için bildirim kimliğiniz Expo'nun push bildirim altyapısı ile (ve o altyapı üzerinden Apple/Google'ın kendi bildirim servisleriyle) paylaşılır. Bunun dışında verileriniz hiçbir reklam, analitik veya pazarlama şirketiyle paylaşılmaz, satılmaz.

VERİ KAYNAĞI HAKKINDA
Uygulamada gösterilen dosya durumu bilgileri, Romanya makamlarının resmi web sitesi cetatenie.just.ro'da halka açık olarak yayınlanan PDF listelerinden otomatik olarak derlenir -- bu veriler zaten kamuya açıktır.

GÜVENLİK
Veriler, sunucumuzla şifreli bağlantı (HTTPS) üzerinden iletilir.

VERİLERİNİZİN SİLİNMESİ
Favori dosyalarınızı istediğiniz zaman "Favorilerim" sekmesinden kaldırabilirsiniz. Bildirim iznini telefonunuzun Ayarlar kısmından her zaman kapatabilirsiniz. Tüm verilerinizin tamamen silinmesini talep etmek için aşağıdaki e-postayla bize ulaşabilirsiniz.

ÇOCUKLAR
Bu uygulama çocuklara yönelik değildir, bilerek 13 yaş altı kullanıcılardan veri toplamaz.

DEĞİŞİKLİKLER
Bu politika güncellenirse, güncel hali her zaman bu sayfada (uygulama içi "Yasal Bilgiler" sekmesi) yer alacaktır.

İLETİŞİM
Sorularınız için: ahmet.knby.25@gmail.com`,
    // Sekme başlıkları
    sekmeAnaSayfa: 'Ana Sayfa',
    sekmeFavorilerim: 'Favorilerim',
    // 2026-08-16: deneysel "adım adım kesin arama" sekmesi -- kullanıcı
    // isteğiyle, ana akıştan tamamen bağımsız bir test olarak eklendi.
    // 2026-08-16: İstatistikler sekmesi.
    sekmeIstatistikler: 'İstatistikler',
    sekmeYasalMetin: 'Yasal Bilgiler',
    istatistikBaslik: 'İstatistikler',
    istatistikKisiselBaslik: 'Yılınıza Göre Durumunuz',
    istatistikKisiselAciklama: 'Dosya numaranızı ve başvuru yılınızı girin -- o yıl kaç başvuru kabul edildi, kaçı onaylandı ve dosyanız (onaylanmadıysa) bekleyenler arasında tahmini kaçıncı sırada, görün.',
    istatistikKisiselEksikAlan: 'Lütfen hem dosya numarası hem yıl girin.',
    istatistikGoruntuleButon: 'Görüntüle',
    istatistikKisiselBulunamadi: '{yil} yılı için sistemde bu numarayla eşleşen bir stadiu kaydı bulunamadı.',
    istatistikKisiselOnaylanmis: 'Tebrikler! {yil} yılı başvurunuz zaten ONAYLANMIŞ (ordine) durumda.',
    istatistikKisiselBekliyor: '{yil} yılı için, henüz onaylanmamış {toplam} başvuru arasında dosyanız tahmini {sira}. sırada. Sizden sonra {kalan} başvuru daha var.',
    istatistikSiraUyarisi: 'Bu sıralama resmi bir kuyruk numarası DEĞİLDİR -- dosya numaralarının kayıt sırasına göre verildiği varsayımıyla yapılan bir tahmindir.',
    istatistikMaddeSeciniz: 'Lütfen maddenizi seçin.',
    istatistikTumZamanlar: 'Tüm yıllar dahil: dosyanız {toplam} bekleyen arasında tahmini {sira}. sırada.',
    istatistikSon7GunBaslik: 'Son 7 Gün',
    istatistikSon7GunMetin: 'Son 7 günde {pdf} PDF tarandı, {yeni} yeni kayıt eklendi.',
    istatistikYakinKomsuBaslik: '🎯 En yakın onaylanmış numaralar',
    istatistikYakinKomsuAciklama: 'Aynı yılda, size en yakın numaradan önce ve sonra onaylanmış dosyalar (yayın tarihi bilgisi elimizde olmadığı için sadece numara farkı gösteriliyor).',
    istatistikYakinKomsuAlt: 'Önce: {no} numara ({fark} numara önünüzde)',
    istatistikYakinKomsuUst: 'Sonra: {no} numara ({fark} numara arkanızda)',
    istatistikYakinKomsuYok: 'Bu yılda henüz bu yönde onaylanmış bir numara yok.',
    istatistikToplamKabul: 'Toplam kabul (stadiu):',
    istatistikToplamOnay: 'Toplam onay (ordine):',
    istatistikToplamBekleyen: 'Onay bekleyen:',
    istatistikGenelBaslik: 'Genel Sistem İstatistiği',
    istatistikGenelAciklama: 'Sistemde kayıtlı tüm dosya numaralarına göre, güncel toplam kabul/onay/bekleyen durumu.',
    istatistikYillikGrafikBaslik: 'Yıllara Göre Dağılım',
    istatistikGenelDipnot: 'Bu istatistikler, cetatenie.just.ro sitesinde yayınlanan resmi PDF listelerinden otomatik hesaplanmıştır -- resmi bir kaynak değildir, sadece bilgilendirme amaçlıdır. Yeni PDF eklendikçe düzenli olarak güncellenir.',
    // Sorgu geçmişi (ana ekran)
    gecmisBaslik: 'Son Aramalar',
    gecmisTemizle: 'Temizle',
    // Favorilere ekle/çıkar (sonuç kartı + Favorilerim ekranı)
    favoriEkleButon: '☆ Favorilere Ekle',
    favoridekiButon: '★ Favorilerde',
    favoriEklendiMesaji: 'Favorilere eklendi. Durum değiştiğinde Favorilerim sekmesinden takip edebilirsiniz.',
    // Favorilerim ekranı
    favorilerimAciklama: 'Favorilere eklediğiniz dosya numaralarının güncel durumu.',
    favorilerimBosBaslik: 'Henüz favori dosyanız yok',
    favorilerimBosMetin: 'Ana ekranda bir sonucu "Favorilere Ekle" ile buraya kaydedebilirsiniz.',
    favorilerimYukleniyor: 'Favoriler yükleniyor...',
    favorilerimHata: 'Favoriler yüklenemedi. Sunucuya bağlanılamadı.',
    favoridenCikarButon: 'Çıkar',
    favorilerimYenile: 'Yenile',
    favorilerimHenuzSonucYok: 'Bu numara için henüz kayıtlı bir sonuç yok, taranmaya devam ediliyor.',
    // 2026-08-18 EKLENTİSİ (kullanıcı isteği): Ana Sayfa'daki bilgi (i)
    // ikonuyla açılan "Özellikler" sayfası -- uygulamanın kullanıcılara
    // sunduğu hizmetleri tek bir yerde özetler, kullanıcı Play Store'da
    // görmese bile uygulama içinden tüm özellikleri keşfedebilsin diye.
    ozelliklerBaslik: 'Uygulama Özellikleri',
    ozelliklerAciklama: 'Romanya Dosya Takip, vatandaşlık başvuru sürecinizi kolaylaştırmak için şu hizmetleri sunar:',
    ozellikler: [
      { ikon: '🔍', baslik: 'Anında Sorgulama', aciklama: 'Dosya numaranızı girin, Stadiu Dosar ve Ordine kategorilerinde saniyeler içinde güncel durumunuzu görün.' },
      { ikon: '🔔', baslik: 'Otomatik Bildirim', aciklama: 'Favorilere eklemeseniz bile, sorguladığınız bir dosya numarası onaylandığında size otomatik bildirim gönderilir.' },
      { ikon: '⭐', baslik: 'Favorilerim', aciklama: 'Takip etmek istediğiniz dosya numaralarını favorilere ekleyin, tek ekrandan hepsinin güncel durumunu görün.' },
      { ikon: '📊', baslik: 'İstatistikler', aciklama: 'Sıranızdaki tahmini yerinizi görün, genel başvuru istatistiklerini ve yıllara göre dağılımı inceleyin.' },
      { ikon: '📄', baslik: 'Resmi Belge Görüntüleme', aciklama: 'Sistemin sizin için bulduğu resmi PDF belgesini uygulamadan doğrudan açıp inceleyin.' },
      { ikon: '🌐', baslik: '3 Dil Desteği', aciklama: 'Türkçe, İngilizce ve Romence arasında anında geçiş yapın.' },
      { ikon: '🔒', baslik: 'Gizlilik Odaklı', aciklama: 'Ad, TC/CNP kimlik numarası, adres gibi hiçbir kişisel bilginiz istenmez ya da saklanmaz.' },
      { ikon: '💳', baslik: 'Tek Seferlik Satın Alma', aciklama: 'Satın aldığınız uygulamayı, aynı Google hesabıyla istediğiniz kadar cihaza ücretsiz olarak tekrar yükleyebilirsiniz -- telefon değiştirseniz, kaybetseniz ya da bozulsa bile tekrar ödeme yapmanız gerekmez.' },
    ],
  },
  en: {
    appAdi: 'Romania File Tracker',
    appSlogan: 'Detailed Citizenship & Status Lookup',
    dosyaNoEtiket: 'File Number *',
    dosyaNoOrnek: 'e.g. 12345',
    yilEtiket: 'Year',
    yilOrnek: 'e.g. 2023',
    anaKategoriEtiket: 'Main Category',
    altKategoriEtiket: 'Sub-category',
    sorgulaButon: 'Search',
    hataBosNumara: 'Please enter a file number.',
    hataBaglanti: 'Could not connect to the server. Please check your internet connection.',
    sonucBaslik: 'Search Results',
    durumEtiketOnEki: 'Status:',
    resmiBelgeButon: '🔗 View on Official Website',
    yerelBelgeButon: '📄 View Downloaded PDF',
    yerelBelgeAciklama: 'This is an exact copy of the PDF our system downloaded from the official site, containing your file number.',
    altUyari: 'These results are for informational purposes only. Please check the official document/source for final and binding information.',
    footerImza: '🔒 Secured & Encrypted System · By @knby · © 2026',
    sonucBulunamadi: 'No record matching this number was found.',
    sonucBaskaKategoride: 'This number exists in the system, but not in the category you selected. It was found under: {kategori}',
    kategoriUyariBaslik: 'Wrong Category Selected',
    kategoriUyariMetin: 'Your file number exists in the system under {kategori}. Please select that category and search again.',
    kategoriUyariUygula: 'Search again with this category',
    kategoriUyariTamam: 'OK',
    siteServisDisiBanner: 'The official cetatenie.just.ro website is currently down.',
    siteServisDisiEkAciklama: 'Your search will run against our database, last updated on {tarih}.',
    sonucMesaji: {
      stadiu: 'Your citizenship application file has been accepted into the system as Stage 1. To track the approval status (Stage 2) of your application, you can search again by selecting the ORDINE category.',
      ordine: 'Congratulations! Your citizenship application has been approved.',
    },
    durumRozeti: {
      stadiu: 'IN PROGRESS',
      ordine: 'APPROVED',
    },
    durumBulunamadi: 'NOT FOUND',
    cokluSonucUyarisi: 'Your number matched multiple results because file numbers can be reused in different years. To find the exact result, please enter the main category, sub-category and year information you were given at the time of your application in the fields above, then search again.',
    dogruSonucIpucu: 'For the most accurate result, we recommend entering the main category, sub-category and year information you were given at the time of your application above.',
    sonucHenuzOrdineGecmedi: 'Your file number is currently published under STADIU (Stage 1). It has not yet been published under ORDINE (Stage 2 - approval).',
    sonucZatenOrdineGecti: 'Good news: your file number has now moved to ORDINE (Stage 2 - approval). You can search again by selecting the ORDINE category to see your current status.',
    disclaimerBaslik: 'Important Notice',
    disclaimerButon: 'I Have Read and Understood, Continue',
    disclaimerMetin: `This application is not an official Romanian government body and has no affiliation with the Romanian Ministry of Internal Affairs, any Consulate, or the Autoritatea Națională pentru Cetățenie (ANC — National Citizenship Authority).

The app automatically scans the PDF lists publicly published at cetatenie.just.ro (the Stadiu Dosar and Ordine pages) and provides a file-number search for your convenience.

The only official and binding source is the official website of the Romanian authorities. The developer cannot be held responsible for delays, missing/incorrect data display, or technical issues originating from this app.

To avoid any loss of rights, you are also advised to follow consulate announcements yourself. By using this app, you are deemed to accept these terms.`,
    gizlilikBaslik: 'Privacy Policy',
    gizlilikMetin: `Last updated: August 17, 2026

DATA WE COLLECT
This app collects a limited amount of technical data in order to send you notifications and remember your favorite files:
• A notification identifier (Expo/Apple/Google push token) -- only collected if you grant notification permission.
• A random, anonymous identifier generated for your device (does NOT contain your name or phone number).
• The file numbers and years you add to your favorites.
• The file number/year/category you enter when searching (sent to our server to look up the result).
• When you search for a file number that has not yet been approved, it is also automatically recorded in the background -- even if you do not add it to favorites -- so we can notify you once it is approved.

WHAT WE DO NOT COLLECT
We never ask for or collect your name, surname, email address, phone number, national ID number, location, camera/microphone access, or contacts.

WHY WE USE THIS DATA
• To notify you when your file's status changes (e.g. when it is approved).
• To remember your favorites list.
• To correctly return your search results.

SHARING WITH THIRD PARTIES
To deliver notifications to your phone, your notification identifier is shared with Expo's push notification infrastructure (and, through it, with Apple's and Google's own notification services). Beyond this, your data is never shared with or sold to any advertising, analytics, or marketing company.

ABOUT THE SOURCE DATA
The file status information shown in the app is automatically compiled from PDF lists publicly published on the official website of the Romanian authorities, cetatenie.just.ro -- this data is already public.

SECURITY
Data is transmitted to our server over an encrypted (HTTPS) connection.

DELETING YOUR DATA
You can remove your favorite files at any time from the "Favorites" tab. You can disable notification permission at any time from your phone's Settings. To request complete deletion of all your data, contact us at the email address below.

CHILDREN
This app is not directed at children and does not knowingly collect data from users under 13.

CHANGES
If this policy is updated, the current version will always be available here (in the in-app "Legal Information" tab).

CONTACT
For questions: ahmet.knby.25@gmail.com`,
    sekmeAnaSayfa: 'Home',
    sekmeFavorilerim: 'Favorites',
    sekmeIstatistikler: 'Statistics',
    sekmeYasalMetin: 'Legal Information',
    istatistikBaslik: 'Statistics',
    istatistikKisiselBaslik: 'Your Status by Year',
    istatistikKisiselAciklama: 'Enter your file number and application year -- see how many applications were accepted that year, how many were approved, and (if not yet approved) your estimated position among those still waiting.',
    istatistikKisiselEksikAlan: 'Please enter both a file number and a year.',
    istatistikGoruntuleButon: 'View',
    istatistikKisiselBulunamadi: 'No stadiu record matching this number was found in the system for {yil}.',
    istatistikKisiselOnaylanmis: 'Congratulations! Your {yil} application has already been APPROVED (ordine).',
    istatistikKisiselBekliyor: 'For {yil}, your file is estimated to be in position {sira} among {toplam} not-yet-approved applications. There are {kalan} more applications after you.',
    istatistikSiraUyarisi: 'This ranking is NOT an official queue number -- it is an estimate based on the assumption that file numbers are issued in registration order.',
    istatistikMaddeSeciniz: 'Please select your sub-category.',
    istatistikTumZamanlar: 'Across all years: your file is estimated to be in position {sira} among {toplam} waiting.',
    istatistikSon7GunBaslik: 'Last 7 Days',
    istatistikSon7GunMetin: '{pdf} PDFs scanned, {yeni} new records added in the last 7 days.',
    istatistikYakinKomsuBaslik: '🎯 Nearest approved numbers',
    istatistikYakinKomsuAciklama: 'Files approved just before and after your number, same year (we only show the number gap, not the publish date, since we don\'t have that data).',
    istatistikYakinKomsuAlt: 'Before: number {no} ({fark} numbers ahead of you)',
    istatistikYakinKomsuUst: 'After: number {no} ({fark} numbers behind you)',
    istatistikYakinKomsuYok: 'No approved number in this direction yet for this year.',
    istatistikToplamKabul: 'Total accepted (stadiu):',
    istatistikToplamOnay: 'Total approved (ordine):',
    istatistikToplamBekleyen: 'Awaiting approval:',
    istatistikGenelBaslik: 'Overall System Statistics',
    istatistikGenelAciklama: 'Current totals of accepted/approved/pending files based on all file numbers recorded in the system.',
    istatistikYillikGrafikBaslik: 'Breakdown by Year',
    istatistikGenelDipnot: 'These statistics are automatically calculated from the official PDF lists published on cetatenie.just.ro -- they are not an official source and are for informational purposes only. Updated regularly as new PDFs are added.',
    gecmisBaslik: 'Recent Searches',
    gecmisTemizle: 'Clear',
    favoriEkleButon: '☆ Add to Favorites',
    favoridekiButon: '★ In Favorites',
    favoriEklendiMesaji: 'Added to favorites. You can track status changes from the Favorites tab.',
    favorilerimAciklama: 'Current status of the file numbers you added to favorites.',
    favorilerimBosBaslik: 'No favorites yet',
    favorilerimBosMetin: 'You can save a result to this list using "Add to Favorites" on the home screen.',
    favorilerimYukleniyor: 'Loading favorites...',
    favorilerimHata: 'Could not load favorites. Could not connect to the server.',
    favoridenCikarButon: 'Remove',
    favorilerimYenile: 'Refresh',
    favorilerimHenuzSonucYok: 'No record for this number yet, scanning continues.',
    ozelliklerBaslik: 'App Features',
    ozelliklerAciklama: 'Romania File Tracker offers the following services to make your citizenship application process easier:',
    ozellikler: [
      { ikon: '🔍', baslik: 'Instant Search', aciklama: 'Enter your file number and see your current status in the Stadiu Dosar and Ordine categories within seconds.' },
      { ikon: '🔔', baslik: 'Automatic Notifications', aciklama: 'Even without adding it to favorites, you get notified automatically when a file number you searched for gets approved.' },
      { ikon: '⭐', baslik: 'My Favorites', aciklama: 'Add the file numbers you want to track to favorites and see their current status all on one screen.' },
      { ikon: '📊', baslik: 'Statistics', aciklama: 'See your estimated position in the queue and review overall application statistics and the yearly breakdown.' },
      { ikon: '📄', baslik: 'Official Document Viewer', aciklama: 'Open and review the official PDF document the system found for you, directly within the app.' },
      { ikon: '🌐', baslik: '3 Language Support', aciklama: 'Switch instantly between Turkish, English, and Romanian.' },
      { ikon: '🔒', baslik: 'Privacy-Focused', aciklama: 'No personal information such as your name, national ID number, or address is ever requested or stored.' },
      { ikon: '💳', baslik: 'One-Time Purchase', aciklama: 'You can reinstall the app you purchased for free on as many devices as you like, as long as you sign in with the same Google account -- no need to pay again if you change, lose, or break your phone.' },
    ],
  },
  ro: {
    appAdi: 'Urmărire Dosar România',
    appSlogan: 'Interogare Detaliată Cetățenie și Stadiu',
    dosyaNoEtiket: 'Număr Dosar *',
    dosyaNoOrnek: 'ex: 12345',
    yilEtiket: 'An',
    yilOrnek: 'ex: 2023',
    anaKategoriEtiket: 'Categorie Principală',
    altKategoriEtiket: 'Subcategorie',
    sorgulaButon: 'Caută',
    hataBosNumara: 'Vă rugăm introduceți un număr de dosar.',
    hataBaglanti: 'Nu s-a putut conecta la server. Verificați conexiunea la internet.',
    sonucBaslik: 'Rezultatele Căutării',
    durumEtiketOnEki: 'Stadiu:',
    resmiBelgeButon: '🔗 Vizualizați pe Site-ul Oficial',
    yerelBelgeButon: '📄 Vizualizați PDF-ul Descărcat',
    yerelBelgeAciklama: 'Aceasta este o copie exactă a PDF-ului descărcat de sistemul nostru de pe site-ul oficial, care conține numărul dumneavoastră de dosar.',
    altUyari: 'Aceste rezultate au caracter informativ. Pentru informații finale și obligatorii, vă rugăm consultați documentul/sursa oficială.',
    // Bilinçli olarak çevrilmiyor: marka/güvenlik imzası, dil ne olursa
    // olsun İngilizce kalması isteniyor (kullanıcı talebi).
    footerImza: '🔒 Secured & Encrypted System · By @knby · © 2026',
    sonucBulunamadi: 'Nu a fost găsită nicio înregistrare care să corespundă acestui număr.',
    sonucBaskaKategoride: 'Acest număr există în sistem, dar nu în categoria selectată. A fost găsit la: {kategori}',
    kategoriUyariBaslik: 'Categorie Greșită Selectată',
    kategoriUyariMetin: 'Numărul dvs. de dosar există în sistem la categoria {kategori}. Vă rugăm selectați categoria respectivă și căutați din nou.',
    kategoriUyariUygula: 'Caută din nou cu această categorie',
    kategoriUyariTamam: 'OK',
    siteServisDisiBanner: 'Site-ul oficial cetatenie.just.ro este momentan indisponibil.',
    siteServisDisiEkAciklama: 'Căutarea dvs. va folosi baza noastră de date, actualizată ultima dată la {tarih}.',
    sonucMesaji: {
      stadiu: 'Dosarul cererii dvs. de cetățenie a fost acceptat în sistem ca Etapa 1. Pentru a urmări starea de aprobare (Etapa 2) a cererii dvs., puteți căuta din nou selectând categoria ORDINE.',
      ordine: 'Felicitări! Cererea dumneavoastră de cetățenie a fost aprobată.',
    },
    durumRozeti: {
      stadiu: 'ÎN CURS',
      ordine: 'APROBAT',
    },
    durumBulunamadi: 'NEGĂSIT',
    cokluSonucUyarisi: 'Numărul dvs. a găsit mai multe rezultate deoarece numerele de dosar pot fi reutilizate în ani diferiți. Pentru a găsi rezultatul exact, introduceți categoria principală, subcategoria și anul care v-au fost furnizate la momentul depunerii cererii în câmpurile de mai sus și căutați din nou.',
    dogruSonucIpucu: 'Pentru cel mai exact rezultat, vă recomandăm să introduceți mai sus categoria principală, subcategoria și anul care v-au fost furnizate la momentul depunerii cererii.',
    sonucHenuzOrdineGecmedi: 'Numărul dvs. de dosar este momentan publicat la STADIU (Etapa 1). Nu a fost încă publicat la ORDINE (Etapa 2 - aprobare).',
    sonucZatenOrdineGecti: 'Vești bune: numărul dvs. de dosar a trecut acum la ORDINE (Etapa 2 - aprobare). Puteți căuta din nou selectând categoria ORDINE pentru a vedea starea actuală.',
    disclaimerBaslik: 'Notificare Importantă',
    disclaimerButon: 'Am Citit și Am Înțeles, Continuă',
    disclaimerMetin: `Această aplicație nu este o instituție oficială a statului român și nu are nicio legătură cu Ministerul de Interne al României, vreun Consulat sau Autoritatea Națională pentru Cetățenie (ANC).

Aplicația scanează automat listele PDF publicate public pe cetatenie.just.ro (paginile Stadiu Dosar și Ordine) și oferă o căutare după numărul dosarului, pentru confortul dumneavoastră.

Singura sursă oficială și obligatorie este site-ul web oficial al autorităților române. Dezvoltatorul nu poate fi tras la răspundere pentru întârzieri, afișarea unor date lipsă/incorecte sau probleme tehnice provenite din aplicație.

Pentru a evita pierderea unor drepturi, vă recomandăm să urmăriți personal și anunțurile consulatului. Prin utilizarea aplicației, se consideră că acceptați acești termeni.`,
    gizlilikBaslik: 'Politica de Confidențialitate',
    gizlilikMetin: `Ultima actualizare: 17 august 2026

DATE PE CARE LE COLECTĂM
Această aplicație colectează o cantitate limitată de date tehnice pentru a vă putea trimite notificări și a vă reține fișierele favorite:
• Un identificator de notificare (token push Expo/Apple/Google) -- colectat doar dacă acordați permisiunea de notificare.
• Un identificator anonim, generat aleatoriu pentru dispozitivul dvs. (NU conține numele sau numărul dvs. de telefon).
• Numerele de dosar și anii pe care le adăugați la favorite.
• Numărul de dosar/anul/categoria pe care le introduceți la căutare (trimise serverului nostru pentru a găsi rezultatul).
• Atunci când căutați un număr de dosar care nu a fost încă aprobat, acesta este înregistrat automat și în fundal -- chiar dacă nu îl adăugați la favorite -- pentru a vă putea notifica odată ce este aprobat.

CE NU COLECTĂM
Nu vă cerem și nu colectăm niciodată numele, prenumele, adresa de e-mail, numărul de telefon, codul numeric personal (CNP), locația, accesul la cameră/microfon sau contactele dvs.

DE CE FOLOSIM ACESTE DATE
• Pentru a vă notifica atunci când starea dosarului dvs. se schimbă (de exemplu, când este aprobat).
• Pentru a reține lista dvs. de favorite.
• Pentru a returna corect rezultatele căutării dvs.

PARTAJARE CU TERȚI
Pentru ca notificările să ajungă la telefonul dvs., identificatorul dvs. de notificare este partajat cu infrastructura de notificări push Expo (și, prin aceasta, cu propriile servicii de notificare ale Apple și Google). În afară de aceasta, datele dvs. nu sunt niciodată partajate cu sau vândute către vreo companie de publicitate, analiză sau marketing.

DESPRE SURSA DATELOR
Informațiile despre starea dosarului afișate în aplicație sunt compilate automat din listele PDF publicate public pe site-ul oficial al autorităților române, cetatenie.just.ro -- aceste date sunt deja publice.

SECURITATE
Datele sunt transmise către serverul nostru printr-o conexiune criptată (HTTPS).

ȘTERGEREA DATELOR DVS.
Puteți elimina fișierele favorite oricând din fila "Favorite". Puteți dezactiva permisiunea de notificare oricând din Setările telefonului dvs. Pentru a solicita ștergerea completă a tuturor datelor dvs., contactați-ne la adresa de e-mail de mai jos.

COPII
Această aplicație nu se adresează copiilor și nu colectează cu bună știință date de la utilizatori sub 13 ani.

MODIFICĂRI
Dacă această politică este actualizată, versiunea curentă va fi întotdeauna disponibilă aici (în fila din aplicație "Informații Legale").

CONTACT
Pentru întrebări: ahmet.knby.25@gmail.com`,
    sekmeAnaSayfa: 'Acasă',
    sekmeFavorilerim: 'Favorite',
    sekmeIstatistikler: 'Statistici',
    sekmeYasalMetin: 'Informații Legale',
    istatistikBaslik: 'Statistici',
    istatistikKisiselBaslik: 'Starea Dvs. pe An',
    istatistikKisiselAciklama: 'Introduceți numărul de dosar și anul cererii -- vedeți câte cereri au fost acceptate în acel an, câte au fost aprobate și (dacă nu a fost încă aprobată) poziția estimată a dosarului dvs. printre cele care așteaptă.',
    istatistikKisiselEksikAlan: 'Vă rugăm introduceți atât numărul de dosar, cât și anul.',
    istatistikGoruntuleButon: 'Vizualizează',
    istatistikKisiselBulunamadi: 'Nu a fost găsită nicio înregistrare stadiu care să corespundă acestui număr pentru {yil}.',
    istatistikKisiselOnaylanmis: 'Felicitări! Cererea dvs. din {yil} a fost deja APROBATĂ (ordine).',
    istatistikKisiselBekliyor: 'Pentru {yil}, dosarul dvs. se estimează a fi pe poziția {sira} din {toplam} cereri neaprobate încă. Mai sunt {kalan} cereri după dvs.',
    istatistikSiraUyarisi: 'Această clasificare NU este un număr oficial de coadă -- este o estimare bazată pe presupunerea că numerele de dosar sunt emise în ordinea înregistrării.',
    istatistikMaddeSeciniz: 'Vă rugăm selectați subcategoria dvs.',
    istatistikTumZamanlar: 'Toți anii incluși: dosarul dvs. este estimat pe poziția {sira} din {toplam} în așteptare.',
    istatistikSon7GunBaslik: 'Ultimele 7 Zile',
    istatistikSon7GunMetin: '{pdf} PDF-uri scanate, {yeni} înregistrări noi adăugate în ultimele 7 zile.',
    istatistikYakinKomsuBaslik: '🎯 Cele mai apropiate numere aprobate',
    istatistikYakinKomsuAciklama: 'Dosare aprobate imediat înainte și după numărul dvs., același an (arătăm doar diferența de număr, nu data publicării, deoarece nu avem această informație).',
    istatistikYakinKomsuAlt: 'Înainte: numărul {no} ({fark} numere înaintea dvs.)',
    istatistikYakinKomsuUst: 'După: numărul {no} ({fark} numere după dvs.)',
    istatistikYakinKomsuYok: 'Niciun număr aprobat în această direcție încă pentru acest an.',
    istatistikToplamKabul: 'Total acceptate (stadiu):',
    istatistikToplamOnay: 'Total aprobate (ordine):',
    istatistikToplamBekleyen: 'În așteptarea aprobării:',
    istatistikGenelBaslik: 'Statistici Generale ale Sistemului',
    istatistikGenelAciklama: 'Totalurile actuale ale dosarelor acceptate/aprobate/în așteptare, pe baza tuturor numerelor de dosar înregistrate în sistem.',
    istatistikYillikGrafikBaslik: 'Distribuție pe Ani',
    istatistikGenelDipnot: 'Aceste statistici sunt calculate automat din listele PDF oficiale publicate pe cetatenie.just.ro -- nu reprezintă o sursă oficială și au doar scop informativ. Se actualizează periodic pe măsură ce sunt adăugate noi PDF-uri.',
    gecmisBaslik: 'Căutări Recente',
    gecmisTemizle: 'Șterge',
    favoriEkleButon: '☆ Adaugă la Favorite',
    favoridekiButon: '★ În Favorite',
    favoriEklendiMesaji: 'Adăugat la favorite. Puteți urmări schimbările de stadiu din secțiunea Favorite.',
    favorilerimAciklama: 'Stadiul actual al numerelor de dosar adăugate la favorite.',
    favorilerimBosBaslik: 'Niciun favorit încă',
    favorilerimBosMetin: 'Puteți salva un rezultat aici folosind "Adaugă la Favorite" pe ecranul principal.',
    favorilerimYukleniyor: 'Se încarcă favoritele...',
    favorilerimHata: 'Favoritele nu au putut fi încărcate. Nu s-a putut conecta la server.',
    favoridenCikarButon: 'Elimină',
    favorilerimYenile: 'Reîmprospătează',
    favorilerimHenuzSonucYok: 'Nu există încă o înregistrare pentru acest număr, scanarea continuă.',
    ozelliklerBaslik: 'Funcțiile Aplicației',
    ozelliklerAciklama: 'Romanya Dosya Takip oferă următoarele servicii pentru a vă simplifica procesul de cerere de cetățenie:',
    ozellikler: [
      { ikon: '🔍', baslik: 'Căutare Instantanee', aciklama: 'Introduceți numărul dosarului și vedeți starea actuală în categoriile Stadiu Dosar și Ordine în câteva secunde.' },
      { ikon: '🔔', baslik: 'Notificări Automate', aciklama: 'Chiar dacă nu îl adăugați la favorite, sunteți notificat automat atunci când un număr de dosar căutat este aprobat.' },
      { ikon: '⭐', baslik: 'Favoritele Mele', aciklama: 'Adăugați numerele de dosar pe care doriți să le urmăriți la favorite și vedeți starea lor actuală pe un singur ecran.' },
      { ikon: '📊', baslik: 'Statistici', aciklama: 'Vedeți poziția estimată în coadă și consultați statisticile generale ale cererilor, precum și distribuția pe ani.' },
      { ikon: '📄', baslik: 'Vizualizare Document Oficial', aciklama: 'Deschideți și consultați documentul PDF oficial găsit de sistem pentru dvs., direct din aplicație.' },
      { ikon: '🌐', baslik: 'Suport pentru 3 Limbi', aciklama: 'Comutați instantaneu între turcă, engleză și română.' },
      { ikon: '🔒', baslik: 'Axat pe Confidențialitate', aciklama: 'Nicio informație personală precum numele, CNP-ul sau adresa dvs. nu este niciodată solicitată sau stocată.' },
      { ikon: '💳', baslik: 'Achiziție Unică', aciklama: 'Puteți reinstala gratuit aplicația achiziționată pe oricâte dispozitive doriți, atâta timp cât vă conectați cu același cont Google -- nu trebuie să plătiți din nou dacă vă schimbați, pierdeți sau se strică telefonul.' },
    ],
  },
} as const;

type CeviriSeti = typeof CEVIRILER['tr'];

type DilBaglami = {
  dil: DilKodu;
  dilDegistir: (yeni: DilKodu) => void;
  t: CeviriSeti;
};

const DilContext = createContext<DilBaglami | null>(null);

export function DilProvider({ children }: { children: React.ReactNode }) {
  const [dil, setDil] = useState<DilKodu>('tr');

  useEffect(() => {
    (async () => {
      try {
        const kayitli = await AsyncStorage.getItem(DIL_ANAHTARI);
        if (kayitli === 'tr' || kayitli === 'en' || kayitli === 'ro') {
          setDil(kayitli);
        }
      } catch {
        // Okunamazsa varsayılan (tr) ile devam edilir.
      }
    })();
  }, []);

  const dilDegistir = (yeni: DilKodu) => {
    setDil(yeni);
    AsyncStorage.setItem(DIL_ANAHTARI, yeni).catch(() => {
      // Kaydedilemezse bile mevcut oturumda dil değişikliği geçerli kalır.
    });
  };

  const deger = useMemo(
    // `CEVIRILER[dil]` -- dil bir birleşim (union) tipi olduğu için burada
    // tr/en/ro'nun üç FARKLI literal string tipinin birleşimi çıkıyor;
    // ama `t` alanı `CeviriSeti` (sadece tr'nin literal tipi) bekliyor.
    // Üçü de yapısal olarak (aynı anahtarlar, hepsi string) birebir uyumlu
    // olduğu için burada güvenli bir tip ataması (as) yapılıyor.
    () => ({ dil, dilDegistir, t: CEVIRILER[dil] as CeviriSeti }),
    [dil]
  );

  return <DilContext.Provider value={deger}>{children}</DilContext.Provider>;
}

export function useDil(): DilBaglami {
  const baglam = useContext(DilContext);
  if (!baglam) {
    throw new Error('useDil() yalnızca <DilProvider> içinde kullanılabilir.');
  }
  return baglam;
}
