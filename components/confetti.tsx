import React, { useEffect, useMemo, useRef } from 'react';
import { Animated, Dimensions, StyleSheet, View } from 'react-native';

// "ORDINE" (onay) eşleşmesi bulunduğunda kutlama amaçlı bir konfeti yağmuru.
// Yeni bir npm paketi eklemeden (react-native-confetti-cannon vb. bir kurulum
// gerektirirdi, bu ortamdan npm install çalıştıramıyoruz) React Native'in
// kendi Animated API'siyle yazıldı -- ek bağımlılık yok.
//
// Kullanım: sonuçlarda bir "onay" (ordine eşleşmesi) bulunduğunda, index.tsx
// bu bileşeni birkaç saniyeliğine `key` propunu değiştirerek render eder --
// her yeni onay sonucunda animasyon baştan tetiklenir.

const { width: EKRAN_GENISLIK, height: EKRAN_YUKSEKLIK } = Dimensions.get('window');
// 2026-08-15: koyu lacivert/antrasit + altın + yeşil temasıyla güncellendi
// -- bu konfeti SADECE "ONAYLANDI" (artık yeşil kurdele) anında
// tetiklendiği için renkler altın + yeşil (indirme butonuyla aynı aile) +
// beyaza çevrildi, kırmızı paletten tamamen çıkarıldı.
const RENKLER = ['#E3A83B', '#1E7A4C', '#F5F7FA', '#8DD6AE'];
const PARCA_SAYISI = 40;

type Parca = {
  x: number;
  renk: string;
  genislik: number;
  yukseklik: number;
  gecikme: number;
  sure: number;
  donusYonu: number;
  savrulmaMesafesi: number;
};

function parcalariUret(): Parca[] {
  return Array.from({ length: PARCA_SAYISI }, () => {
    const dikey = Math.random() > 0.5;
    return {
      x: Math.random() * EKRAN_GENISLIK,
      renk: RENKLER[Math.floor(Math.random() * RENKLER.length)],
      genislik: dikey ? 6 + Math.random() * 4 : 9 + Math.random() * 5,
      yukseklik: dikey ? 10 + Math.random() * 6 : 6 + Math.random() * 3,
      gecikme: Math.random() * 450,
      sure: 2200 + Math.random() * 1600,
      donusYonu: Math.random() > 0.5 ? 1 : -1,
      savrulmaMesafesi: 16 + Math.random() * 34,
    };
  });
}

function KonfettiParcasi({ parca }: { parca: Parca }) {
  const ilerleme = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const animasyon = Animated.timing(ilerleme, {
      toValue: 1,
      duration: parca.sure,
      delay: parca.gecikme,
      useNativeDriver: true,
    });
    animasyon.start();
    return () => animasyon.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const translateY = ilerleme.interpolate({
    inputRange: [0, 1],
    outputRange: [-20, EKRAN_YUKSEKLIK + 20],
  });
  const translateX = ilerleme.interpolate({
    inputRange: [0, 0.25, 0.5, 0.75, 1],
    outputRange: [
      0,
      parca.donusYonu * parca.savrulmaMesafesi,
      0,
      -parca.donusYonu * parca.savrulmaMesafesi,
      0,
    ],
  });
  const rotate = ilerleme.interpolate({
    inputRange: [0, 1],
    outputRange: ['0deg', `${parca.donusYonu * 620}deg`],
  });
  const opacity = ilerleme.interpolate({
    inputRange: [0, 0.05, 0.85, 1],
    outputRange: [0, 1, 1, 0],
  });

  return (
    <Animated.View
      style={{
        position: 'absolute',
        left: parca.x,
        width: parca.genislik,
        height: parca.yukseklik,
        backgroundColor: parca.renk,
        borderRadius: 2,
        opacity,
        transform: [{ translateY }, { translateX }, { rotate }],
      }}
    />
  );
}

export default function KonfettiYagmuru() {
  const parcalar = useMemo(() => parcalariUret(), []);
  return (
    <View style={StyleSheet.absoluteFillObject} pointerEvents="none">
      {parcalar.map((p, i) => (
        <KonfettiParcasi key={i} parca={p} />
      ))}
    </View>
  );
}
