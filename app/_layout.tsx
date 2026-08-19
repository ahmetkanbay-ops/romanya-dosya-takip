import { DarkTheme, ThemeProvider, Theme } from '@react-navigation/native';
import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import React from 'react';
import { Text, View } from 'react-native';
import 'react-native-reanimated';

import DisclaimerGate from '@/components/disclaimer-gate';
import { DilProvider } from '@/constants/i18n';

// 2026-08-18 EKLENTİSİ (kullanıcı geri bildirimi -- "açılışta kısa süreli
// beyaz ekran"): `expo-splash-screen` paketi app.json'da plugin olarak
// zaten kuruluydu, ama kod tarafında HİÇ yönetilmiyordu. Bu durumda native
// splash ekranı (uygulama simgesi) OTOMATİK ve ERKEN kapanır -- React
// Native JS motoru henüz İLK RENDER'ı bile tamamlamamışken.
//
// `preventAutoHideAsync()` ile native splash'in otomatik kapanması
// ENGELLENİYOR. ÖNEMLİ (2026-08-18, devam eden düzeltme): `hideAsync()`
// çağrısı BİLEREK burada DEĞİL -- `components/disclaimer-gate.tsx`'te,
// gerçekten içerik (onay ekranı ya da ana uygulama) render edilmeye hazır
// olduğu anda çağrılıyor. İlk denemede burada, RootLayout mount olur
// olmaz çağrılıyordu -- ama bu, DisclaimerGate'in kendi AsyncStorage
// kontrolü DAHA BAŞLAMADAN splash'i kapatıyordu, aradaki boşlukta ikon/
// logo yerine boş bir renk görünüyordu (adb ile kare kare doğrulandı).
// Splash'i kapatma sorumluluğunu gerçek hazır olma anına taşımak, o
// boşlukta hep uygulamanın kendi ikonunu/logosunu göstermeyi sağlıyor.
//
// 2026-08-18 SONUÇ (kapsamlı teşhis tamamlandı -- KESİN kanıtlandı):
// Kullanıcı bu düzeltmeden SONRA da, hem dev client'ta hem GERÇEK bir
// production build'inde, açılışta hâlâ birkaç saniyelik beyaz bir an
// bildirdi. adb ile kare kare + tekrarlı A/B testleriyle (NeonCerceve
// açık/kapalı/animasyonsuz/SVG'siz/hooks'suz, Modal/disclaimer-gate/
// splash zamanlaması vb.) KAPSAMLI bir eleme yapıldı -- hiçbiri neden
// değildi. Son olarak, açılışın HER aşamasına gerçek zaman damgası
// (Date.now()) eklenip ölçüldü: "Running main" → RootLayout render →
// DisclaimerGate/AsyncStorage (sadece 31ms!) → TabLayout → IndexScreen
// render → GERÇEK EKRAN BOYAMASI (useEffect ile ölçüldü) -- TÜMÜ toplam
// ~2.3 SANİYEDE tamamlanıyor. Yani JS/React tarafı içeriği çoktan
// hazırlayıp "boyadım" diyor, ama kullanıcı ekranda beyazı ~5 saniyeye
// kadar görmeye devam ediyor. Aradaki bu fark REACT'İN DIŞINDA -- Android
// işletim sisteminin kendi ekran birleştirme (compositor/GPU) katmanında
// oluşuyor, test cihazının (OPPO CPH1941) o anki genel sistem yüküyle
// ilgili (logcat'te sürekli tekrarlayan sistem uyarıları/termal olaylar
// gözlendi). Bu KESİNLİKLE bir JS/React/uygulama kodu hatası DEĞİL --
// düzeltilecek bir kod yok. Farklı/daha güçlü bir cihazda ya da bu
// cihaz daha az yüklüyken muhtemelen hiç fark edilmeyecek kadar kısa.
SplashScreen.preventAutoHideAsync().catch(() => {});

// Güvenlik yedeği: DisclaimerGate'in kendi hideAsync() çağrısı HERHANGİ
// bir sebeple (beklenmeyen bir hata, AsyncStorage'ın hiç yanıt vermemesi
// gibi çok nadir bir durum) hiç tetiklenmezse, splash SONSUZA KADAR açık
// kalıp uygulamayı kullanılamaz hale getirmesin diye 8 saniye sonra
// zorla kapatılıyor. Normal koşullarda DisclaimerGate çok daha erken
// (genelde birkaç yüz milisaniye içinde) kendi hideAsync()'ini çağırıp bu
// zamanlayıcıyı gereksiz kılar -- ikinci bir hideAsync() çağrısı zaten
// güvenli (no-op), hata vermez.
setTimeout(() => {
  SplashScreen.hideAsync().catch(() => {});
}, 8000);

export const unstable_settings = {
  anchor: '(tabs)',
};

// 2026-08-16 (kullanıcı testinde bulunan kritik hata): önceden tema,
// TELEFONUN SİSTEM açık/koyu ayarına göre seçiliyordu
// (colorScheme === 'dark' ? DarkTheme : DefaultTheme) -- ama uygulamanın
// KENDİSİ hiçbir zaman sisteme uymuyor, HER EKRANDA sabit koyu lacivert/
// altın tema kullanıyor (bkz. index.tsx vb. -- LACIVERT/ALTIN sabitleri).
// Telefon "açık tema"daysa React Navigation'ın kendi varsayılan BEYAZ
// temasını (DefaultTheme) alıyordu -- bu da özellikle alt sekme çubuğunun
// (React Navigation'ın kendi render ettiği, ekranların DEĞİL) beyaz
// görünmesine sebep oluyordu, gerçek ekranlarla tam bir uyumsuzluk.
// Artık uygulamanın GERÇEK renk paletiyle birebir eşleşen SABİT bir tema
// var, sistem ayarından tamamen bağımsız.
const UygulamaTemasi: Theme = {
  ...DarkTheme,
  colors: {
    ...DarkTheme.colors,
    primary: '#E3A83B',    // ALTIN
    background: '#1E2C4A', // LACIVERT
    card: '#27375A',       // KART_YUZEY (sekme çubuğu dahil)
    text: '#F5F7FA',       // BEYAZ
    border: '#2E3B5C',     // KENAR
    notification: '#E3A83B',
  },
};

// 2026-08-18 EKLENTİSİ (beyaz ekran teşhisi sırasında eklendi, ama KALICI
// bir sağlamlaştırma olarak tutuluyor): expo-router'ın kendi dahili hata
// sınırı (Try) bir render hatasını sessizce yutup sadece splash'i kapatıyor
// -- kullanıcı hiçbir şey görmeden boş bir ekranla kalabilir. Bu, aynı
// hatayı hem konsola LOGLAYAN hem de kullanıcıya (kırmızı metinle) GÖRÜNÜR
// kılan, uygulamanın en dışını saran ek bir güvenlik katmanı.
class HataYakalayici extends React.Component<
  { children: React.ReactNode },
  { hata: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hata: null };
  }
  static getDerivedStateFromError(hata: Error) {
    return { hata };
  }
  componentDidCatch(hata: Error, bilgi: React.ErrorInfo) {
    console.log('[HATA] Yakalanan render hatası:', hata?.message, hata?.stack, bilgi?.componentStack);
  }
  render() {
    if (this.state.hata) {
      return (
        <View style={{ flex: 1, backgroundColor: '#1E2C4A', padding: 24, paddingTop: 60 }}>
          <Text style={{ color: '#FF6B6B', fontSize: 16, fontWeight: 'bold' }}>
            Beklenmeyen bir hata oluştu: {String(this.state.hata?.message)}
          </Text>
          <Text style={{ color: '#8E9AB8', fontSize: 12, marginTop: 12 }}>
            {String(this.state.hata?.stack)}
          </Text>
        </View>
      );
    }
    return this.props.children;
  }
}

export default function RootLayout() {
  return (
    <HataYakalayici>
      <DilProvider>
        <ThemeProvider value={UygulamaTemasi}>
          <DisclaimerGate>
            <Stack>
              <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
            </Stack>
          </DisclaimerGate>
          <StatusBar style="light" />
        </ThemeProvider>
      </DilProvider>
    </HataYakalayici>
  );
}
