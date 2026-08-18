import React from 'react';
import { StyleSheet, View } from 'react-native';

// İki küçük, BİLEREK arma/resmi mühür OLMAYAN dekoratif bayrak işareti.
// Kullanıcının seçtiği referans görsellere göre eklendi.

// 1) Küçük "rozet" -- yuvarlak köşeli, 3 yatay renk bandından oluşan
//    kompakt bir logo/işaret (başlıkta app adının yanında kullanılır).
export function BayrakRozeti({ genislik = 26, yukseklik = 18 }: { genislik?: number; yukseklik?: number }) {
  return (
    <View style={[styles.rozet, { width: genislik, height: yukseklik, borderRadius: yukseklik * 0.22 }]}>
      <View style={[styles.rozetBant, { backgroundColor: '#002B7F' }]} />
      <View style={[styles.rozetBant, { backgroundColor: '#FCD116' }]} />
      <View style={[styles.rozetBant, { backgroundColor: '#CE1126' }]} />
    </View>
  );
}

// 2) Üç noktalı işaret -- alt başlığın yanında küçük bir süsleme.
export function BayrakNoktalari({ boyut = 6 }: { boyut?: number }) {
  return (
    <View style={styles.noktaSatir}>
      <View style={[styles.nokta, { width: boyut, height: boyut, borderRadius: boyut / 2, backgroundColor: '#4A6FA5' }]} />
      <View style={[styles.nokta, { width: boyut, height: boyut, borderRadius: boyut / 2, backgroundColor: '#FCD116' }]} />
      <View style={[styles.nokta, { width: boyut, height: boyut, borderRadius: boyut / 2, backgroundColor: '#E4536B' }]} />
    </View>
  );
}

const styles = StyleSheet.create({
  // 2026-08-15: koyu lacivert/antrasit + altın temasıyla, üstteki simgenin
  // çerçevesi altın/hardal sarısı yapıldı (kullanıcının tarif ettiği
  // referansta "kalkan simgesinin çerçevesi" altın).
  rozet: {
    flexDirection: 'row',
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: '#E3A83B',
  },
  rozetBant: { flex: 1 },
  noktaSatir: { flexDirection: 'row', gap: 4, alignItems: 'center' },
  nokta: {},
});
