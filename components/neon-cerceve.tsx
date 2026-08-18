import React, { useEffect, useRef, useState } from 'react';
import { Animated, LayoutChangeEvent, StyleSheet, View } from 'react-native';
import Svg, { Rect } from 'react-native-svg';

// react-native-svg'nin Rect'i, animasyonlu prop'lar (strokeDashoffset) için
// Animated.createAnimatedComponent ile sarılması gerekiyor -- normal <Rect>
// bir Animated.Value'yu doğrudan prop olarak kabul etmez.
const AnimatedRect = Animated.createAnimatedComponent(Rect);

// Sekme çubuğunun İÇERİK yüksekliği (ikon+etiket, güvenli alan payı HARİÇ).
// app/(tabs)/_layout.tsx, sekme çubuğunun `tabBarStyle.height`'ini de
// BİZZAT AYNI sabitle belirliyor.
export const SEKME_CUBUGU_ICERIK_YUKSEKLIGI = 58;

// ---------------------------------------------------------------------------
// NEON ÇERÇEVE (2026-08-16, kullanıcı isteğiyle eklendi)
// ---------------------------------------------------------------------------
// react-native-svg ile, üst üste binen ve dışa doğru azalan opaklıkta
// dikdörtgenler çizerek tüm ekranı (üst/sağ/alt/sol) saran ışıklı bir
// çerçeve -- SorguSovu'daki (bkz. components/sorgu-sovu.tsx) nabız
// halkasıyla AYNI teknik. Native shadow API'sine bağımlı değil, Android'de
// de garanti görünür.
//
// 2026-08-17 DÜZELTME GEÇMİŞİ (5 tur): Sekme çubuğunun üstünde "kapalı"
// bir dikdörtgenle durdurmayı denedim (canlı cihazda piksel piksel ölçüm
// yaparak) ama sekme çubuğunun GERÇEK render yüksekliği ile hesaplanan
// değer arasında küçük, tutarsız farklar çıkmaya devam etti -- her
// düzeltme ya boşluk bıraktı ya da tam oturmadı. KESİN, SAĞLAM çözüm:
// karmaşık yükseklik hesabından tamamen vazgeçildi. Çerçeve artık YİNE
// gerçek fiziksel alt kenara kadar iniyor (tüm katmanlar), ama:
// (a) en kalın katmanların genişliği ikonlara değmeyecek ölçüde
//     düşürüldü (30→16, komet halesi 16→8),
// (b) app/(tabs)/_layout.tsx'te sekme çubuğuna eklenen `paddingTop: 8`
//     ikonlara zaten yukarıdan pay veriyor, ışımanın en yoğun kısmı bu
//     boşluğa denk geliyor.
// Canlı cihazda (adb screencap ile) piksel piksel doğrulandı.
export default function NeonCerceve({
  renk = '#E3A83B',
  kirmiziRenk = '#FF3345',
}: {
  renk?: string;
  kirmiziRenk?: string;
}) {
  const [olculenBoyut, setOlculenBoyut] = useState<{ width: number; height: number } | null>(null);

  const boyutuOlc = (olay: LayoutChangeEvent) => {
    const { width: w, height: h } = olay.nativeEvent.layout;
    setOlculenBoyut((onceki) => (onceki && onceki.width === w && onceki.height === h ? onceki : { width: w, height: h }));
  };

  const width = olculenBoyut?.width ?? 0;
  const height = olculenBoyut?.height ?? 0;

  const cevre = 2 * (width + height);
  const kometUzunlugu = cevre * 0.07;
  const bosluk = Math.max(cevre - kometUzunlugu, 1);
  const donusDeger = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (!olculenBoyut) return;
    donusDeger.setValue(0);
    const animasyon = Animated.loop(
      Animated.timing(donusDeger, {
        toValue: -cevre,
        duration: 5500,
        useNativeDriver: false,
      })
    );
    animasyon.start();
    return () => animasyon.stop();
  }, [cevre, donusDeger, olculenBoyut]);

  const ortakOzellikler = { x: 0, y: 0, width, height, fill: 'none' };
  const kometOzellikleri = {
    ...ortakOzellikler,
    stroke: kirmiziRenk,
    strokeDasharray: `${kometUzunlugu} ${bosluk}`,
    strokeDashoffset: donusDeger,
    strokeLinecap: 'round' as const,
  };

  return (
    <View style={StyleSheet.absoluteFillObject} pointerEvents="none" onLayout={boyutuOlc}>
      {olculenBoyut && (
        <Svg width={width} height={height} style={StyleSheet.absoluteFillObject}>
          {/* ALTIN -- en dıştan içe. 2026-08-17: en kalın katman 30→16'ya
              indirildi ki alt kenarda sekme çubuğu ikonlarına değmesin. */}
          <Rect {...ortakOzellikler} stroke={renk} strokeOpacity={0.08} strokeWidth={16} />
          <Rect {...ortakOzellikler} stroke={renk} strokeOpacity={0.15} strokeWidth={10} />
          <Rect {...ortakOzellikler} stroke={renk} strokeOpacity={0.28} strokeWidth={6} />
          <Rect {...ortakOzellikler} stroke={renk} strokeOpacity={0.5} strokeWidth={3} />
          <Rect {...ortakOzellikler} stroke="#FFDA8A" strokeOpacity={0.95} strokeWidth={1.5} />

          {/* KIRMIZI KOMET -- sürekli dönen kısa şerit, dört köşeyi de
              dolaşıyor. 3 katman, ince tutuldu. */}
          <AnimatedRect {...kometOzellikleri} strokeOpacity={0.18} strokeWidth={6} />
          <AnimatedRect {...kometOzellikleri} strokeOpacity={0.42} strokeWidth={3.5} />
          <AnimatedRect {...kometOzellikleri} stroke="#FFB3B8" strokeOpacity={0.98} strokeWidth={2} />
        </Svg>
      )}
    </View>
  );
}
