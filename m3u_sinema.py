import requests
import os
import re
import json
from datetime import datetime, timedelta, timezone
from collections import Counter

# --- AYARLAR ---
m3u_sources = [
    ("https://raw.githubusercontent.com/Lunedor/iptvTR/refs/heads/main/FilmArsiv.m3u", "Lunedor"),
    ("https://raw.githubusercontent.com/Zerk1903/zerkfilm/refs/heads/main/Filmler.m3u", "Zerk"),
    ("https://tinyurl.com/2ao2rans", "powerboard"),
]

birlesik_dosya = "birlesik_sinema.m3u"
kayit_json_dir = "kayit_json_sinema"
ana_kayit_json = os.path.join(kayit_json_dir, "birlesik_sinema_links.json")
KOPYA_IKONU = "🔄"

if not os.path.exists(kayit_json_dir):
    os.makedirs(kayit_json_dir)

# --- İSİM TEMİZLEME FONKSİYONU (YILI KORUR) ---
def clean_display_name(name):
    """
    (2016) gibi tarihleri korur, [8.7], (Aksiyon), (🌟6.6) gibi kısımları siler.
    """
    # 1. Köşeli parantez içindeki her şeyi sil [Puan] [4K] vb.
    name = re.sub(r'\[.*?\]', '', name)

    # 2. İçinde tam olarak 4 hane rakam olan parantezleri (Yılları) geçici olarak korumaya al
    yillar = re.findall(r'\(\d{4}\)', name)
    for i, yil in enumerate(yillar):
        name = name.replace(yil, f"[[YIL_{i}]]")

    # 3. Geri kalan tüm normal parantezleri ve içindekileri sil
    name = re.sub(r'\(.*?\)', '', name)

    # 4. Korunan yılları geri yükle
    for i, yil in enumerate(yillar):
        name = name.replace(f"[[YIL_{i}]]", yil)

    # 5. Başta veya sonda kalabilecek yıldız, boşluk ve alt tireleri temizle
    name = name.replace("🌟", "").replace("_", " ").strip()
    
    # 6. Birden fazla boşluk kaldıysa teke indir
    name = ' '.join(name.split())
    return name

def safe_extract_channel_key(extinf_line, url_line):
    # Logo içindeki virgül hatasını önlemek için teknik temizlik
    clean_line = re.sub(r'logo="([^"]+?)"', lambda m: f'logo="{m.group(1).replace(",", "%2C")}"', extinf_line)
    match = re.search(r',([^,]*)$', clean_line)
    channel_name = match.group(1).strip() if match else 'Bilinmeyen Film'
    channel_name = channel_name.replace("_", " ").strip()
    return (channel_name, url_line.strip())

def process_metadata(extinf_line, source_name, add_time):
    if 'type="video"' not in extinf_line:
        extinf_line = extinf_line.replace("#EXTINF:-1", '#EXTINF:-1 type="video"')
    
    if 'group-author=' not in extinf_line:
        extinf_line = re.sub(r',', f' group-author="{source_name}",', extinf_line, count=1)
    
    clean_time = add_time.replace(" ", "_")
    if 'group-time=' not in extinf_line:
        extinf_line = re.sub(r',', f' group-time="{clean_time}",', extinf_line, count=1)
    
    m_title = re.search(r'group-title="([^"]*)"', extinf_line)
    if not m_title or not m_title.group(1).strip():
        if 'group-title=' in extinf_line:
            extinf_line = re.sub(r'group-title="[^"]*"', f'group-title="{source_name}"', extinf_line)
        else:
            extinf_line = re.sub(r',', f' group-title="{source_name}",', extinf_line, count=1)
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

# --- ZAMAN AYARLARI ---
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

# Kopya kontrolü için temiz isimleri say
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
    
    # YENİLER
    for (key, extinf, url, t, ts, src) in tum_yeni_kanallar:
        saat_str = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y %H:%M")
        extinf = process_metadata(extinf, src, ts)
        extinf = re.sub(r'group-title="[^"]*"', f'group-title="✨YENİ [{src}]"', extinf)
        extinf = re.sub(r',.*', f',{key[0]} [{saat_str}]', extinf)
        f.write(extinf + "\n" + url + "\n")

    # ESKİLER
    for (key, extinf, url, t, ts, src) in tum_eski_kanallar:
        fark = (today_obj - datetime.strptime(t, "%Y-%m-%d")).days
        extinf = process_metadata(extinf, src, ts)
        
        if fark < 30:
            saat_str = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y %H:%M")
            extinf = re.sub(r'group-title="[^"]*"', f'group-title="✨YENİ [{src}]"', extinf)
            extinf = re.sub(r',.*', f',{key[0]} [{saat_str}]', extinf)
        else:
            extinf = re.sub(r',.*', f',{key[0]}', extinf)
            f.write(extinf + "\n" + url + "\n")

with open(ana_kayit_json, "w", encoding="utf-8") as f:
    json.dump(ana_link_dict, f, ensure_ascii=False, indent=2)

print(f"Bitti! Film yıllarını (20xx) koruyan parantez istisnası uygulandı.")
