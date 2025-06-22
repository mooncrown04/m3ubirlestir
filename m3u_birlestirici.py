import requests
import os
import re
import json
from datetime import datetime, timedelta

m3u_sources = [
    (
        "https://dl.dropbox.com/scl/fi/dj74gt6awxubl4yqoho07/github.m3u?rlkey=m7pzzvk27d94bkfl9a98tluai",
        "moon"
    ),
    (
        "https://raw.githubusercontent.com/Lunedor/iptvTR/refs/heads/main/FilmArsiv.m3u",
        "iptvTR"
    ),
    (
        "https://raw.githubusercontent.com/Zerk1903/zerkfilm/refs/heads/main/Filmler.m3u",
        "zerkfilm"
    ),
]

birlesik_dosya = "birlesik.m3u"
link_kayit_dir = "link_kayitlar"
if not os.path.exists(link_kayit_dir):
    os.makedirs(link_kayit_dir)

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
                anahtar = extract_channel_key(extinf_line, url_line)
                kanal_list.append((anahtar, extinf_line, url_line))
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

bugun = datetime.now().strftime("%Y-%m-%d")
bugun_obj = datetime.strptime(bugun, "%Y-%m-%d")
header_lines = ["#EXTM3U\n"]
all_channels = []

for m3u_url, source_name in m3u_sources:
    # Her kaynak için link kayıt dosyası
    link_json_file = os.path.join(link_kayit_dir, f"{source_name}.json")
    link_dict = load_json(link_json_file)  # {(kanal_adı, url): eklenme_tarihi}
    link_date_map = {tuple(eval(k)): v for k, v in link_dict.items()}  # string -> tuple

    try:
        response = requests.get(m3u_url, timeout=20)
        response.raise_for_status()
    except Exception as e:
        print(f"{m3u_url} alınamadı: {e}")
        continue

    lines = response.text.splitlines()
    kanal_list = parse_m3u_lines(lines)

    yeni_kanallar = []
    eski_kanallar = []
    yeni_link_date_map = dict(link_date_map)  # yeni json için

    for (key, extinf, url) in kanal_list:
        if key not in link_date_map:
            yeni_kanallar.append((key, extinf, url))
            yeni_link_date_map[str(key)] = bugun
        else:
            eski_kanallar.append((key, extinf, url))

    # 1 haftadan eski "yeni" linkler orijinal gruba alınacak
    yeni_grup_satirlari = []
    orijinal_grup_satirlari = []

    for (key, extinf, url) in kanal_list:
        eklenme_tarihi = yeni_link_date_map.get(str(key), bugun)
        tarih_obj = datetime.strptime(eklenme_tarihi, "%Y-%m-%d")
        if (bugun_obj - tarih_obj).days < 7:
            # Hala yeni
            yeni_grup_satirlari.append((extinf, url, eklenme_tarihi))
        else:
            # Artık orijinal gruba
            orijinal_grup_satirlari.append((extinf, url, eklenme_tarihi))

    # YENİ group-title
    if yeni_grup_satirlari:
        header_lines.append(f'#EXTINF:-1 group-title="[YENİ] [{source_name}] [Eklenme Tarihleri]",\n{m3u_url}\n')
        for extinf, url, eklenme_tarihi in yeni_grup_satirlari:
            # Eklenme tarihi extinf'e eklenebilir
            all_channels.append((f'{extinf} EklenmeTarihi="{eklenme_tarihi}"', url))

    # Orijinal group-title
    header_lines.append(f'#EXTINF:-1 group-title="[{source_name}] [Tüm Kanallar]",\n{m3u_url}\n')
    for extinf, url, eklenme_tarihi in orijinal_grup_satirlari:
        all_channels.append((f'{extinf} EklenmeTarihi="{eklenme_tarihi}"', url))

    # Kayıt güncelle
    save_json({str(k): v for k, v in yeni_link_date_map.items()}, link_json_file)

# Birleşik dosyayı yaz
with open(birlesik_dosya, "w", encoding="utf-8") as outfile:
    for line in header_lines:
        outfile.write(line)
    for extinf, stream_url in all_channels:
        outfile.write(extinf + "\n")
        outfile.write(stream_url + "\n")
