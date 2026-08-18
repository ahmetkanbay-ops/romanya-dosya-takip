import LottieView from 'lottie-react-native';
import React, { useEffect, useRef, useState } from 'react';
import { Modal, StyleSheet, Text, View } from 'react-native';

// ---------------------------------------------------------------------------
// SORGU ŞOVU (2026-08-16 eklendi, 2026-08-17'de LottieFiles animasyonuyla
// DEĞİŞTİRİLDİ -- kullanıcının kendi indirdiği "Searching" (BurtTru,
// lottiefiles.com/9060-searching) animasyonu, web önizlemesinde onaylandı)
// ---------------------------------------------------------------------------
// Önceki sürüm react-native-svg ile elle çizilmiş dönen bir yay kullanıyordu.
// Artık gerçek bir Lottie animasyonu oynatılıyor: bir büyüteç ekranda daire
// çizerek "arama" hareketi yapıyor, arkasında parlayan noktalar beliriyor
// (bkz. assets/animasyonlar/sorgu-arama.json -- ham Lottie JSON, kullanıcının
// indirdiği .lottie dosyasından çıkarıldı).
//
// assets/animasyonlar/sorgu-arama.json, kullanıcının indirdiği ham dosyaya
// göre birkaç kez elle düzenlendi (bkz. json dosyasının kendisi ham veri
// olduğu için yorum içeremiyor, düzenleme geçmişi burada tutuluyor):
//
// 1) Arka plan katmanı silindi ("形状图层 1", ind:13) -- tüm kareyi kaplayan
//    koyu lacivert bir dikdörtgendi, bileşenin kendi Modal zeminiyle
//    çakışıp "içte mavi kare, dışta siyah" görünümü yaratıyordu.
//
// 2) "Tam eksenli dönme" denemesi (büyüteci merkeze sabitleyip kendi
//    ekseninde döndürme) kullanıcı tarafından REDDEDİLDİ -- orijinal
//    "köşeden köşeye dolaşma" hareketi GERİ getirildi.
//
// 3) KRİTİK BULGU (kullanıcının gönderdiği gerçek cihaz ekran kaydından
//    anlaşıldı): Bu animasyon, hareketin sürekli tekrarlanmasını After
//    Effects "expression" (loopOut('cycle',0)) ile sağlıyordu. Web
//    önizlemesi (lottie-web, tarayıcıda) expression'ları çalıştırabildiği
//    için orada hep doğru görünüyordu -- ama `lottie-react-native`'in
//    ANDROID/iOS'ta kullandığı NATIVE Lottie kütüphaneleri (lottie-android/
//    lottie-ios) expression'ları DESTEKLEMİYOR. Telefonda animasyon bu
//    yüzden sadece keyframe'lerin TEK bir geçişini oynatıp donuyordu --
//    web önizlemesi güvenilmez bir test ortamı olmuş oldu. Çözüm: TÜM
//    expression'lar ("x" anahtarı, 6 farklı özellikte) JSON'dan silindi;
//    başlangıç (t=0) ve bitiş (t=60) kare değerleri zaten birebir aynı
//    olduğu için, üst seviye ip/op (0-60) + LottieView'ın native `loop`
//    prop'u tek başına kesintisiz bir döngü sağlıyor -- expression'a hiç
//    gerek kalmadan, native'de de garanti çalışıyor.
//
// 4) Dolaşma yörüngesinin ve sallanmanın kare zamanlaması eşit aralıklara
//    yayıldı (0,15,30,45,60) -- orijinalinde ilk çeyrekte sıkışıp son
//    çeyrekte "sürünüyormuş" gibi göründüğü için.
//
// Zamanlama burada DEĞİL, çağıran tarafta (index.tsx) yönetiliyor -- bu
// bileşen sadece `gorunur` true olduğu sürece animasyonu döngüsel oynatır;
// index.tsx hem gerçek API isteğini hem 5 saniyelik minimum süreyi PARALEL
// bekleyip ikisi de bitince `gorunur`'ı false yapıyor.

const LACIVERT = '#0A0E14';
const BEYAZ = '#F5F7FA';

// 2026-08-17 (kullanıcı isteği): mercek tam olarak TUR_SAYISI kez dönüp
// duracak.
//
// ÖNEMLİ: lottie-react-native'in `loop` prop'u SADECE boolean kabul ediyor
// (sayı değil) -- "N kez oynat" diye bir yerleşik özelliği yok. Bu yüzden
// `loop={false}` + imperatif `play()` + `onAnimationFinish` callback'i
// birlikte kullanılıyor: her bitişte sayaç bir artırılıyor, TUR_SAYISI'na
// ulaşana kadar yeniden `play()` çağrılıyor.
export const TUR_SAYISI = 3;
// Animasyonun (assets/animasyonlar/sorgu-arama.json) DOĞAL tek tur süresi:
// JSON'un kendi ip/op'u 0-60 kare, 30fps -> 60/30 = 2sn.
const TUR_DOGAL_SURESI_SN = 2;
// 2026-08-17 (kullanıcı isteği, 3. tur): toplam TUR_SAYISI tur 5-6sn'de
// bitsin -- hedef toplam 5.5sn, yani tek tur ~1.83sn (doğal 2sn'den bile
// biraz HIZLI, TUR_HIZI 1'in az üstünde çıkıyor).
const TOPLAM_HEDEF_SN = 5.5;
const TUR_SURESI_SN = TOPLAM_HEDEF_SN / TUR_SAYISI;
const TUR_HIZI = TUR_DOGAL_SURESI_SN / TUR_SURESI_SN;
export const TOPLAM_SOV_SURESI_MS = TOPLAM_HEDEF_SN * 1000;

const DURUM_METINLERI = [
  'DOSYALAR TARANIYOR...',
  'KAYITLAR KARŞILAŞTIRILIYOR...',
  'KATEGORİLER KONTROL EDİLİYOR...',
  'SONUÇ HAZIRLANIYOR...',
];

export default function SorguSovu({ gorunur }: { gorunur: boolean }) {
  const [metinIndex, setMetinIndex] = useState(0);
  const lottieRef = useRef<LottieView>(null);
  const turSayaci = useRef(0);

  useEffect(() => {
    if (!gorunur) return;
    setMetinIndex(0);
    turSayaci.current = 0;
    // autoPlay yerine elle başlatılıyor -- `onAnimationFinish` ile aynı
    // "tekrar oynat" mekanizmasını kullanmak için (bkz. aşağıdaki not).
    lottieRef.current?.play();

    const metinAraligi = setInterval(() => {
      setMetinIndex((onceki) => (onceki + 1) % DURUM_METINLERI.length);
    }, 1300);

    return () => clearInterval(metinAraligi);
  }, [gorunur]);

  const turBittiginde = (iptalEdildiMi: boolean) => {
    if (iptalEdildiMi) return; // modal kapanırken tetiklenmiş olabilir, tekrar oynatma
    turSayaci.current += 1;
    if (turSayaci.current < TUR_SAYISI) {
      lottieRef.current?.play();
    }
    // TUR_SAYISI'na ulaşıldıysa hiçbir şey yapma -- son karede duruyor.
  };

  if (!gorunur) return null;

  return (
    <Modal visible={gorunur} transparent animationType="fade" statusBarTranslucent>
      <View style={styles.arkaPlan}>
        <LottieView
          ref={lottieRef}
          source={require('@/assets/animasyonlar/sorgu-arama.json')}
          loop={false}
          onAnimationFinish={turBittiginde}
          speed={TUR_HIZI}
          style={styles.lottie}
        />
        <View style={styles.metinKapsayici}>
          <Text style={styles.durumMetni}>{DURUM_METINLERI[metinIndex]}</Text>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  arkaPlan: {
    flex: 1,
    backgroundColor: LACIVERT,
    justifyContent: 'center',
    alignItems: 'center',
  },
  lottie: {
    width: 220,
    height: 220,
  },
  metinKapsayici: {
    marginTop: -10,
    alignItems: 'center',
    paddingHorizontal: 40,
  },
  durumMetni: {
    color: BEYAZ,
    fontSize: 13,
    fontWeight: '700',
    letterSpacing: 1.2,
    textAlign: 'center',
  },
});
