import { Tabs } from 'expo-router';
import React from 'react';
import { View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { HapticTab } from '@/components/haptic-tab';
import NeonCerceve, { SEKME_CUBUGU_ICERIK_YUKSEKLIGI } from '@/components/neon-cerceve';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { useDil } from '@/constants/i18n';

// 2026-08-16: sekme çubuğu rengi artık TELEFONUN sistem açık/koyu ayarına
// (Colors[colorScheme].tint) DEĞİL, uygulamanın kendi SABİT koyu lacivert/
// altın paletine bağlı -- app/_layout.tsx'teki ThemeProvider düzeltmesiyle
// aynı gerekçe (bkz. o dosyadaki not): uygulama hiçbir zaman sisteme
// uymuyor, hep aynı tema. Eskiden sistem "açık"taysa aktif sekme rengi de
// LACİVERT oluyordu -- lacivert zemin üzerinde lacivert ikon, neredeyse
// görünmezdi.
const ALTIN = '#E3A83B';
const GRI = '#8E9AB8';
const KART_YUZEY = '#27375A';
const KENAR = '#2E3B5C';

export default function TabLayout() {
  const { t } = useDil();
  const guvenliAlan = useSafeAreaInsets();

  return (
    // 2026-08-16 (kullanıcı geri bildirimi): neon çerçeve önceden SADECE
    // index.tsx'in kendi SafeAreaView'ı içindeydi -- bu yüzden (a) alt
    // sekme çubuğunu (Tabs navigator'ın kendi render ettiği, tek tek
    // ekranların DIŞINDA bir bileşen) hiç kapsamıyordu, (b) diğer 3 sekmede
    // hiç görünmüyordu. Artık TÜM <Tabs> navigator'ının (sekme çubuğu
    // dahil) üzerine, TEK bir yerden, tüm sekmelerde ORTAK olacak şekilde
    // ekleniyor -- her ekranın kendi dosyasına ayrı ayrı eklemeye gerek yok.
    //
    // 2026-08-17 DÜZELTME (5. tur, KESİN çözüm): Sekme çubuğunun yüksekliğini
    // React Navigation'dan bağımsız hesaplayıp NeonCerceve'i tam onun
    // üstünde durdurmaya çalışmak, canlı cihazda piksel piksel ölçüme
    // rağmen tutarlı bir sonuç vermedi (küçük ama inatçı farklar). Bunun
    // yerine NeonCerceve tekrar TAM ekranı (gerçek alt kenara kadar)
    // kaplıyor, ama ince tutuldu; burada sadece ikonlara nefes payı vermek
    // için `paddingTop` ekleniyor -- karmaşık yükseklik eşleştirmesine
    // artık gerek yok.
    <View style={{ flex: 1 }}>
      <Tabs
        screenOptions={{
          tabBarActiveTintColor: ALTIN,
          tabBarInactiveTintColor: GRI,
          tabBarStyle: {
            backgroundColor: KART_YUZEY,
            borderTopColor: KENAR,
            height: SEKME_CUBUGU_ICERIK_YUKSEKLIGI + guvenliAlan.bottom,
            paddingTop: 10,
            paddingBottom: guvenliAlan.bottom,
          },
          headerShown: false,
          tabBarButton: HapticTab,
        }}>
        <Tabs.Screen
          name="index"
          options={{
            title: t.sekmeAnaSayfa,
            tabBarIcon: ({ color }) => <IconSymbol size={28} name="house.fill" color={color} />,
          }}
        />
        {/* 2026-08-16: İstatistikler sekmesi -- kullanıcı isteğiyle eklendi
            (bkz. app/(tabs)/istatistikler.tsx üstündeki not). Kullanıcı
            isteğiyle ortaya, Favorilerim'in önüne alındı. */}
        <Tabs.Screen
          name="istatistikler"
          options={{
            title: t.sekmeIstatistikler,
            tabBarIcon: ({ color }) => <IconSymbol size={28} name="chart.bar.fill" color={color} />,
          }}
        />
        <Tabs.Screen
          name="favorilerim"
          options={{
            title: t.sekmeFavorilerim,
            tabBarIcon: ({ color }) => <IconSymbol size={28} name="star.fill" color={color} />,
          }}
        />
        {/* 2026-08-16: "Yasal Metin" sekmesi -- kullanıcı isteğiyle, ilk
            açılışta gösterilen sorumluluk reddi metnine kalıcı erişim için
            eklendi (bkz. app/(tabs)/yasal-metin.tsx üstündeki not). En sağda. */}
        <Tabs.Screen
          name="yasal-metin"
          options={{
            title: t.sekmeYasalMetin,
            tabBarIcon: ({ color }) => <IconSymbol size={28} name="doc.text.fill" color={color} />,
          }}
        />
      </Tabs>
      <NeonCerceve />
    </View>
  );
}
