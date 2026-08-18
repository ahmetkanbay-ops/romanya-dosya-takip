import { DarkTheme, ThemeProvider, Theme } from '@react-navigation/native';
import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import 'react-native-reanimated';

import DisclaimerGate from '@/components/disclaimer-gate';
import { DilProvider } from '@/constants/i18n';

// 2026-08-18 EKLENTİSİ (kullanıcı geri bildirimi -- "açılışta kısa süreli
// beyaz ekran"): `expo-splash-screen` paketi app.json'da plugin olarak
// zaten kuruluydu, ama kod tarafında HİÇ yönetilmiyordu. Bu durumda native
// splash ekranı (uygulama simgesi) OTOMATİK ve ERKEN kapanır -- React
// Native JS motoru henüz İLK RENDER'ı bile tamamlamamışken. Native splash
// ile gerçek içerik (RootLayout'un render ettiği koyu lacivert arayüz)
// arasındaki bu boşlukta, hazırlanmamış/boş bir View (varsayılan beyaz
// arka plan) kısa bir an görünüyordu.
//
// Çözüm: `preventAutoHideAsync()` ile native splash'in otomatik kapanması
// ENGELLENİYOR, `RootLayout` mount olduğunda (JS render'ı GERÇEKTEN
// tamamlandığında) `hideAsync()` ile MANUEL kapatılıyor. Böylece geçiş
// splash'ten DOĞRUDAN hazır içeriğe oluyor, aradaki beyaz an ortadan
// kalkıyor. Hata olursa (nadiren, ör. zaten gizliyse) sessizce yutuluyor
// -- bu kozmetik bir iyileştirme, asla uygulamanın açılmasını engellememeli.
SplashScreen.preventAutoHideAsync().catch(() => {});

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
  useEffect(() => {
    // JS render'ı buraya kadar tamamlandı (component mount oldu) --
    // native splash'i şimdi güvenle kapatabiliriz.
    SplashScreen.hideAsync().catch(() => {});
  }, []);

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
