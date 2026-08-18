import { useFocusEffect } from '@react-navigation/native';
import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  Linking,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
// bkz. index.tsx'teki 2026-08-15 notu -- react-native'in SafeAreaView'ı
// Android'de çalışmıyor, bu yüzden react-native-safe-area-context'ten
// alınıyor.
import { SafeAreaView } from 'react-native-safe-area-context';

import { apiIstek, cihazKimligiGetir } from '@/constants/api';
import { useDil } from '@/constants/i18n';

// "Favorilerim" ekranı (Faz 2) -- kullanıcının ana ekranda bir sonuca
// dokunarak eklediği dosya numaralarının GÜNCEL durumunu tek ekranda
// gösterir. Backend zaten /api/favorilerim uç noktasını sağlıyor (bkz.
// backend/main.py); bu ekran sadece görüntülüyor + ekleme/çıkarma.
//
// Kimlik: gerçek push bildirimleri henüz kurulmadığı için (ayrı bir native
// paket + EAS proje kurulumu gerektiriyor, sonraki aşama), bu cihaza özel
// rastgele bir kimlik (bkz. constants/api.ts) "expo_push_token" alanı
// olarak kullanılıyor -- favorileri doğru şekilde eşleştirmek için yeterli,
// sadece push bildirimi göndermek için henüz gerçek bir token değil.

type FavoriSonuc = {
  ana_kategori: string;
  alt_kategori: string;
  mesaj: string;
  eslesti: boolean;
  dosya_no?: string | null;
  resmi_pdf_url?: string | null;
  yerel_pdf_url?: string | null;
};

type FavoriKaydi = {
  dosya_no: string;
  // 2026-08-16: favorinin kaydedildiği SPESİFİK yıl -- silme işleminde de
  // aynı kaydı hedeflemek için gerekiyor (bkz. favoridenCikar notu).
  yil: string | null;
  bulundu: boolean;
  sonuclar: FavoriSonuc[];
};

type DurumTipi = 'onay' | 'islemde' | 'bulunamadi';

function durumTipiGetir(s: FavoriSonuc): DurumTipi {
  if (s.eslesti && s.ana_kategori === 'ordine') return 'onay';
  if (s.eslesti && s.ana_kategori === 'stadiu') return 'islemde';
  return 'bulunamadi';
}

// 2026-08-16 (düzeltme): önceden backend'in DB'ye o an kaydettiği HAM
// 'mesaj' metni doğrudan gösteriliyordu -- bu hem her zaman Türkçe kalıyordu
// (uygulamanın dil seçimini yok sayıyordu) hem de mesaj metnini değiştirmek
// binlerce eski veritabanı kaydını güncellemeyi gerektiriyordu. index.tsx'te
// olduğu gibi, mesaj artık İSTEMCİ tarafında, seçili dile göre üretiliyor.
function sonucMetniGetir(s: FavoriSonuc, t: any): string {
  const tip = durumTipiGetir(s);
  if (tip === 'onay') return t.sonucMesaji.ordine;
  if (tip === 'islemde') return t.sonucMesaji.stadiu;
  return t.sonucBulunamadi;
}

// 2026-08-15: ana ekranla (index.tsx) BİREBİR aynı koyu lacivert/antrasit +
// altın + yeşil paleti.
const LACIVERT = '#1E2C4A';
const KART_YUZEY = '#27375A';
const ALTIN = '#E3A83B';
const BEYAZ = '#F5F7FA';
const GRI = '#8E9AB8';
const YESIL_INDIR = '#1E7A4C';
const ZEMIN = LACIVERT;
const KENAR = '#2E3B5C';

const RIBBON_RENK: Record<DurumTipi, string> = {
  onay: YESIL_INDIR,
  islemde: ALTIN,
  bulunamadi: '#4A5573',
};
// Altın zeminde beyaz metin okunaklı değil -- durum başına ayrı metin rengi.
const RIBBON_METIN_RENK: Record<DurumTipi, string> = {
  onay: '#fff',
  islemde: LACIVERT,
  bulunamadi: '#fff',
};
const DURUM_IKONU: Record<DurumTipi, string> = { onay: '✅', islemde: '⏳', bulunamadi: '⚪' };

export default function FavorilerimEkrani() {
  const { t } = useDil();
  const [favoriler, setFavoriler] = useState<FavoriKaydi[] | null>(null);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState(false);
  const [yenileniyorMu, setYenileniyorMu] = useState(false);

  const yukle = useCallback(async (arkaPlanda = false) => {
    if (!arkaPlanda) setYukleniyor(true);
    setHata(false);
    try {
      const kimlik = await cihazKimligiGetir();
      const yanit = await apiIstek(`/api/favorilerim?token=${encodeURIComponent(kimlik)}`);
      const veri = await yanit.json();
      setFavoriler(veri.favoriler || []);
    } catch {
      setHata(true);
    } finally {
      setYukleniyor(false);
      setYenileniyorMu(false);
    }
  }, []);

  // Sekme her odaklandığında (ör. ana ekrandan favori eklendikten sonra bu
  // sekmeye geçildiğinde) listeyi tazeler.
  useFocusEffect(
    useCallback(() => {
      yukle(true);
    }, [yukle])
  );

  // 2026-08-16: 'yil' de gönderiliyor -- backend artık favorileri
  // dosya_no_norm + yil ikilisiyle eşleştiriyor (bkz. backend/main.py
  // favori_sil notu), sadece dosya_no yeterli değil.
  const favoridenCikar = async (dosyaNo: string, yil: string | null) => {
    try {
      const kimlik = await cihazKimligiGetir();
      await apiIstek('/api/favori-sil', {
        method: 'POST',
        body: JSON.stringify({ expo_push_token: kimlik, dosya_no: dosyaNo, yil }),
      });
      setFavoriler((onceki) =>
        onceki ? onceki.filter((f) => !(f.dosya_no === dosyaNo && f.yil === yil)) : onceki
      );
    } catch {
      // Sessizce yok say -- kullanıcı "Yenile" ile tekrar deneyebilir.
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl refreshing={yenileniyorMu} onRefresh={() => { setYenileniyorMu(true); yukle(true); }} tintColor={LACIVERT} />
        }
      >
        <Text style={styles.baslik}>⭐ {t.sekmeFavorilerim}</Text>
        <Text style={styles.aciklama}>{t.favorilerimAciklama}</Text>

        {yukleniyor && (
          <View style={styles.ortaKutu}>
            <ActivityIndicator color={LACIVERT} />
            <Text style={styles.durumMetni}>{t.favorilerimYukleniyor}</Text>
          </View>
        )}

        {!yukleniyor && hata && (
          <View style={styles.ortaKutu}>
            <Text style={styles.durumMetni}>{t.favorilerimHata}</Text>
          </View>
        )}

        {!yukleniyor && !hata && favoriler && favoriler.length === 0 && (
          <View style={styles.ortaKutu}>
            <Text style={styles.bosBaslik}>{t.favorilerimBosBaslik}</Text>
            <Text style={styles.durumMetni}>{t.favorilerimBosMetin}</Text>
          </View>
        )}

        {!yukleniyor && !hata && favoriler && favoriler.map((fav) => (
          <View key={`${fav.dosya_no}|${fav.yil || ''}`} style={styles.kart}>
            <View style={styles.kartUst}>
              <Text style={styles.kartBaslik}>{fav.dosya_no}</Text>
              <TouchableOpacity onPress={() => favoridenCikar(fav.dosya_no, fav.yil)} style={styles.cikarButon}>
                <Text style={styles.cikarButonMetin}>✕ {t.favoridenCikarButon}</Text>
              </TouchableOpacity>
            </View>
            {fav.bulundu ? (
              fav.sonuclar.map((s, i) => {
                const tip = durumTipiGetir(s);
                return (
                  <View key={i} style={styles.sonucSatiri}>
                    <View style={[styles.rozet, { backgroundColor: RIBBON_RENK[tip] }]}>
                      <Text style={[styles.rozetMetin, { color: RIBBON_METIN_RENK[tip] }]}>
                        {DURUM_IKONU[tip]} {s.ana_kategori?.toUpperCase()}
                      </Text>
                    </View>
                    {/* 2026-08-15: aynı favori numarası birden fazla (farklı
                        yıl/kategori) gerçek dosyayla eşleşebiliyor -- hangisi
                        olduğunu gözle ayırt edebilmek için tam eşleşen
                        numara gösteriliyor (bkz. index.tsx'teki aynı not). */}
                    {tip !== 'bulunamadi' && s.dosya_no ? (
                      <Text style={styles.eslesenNo}>Eşleşen numara: {s.dosya_no}</Text>
                    ) : null}
                    <Text style={styles.sonucMesaji}>{sonucMetniGetir(s, t)}</Text>
                    {tip !== 'bulunamadi' && s.resmi_pdf_url ? (
                      <TouchableOpacity onPress={() => Linking.openURL(s.resmi_pdf_url!)}>
                        <Text style={styles.linkMetin}>{t.resmiBelgeButon}</Text>
                      </TouchableOpacity>
                    ) : null}
                  </View>
                );
              })
            ) : (
              <Text style={styles.durumMetni}>{t.favorilerimHenuzSonucYok}</Text>
            )}
          </View>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: ZEMIN },
  scrollContent: { padding: 20, paddingTop: 24 },
  baslik: { fontSize: 22, fontWeight: 'bold', color: BEYAZ, marginBottom: 4 },
  aciklama: { fontSize: 13, color: GRI, marginBottom: 18, lineHeight: 19 },
  ortaKutu: { alignItems: 'center', paddingVertical: 40, gap: 8 },
  bosBaslik: { fontSize: 16, fontWeight: '700', color: BEYAZ, marginBottom: 4 },
  durumMetni: { fontSize: 13, color: GRI, textAlign: 'center', paddingHorizontal: 20 },
  kart: {
    backgroundColor: KART_YUZEY, borderRadius: 16, padding: 16, marginBottom: 14,
    borderWidth: 1, borderColor: KENAR,
  },
  kartUst: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  kartBaslik: { fontSize: 16, fontWeight: '800', color: BEYAZ },
  cikarButon: { paddingVertical: 5, paddingHorizontal: 10, borderRadius: 8, backgroundColor: '#2E1B22' },
  cikarButonMetin: { fontSize: 11.5, color: '#E4536B', fontWeight: '700' },
  sonucSatiri: { marginTop: 6, paddingTop: 10, borderTopWidth: 1, borderTopColor: KENAR },
  rozet: { alignSelf: 'flex-start', paddingVertical: 4, paddingHorizontal: 10, borderRadius: 8, marginBottom: 6 },
  rozetMetin: { fontSize: 11, fontWeight: '800' },
  eslesenNo: { fontSize: 12, fontWeight: '700', color: ALTIN, marginBottom: 4 },
  sonucMesaji: { fontSize: 13.5, color: BEYAZ, lineHeight: 19 },
  linkMetin: { fontSize: 12.5, color: ALTIN, fontWeight: '600', textDecorationLine: 'underline', marginTop: 6 },
});
