import requests
import os
import re
import json
from datetime import datetime, timedelta, timezone
from collections import Counter

# --- AYARLAR ---
m3u_sources = [
    ("https://tinyurl.com/FanatikPlayDizi", "FanatikPlay"),
    ("https://raw.githubusercontent.com/Zerk1903/zerkfilm/refs/heads/main/Diziler.m3u", "Zerk"),
    ("https://tinyurl.com/24lt9aqs", "powerboard"),
]

birlesik_dosya = "birlesik_diziler.m3u"
kayit_json_dir = "kayit_json_dizi"
ana_kayit_json = os.path.join(kayit_json_dir, "birlesik_dizi_links.json")
KOPYA_IKONU = "🔄"

if not os.path.exists(kayit_json_dir):
    os.makedirs(kayit_json_dir)

# --- FORMAT VE TEMİZLİK FONKSİYONLARI ---

def standardize_episode_names(name):
    """Dizi bölümlerini S01E01 formatına sokar."""
    # "1. Sezon 8. Bölüm" -> S01E08
    name = re.sub(r'(\d+)\.\s*Sezon\s*(\d+)\.\s*Bölüm', lambda m: f"S{int(m.group(1)):02d}E{int(m.group(2)):02d}", name, flags=re.IGNORECASE)
    # "- 3. Bölüm" -> S01E03
    name = re.sub(r'-\s*(\d+)\.\s*Bölüm', lambda m: f"S01E{int(m.group(1)):02d}", name, flags=re.IGNORECASE)
    # "s1e8" veya "s01e8" -> S01E08
    name = re.sub(r's(\d+)e(\d+)', lambda m: f"S{int(m.group(1)):02d}E{int(m.group(2)):02d}", name, flags=re.IGNORECASE)
    # S01E08a gibi sondaki küçük harfleri siler
    name = re.sub(r'S(\d{2})E(\d{2})[a-z]', r'S\1E\2', name)
    return name

def clean_display_name(name):
    # 1. Köşeli parantez içindekileri sil [8.7] [Aksiyon] vb.
    name = re.sub(r'\[.*?\]', '', name)
    
    # 2. Yılları koruma (2016)
    yillar = re.findall(r'\(\d{4}\)', name)
    for i, yil in enumerate(yillar):
        name = name.replace(yil, f"[[YIL_{i}]]")

    # 3. Normal parantez içindeki diğer her şeyi sil (Puan, Tür vb.)
    name = re.sub(r'\(.*?\)', '', name)

    # 4. Yılları geri yükle
    for i, yil in enumerate(yillar):
        name = name.replace(f"[[YIL_{i}]]", yil)

    # 5. Dizi bölüm formatını standartlaştır (S01E01)
    name = standardize_episode_names(name)

    # 6. Gereksiz karakter ve boşluk temizliği
    name = name.replace("🌟", "").replace("_", " ").strip()
    name = ' '.join(name.split())
    
    return name

def safe_extract_channel_key(extinf_line, url_line):
    clean_line = re.sub(r'logo="([^"]+?)"', lambda m: f'logo="{m.group(1).replace(",", "%2C")}"', extinf_line)
    match = re.search(r',([^,]*)$', clean_line)
    channel_name = match.group(1).strip() if match else 'Bilinmeyen Dizi'
    return (channel_name, url_line.strip())

def process_metadata(extinf_line, source_name, add_time, is_new=False):
    if 'type="video"' not in extinf_line:
        extinf_line = extinf_line.replace("#EXTINF:-1", '#EXTINF:-1 type="video"')
    
    author_val = f"📺 YENİ DİZİ [{source_name}]" if is_new else source_name
    
    if 'group-author=' in extinf_line:
        extinf_line = re.sub(r'group-author="[^"]*"', f'group-author="{author_val}"', extinf_line)
    else:
        extinf_line = re.sub(r',', f' group-author="{author_val}",', extinf_line, count=1)
    
    clean_time = add_time.replace(" ", "_")
    if 'group-time=' in extinf_line:
        extinf_line = re.sub(r'group-time="[^"]*"', f'group-time="{clean_time}"', extinf_line)
    else:
        extinf_line = re.sub(r',', f' group-time="{clean_time}",', extinf_line, count=1)
        
    return extinf_line

def parse_m3u_lines(lines):
    kanal_list = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF") and i + 1 < len(lines):
            extinf_line = line
            url_line = lines[i + 1].strip()
            key_data = safe_extract_channel_key(extinf_line, url_line)
            kanal_list.append((key_data, extinf_line, url_line))
            i += 2
        else:
            i += 1
    return kanal_list

# --- ZAMAN ---
tr_tz = timezone(timedelta(hours=3)) 
now_tr = datetime.now(tr_tz)
today = now_tr.strftime("%Y-%m-%d")
now_full = now_tr.strftime("%Y-%m-%d %H:%M:%S")
today_obj = datetime.strptime(today, "%Y-%m-%d")

# --- İŞLEM ---
ana_link_dict = {}
if os.path.exists(ana_kayit_json):
    with open(ana_kayit_json, "r", encoding="utf-8") as f:
        ana_link_dict = json.load(f)

hepsi_gecici = [] 
gorulen_url_ler = set()

for m3u_url, source_name in m3u_sources:
    try:
        print(f"[+] {source_name} çekiliyor...")
        req = requests.get(m3u_url, timeout=25)
        req.raise_for_status()
        lines = req.text.splitlines()
        kanal_list = parse_m3u_lines(lines)

        for (key, extinf, url) in kanal_list:
            if url in gorulen_url_ler: continue
            gorulen_url_ler.add(url)
            hepsi_gecici.append((key, extinf, url, source_name))
    except Exception as e:
        print(f"⚠️ Hata: {source_name} -> {e}")

# İsimleri temizle ve kopyaları say
isim_sayaci = Counter([clean_display_name(item[0][0]).lower() for item in hepsi_gecici])

tum_yeni_kanallar = []
tum_eski_kanallar = []

for (key, extinf, url, source_name) in hepsi_gecici:
    temiz_isim = clean_display_name(key[0])
    display_name = f"{KOPYA_IKONU} {temiz_isim}" if isim_sayaci[temiz_isim.lower()] > 1 else temiz_isim
    
    dict_key = f"{key[0]}|{url}" 
    if dict_key in ana_link_dict:
        kayit = ana_link_dict[dict_key]
        tum_eski_kanallar.append(((display_name, url), extinf, url, kayit["tarih"], kayit["tarih_saat"], source_name))
    else:
        ana_link_dict[dict_key] = {"tarih": today, "tarih_saat": now_full}
        tum_yeni_kanallar.append(((display_name, url), extinf, url, today, now_full, source_name))

# --- SIRALAMA VE YAZMA ---
tum_yeni_kanallar.sort(key=lambda x: x[0][0].lower())
tum_eski_kanallar.sort(key=lambda x: x[0][0].lower())

with open(birlesik_dosya, "w", encoding="utf-8") as f:
    f.write("#EXTM3U\n")
    
    for (key, extinf, url, t, ts, src) in tum_yeni_kanallar:
        extinf = process_metadata(extinf, src, ts, is_new=True)
        # İsmi temizlenmiş halle değiştir (S01E01 formatında ve []/() temizlenmiş)
        extinf = re.sub(r',.*', f',{key[0]}', extinf)
        f.write(extinf + "\n" + url + "\n")

    for (key, extinf, url, t, ts, src) in tum_eski_kanallar:
        fark = (today_obj - datetime.strptime(t, "%Y-%m-%d")).days
        is_new_tag = True if fark < 15 else False
        extinf = process_metadata(extinf, src, ts, is_new=is_new_tag)
        extinf = re.sub(r',.*', f',{key[0]}', extinf)
        f.write(extinf + "\n" + url + "\n")

with open(ana_kayit_json, "w", encoding="utf-8") as f:
    json.dump(ana_link_dict, f, ensure_ascii=False, indent=2)

print(f"Tamamlandı! Köşeli parantezler silindi, dizi isimleri S01E01 formatına çevrildi.")
