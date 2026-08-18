import AsyncStorage from '@react-native-async-storage/async-storage';
import React, { useEffect, useState } from 'react';
import { Modal, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { BayrakRozeti, BayrakNoktalari } from '@/components/flag-mark';
import LanguageSwitcher from '@/components/language-switcher';
import Yapraklar from '@/components/yapraklar';
import { useDil } from '@/constants/i18n';

// Bu sürüm numarasını artırırsan (v2, v3...) kullanıcıya onay ekranı
// tekrar gösterilir -- metni önemli ölçüde değiştirirsen bunu kullan.
// Not: onay durumu dilden bağımsızdır -- kullanıcı hangi dilde okuyup kabul
// ettiyse bir daha sorulmaz, sadece görüntülenen dil değişir.
const ONAY_ANAHTARI = 'sorumluluk_reddi_onaylandi_v1';

// 2026-08-15: ana ekranla (index.tsx) BİREBİR aynı koyu lacivert/antrasit +
// altın tema -- daha önce bu ekran eski (emerald) temada kalmıştı, kullanıcı
// isteğiyle senkronize edildi (aynı tam genişlik başlık + Yapraklar + koyu
// kart yaklaşımı).
const LACIVERT = '#1E2C4A';
const KART_YUZEY = '#27375A';
const ALTIN = '#E3A83B';
const BEYAZ = '#F5F7FA';
const GRI = '#8E9AB8';
const KENAR = '#2E3B5C';

export default function DisclaimerGate({ children }: { children: React.ReactNode }) {
  const { t } = useDil();
  const [gosterilsin, setGosterilsin] = useState(false);
  const [yukleniyor, setYukleniyor] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const deger = await AsyncStorage.getItem(ONAY_ANAHTARI);
        setGosterilsin(deger !== 'evet');
      } catch {
        setGosterilsin(true);
      } finally {
        setYukleniyor(false);
      }
    })();
  }, []);

  const kabulEt = async () => {
    try {
      await AsyncStorage.setItem(ONAY_ANAHTARI, 'evet');
    } catch {
      // AsyncStorage'a yazılamazsa bile kullanıcıyı bir sonraki açılışta
      // tekrar bilgilendirmek zarar vermez -- sessizce devam ediyoruz.
    }
    setGosterilsin(false);
  };

  // AsyncStorage kontrolü bitene kadar hiçbir şey gösterme (kısa an için
  // ana ekranın "yanıp sönmesini" engeller).
  if (yukleniyor) {
    return null;
  }

  return (
    <>
      {children}
      <Modal visible={gosterilsin} animationType="fade" transparent={false}>
        <View style={styles.disKapsayici}>
          {/* Ana ekranla (index.tsx) BİREBİR aynı: tam genişlik, köşesiz,
              düz lacivert başlık + arkasında yavaşça süzülen yapraklar. */}
          <View style={styles.hero}>
            <Yapraklar />
            <LanguageSwitcher varyant="koyu" />
            <View style={styles.appAdiSatir}>
              <BayrakRozeti />
              <Text style={styles.heroBaslik}>{t.appAdi}</Text>
            </View>
            <BayrakNoktalari />
          </View>
          <View style={styles.kart}>
            <ScrollView contentContainerStyle={styles.scroll}>
              <Text style={styles.baslik}>{t.disclaimerBaslik}</Text>
              <Text style={styles.metin}>{t.disclaimerMetin}</Text>
            </ScrollView>
            <TouchableOpacity style={styles.buton} onPress={kabulEt}>
              <Text style={styles.butonMetin}>{t.disclaimerButon}</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  disKapsayici: { flex: 1, backgroundColor: LACIVERT },
  hero: {
    backgroundColor: LACIVERT,
    paddingTop: 54,
    paddingHorizontal: 20,
    paddingBottom: 20,
    // 2026-08-16: "overflow: hidden" kaldırıldı -- dil seçici açılır
    // menüsünü (bkz. language-switcher.tsx) kesmesin diye (bkz.
    // app/(tabs)/index.tsx heroKart'taki aynı düzeltme notu). Yapraklar
    // kendi kırpmasını kendi içinde yapıyor artık.
    position: 'relative',
  },
  appAdiSatir: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, marginTop: 16 },
  heroBaslik: { fontSize: 18, fontWeight: 'bold', color: '#fff' },
  kart: {
    flex: 1,
    backgroundColor: KART_YUZEY,
    borderRadius: 18,
    marginHorizontal: 16,
    marginTop: 18,
    marginBottom: 20,
    paddingHorizontal: 20,
    paddingTop: 20,
    borderWidth: 1,
    borderColor: KENAR,
    overflow: 'hidden',
  },
  scroll: { paddingBottom: 20 },
  baslik: { fontSize: 20, fontWeight: 'bold', marginBottom: 14, color: BEYAZ },
  metin: { fontSize: 15, lineHeight: 23, color: GRI },
  buton: {
    backgroundColor: ALTIN,
    padding: 16,
    borderRadius: 12,
    alignItems: 'center',
    marginVertical: 18,
    shadowColor: ALTIN,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.35,
    shadowRadius: 10,
    elevation: 4,
  },
  butonMetin: { color: LACIVERT, fontSize: 16, fontWeight: 'bold' },
});
