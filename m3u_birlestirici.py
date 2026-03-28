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

birlesik_dosya = "birlesik.m3u"
kayit_json_dir = "kayit_json"
ana_kayit_json = os.path.join(kayit_json_dir, "birlesik_links.json")
KOPYA_IKONU = "🔄"  # Aynı isimde başka link varsa eklenecek ikon

if not os.path.exists(kayit_json_dir):
    os.makedirs(kayit_json_dir)

# --- YARDIMCI FONKSİYONLAR ---
def safe_extract_channel_key(extinf_line, url_line):
    clean_line = re.sub(r'logo="([^"]+?)"', lambda m: f'logo="{m.group(1).replace(",", "%2C")}"', extinf_line)
    match = re.search(r',([^,]*)$', clean_line)
    channel_name = match.group(1).strip() if match else 'Bilinmeyen Kanal'
    channel_name = channel_name.replace("_", " ").strip()
    return (channel_name, url_line.strip())

def add_video_type(extinf_line):
    if 'type="video"' not in extinf_line:
        extinf_line = extinf_line.replace("#EXTINF:-1", '#EXTINF:-1 type="video"')
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

# --- ZAMAN AYARI (UTC+3 Türkiye) ---
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

tum_yeni_kanallar = []
tum_eski_kanallar = []
gorulen_url_ler = set()
hepsi_gecici = [] # Kopya sayacı için tüm adayları burada toplayacağız

# 1. Aşama: Tüm benzersiz linkleri topla
for m3u_url, source_name in m3u_sources:
    try:
        print(f"[+] {source_name} indiriliyor...")
        req = requests.get(m3u_url, timeout=25)
        req.raise_for_status()
        lines = req.text.splitlines()
        kanal_list = parse_m3u_lines(lines)

        for (key, extinf, url) in kanal_list:
            if url in gorulen_url_ler: continue
            gorulen_url_ler.add(url)
            hepsi_gecici.append((key, extinf, url, source_name))
    except Exception as e:
        print(f"⚠️ {source_name} hatası: {e}")

# 2. Aşama: Kopya İsimleri Say (Büyük-Küçük harf duyarsız)
isim_sayaci = Counter([item[0][0].lower() for item in hepsi_gecici])

# 3. Aşama: Kanalları Yeni/Eski olarak ayır ve İkonu ekle
for (key, extinf, url, source_name) in hepsi_gecici:
    kanal_ismi = key[0]
    # Eğer bu isimden birden fazla varsa ikonu ekle
    display_name = f"{KOPYA_IKONU} {kanal_ismi}" if isim_sayaci[kanal_ismi.lower()] > 1 else kanal_ismi
    
    dict_key = f"{kanal_ismi}|{url}"
    if dict_key in ana_link_dict:
        kayit = ana_link_dict[dict_key]
        tum_eski_kanallar.append(((display_name, url), extinf, url, kayit["tarih"], kayit["tarih_saat"], source_name))
    else:
        ana_link_dict[dict_key] = {"tarih": today, "tarih_saat": now_full}
        tum_yeni_kanallar.append(((display_name, url), extinf, url, today, now_full, source_name))

# --- YAZMA VE SIRALAMA ---
tum_yeni_kanallar.sort(key=lambda x: x[0][0].lower())
tum_eski_kanallar.sort(key=lambda x: x[0][0].lower())

with open(birlesik_dosya, "w", encoding="utf-8") as f:
    f.write("#EXTM3U\n")
    
    # Yeni Kanallar
    for (key, extinf, url, t, ts, src) in tum_yeni_kanallar:
        saat_str = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y %H:%M")
        extinf = add_video_type(extinf)
        extinf = re.sub(r'group-title="[^"]*"', f'group-title="✨YENİ [{src}]"', extinf)
        extinf = re.sub(r',.*', f',{key[0]} [{saat_str}]', extinf)
        f.write(extinf + "\n" + url + "\n")

    # Eski Kanallar
    for (key, extinf, url, t, ts, src) in tum_eski_kanallar:
        fark = (today_obj - datetime.strptime(t, "%Y-%m-%d")).days
        extinf = add_video_type(extinf)
        
        if fark < 30:
            saat_str = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y %H:%M")
            extinf = re.sub(r'group-title="[^"]*"', f'group-title="✨YENİ [{src}]"', extinf)
            extinf = re.sub(r',.*', f',{key[0]} [{saat_str}]', extinf)
        else:
            m_g = re.search(r'group-title="([^"]*)"', extinf)
            org_g = m_g.group(1) if m_g else src
            new_g = f"{org_g} [{src}]" if src not in org_g else org_g
            extinf = re.sub(r'group-title="[^"]*"', f'group-title="{new_g}"', extinf)
            extinf = re.sub(r',.*', f',{key[0]}', extinf)
            
        f.write(extinf + "\n" + url + "\n")

with open(ana_kayit_json, "w", encoding="utf-8") as f:
    json.dump(ana_link_dict, f, ensure_ascii=False, indent=2)

print(f"Bitti! {len(gorulen_url_ler)} kanal işlendi. Tekrar eden içeriklere {KOPYA_IKONU} eklendi.")
