import Constants from 'expo-constants';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as SecureStore from 'expo-secure-store';

// YEDEK (fallback) yerel IP -- Faz 3'te Render'a taşındığında bu satır ve
// aşağıdaki otomatik tespit mekanizması tamamen ortadan kalkacak. Sadece
// aşağıdaki otomatik tespit BAŞARISIZ olursa (ör. tunnel modunda, bkz. not)
// kullanılıyor -- elle güncel tutulması artık ZORUNLU DEĞİL.
const YEDEK_YEREL_IP = '192.168.1.12';

// 2026-08-16 (beşinci ve KALICI çözüm -- kullanıcı isteğiyle): önceden bu IP
// her ağ değişiminde (Wi-Fi/Ethernet arasında geçiş, DHCP yeniden atama, vb.)
// ELLE güncellenmesi gerekiyordu -- bu oturumda 4 kez sorun çıkardı. Artık
// Expo'nun kendi bildiği bağlantı adresinden (expo-constants) OTOMATİK
// okunuyor: Expo Go/dev client, Metro'ya hangi host üzerinden bağlandıysa
// (ör. "192.168.1.12:8081") bunu zaten biliyor -- biz de backend'in AYNI
// bilgisayarda çalıştığını varsayıp sadece portu (10000) değiştirip
// kullanıyoruz. Böylece ağ değiştiğinde KOD DEĞİŞİKLİĞİ GEREKMİYOR.
//
// İSTİSNA: "--tunnel" modunda (uzak ağ/firewall sorunları için kullanılan
// Expo bulut röle modu) bu adres artık bir IP değil, "*.exp.direct" gibi bir
// tünel adı oluyor -- o zaman portu değiştirip kullanmak ANLAMSIZ (backend'in
// kendisi tünellenmiyor, sadece Metro tünelleniyor). Bu durumda YEDEK_YEREL_IP'ye
// düşülüyor -- tunnel modunda hâlâ telefon+bilgisayarın AYNI yerel ağda
// olması gerekiyor (backend tünellenmediği için), bu durumda yukarıdaki
// yedek IP'yi elle güncel tutman gerekir.
function otomatikApiTabanTespitEt(): string {
  const hostUri = Constants.expoConfig?.hostUri || (Constants as any).manifest2?.extra?.expoGo?.debuggerHost;
  if (hostUri && typeof hostUri === 'string') {
    const ip = hostUri.split(':')[0];
    // Basit IPv4 kontrolü -- tünel modundaki host adları (harf içerir) bunu geçemez.
    if (/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(ip)) {
      return `http://${ip}:10000`;
    }
  }
  return `http://${YEDEK_YEREL_IP}:10000`;
}

// 2026-08-19 (Render'a taşıma): "preview"/"production" build profilleri
// (bkz. eas.json "env" alanları), EXPO_PUBLIC_API_TABAN'ı Render'ın gerçek
// adresine sabitliyor -- bu build'lerde artık yerel IP tahmini/otomatik
// tespit HİÇ devreye girmiyor. Bu değişken ayarlanmadığında (yerel `npm
// start`/Metro geliştirme, ya da "development" build profili) davranış
// TAMAMEN ESKİSİ GİBİ kalır -- otomatik yerel IP tespiti/yedek IP.
const SABIT_API_TABAN = process.env.EXPO_PUBLIC_API_TABAN;

export const API_TABAN = SABIT_API_TABAN || otomatikApiTabanTespitEt();

// EXPO_PUBLIC_ önekli değişkenler Expo tarafından build zamanında otomatik
// gömülür -- ayrı bir paket gerekmez. Proje kökünde (backend/ DEĞİL, mobil
// projenin kendi kökünde) bir ".env" dosyası oluşturup
//   EXPO_PUBLIC_APP_KEY=...
// satırını eklersen burada otomatik okunur ve backend'e her istekte
// gönderilir. Hiç ayarlanmazsa boş string döner -- backend'de APP_API_KEY
// ayarlanmadığı sürece bu durum hiçbir sorun yaratmaz (bkz. backend/main.py
// app_anahtarini_dogrula notu). İKİ TARAFTA DA (backend .env +  bu .env)
// AYNI değeri kullanman gerekiyor.
export const APP_KEY = process.env.EXPO_PUBLIC_APP_KEY || '';

const CIHAZ_KIMLIGI_ANAHTARI = 'cihaz_kimligi_v1';
let bellekteCihazKimligi: string | null = null;

// 2026-08-18 (güvenlik denetimi madde 6 -- GEÇİCİ OLARAK GERİ ALINDI):
// expo-crypto'nun getRandomBytesAsync'ine geçilmişti, ama bu NATIVE kod
// içeren bir modül -- telefondaki dev client (EAS build) bu paket
// eklenmeden ÖNCE derlendiği için "Cannot find native module 'ExpoCrypto'"
// hatasıyla uygulama AÇILIŞTA ÇÖKÜYORDU (beyaz ekran olarak görünüyordu).
// Native modül gerektiren bir paket, yeni bir "eas build" ile telefona
// yeniden yüklenmeden JS tarafından kullanılamıyor -- sadece "npx expo
// install" + kod değişikliği yeterli değil. Play Store'a hazırlanırken
// zaten yeni bir native build yapılacak (bkz. yapılacaklar listesi) --
// o build'den SONRA bu fonksiyon tekrar Crypto.getRandomBytesAsync'e
// geçirilmeli (expo-crypto paketi package.json'da hâlâ duruyor, sadece
// burada kullanılmıyor). Şimdilik Math.random() tabanlı eski yönteme
// dönüldü -- düşük risk (sadece bir cihaz kimliği, şifre/token değil),
// uygulamanın çalışır olması daha öncelikli.
function rastgeleKimlikUret(): string {
  const rastgele = Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2);
  return `cihaz-${rastgele}`;
}

// 2026-08-19 (yapılacaklar listesi madde 10 -- cihaz verisini şifreleme):
// Cihaz kimliği artık ÖNCELİKLE expo-secure-store'da tutuluyor (Android
// Keystore / iOS Keychain -- işletim sisteminin kendi şifreli deposu),
// AsyncStorage'daki gibi düz metin DEĞİL. Bu, footer'daki "Secured &
// Encrypted System" imzasının cihaz tarafını da gerçek kılıyor.
//
// ÖNEMLİ (ExpoCrypto çökmesinden alınan ders -- bkz. rastgeleKimlikUret
// notu): expo-secure-store NATIVE bir modül, telefondaki mevcut dev
// client/build bu paket eklenmeden ÖNCE derlendiyse SecureStore çağrıları
// çalışmaz. Bu yüzden burada ASLA doğrudan çağrılmıyor -- önce
// isAvailableAsync() ile (o da try/catch içinde) kontrol ediliyor, hiçbir
// adımda hata fırlatılırsa sessizce eski AsyncStorage yoluna düşülüyor.
// Yani: yeni native build'i olmayan eski bir kurulumda uygulama ASLA
// çökmez, sadece yeni build alınana kadar eski (şifresiz) yöntemle çalışmaya
// devam eder -- yeni build gelince otomatik olarak SecureStore'a geçer.
async function secureStoreKullanilabilirMi(): Promise<boolean> {
  try {
    return await SecureStore.isAvailableAsync();
  } catch {
    return false;
  }
}

/**
 * Bu cihaz/kurulum için kalıcı, rastgele bir kimlik döndürür. Favorileri
 * "kim"in eklediğini backend'e söylemek için kullanılır (bkz.
 * backend/main.py favoriler uç noktaları -- expo_push_token alanı bugün
 * için gerçek bir Expo push token DEĞİL, bu cihaz kimliği). İleride gerçek
 * push bildirimleri eklendiğinde, gerçek token bu kimliğin YERİNE değil,
 * EK olarak /api/push-token'a kaydedilecek şekilde genişletilebilir.
 */
export async function cihazKimligiGetir(): Promise<string> {
  if (bellekteCihazKimligi) return bellekteCihazKimligi;

  if (await secureStoreKullanilabilirMi()) {
    try {
      const guvenliKayitli = await SecureStore.getItemAsync(CIHAZ_KIMLIGI_ANAHTARI);
      if (guvenliKayitli) {
        bellekteCihazKimligi = guvenliKayitli;
        return guvenliKayitli;
      }
      // Güvenli depoda yok -- daha ÖNCE (bu güncellemeden önce) AsyncStorage'a
      // yazılmış bir kimlik olabilir. Öyleyse YENİ bir kimlik ÜRETMİYORUZ --
      // varsa onu güvenli depoya TAŞIYIP kullanmaya devam ediyoruz. Aksi
      // halde mevcut kullanıcıların favorileri/push kaydı, sahiplenilen
      // kimlik değiştiği için sessizce "kaybolurdu".
      const eskiKayitli = await AsyncStorage.getItem(CIHAZ_KIMLIGI_ANAHTARI).catch(() => null);
      if (eskiKayitli) {
        await SecureStore.setItemAsync(CIHAZ_KIMLIGI_ANAHTARI, eskiKayitli);
        await AsyncStorage.removeItem(CIHAZ_KIMLIGI_ANAHTARI).catch(() => {});
        bellekteCihazKimligi = eskiKayitli;
        return eskiKayitli;
      }
      const yeni = rastgeleKimlikUret();
      await SecureStore.setItemAsync(CIHAZ_KIMLIGI_ANAHTARI, yeni);
      bellekteCihazKimligi = yeni;
      return yeni;
    } catch {
      // SecureStore beklenmedik şekilde başarısız oldu -- aşağıdaki eski
      // AsyncStorage yoluna sessizce düşülüyor, uygulama çökmüyor.
    }
  }

  // Güvenli depo yok/kullanılamıyor -- eski (AsyncStorage) yöntem, geriye
  // dönük uyumluluk için.
  try {
    const kayitli = await AsyncStorage.getItem(CIHAZ_KIMLIGI_ANAHTARI);
    if (kayitli) {
      bellekteCihazKimligi = kayitli;
      return kayitli;
    }
    const yeni = rastgeleKimlikUret();
    await AsyncStorage.setItem(CIHAZ_KIMLIGI_ANAHTARI, yeni);
    bellekteCihazKimligi = yeni;
    return yeni;
  } catch {
    // AsyncStorage'a hiç yazılamazsa bile (çok nadir) oturum boyunca
    // geçerli bir kimlikle devam edebilelim diye bellekte üretiyoruz.
    const gecici = rastgeleKimlikUret();
    bellekteCihazKimligi = gecici;
    return gecici;
  }
}

/**
 * Tüm API isteklerinde ortak base URL + uygulama anahtarı header'ını
 * otomatik ekleyen fetch sarmalayıcısı. `yol` "/api/..." ile başlamalı.
 */
export async function apiIstek(yol: string, secenekler: RequestInit = {}): Promise<Response> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((secenekler.headers as Record<string, string>) || {}),
  };
  if (APP_KEY) headers['X-App-Key'] = APP_KEY;
  return fetch(`${API_TABAN}${yol}`, { ...secenekler, headers });
}
