import requests
import os
import re
import json
from datetime import datetime

m3u_sources = [
    ("https://dl.dropbox.com/scl/fi/dj74gt6awxubl4yqoho07/github.m3u?rlkey=m7pzzvk27d94bkfl9a98tluai", "moon"),
    ("https://raw.githubusercontent.com/Lunedor/iptvTR/refs/heads/main/FilmArsiv.m3u", "iptvTR"),
    ("https://raw.githubusercontent.com/Zerk1903/zerkfilm/refs/heads/main/Filmler.m3u", "zerkfilm"),
]

birlesik_dosya = "birlesik.m3u"
eski_dosya = "birlesik_eski.m3u"
yeni_takip_json = "yeni_linkler.json"

def parse_m3u(filename):
    if not os.path.exists(filename):
        return set()
    with open(filename, encoding="utf-8") as f:
        lines = f.readlines()
    kanal_set = set()
    last_extinf = None
    for line in lines:
        line = line.strip()
        if line.startswith("#EXTINF"):
            last_extinf = line
        elif last_extinf and line and not line.startswith("#"):
            extinf_core = re.sub(r'group-title="[^"]*"', '', last_extinf)
            anahtar = (extinf_core.strip(), line)
            kanal_set.add(anahtar)
            last_extinf = None
    return kanal_set

# Eski dosyadan mevcut linkleri al
eski_kanallar = parse_m3u(eski_dosya)

# Yeni eklenenlerin tarihini oku
if os.path.exists(yeni_takip_json):
    with open(yeni_takip_json, "r", encoding="utf-8") as jf:
        yeni_dict = json.load(jf)
else:
    yeni_dict = {}

def anahtar2str(anahtar):
    return anahtar[0] + "||" + anahtar[1]

bugun = datetime.now().strftime("%Y-%m-%d")

header_lines = ["#EXTM3U\n"]
all_channels = []

for m3u_url, source_name in m3u_sources:
    try:
        response = requests.get(m3u_url, timeout=20)
        response.raise_for_status()
    except Exception as e:
        print(f"{m3u_url} alınamadı: {e}")
        continue

    lines = response.text.splitlines()
    i = 0
    yeni_bu_kaynak = 0  # Yeni link sayacı
    kanallar_blok = []

    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            extinf = line
            stream_url = lines[i + 1].strip() if i + 1 < len(lines) else ""
            extinf_core = re.sub(r'group-title="[^"]*"', '', extinf)
            anahtar = (extinf_core.strip(), stream_url)
            anahtar_str = anahtar2str(anahtar)

            # Yeni mi?
            if anahtar not in eski_kanallar:
                yeni_bu_kaynak += 1

            kanallar_blok.append((extinf, stream_url))
            i += 2
        else:
            i += 1

    # Her kaynak için group-title ile özet başlık satırı
    if yeni_bu_kaynak > 0:
        group_title_info = f"[{source_name}] [ {yeni_bu_kaynak} yeni link eklendi {bugun} ]"
    else:
        group_title_info = f"[{source_name}] [ yeni link yok {bugun} ]"
    header_lines.append(f'#EXTINF:-1 group-title="{group_title_info}",\n{m3u_url}\n')

    # Asıl kanallar, aşağıya eklenecek
    all_channels.extend(kanallar_blok)

# Dosyaya yaz
with open(birlesik_dosya, "w", encoding="utf-8") as outfile:
    for line in header_lines:
        outfile.write(line)
    for extinf, stream_url in all_channels:
        outfile.write(extinf + "\n")
        outfile.write(stream_url + "\n")
