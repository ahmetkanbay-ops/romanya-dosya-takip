import AsyncStorage from '@react-native-async-storage/async-storage';
import React, { useEffect, useState } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TextInput,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Linking,
  Modal,
} from 'react-native';
// ÖNEMLİ (2026-08-15 düzeltmesi): react-native'in KENDİ SafeAreaView'ı
// SADECE iOS'ta güvenli alan boşluğu ekler -- Android'de hiçbir şey
// yapmaz (düz bir View gibi davranır). Bu yüzden Android'de içerik
// (dil pili, başlık) telefonun durum çubuğu/saat-pil simgeleriyle iç içe
// görünüyordu. react-native-safe-area-context'ten gelen sürüm HER İKİ
// platformda da doğru çalışıyor (proje zaten bu paketi kullanıyor).
import { SafeAreaView } from 'react-native-safe-area-context';
import { BayrakRozeti } from '@/components/flag-mark';
import KonfettiYagmuru from '@/components/confetti';
import LanguageSwitcher from '@/components/language-switcher';
import OzelliklerModal from '@/components/ozellikler-modal';
import SorguSovu, { TOPLAM_SOV_SURESI_MS } from '@/components/sorgu-sovu';
import Yapraklar from '@/components/yapraklar';
import { apiIstek, cihazKimligiGetir } from '@/constants/api';
import { useDil } from '@/constants/i18n';
import { usePushBildirimleri } from '@/hooks/use-push-bildirimleri';

// Alt kategoriler listesi -- BİLEREK çevrilmiyor, cetatenie.just.ro'daki
// resmi başlıklarla birebir aynı kalmalı (bkz. constants/i18n.tsx notu).
// NOT: "NR. DOSAR" ve "CONSULAT / ANC" backend'de TEK kategoriye
// birleştirildi -- sitede aslında tek bir (uzun, alt satıra sarılan)
// sekme başlığıymış, iki ayrı sekme değilmiş. Backend'de site eşleştirmesi
// için sadece "NR. DOSAR" kullanılıyor (bkz. backend/dosya_utils.py notu).
const STADIU_ALT_KATEGORILERI = [
  "ARTICOLUL 11", "ARTICOLUL 8", "ARTICOLUL 8″1", "ARTICOLUL 8″2",
  "ARTICOLUL 10", "NR. DOSAR",
  "REZULTATE INTERVIU ART. 8", "INVITATII INTERVIU ART. 8",
  "REZULTATE INTERVIU ART. 8.1", "INVITATII INTERVIU ART. 8.1"
];
const ORDINE_ALT_KATEGORILERI = [
  "Ordine articolul 11", "Ordine articolul 8", "Ordine articolul 8”1",
  "Ordine articolul 10", "Ordine articolul 27", "Ordine minori"
];

// Sonuç durum tipi: onay (✅ ordine eşleşti), islemde (⏳ stadiu eşleşti),
// bulunamadi (⚪ eşleşme yok). Görsel (ikon + kurdele rengi) buna göre seçilir.
type DurumTipi = 'onay' | 'islemde' | 'bulunamadi';

function durumTipiGetir(item: any): DurumTipi {
  if (item.eslesti && item.ana_kategori === 'ordine') return 'onay';
  if (item.eslesti && item.ana_kategori === 'stadiu') return 'islemde';
  return 'bulunamadi';
}

// 2026-08-15: "servis dışı" banner'ı kaygı verici durabildiği için, backend
// /api/durum'un döndürdüğü son başarılı tarama zaman damgasını okunaklı bir
// Türkçe tarihe çeviriyoruz -- "verileriniz en son X'te güncellendi" ek
// metni için (bkz. banner JSX'i). Ham ISO metni ayrıştırılamazsa null
// döner, bu durumda ek metin hiç gösterilmez.
function sonGuncellemeMetniOlustur(isoTarih: string | null): string | null {
  if (!isoTarih) return null;
  const tarih = new Date(isoTarih);
  if (isNaN(tarih.getTime())) return null;
  const gun = tarih.toLocaleDateString('tr-TR', { day: 'numeric', month: 'long', year: 'numeric' });
  const saat = tarih.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
  return `${gun}, ${saat}`;
}

const DURUM_IKONU: Record<DurumTipi, string> = {
  onay: '✅',
  islemde: '⏳',
  bulunamadi: '⚪',
};

export default function IndexScreen() {
  const { t } = useDil();
  // Ana ekrana ulaşan kullanıcıdan (yani sorumluluk reddini zaten kabul
  // etmiş) bildirim izni ister + verilirse gerçek push token'ı kaydeder
  // (bkz. hooks/use-push-bildirimleri.ts).
  usePushBildirimleri();
  const [dosyaNo, setDosyaNo] = useState('');
  const [yil, setYil] = useState('');
  const [anaKategori, setAnaKategori] = useState<'stadiu' | 'ordine' | null>(null);
  const [altKategori, setAltKategori] = useState<string | null>(null);

  const [loading, setLoading] = useState(false);
  // 2026-08-16: "Sorgula" şovu -- bkz. sorgulaYap ve SorguSovu bileşeni notu.
  const [sovGoster, setSovGoster] = useState(false);
  const [sonuclar, setSonuclar] = useState<any[] | null>(null);
  const [hata, setHata] = useState('');
  const [servisDisiMi, setServisDisiMi] = useState(false);
  const [sonGuncelleme, setSonGuncelleme] = useState<string | null>(null);
  const [konfetiGoster, setKonfetiGoster] = useState(false);
  const [konfetiAnahtari, setKonfetiAnahtari] = useState(0);
  // 2026-08-18 EKLENTİSİ (kullanıcı isteği: "kullanıcılar uygulamanın
  // bütün özelliklerini bilmeleri çok güzel olur") -- Ana Sayfa'daki
  // bilgi (i) ikonuyla açılan "Özellikler" sayfasının görünürlüğü.
  const [ozelliklerGoster, setOzelliklerGoster] = useState(false);
  // 2026-08-16 (kullanıcı testinde bulunan tasarım hatası düzeltmesi):
  // önceden TEK bir global "Favorilere Ekle" butonu vardı ve sadece arama
  // kutusundaki HAM metni gönderiyordu -- birden fazla sonuç kartı varsa
  // (numara farklı yıllarda tekrar kullanılmışsa) hangi SPESİFİK kaydın
  // favorilendiği hiç kaydedilmiyordu. Artık her kart KENDİ favori
  // butonuna sahip ve o kartın gerçek dosya_no+yıl'ını gönderiyor. Set'ler
  // "dosya_no|yil" anahtarıyla hangi kartların favori/işlemde olduğunu
  // tutuyor (yeni bir arama başlayınca sıfırlanır -- backend'de "zaten
  // favoride mi" diye ayrıca bir sorgu yok, bu önceki tekli-buton
  // davranışıyla da aynıydı).
  const [favoriAnahtarlari, setFavoriAnahtarlari] = useState<Set<string>>(new Set());
  const [favoriIslemdeAnahtarlari, setFavoriIslemdeAnahtarlari] = useState<Set<string>>(new Set());

  // 2026-08-16: kullanıcı YANLIŞ bir alt kategori VE/VEYA yıl girip
  // aradığında (dosya numarası gerçekte BAŞKA bir kategoride/yılda varsa),
  // backend bunu "baska_kategoride_bulundu" alanında bildiriyor. Bu durumda
  // kullanıcının gözden kaçırmaması için tam ekran, dikkat çekici bir uyarı
  // gösteriyoruz (bkz. aşağıdaki Modal). null = uyarı kapalı, dolu dizi =
  // uyarı açık ve dosyanın GERÇEK kategorisi/yılı bu dizide.
  const [kategoriUyarisi, setKategoriUyarisi] = useState<
    { ana_kategori: string; alt_kategori: string; yil: string | null }[] | null
  >(null);
  const aktifAltKategoriler = anaKategori === 'stadiu' ? STADIU_ALT_KATEGORILERI :
                             anaKategori === 'ordine' ? ORDINE_ALT_KATEGORILERI : [];

  // Ana ekran açıldığında resmi kaynağın anlık erişilebilirliğini kontrol
  // eder (bkz. backend /api/durum). Sadece mesai saatleri içindeki gerçek
  // kesintilerde banner gösterilir -- mesai dışı olası bakım kesintileri
  // için backend zaten "servis_disi: false" döndürür, burada ek bir kontrol
  // gerekmez. Bu kontrol sessizce başarısız olabilir (ör. sunucuya hiç
  // ulaşılamıyorsa) -- ana sorgulama işlevini etkilemesin diye hata
  // durumunda banner basitçe gösterilmez.
  useEffect(() => {
    let iptal = false;
    apiIstek('/api/durum')
      .then((r) => r.json())
      .then((veri) => {
        if (!iptal) {
          setServisDisiMi(Boolean(veri?.servis_disi));
          setSonGuncelleme(typeof veri?.son_guncelleme === 'string' ? veri.son_guncelleme : null);
        }
      })
      .catch(() => {
        // Sessizce yok say -- bu sadece bilgilendirici bir banner.
      });
    return () => {
      iptal = true;
    };
  }, []);

  // `override` -- kategori uyarısı modalındaki "Bu kategoriyle sorgula"
  // butonu için: state güncellemeleri (setAnaKategori/setAltKategori) React
  // içinde asenkron/batch işlendiğinden, aynı fonksiyon içinde hemen ardından
  // eski (güncellenmemiş) state ile arama yapılırdı. Bunun yerine yeni
  // değerler doğrudan parametre olarak geçiliyor.
  const sorgulaYap = async (
    dosyaNoDegeri: string,
    override?: { ana_kategori: string | null; alt_kategori: string | null; yil: string | null }
  ) => {
    if (!dosyaNoDegeri.trim()) {
      setHata(t.hataBosNumara);
      return;
    }
    const kullanilacakAnaKategori = override ? override.ana_kategori : anaKategori;
    const kullanilacakAltKategori = override ? override.alt_kategori : altKategori;
    const kullanilacakYil = override ? override.yil : (yil.trim() || null);
    setHata('');
    setLoading(true);
    // 2026-08-16 (kullanıcı isteği): "Sorgula"ya basınca ~5 saniyelik bir
    // görsel şov oynatılır -- "dosya taraması yapılıyor" hissi versin diye.
    // Süre burada DEĞİL, aşağıdaki finally bloğunda yönetiliyor: gerçek API
    // isteği ile 5sn'lik minimum süre PARALEL bekleniyor, ikisinden hangisi
    // uzun sürerse o kadar gösteriliyor (kullanıcı asla yarıda kesilmiş bir
    // şov görmez, ama API çok hızlı dönse bile şov en az 5sn oynar).
    setSovGoster(true);
    const sovBaslangicZamani = Date.now();
    setSonuclar(null);
    setFavoriAnahtarlari(new Set());
    setKategoriUyarisi(null);
    // 2026-08-17 düzeltmesi: konfeti tetikleme kararı try bloğunda veriliyor
    // ama GÖRSEL OLARAK başlatma işlemi finally'e, yani SorguSovu tam
    // kapandıktan sonraya taşındı (bkz. asagidaki not).
    let onayVarMi = false;
    try {
      // 2026-08-17 EKLENTİSİ (kullanıcı isteği): favori eklemek artık
      // bildirim almanın ŞARTI değil -- cihaz kimliği her sorguyla
      // birlikte gönderiliyor, backend eşleşen/henüz onaylanmamış
      // sonuçlar için sessizce arka planda bir izleme kaydı oluşturuyor
      // (bkz. backend main.py _otomatik_izlemeye_al).
      const cihazKimligi = await cihazKimligiGetir();
      const response = await apiIstek('/api/sorgula', {
        method: 'POST',
        body: JSON.stringify({
          dosya_no: dosyaNoDegeri.trim(),
          yil: kullanilacakYil,
          ana_kategori: kullanilacakAnaKategori,
          alt_kategori: kullanilacakAltKategori,
          cihaz_kimligi: cihazKimligi
        })
      });
      const data = await response.json();
      const yeniSonuclar = data.sonuclar || [];
      setSonuclar(yeniSonuclar);

      // Kullanıcı bir kategori seçmiş ama dosya numarası GERÇEKTE başka bir
      // kategorideyse, backend bunu bildiriyor -- gözden kaçırılmaması için
      // tam ekran uyarı gösteriyoruz (bkz. Modal JSX'i). İSTİSNA (2026-08-16):
      // stadiu<->ordine aşama geçişi bir "hata" değil, normal bir durum --
      // bunun için tam ekran (kırmızı/ünlemli) uyarı GÖSTERİLMİYOR, sadece
      // sakin bir kart mesajı yeterli (bkz. asamaGecisMesajiGetir).
      const yanlisKategoriKaydi = yeniSonuclar.find(
        (item: any) =>
          item.baska_kategoride_bulundu &&
          item.baska_kategoride_bulundu.length > 0 &&
          !asamaGecisMesajiGetir(item)
      );
      if (yanlisKategoriKaydi) {
        setKategoriUyarisi(yanlisKategoriKaydi.baska_kategoride_bulundu);
      }

      // ORDINE (onay) eşleşmesi varsa kutlama amaçlı konfeti yağmuru
      // tetiklenecek -- ama BURADA değil (bkz. finally). Burada sadece
      // karar veriliyor, gerçek tetikleme SorguSovu tamamen kapandıktan
      // sonraya erteleniyor.
      onayVarMi = yeniSonuclar.some(
        (item: any) => item.eslesti && item.ana_kategori === 'ordine'
      );
    } catch (err) {
      setHata(t.hataBaglanti);
    } finally {
      // 2026-08-17: sabit 5000ms yerine, SorguSovu'nun kendi bildirdiği
      // TOPLAM_SOV_SURESI_MS kullanılıyor (mercek TAM 3 tur atana kadar) --
      // yoksa Lottie animasyonu turları bitirmeden modal kapanırdı.
      const gecenSure = Date.now() - sovBaslangicZamani;
      const kalanSure = TOPLAM_SOV_SURESI_MS - gecenSure;
      if (kalanSure > 0) {
        await new Promise((cozul) => setTimeout(cozul, kalanSure));
      }
      setSovGoster(false);
      setLoading(false);
      // 2026-08-17 düzeltmesi: Eskiden konfeti API cevabı gelir gelmez
      // (yukarıdaki try içinde) başlatılıyordu -- ama <SorguSovu> JSX'te
      // <KonfettiYagmuru>'nun ÜZERİNDE render edildiği için (bkz. render
      // sırası), backend hızlı cevap verdiğinde konfetinin 4.2sn'lik ömrü
      // tamamen şovun ARKASINDA, kullanıcı hiç görmeden başlayıp bitiyordu
      // ("dosya onaylandı ama konfeti patlamadı" hatası, 2026-08-17'de
      // kullanıcı tarafından bildirildi). Artık konfeti, şov TAMAMEN
      // kapandıktan (setSovGoster(false)) SONRA, her zaman tam görünür
      // şekilde başlıyor.
      if (onayVarMi) {
        setKonfetiAnahtari((k) => k + 1);
        setKonfetiGoster(true);
        setTimeout(() => setKonfetiGoster(false), 4200);
      }
    }
  };

  const handleSorgula = () => sorgulaYap(dosyaNo);

  // Uyarı modalındaki "Bu kategoriyle tekrar sorgula" butonu: filtreleri
  // dosyanın GERÇEK kategorisine/yılına ayarlayıp aramayı otomatik tekrarlar.
  const kategoriUyarisiniUygula = (kategori: { ana_kategori: string; alt_kategori: string; yil: string | null }) => {
    const yeniAna = kategori.ana_kategori as 'stadiu' | 'ordine';
    setAnaKategori(yeniAna);
    setAltKategori(kategori.alt_kategori);
    setYil(kategori.yil || '');
    setKategoriUyarisi(null);
    sorgulaYap(dosyaNo, { ana_kategori: yeniAna, alt_kategori: kategori.alt_kategori, yil: kategori.yil });
  };

  // Her kartın kendi anahtarı: "dosya_no|yil" -- aynı arama içinde iki farklı
  // karta ait olabileceğinden hem dosya_no hem yıl birlikte kullanılıyor.
  const favoriAnahtariOlustur = (item: any): string => `${item.dosya_no || ''}|${item.yil || ''}`;

  const favoriyeEkleCikar = async (item: any) => {
    const anahtar = favoriAnahtariOlustur(item);
    if (!item.dosya_no || favoriIslemdeAnahtarlari.has(anahtar)) return;
    setFavoriIslemdeAnahtarlari((onceki) => new Set(onceki).add(anahtar));
    const zatenFavoride = favoriAnahtarlari.has(anahtar);
    try {
      const kimlik = await cihazKimligiGetir();
      const yol = zatenFavoride ? '/api/favori-sil' : '/api/favori-ekle';
      await apiIstek(yol, {
        method: 'POST',
        body: JSON.stringify({ expo_push_token: kimlik, dosya_no: item.dosya_no, yil: item.yil || null }),
      });
      setFavoriAnahtarlari((onceki) => {
        const yeni = new Set(onceki);
        if (zatenFavoride) yeni.delete(anahtar); else yeni.add(anahtar);
        return yeni;
      });
    } catch {
      // Sessizce yok say -- kullanıcı tekrar deneyebilir.
    } finally {
      setFavoriIslemdeAnahtarlari((onceki) => {
        const yeni = new Set(onceki);
        yeni.delete(anahtar);
        return yeni;
      });
    }
  };

  // Backend'in döndürdüğü ham (Türkçe) mesaj/durum yerine, seçili dile göre
  // ana_kategori bazında burada belirlenen metni gösteriyoruz -- böylece
  // sunucu tarafında hiçbir değişiklik yapmadan tüm sonuç mesajları anında
  // 3 dilde de doğru gösterilebiliyor.
  //
  // ÖNEMLİ: backend, eşleşme BULUNAMADIĞINDA bile ana_kategori alanını
  // (kullanıcının seçtiği filtre neyse onu) geri döndürür -- bu yüzden
  // önce item.eslesti kontrol edilmeden sadece ana_kategori'ye bakılırsa,
  // "kayıt yok" durumunda yanlışlıkla "onaylandı/işlemde" başarı mesajı
  // gösterilir. durumTipiGetir() bu kontrolü merkezi olarak yapıyor.
  // "ORDINE / Ordine articolul 11 (2021)" gibi tek bir kategori+yıl etiketi
  // üretir -- hem sonuç kartındaki mesajda hem tam ekran uyarı modalında
  // aynı biçim kullanılıyor.
  const kategoriEtiketiOlustur = (k: { ana_kategori: string; alt_kategori: string; yil?: string | null }): string => {
    const temel = `${(k.ana_kategori || '').toUpperCase()} / ${k.alt_kategori}`;
    return k.yil ? `${temel} (${k.yil})` : temel;
  };

  // 2026-08-16 (kullanıcı isteği): "yanlış kategori" durumunun ÖZEL bir
  // hali var -- kullanıcı ORDINE'de arayıp numarası SADECE stadiu'da
  // bulunuyorsa, bu bir "hata/yanlış seçim" değil, tamamen NORMAL bir durum
  // (başvuru henüz 2. aşamaya geçmemiş). Bunu genel "yanlış kategori"
  // uyarısıyla karıştırmak yerine (hem yanlış tonlu -- kırmızı/ünlemli tam
  // ekran uyarı gereksiz kaygı verir, hem yanlış ifade -- "yanlış kategori
  // seçtiniz" demek yanlış, kullanıcı doğru kategoriyi seçti, sonuç henüz
  // orada yok), özel ve sakin bir bilgilendirme mesajı gösteriyoruz. Aynı
  // mantığın simetriği: STADIU'da arayıp SADECE ordine'de bulunuyorsa, bu
  // aslında İYİ HABER (zaten onaylanmış) -- onu da ayrıca karşılıyoruz.
  // Modal'ı (tam ekran uyarı) TETİKLEMİYOR -- bkz. sorgulaYap'taki kontrol.
  const asamaGecisMesajiGetir = (item: any): string | null => {
    const digerKategoriler: { ana_kategori: string }[] = item.baska_kategoride_bulundu || [];
    if (digerKategoriler.length === 0) return null;
    const anaKategoriler = new Set(digerKategoriler.map((k) => k.ana_kategori));
    if (anaKategoriler.size !== 1) return null;
    if (item.ana_kategori === 'ordine' && anaKategoriler.has('stadiu')) {
      return t.sonucHenuzOrdineGecmedi;
    }
    if (item.ana_kategori === 'stadiu' && anaKategoriler.has('ordine')) {
      return t.sonucZatenOrdineGecti;
    }
    return null;
  };

  const sonucMetniGetir = (item: any): string => {
    const tip = durumTipiGetir(item);
    if (tip === 'onay') return t.sonucMesaji.ordine;
    if (tip === 'islemde') return t.sonucMesaji.stadiu;
    const asamaMesaji = asamaGecisMesajiGetir(item);
    if (asamaMesaji) return asamaMesaji;
    // 2026-08-16: kullanıcı bir kategori/yıl filtresi seçip aradığında
    // numara orada yoksa ama BAŞKA bir kategoride/yılda varsa, backend bunu
    // "baska_kategoride_bulundu" alanında bildiriyor -- burada genel
    // "bulunamadı" yerine kullanıcıyı doğru kategoriye/yıla yönlendiren bir
    // mesaj gösteriyoruz (bkz. backend/main.py /api/sorgula notu).
    const digerKategoriler: { ana_kategori: string; alt_kategori: string; yil?: string | null }[] =
      item.baska_kategoride_bulundu || [];
    if (digerKategoriler.length > 0) {
      const kategoriMetni = digerKategoriler.slice(0, 3).map(kategoriEtiketiOlustur).join(', ');
      return t.sonucBaskaKategoride.replace('{kategori}', kategoriMetni);
    }
    return t.sonucBulunamadi;
  };

  const durumRozetiGetir = (item: any): string => {
    const tip = durumTipiGetir(item);
    if (tip === 'onay') return t.durumRozeti.ordine;
    if (tip === 'islemde') return t.durumRozeti.stadiu;
    return t.durumBulunamadi;
  };

  return (
    <SafeAreaView style={styles.container}>
      {/* 2026-08-15: kullanıcı isteği -- üstteki koyu alan artık sayfa
          zeminiyle AYNI renkte olduğu için (koyu lacivert/antrasit tema),
          onu diğer içerikle aynı kenar boşluklu bir "kart" gibi göstermenin
          anlamı kalmadı -- ayrı/gereksiz bir duruş sergiliyordu. Bu yüzden
          ScrollView'ın DIŞINA, kenar boşluksuz/tam genişlikte, gerçek bir
          üst başlık (header) olarak taşındı. Aynı sebeple altındaki
          "erime" geçişi de (bkz. piksel-erime.tsx) kaldırıldı.
          SVG GRADYAN DA KALDIRILDI (2026-08-15, ikinci düzeltme): gradyan
          dikdörtgeni ile View'ın kendi arka plan rengi arasında kenarlarda
          ince bir çizgi/kesişim artefaktı oluşuyordu -- kullanıcı "her yer
          aynı tonda düz mavi olsun" dedi, haklı: artık heroKart SADECE
          backgroundColor (LACIVERT) kullanıyor, hiçbir gradyan/Svg katmanı
          yok -- çizginin kök nedeni tamamen ortadan kalktı. */}
      <View style={styles.heroKart}>
        <Yapraklar />
        {/* 2026-08-18 (kullanıcı isteği -- yerleşim değişikliği): bayrak
            rozeti artık BAŞLIĞIN SOLUNDA, dil seçici SAĞINDA -- önceki
            düzenin (dil solda, bayrak sağda) tam tersi. Özellikler (bilgi)
            ikonu artık ortada/üstte değil, dil seçicinin HEMEN ALTINDA,
            sağ tarafta dikey olarak istifleniyor. */}
        <View style={styles.appAdiSatir}>
          <BayrakRozeti />
          <Text style={styles.headerTitle}>{t.appAdi}</Text>
          <View style={styles.sagUstKontroller}>
            <LanguageSwitcher varyant="koyu" acilisYonu="sol" />
            <TouchableOpacity
              style={styles.bilgiButonu}
              onPress={() => setOzelliklerGoster(true)}
              hitSlop={10}
            >
              <Text style={styles.bilgiButonuMetin}>ⓘ</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={{ flex: 1 }}
      >
        <ScrollView contentContainerStyle={styles.scrollContent}>
          {servisDisiMi && (
            <View style={styles.servisDisiBanner}>
              <Text style={styles.servisDisiMetin}>⚠️ {t.siteServisDisiBanner}</Text>
              {/* 2026-08-15: kullanıcı isteğiyle eklendi -- yukarıdaki uyarı
                  tek başına kaygı verici durabiliyor, verilerin taze
                  kaldığını hatırlatan bu ek satır ferahlık veriyor. Son
                  tarama zamanı bilinmiyorsa (henüz hiç çalışmadıysa) bu
                  satır hiç gösterilmez. */}
              {sonGuncellemeMetniOlustur(sonGuncelleme) && (
                <Text style={styles.servisDisiEkMetin}>
                  {t.siteServisDisiEkAciklama.replace('{tarih}', sonGuncellemeMetniOlustur(sonGuncelleme) ?? '')}
                </Text>
              )}
            </View>
          )}
          {/* Dosya Numarası */}
          <View style={styles.inputGroup}>
            <Text style={styles.label}>{t.dosyaNoEtiket}</Text>
            <TextInput
              style={styles.input}
              placeholder={t.dosyaNoOrnek}
              placeholderTextColor={GRI}
              keyboardType="numeric"
              value={dosyaNo}
              onChangeText={setDosyaNo}
            />
          </View>
          {/* 2026-08-16 (kullanıcı isteği): "Son Aramalar" geçmiş bölümü
              görüntü kirliliği yaptığı ve satırların aşağı kaymasına sebep
              olduğu için tamamen kaldırıldı. */}
          {/* Yıl */}
          <View style={styles.inputGroup}>
            <Text style={styles.label}>{t.yilEtiket}</Text>
            <TextInput
              style={styles.input}
              placeholder={t.yilOrnek}
              placeholderTextColor={GRI}
              keyboardType="numeric"
              value={yil}
              onChangeText={setYil}
            />
          </View>
          {/* Ana Kategori Seçimi */}
          <View style={styles.inputGroup}>
            <Text style={styles.label}>{t.anaKategoriEtiket}</Text>
            <View style={styles.row}>
              <TouchableOpacity
                style={[styles.chip, anaKategori === 'stadiu' && styles.chipActive]}
                onPress={() => { setAnaKategori('stadiu'); setAltKategori(null); }}
              >
                <Text style={[styles.chipText, anaKategori === 'stadiu' && styles.chipTextActive]}>Stadiu Dosar</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.chip, anaKategori === 'ordine' && styles.chipActive]}
                onPress={() => { setAnaKategori('ordine'); setAltKategori(null); }}
              >
                <Text style={[styles.chipText, anaKategori === 'ordine' && styles.chipTextActive]}>Ordine</Text>
              </TouchableOpacity>
            </View>
          </View>
          {/* Alt Kategori Seçimi */}
          {anaKategori && (
            <View style={styles.inputGroup}>
              <Text style={styles.label}>{t.altKategoriEtiket}</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.subCategoryScroll}>
                {aktifAltKategoriler.map((kat, index) => (
                  <TouchableOpacity
                    key={index}
                    style={[styles.subChip, altKategori === kat && styles.subChipActive]}
                    onPress={() => setAltKategori(altKategori === kat ? null : kat)}
                  >
                    <Text style={[styles.subChipText, altKategori === kat && styles.subChipTextActive]}>{kat}</Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>
            </View>
          )}
          {/* 2026-08-16 (kullanıcı isteği): proaktif ipucu -- kullanıcı
              aramadan ÖNCE bilsin diye, alanların hemen altında, küçük ve
              göze batmayan bir metin. Birden fazla sonuç çıktığında ayrıca
              gösterilen "cokluSonucUyarisi" banner'ını (tepkisel) TEKRARLAMIYOR,
              tamamlıyor: bu ipucu dikkatli okuyanı en baştan doğru yönlendirir,
              öteki ise atlayıp boş arayanı sonradan yakalar. */}
          <Text style={styles.ipucuMetin}>💡 {t.dogruSonucIpucu}</Text>
          {hata ? <Text style={styles.errorText}>{hata}</Text> : null}
          {/* Sorgula Butonu */}
          <TouchableOpacity style={styles.button} onPress={handleSorgula} disabled={loading}>
            {loading ? <ActivityIndicator color="#16233D" /> : <Text style={styles.buttonText}>{t.sorgulaButon}</Text>}
          </TouchableOpacity>
          {/* Sonuçlar */}
          {sonuclar && (
            <View style={styles.resultContainer}>
              <View style={styles.resultBaslikSatiri}>
                <Text style={styles.resultHeader}>{t.sonucBaslik}</Text>
              </View>
              {/* 2026-08-16 (kullanıcı isteği): dosya numaraları farklı
                  yıllarda tekrar kullanılabildiği için (bkz. backend
                  testleri), aynı numara birden fazla gerçek kayıtla
                  eşleşebiliyor -- bu NORMAL ama kullanıcı kafası karışmasın
                  diye, birden fazla sonuç çıktığında doğru/tekil sonuca
                  nasıl ulaşacağını anlatan bir bilgilendirme gösteriliyor. */}
              {sonuclar.length > 1 && (
                <View style={styles.cokluSonucKutu}>
                  <Text style={styles.cokluSonucMetin}>ℹ️ {t.cokluSonucUyarisi}</Text>
                </View>
              )}
              {sonuclar.map((item, index) => {
                const tip = durumTipiGetir(item);
                return (
                  <View key={index} style={styles.card}>
                    <View style={[styles.kurdele, RIBBON_RENK[tip]]}>
                      <Text style={[styles.kurdeleMetin, { color: RIBBON_METIN_RENK[tip] }]}>
                        {DURUM_IKONU[tip]} {durumRozetiGetir(item)}
                      </Text>
                    </View>
                    <Text style={styles.cardCategory}>{item.ana_kategori?.toUpperCase()} / {item.alt_kategori}</Text>
                    {/* 2026-08-15 (kritik düzeltme): baştaki rakam TEK BAŞINA
                        eşsiz değil -- aynı numara farklı yıllarda farklı
                        kişilere ait olabiliyor (bkz. backend notu). Yıl
                        girilmeden birden fazla sonuç çıkarsa, kullanıcı
                        BURADAN eşleşen TAM numarayı görüp gerçekten kendisine
                        ait olanı gözle ayırt edebilsin diye ekleniyor. */}
                    {tip !== 'bulunamadi' && item.dosya_no ? (
                      <Text style={styles.cardDosyaNo}>Eşleşen numara: {item.dosya_no}</Text>
                    ) : null}
                    <Text style={styles.cardMessage}>{sonucMetniGetir(item)}</Text>
                    {/* PDF butonları SADECE gerçek bir eşleşme varsa gösterilir --
                        "bulunamadı" sonucunda kırık/anlamsız bir bağlantı
                        gösterilmesin diye tip === 'bulunamadi' ise hiçbiri render edilmez. */}
                    {tip !== 'bulunamadi' && item.yerel_pdf_url ? (
                      <>
                        <TouchableOpacity
                          style={styles.yerelPdfButon}
                          onPress={() => Linking.openURL(item.yerel_pdf_url)}
                        >
                          <Text style={styles.yerelPdfMetin}>{t.yerelBelgeButon}</Text>
                        </TouchableOpacity>
                        <Text style={styles.yerelPdfAciklama}>{t.yerelBelgeAciklama}</Text>
                      </>
                    ) : null}
                    {tip !== 'bulunamadi' && item.resmi_pdf_url ? (
                      <TouchableOpacity
                        style={styles.resmiLinkButon}
                        onPress={() => Linking.openURL(item.resmi_pdf_url)}
                      >
                        <Text style={styles.resmiLinkMetin}>{t.resmiBelgeButon}</Text>
                      </TouchableOpacity>
                    ) : null}
                    {/* 2026-08-16: favori butonu artık her KARTIN kendi
                        dosya_no+yıl'ına özel -- bkz. favoriyeEkleCikar notu. */}
                    {tip !== 'bulunamadi' && item.eslesti ? (() => {
                      const anahtar = favoriAnahtariOlustur(item);
                      const buFavoride = favoriAnahtarlari.has(anahtar);
                      const buIslemde = favoriIslemdeAnahtarlari.has(anahtar);
                      return (
                        <TouchableOpacity
                          style={[styles.favoriButon, buFavoride && styles.favoriButonAktif]}
                          onPress={() => favoriyeEkleCikar(item)}
                          disabled={buIslemde}
                        >
                          <Text style={[styles.favoriButonMetin, buFavoride && styles.favoriButonMetinAktif]}>
                            {buIslemde ? '…' : (buFavoride ? t.favoridekiButon : t.favoriEkleButon)}
                          </Text>
                        </TouchableOpacity>
                      );
                    })() : null}
                  </View>
                );
              })}
              <Text style={styles.uyariMetin}>{t.altUyari}</Text>
            </View>
          )}
          <Text style={styles.footerImza}>🔒 Secured & Encrypted System · By @knby · © 2026</Text>
        </ScrollView>
      </KeyboardAvoidingView>
      {konfetiGoster && <KonfettiYagmuru key={konfetiAnahtari} />}
      <SorguSovu gorunur={sovGoster} />

      {/* 2026-08-16: yanlış alt kategori seçilip arandığında (dosya numarası
          GERÇEKTE başka bir kategorideyse) gözden kaçırılmaması için tam
          ekranı kaplayan, dikkat çekici bir uyarı -- kullanıcı isteği
          üzerine eklendi. */}
      <Modal
        visible={!!kategoriUyarisi}
        transparent
        animationType="fade"
        onRequestClose={() => setKategoriUyarisi(null)}
      >
        <View style={styles.uyariArkaPlan}>
          <View style={styles.uyariKutu}>
            <Text style={styles.uyariIkon}>⚠️</Text>
            <Text style={styles.uyariBaslik}>{t.kategoriUyariBaslik}</Text>
            <Text style={styles.uyariAciklama}>
              {t.kategoriUyariMetin.replace(
                '{kategori}',
                (kategoriUyarisi || []).slice(0, 3).map(kategoriEtiketiOlustur).join(', ')
              )}
            </Text>
            {(kategoriUyarisi || []).slice(0, 2).map((k, i) => (
              <TouchableOpacity
                key={i}
                style={styles.uyariUygulaButon}
                onPress={() => kategoriUyarisiniUygula(k)}
              >
                <Text style={styles.uyariUygulaMetin}>
                  {t.kategoriUyariUygula} ({kategoriEtiketiOlustur(k)})
                </Text>
              </TouchableOpacity>
            ))}
            <TouchableOpacity
              style={styles.uyariTamamButon}
              onPress={() => setKategoriUyarisi(null)}
            >
              <Text style={styles.uyariTamamMetin}>{t.kategoriUyariTamam}</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
      {/* 2026-08-18: OzelliklerModal, düz bir absolute-overlay View (RN'in
          <Modal>'i DEĞİL -- bkz. component içindeki not, disclaimer-gate.tsx
          ile aynı ders). Bu yüzden RN Modal'ın aksine kendi ayrı bir katmanı
          yok -- kardeşler arasında SIRALAMA önemli, en son render edilen en
          üstte görünür. İLK DENEMEDE heroKart'ın hemen altına konmuştu, bu
          da ScrollView içeriğinin ÜSTÜNDE kalmasını engelliyordu (adb ile
          çekilen ekran görüntüsüyle doğrulandı, metinler iç içe geçmişti).
          Doğru yer: bu return'ün EN SONU. */}
      <OzelliklerModal gorunur={ozelliklerGoster} kapat={() => setOzelliklerGoster(false)} />
    </SafeAreaView>
  );
}

// ---------------------------------------------------------------------------
// Tasarım yönü: "Üç Renk, Ölçülü" -- kullanıcının 2026-08-15 onayıyla
// monokrom zümrüt yeşili paletinden, sonra "Üç Renk, Ölçülü" (açık zemin)
// temasından geçilerek 2026-08-15'te KOYU temaya dönüştürüldü. Kullanıcının
// tarif ettiği referans: koyu lacivert/antrasit hem sayfa zemininde hem
// kartlarda hakim; altın/hardal sarısı buton, aktif seçim, vurgulu durum ve
// giriş çerçevelerinde; beyaz başlık/açıklama/sayı metinlerinde; gri
// ikincil/ipucu metinlerinde; yeşil SADECE "PDF'i İndir" butonunda. Romanya
// bayrağı şeridi (mavi-sarı-kırmızı) zaten flag-mark.tsx'te ayrı, değişmedi.
// ---------------------------------------------------------------------------
const LACIVERT = '#1E2C4A';      // sayfa zemini VE kartların temel koyu lacivert/antrasit rengi -- TEK/DÜZ ton, gradyan yok
const KART_YUZEY = '#27375A';    // kart/kutu/giriş alanı yüzeyi -- zeminden bir ton açık, hafif derinlik için
const ALTIN = '#E3A83B';         // altın/hardal sarısı -- buton, aktif kategori, vurgulu durum, giriş çerçevesi (üzerindeki metin LACIVERT olmalı, kontrast için)
const BEYAZ = '#F5F7FA';         // başlık, açıklama ve sayı metinleri
const GRI = '#8E9AB8';           // ikincil/ipucu/alt bilgi metinleri
const YESIL_INDIR = '#1E7A4C';   // SADECE "PDF'i İndir" butonu için koyu yeşil
const ZEMIN = LACIVERT;          // sayfa zemini kartlarla aynı koyu aileden
const KENAR = '#2E3B5C';         // koyu zeminde görünür ince kenarlık
const UYARI_KIRMIZI = '#D64545'; // SADECE "yanlış kategori" tam ekran uyarısı için -- diğer hiçbir yerde kullanılmıyor, dikkat çekmesi kasıtlı

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: ZEMIN },
  scrollContent: { padding: 20, paddingTop: 14 },
  // 2026-08-15: kenar boşluksuz, tam genişlikte gerçek bir üst başlık --
  // artık köşeleri de yuvarlatılmıyor (edge-to-edge bir header'ın "kart"
  // gibi görünmesine gerek yok, bkz. üstteki JSX notu).
  heroKart: {
    backgroundColor: LACIVERT,
    paddingTop: 16,
    paddingHorizontal: 16,
    paddingBottom: 18,
    // 2026-08-16: "overflow: hidden" kaldırıldı -- artık Yapraklar kendi
    // kırpmasını kendi içinde yapıyor (bkz. yapraklar.tsx notu), burada
    // kalırsa dil seçici açılır menüsünü (bkz. language-switcher.tsx)
    // kart sınırının hemen altında keserdi.
    position: 'relative',
  },
  appAdiSatir: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, marginTop: 14 },
  headerTitle: { fontSize: 21, fontWeight: 'bold', color: '#fff' },
  // 2026-08-18 (kullanıcı isteği -- yerleşim değişikliği): dil seçici ve
  // "Özellikler" bilgi ikonu artık SAĞ tarafta, dikey olarak üst üste
  // istifleniyor (dil üstte, bilgi ikonu hemen altında).
  sagUstKontroller: {
    alignItems: 'center',
    gap: 6,
  },
  bilgiButonu: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: 'rgba(255,255,255,0.14)',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 10,
  },
  bilgiButonuMetin: { color: '#fff', fontSize: 17, fontWeight: 'bold' },
  servisDisiBanner: {
    backgroundColor: '#FBE9E7',
    borderWidth: 1,
    borderColor: '#E4536B',
    borderRadius: 12,
    padding: 12,
    marginBottom: 16,
    marginTop: -6,
  },
  servisDisiMetin: { color: '#8a1f2d', fontSize: 12.5, fontWeight: '600', lineHeight: 18 },
  servisDisiEkMetin: { color: '#8a1f2d', fontSize: 11.5, marginTop: 6, lineHeight: 16, opacity: 0.85 },
  inputGroup: { marginBottom: 15 },
  label: { fontSize: 14, fontWeight: '600', color: BEYAZ, marginBottom: 5 },
  input: {
    backgroundColor: KART_YUZEY, borderRadius: 10, padding: 12, fontSize: 16, color: BEYAZ,
    borderWidth: 1, borderColor: ALTIN,
  },
  row: { flexDirection: 'row', gap: 10 },
  chip: { flex: 1, padding: 12, borderRadius: 10, borderWidth: 1, borderColor: KENAR, alignItems: 'center', backgroundColor: KART_YUZEY },
  chipActive: { backgroundColor: ALTIN, borderColor: ALTIN },
  chipText: { fontSize: 14, color: BEYAZ, fontWeight: '500' },
  // Altın zemin üzerinde beyaz metin okunaklı değil -- kontrast için koyu
  // lacivert kullanılıyor (bkz. ALTIN tanımındaki not).
  chipTextActive: { color: LACIVERT },
  subCategoryScroll: { flexDirection: 'row', marginTop: 5 },
  subChip: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: 20, borderWidth: 1, borderColor: KENAR, backgroundColor: KART_YUZEY, marginRight: 8 },
  subChipActive: { backgroundColor: ALTIN, borderColor: ALTIN },
  subChipText: { fontSize: 12, color: GRI },
  subChipTextActive: { color: LACIVERT, fontWeight: 'bold' },
  button: {
    backgroundColor: ALTIN, padding: 15, borderRadius: 12, alignItems: 'center', marginTop: 10,
    shadowColor: ALTIN, shadowOffset: { width: 0, height: 6 }, shadowOpacity: 0.4, shadowRadius: 10, elevation: 5,
  },
  buttonText: { color: LACIVERT, fontSize: 16, fontWeight: 'bold' },
  errorText: { color: '#E4536B', textAlign: 'center', marginVertical: 5 },
  resultContainer: { marginTop: 25 },
  resultBaslikSatiri: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  resultHeader: { fontSize: 18, fontWeight: 'bold', color: BEYAZ },
  // 2026-08-16: artık sonuç kartlarının İÇİNDE (her karta özel), header
  // satırında değil -- bu yüzden alignSelf ile tam genişliğe yayılması
  // engelleniyor, marginTop ile üstündeki butonlardan ayrılıyor.
  favoriButon: { alignSelf: 'flex-start', marginTop: 10, paddingHorizontal: 12, paddingVertical: 7, borderRadius: 10, borderWidth: 1.5, borderColor: ALTIN, backgroundColor: KART_YUZEY },
  favoriButonAktif: { backgroundColor: ALTIN, borderColor: ALTIN },
  favoriButonMetin: { fontSize: 12, fontWeight: '700', color: ALTIN },
  favoriButonMetinAktif: { color: LACIVERT },
  card: {
    backgroundColor: KART_YUZEY, padding: 16, borderRadius: 18, marginBottom: 14,
    borderWidth: 1, borderColor: KENAR,
    overflow: 'hidden', position: 'relative',
  },
  kurdele: {
    position: 'absolute',
    top: 12,
    right: -30,
    paddingVertical: 4,
    paddingHorizontal: 34,
    transform: [{ rotate: '38deg' }],
  },
  kurdeleMetin: { fontSize: 10, fontWeight: '800' },
  cardCategory: { fontSize: 12, fontWeight: 'bold', color: GRI, marginBottom: 5, marginTop: 2, maxWidth: '78%' },
  cardDosyaNo: { fontSize: 12.5, fontWeight: '700', color: ALTIN, marginBottom: 6, maxWidth: '80%' },
  cardMessage: { fontSize: 15, fontWeight: '600', color: BEYAZ, maxWidth: '80%' },
  // "PDF'i İndir" -- kullanıcının tarif ettiği paletteki TEK yeşil öğe.
  yerelPdfButon: {
    marginTop: 12,
    backgroundColor: YESIL_INDIR,
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderRadius: 10,
    alignSelf: 'flex-start',
  },
  yerelPdfMetin: { fontSize: 13, color: '#fff', fontWeight: '700' },
  yerelPdfAciklama: { fontSize: 11, color: GRI, marginTop: 6, lineHeight: 15 },
  resmiLinkButon: { marginTop: 10, alignSelf: 'flex-start' },
  resmiLinkMetin: { fontSize: 13, color: ALTIN, fontWeight: '600', textDecorationLine: 'underline' },
  uyariMetin: { fontSize: 12, color: GRI, textAlign: 'center', marginTop: 15, lineHeight: 18 },
  footerImza: { fontSize: 10.5, color: GRI, textAlign: 'center', marginTop: 22, marginBottom: 4, letterSpacing: 0.2 },

  // Proaktif "doğru sonuç" ipucu metni (2026-08-16) -- form alanlarının
  // altında, sakin/göze batmayan bir alt bilgi tonu.
  ipucuMetin: {
    color: GRI,
    fontSize: 12,
    lineHeight: 17,
    marginTop: -4,
    marginBottom: 14,
    fontStyle: 'italic',
  },

  // Çoklu sonuç bilgilendirme kutusu (2026-08-16) -- uyarı modalı kadar acil
  // değil (kullanıcı hatası değil, doğal bir durum), bu yüzden daha yumuşak/
  // sakin bir "bilgi" tonu kullanılıyor (kırmızı değil, altın/gri).
  cokluSonucKutu: {
    backgroundColor: 'rgba(227, 168, 59, 0.12)',
    borderWidth: 1,
    borderColor: ALTIN,
    borderRadius: 10,
    padding: 12,
    marginBottom: 14,
  },
  cokluSonucMetin: {
    color: BEYAZ,
    fontSize: 13,
    lineHeight: 19,
  },

  // "Yanlış kategori" tam ekran uyarı modalı (2026-08-16).
  uyariArkaPlan: {
    flex: 1,
    backgroundColor: 'rgba(10, 14, 26, 0.88)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  uyariKutu: {
    width: '100%',
    maxWidth: 420,
    backgroundColor: KART_YUZEY,
    borderRadius: 18,
    borderWidth: 2,
    borderColor: UYARI_KIRMIZI,
    padding: 24,
    alignItems: 'center',
  },
  uyariIkon: { fontSize: 52, marginBottom: 10 },
  uyariBaslik: {
    fontSize: 18,
    fontWeight: '800',
    color: UYARI_KIRMIZI,
    textAlign: 'center',
    marginBottom: 10,
  },
  uyariAciklama: {
    fontSize: 14.5,
    color: BEYAZ,
    textAlign: 'center',
    lineHeight: 21,
    marginBottom: 18,
  },
  uyariUygulaButon: {
    backgroundColor: ALTIN,
    borderRadius: 10,
    paddingVertical: 12,
    paddingHorizontal: 16,
    width: '100%',
    marginBottom: 10,
  },
  uyariUygulaMetin: {
    color: LACIVERT,
    fontWeight: '800',
    fontSize: 14,
    textAlign: 'center',
  },
  uyariTamamButon: {
    borderRadius: 10,
    paddingVertical: 12,
    paddingHorizontal: 16,
    width: '100%',
    borderWidth: 1,
    borderColor: KENAR,
    marginTop: 4,
  },
  uyariTamamMetin: {
    color: GRI,
    fontWeight: '700',
    fontSize: 14,
    textAlign: 'center',
  },
});

// Durum tipine göre kurdele arkaplan/metin rengi.
//
// NOT (tasarım kararı, 2026-08-15 -- koyu tema): kullanıcının paletinde
// kırmızı yok; "dosya durumu" için altın/hardal sarısı istendi. Onay/
// işlemde ayrımının kaybolmaması için ONAY durumu, paletteki TEK olumlu/
// başarı rengi olan yeşille (indirme butonuyla aynı aile) eşleştirildi --
// İŞLEMDE ise doğrudan istenen altın tonunda. "Bulunamadı" nötr gri.
const RIBBON_RENK: Record<DurumTipi, object> = {
  onay: { backgroundColor: YESIL_INDIR },
  islemde: { backgroundColor: ALTIN },
  bulunamadi: { backgroundColor: '#4A5573' },
};
const RIBBON_METIN_RENK: Record<DurumTipi, string> = {
  onay: '#fff',
  islemde: LACIVERT,
  bulunamadi: '#fff',
};
