import requests
import os
import re
import json
from datetime import datetime, timedelta

m3u_sources = [
    ("https://dl.dropbox.com/scl/fi/dj74gt6awxubl4yqoho07/github.m3u?rlkey=m7pzzvk27d94bkfl9a98tluai", "moon"),
    ("https://raw.githubusercontent.com/Lunedor/iptvTR/refs/heads/main/FilmArsiv.m3u", "iptvTR"),
    ("https://raw.githubusercontent.com/Zerk1903/zerkfilm/refs/heads/main/Filmler.m3u", "zerkfilm"),
]

birlesik_dosya = "birlesik.m3u"
kayit_json_dir = "kayit_json"
if not os.path.exists(kayit_json_dir):
    os.makedirs(kayit_json_dir)

def extract_channel_key(extinf_line, url_line):
    match = re.match(r'#EXTINF:.*?,(.*)', extinf_line)
    channel_name = match.group(1).strip() if match else ''
    url = url_line.strip()
    return (channel_name, url)

def parse_m3u_lines(lines):
    kanal_list = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            extinf_line = line
            if i + 1 < len(lines):
                url_line = lines[i + 1].strip()
                kanal_list.append((extract_channel_key(extinf_line, url_line), extinf_line, url_line))
            i += 2
        else:
            i += 1
    return kanal_list

def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json(data, filename):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def format_tr_date(date_str):
    # "yyyy-mm-dd" -> "g.m.yyyy"
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{d.day}.{d.month}.{d.year}"

today = datetime.now().strftime("%Y-%m-%d")
today_obj = datetime.strptime(today, "%Y-%m-%d")
header_lines = ["#EXTM3U\n"]
all_channels = []

for m3u_url, source_name in m3u_sources:
    # Her kaynak için kayıt dosyası
    json_file = os.path.join(kayit_json_dir, f"{source_name}.json")
    # { "<kanal_adı>|<url>": {"tarih": "yyyy-mm-dd"} }
    link_dict = load_json(json_file)

    try:
        req = requests.get(m3u_url, timeout=20)
        req.raise_for_status()
    except Exception as e:
        print(f"{m3u_url} alınamadı: {e}")
        continue
    lines = req.text.splitlines()
    kanal_list = parse_m3u_lines(lines)

    yeni_link_dict = dict(link_dict)  # yeni json'a yazılacak
    yeni_kanallar, eski_kanallar = [], []

    for (key, extinf, url) in kanal_list:
        dict_key = f"{key[0]}|{key[1]}"
        if dict_key not in link_dict:
            yeni_link_dict[dict_key] = {"tarih": today}
            yeni_kanallar.append((key, extinf, url, today))
        else:
            eski_kanallar.append((key, extinf, url, link_dict[dict_key]["tarih"]))

    yeni_grup_satirlari = []
    normal_grup_satirlari = []

    for (key, extinf, url, eklenme_tarihi) in yeni_kanallar + eski_kanallar:
        ilk_ad = key[0]
        tarih_obj = datetime.strptime(eklenme_tarihi, "%Y-%m-%d")
        # 7 gün kuralı
        if (today_obj - tarih_obj).days < 7:
            # Yeni grupta tutulacak
            group_title = f'[YENİ] [{source_name}]'
            kanal_isim = f'{ilk_ad} [{format_tr_date(eklenme_tarihi)}]'
            # group-title ile extinf'de eski group-title varsa çıkar
            extinf_clean = re.sub(r'group-title="[^"]*"', f'group-title="{group_title}"', extinf)
            extinf_clean = re.sub(r',.*', f',{kanal_isim}', extinf_clean)
            yeni_grup_satirlari.append((extinf_clean, url))
        else:
            # Orijinal grubunda tutulacak
            group_title = f'{source_name}'
            kanal_isim = f'{ilk_ad} [{format_tr_date(eklenme_tarihi)}]'
            extinf_clean = re.sub(r'group-title="[^"]*"', f'group-title="{group_title}"', extinf)
            extinf_clean = re.sub(r',.*', f',{kanal_isim}', extinf_clean)
            normal_grup_satirlari.append((extinf_clean, url))

    # --- YENİ GRUP başlığı ---
    if yeni_grup_satirlari:
        header_lines.append(f'#EXTINF:-1 group-title="[YENİ] [{source_name}], ",\n')
        for extinf, url in yeni_grup_satirlari:
            all_channels.append((extinf, url))

    # --- NORMAL GRUP başlığı ---
    if normal_grup_satirlari:
        header_lines.append(f'#EXTINF:-1 group-title="[{source_name}], ",\n')
        for extinf, url in normal_grup_satirlari:
            all_channels.append((extinf, url))

    save_json(yeni_link_dict, json_file)

with open(birlesik_dosya, "w", encoding="utf-8") as outfile:
    for line in header_lines:
        outfile.write(line)
    for extinf, stream_url in all_channels:
        outfile.write(extinf + "\n")
        outfile.write(stream_url + "\n")
