import React from 'react';
import { StyleSheet, View } from 'react-native';

// Ekranın en üstünde ince bir Romanya bayrağı renk şeridi (lacivert/altın
// dışında, uygulamaya "havalı"/canlı bir dokunuş katmak için). BİLEREK bir
// arma/resmi mühür DEĞİL -- sadece 3 düz renk bloğu, Faz 0'da kararlaştırılan
// "bayrak renklerinden ilham al ama resmi amblem kullanma" ilkesine uygun.
export default function BayrakSeridi() {
  return (
    <View style={styles.satir}>
      <View style={[styles.blok, { backgroundColor: '#002B7F' }]} />
      <View style={[styles.blok, { backgroundColor: '#FCD116' }]} />
      <View style={[styles.blok, { backgroundColor: '#CE1126' }]} />
    </View>
  );
}

const styles = StyleSheet.create({
  satir: { flexDirection: 'row', height: 5, width: '100%' },
  blok: { flex: 1 },
});
