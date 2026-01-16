import React, { useState } from 'react';
import { SafeAreaView, View, Text, TextInput, Button, Image, ActivityIndicator, ScrollView, Alert } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import * as FileSystem from 'expo-file-system';
import * as MediaLibrary from 'expo-media-library';

// 👇 укажи адрес бэкенда. для Android можно по локалке:
const API_BASE = 'http://192.168.0.16:8000';
// если захочешь, можно потом заменить на https из ngrok

type Media = {
  uri: string;
  type: 'image' | 'video';
  name: string;
  mime: string;
};

export default function App() {
  const [prompt, setPrompt] = useState('');
  const [media, setMedia] = useState<Media | null>(null);
  const [loading, setLoading] = useState(false);
  const [resultImageUri, setResultImageUri] = useState<string | null>(null);
  const [resultVideoUrl, setResultVideoUrl] = useState<string | null>(null);

  async function pickMedia(kind: 'image' | 'video') {
    setResultImageUri(null);
    setResultVideoUrl(null);
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) { Alert.alert('Нужно разрешение на доступ к медиатеке'); return; }
    const res = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: kind === 'image' ? ImagePicker.MediaTypeOptions.Images : ImagePicker.MediaTypeOptions.Videos,
      quality: 1
    });
    if (res.canceled || res.assets.length === 0) return;
    const a = res.assets[0];
    const uri = a.uri!;
    const name = uri.split('/').pop() || (kind === 'image' ? 'image.jpg' : 'video.mp4');
    const mimeGuess = kind === 'image' ? (a.mimeType || 'image/jpeg') : (a.mimeType || 'video/mp4');
    setMedia({ uri, type: kind, name, mime: mimeGuess });
  }

  async function saveToGallery(uri: string) {
    const perm = await MediaLibrary.requestPermissionsAsync();
    if (!perm.granted) return;
    await MediaLibrary.saveToLibraryAsync(uri);
    Alert.alert('Сохранено в галерею');
  }

  async function editImage() {
    if (!media || media.type !== 'image') { Alert.alert('Выбери фото'); return; }
    setLoading(true);
    setResultImageUri(null);
    try {
      const form = new FormData();
      form.append('file', { // @ts-ignore
        uri: media.uri, name: media.name, type: media.mime
      });
      form.append('prompt', prompt);
      form.append('remove_bg', 'false');
      form.append('upscale', 'false');

      const r = await fetch(`${API_BASE}/ai/edit-image`, { method: 'POST', body: form });
      if (!r.ok) throw new Error(`edit-image failed: ${r.status}`);
      const blob = await r.blob();
      const base64 = Buffer.from(await blob.arrayBuffer()).toString('base64');
      const fileUri = FileSystem.cacheDirectory + `edited_${Date.now()}.png`;
      await FileSystem.writeAsStringAsync(fileUri, base64, { encoding: FileSystem.EncodingType.Base64 });
      setResultImageUri(fileUri);
    } catch (e:any) {
      Alert.alert('Ошибка', String(e?.message || e));
    } finally { setLoading(false); }
  }

  async function editVideo() {
    if (!media || media.type !== 'video') { Alert.alert('Выбери видео'); return; }
    setLoading(true);
    setResultVideoUrl(null);
    try {
      const form = new FormData();
      form.append('file', { // @ts-ignore
        uri: media.uri, name: media.name, type: media.mime
      });
      form.append('prompt', prompt);
      form.append('stabilize', 'true');
      form.append('sharpen', 'true');
      form.append('tone', 'cinematic');

      const r = await fetch(`${API_BASE}/ai/edit-video-smart`, { method: 'POST', body: form });
      if (!r.ok) throw new Error(`edit-video failed: ${r.status}`);
      const data = await r.json();
      setResultVideoUrl(`${API_BASE}${data.url}`);
    } catch (e:any) {
      Alert.alert('Ошибка', String(e?.message || e));
    } finally { setLoading(false); }
  }

  async function renderReels() {
    if (!media) { Alert.alert('Выбери медиа (лучше видео)'); return; }
    setLoading(true);
    setResultVideoUrl(null);
    try {
      // upload
      const fd = new FormData();
      fd.append('files', { // @ts-ignore
        uri: media.uri, name: media.name, type: media.mime
      });
      const up = await fetch(`${API_BASE}/upload`, { method: 'POST', body: fd });
      const upJson = await up.json();
      const key = upJson.files[0].key;

      // ai layout (можно пропустить)
      let template: any = null;
      const lr = await fetch(`${API_BASE}/ai/layout`, {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ prompt })
      });
      if (lr.ok) template = await lr.json();

      // старт рендера
      const start = await fetch(`${API_BASE}/render/reels`, {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({
          input_keys: [key],
          music_key: null,
          title: template?.title || prompt || 'Reels',
          template
        })
      });
      const { job_id } = await start.json();

      // poll
      let url = '';
      while (true) {
        await new Promise(r => setTimeout(r, 1200));
        const st = await fetch(`${API_BASE}/jobs/${job_id}`);
        const j = await st.json();
        if (j.status === 'done') { url = `${API_BASE}/outputs/${job_id}.mp4`; break; }
        if (j.status === 'error') throw new Error('render error');
      }
      setResultVideoUrl(url);
    } catch (e:any) {
      Alert.alert('Ошибка', String(e?.message || e));
    } finally { setLoading(false); }
  }

  return (
    <SafeAreaView style={{flex:1}}>
      <ScrollView contentContainerStyle={{padding:16}}>
        <Text style={{fontSize:20, fontWeight:'600', marginBottom:8}}>AI Editor — Android</Text>

        <View style={{flexDirection:'row', gap:8, marginBottom:8}}>
          <Button title="Выбрать фото" onPress={() => pickMedia('image')} />
          <Button title="Выбрать видео" onPress={() => pickMedia('video')} />
        </View>

        {media && <Text style={{marginBottom:8}}>Выбрано: {media.name} ({media.type})</Text>}

        <Text>Промпт</Text>
        <TextInput
          value={prompt}
          onChangeText={setPrompt}
          placeholder="напр.: кинематографично, белый жирный текст сверху по центру, Montserrat"
          multiline
          style={{borderWidth:1,borderColor:'#ccc',borderRadius:8,padding:10,minHeight:60, marginBottom:12}}
        />

        <View style={{gap:8}}>
          <Button title="AI редактировать фото" onPress={editImage} />
          <Button title="AI редактировать видео" onPress={editVideo} />
          <Button title="Собрать Reels (пайплайн)" onPress={renderReels} />
        </View>

        {loading && (<View style={{marginTop:12}}><ActivityIndicator /><Text style={{marginTop:8}}>Обрабатываем…</Text></View>)}

        {resultImageUri && (
          <View style={{marginTop:16}}>
            <Text>Результат (изображение):</Text>
            <Image source={{uri: resultImageUri}} style={{width:'100%', height:400, resizeMode:'contain'}} />
            <View style={{marginTop:8}}>
              <Button title="Сохранить в галерею" onPress={() => saveToGallery(resultImageUri!)} />
            </View>
          </View>
        )}

        {resultVideoUrl && (
          <View style={{marginTop:16}}>
            <Text>Результат (видео):</Text>
            <Text selectable style={{color:'blue'}}>{resultVideoUrl}</Text>
            <Text style={{marginTop:6, opacity:0.7}}>Открой ссылку — файл скачается через браузер</Text>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
