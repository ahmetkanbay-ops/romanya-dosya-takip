import { DarkTheme, ThemeProvider, Theme } from '@react-navigation/native';
import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
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

export default function RootLayout() {
  return (
    <DilProvider>
      <ThemeProvider value={UygulamaTemasi}>
        <DisclaimerGate>
          <Stack>
            <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
            <Stack.Screen name="modal" options={{ presentation: 'modal', title: 'Modal' }} />
          </Stack>
        </DisclaimerGate>
        <StatusBar style="light" />
      </ThemeProvider>
    </DilProvider>
  );
}
