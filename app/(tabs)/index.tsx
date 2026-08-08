import { useState } from 'react';
import { ActivityIndicator, Linking, ScrollView, Text, TextInput, TouchableOpacity, View } from 'react-native';
const API_URL = 'https://romanya-dosya-takip.onrender.com';
export default function HomeScreen() {
  const [dosya, setDosya] = useState('43484');
  const [yukleniyor, setYukleniyor] = useState(false);
  const [sonuc, setSonuc] = useState<any>(null);
  const sorgula = async () => {
    if(!dosya) return;
    setYukleniyor(true); setSonuc(null);
    try{
      const r = await fetch(`${API_URL}/api/sorgula`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({dosya_no:dosya})});
      const d = await r.json();
      setSonuc({no:dosya, durum:d.durum, asama:d.asama, detay:d.mesaj, pdf:d.pdf_url, liste:d.liste_url, eslesti:d.eslesti});
    }catch(e:any){ setSonuc({no:dosya, durum:'HATA', detay:e.message, pdf:null}); }
    setYukleniyor(false);
  };
  return(
    <ScrollView style={{flex:1, backgroundColor:'#f2f4f8'}} contentContainerStyle={{padding:20, paddingTop:60}}>
      <Text style={{fontSize:30, fontWeight:'800', color:'#14224a'}}>Dosya Takip</Text>
      <Text style={{color:'#16a34a', fontWeight:'700'}}>STADIU + ORDINE</Text>
      <View style={{backgroundColor:'white', padding:20, borderRadius:20, marginTop:20}}>
        <Text>Dosya Numaraniz</Text>
        <TextInput placeholder="Ornek: 43484" style={{borderWidth:1.5, borderColor:'#e2e7f0', borderRadius:12, padding:15, fontSize:20, marginTop:8}} value={dosya} onChangeText={setDosya} keyboardType="number-pad" />
        <TouchableOpacity onPress={sorgula} style={{backgroundColor:'#14224a', padding:16, borderRadius:12, alignItems:'center', marginTop:15}}><Text style={{color:'white', fontWeight:'800'}}>SORGULA</Text></TouchableOpacity>
      </View>
      {yukleniyor && <ActivityIndicator style={{marginTop:20}} size="large" />}
      {sonuc && <View style={{backgroundColor:'white', marginTop:20, padding:20, borderRadius:20, borderLeftWidth:5, borderLeftColor: sonuc.eslesti?'#16a34a':'#14224a'}}><Text style={{fontWeight:'800'}}>{sonuc.no} - {sonuc.durum}</Text><Text>{sonuc.detay}</Text>{sonuc.pdf && <TouchableOpacity onPress={()=>Linking.openURL(sonuc.pdf)} style={{marginTop:10, backgroundColor:'#e6eeff', padding:10, borderRadius:8}}><Text style={{textAlign:'center', fontWeight:'700'}}>PDF Ac</Text></TouchableOpacity>}</View>}
    </ScrollView>
  );
}