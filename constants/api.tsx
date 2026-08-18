import Constants from 'expo-constants';
import * as Crypto from 'expo-crypto';
import AsyncStorage from '@react-native-async-storage/async-storage';

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

export const API_TABAN = otomatikApiTabanTespitEt();

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

// 2026-08-18 (güvenlik denetimi madde 6): Math.random() kriptografik
// amaçlar için güvenli değil -- bu kimlik hem favoriler hem (bkz.
// backend main.py _otomatik_izlemeye_al) otomatik izleme için TEK
// yetkilendirme faktörü olduğundan, expo-crypto'nun kriptografik güvenli
// rastgele sayı üretecine (getRandomBytesAsync) geçildi. ÖNEMLİ: mevcut
// kurulumların AsyncStorage'da zaten kayıtlı kimlikleri DEĞİŞMEZ (bkz.
// cihazKimligiGetir -- önce her zaman kayıtlı değeri okur) -- bu, sadece
// YENİ kurulumlarda üretilecek kimlikleri güçlendiriyor.
async function rastgeleKimlikUret(): Promise<string> {
  const baytlar = await Crypto.getRandomBytesAsync(16); // 128 bit
  const onaltilikDize = Array.from(baytlar)
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
  return `cihaz-${onaltilikDize}`;
}

/**
 * Bu cihaz/kurulum için kalıcı, rastgele bir kimlik döndürür. Favorileri
 * "kim"in eklediğini backend'e söylemek için kullanılır (bkz.
 * backend/main.py favoriler uç noktaları -- expo_push_token alanı bugün
 * için gerçek bir Expo push token DEĞİL, bu cihaz kimliği). İleride gerçek
 * push bildirimleri eklendiğinde, gerçek token bu kimliğin YERİNE değil,
 * EK olarak /api/push-token'a kaydedilecek şekilde genişletilebilir.
 * AsyncStorage'da saklanır, ilk kullanımda bir kere üretilir.
 */
export async function cihazKimligiGetir(): Promise<string> {
  if (bellekteCihazKimligi) return bellekteCihazKimligi;
  try {
    const kayitli = await AsyncStorage.getItem(CIHAZ_KIMLIGI_ANAHTARI);
    if (kayitli) {
      bellekteCihazKimligi = kayitli;
      return kayitli;
    }
    const yeni = await rastgeleKimlikUret();
    await AsyncStorage.setItem(CIHAZ_KIMLIGI_ANAHTARI, yeni);
    bellekteCihazKimligi = yeni;
    return yeni;
  } catch {
    // AsyncStorage'a hiç yazılamazsa bile (çok nadir) oturum boyunca
    // geçerli bir kimlikle devam edebilelim diye bellekte üretiyoruz.
    const gecici = await rastgeleKimlikUret();
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
