import requests
import os
import re
from datetime import datetime

m3u_sources = [
    ("https://dl.dropbox.com/scl/fi/dj74gt6awxubl4yqoho07/github.m3u?rlkey=m7pzzvk27d94bkfl9a98tluai", "moon"),
    ("https://raw.githubusercontent.com/Lunedor/iptvTR/refs/heads/main/FilmArsiv.m3u", "iptvTR"),
    ("https://raw.githubusercontent.com/Zerk1903/zerkfilm/refs/heads/main/Filmler.m3u", "zerkfilm"),
]

birlesik_dosya = "birlesik.m3u"
eski_dosya = "birlesik_eski.m3u"

def extract_channel_key(extinf_line, url_line):
    """
    EXTINF satırındaki kanal adını ve url'yi anahtar olarak döndürür.
    """
    match = re.match(r'#EXTINF:.*?,(.*)', extinf_line)
    channel_name = match.group(1).strip() if match else ''
    url = url_line.strip()
    return (channel_name, url)

def parse_m3u(filename):
    """
    Verilen M3U dosyasındaki tüm (kanal adı, url) çiftlerini set olarak döndürür.
    """
    if not os.path.exists(filename):
        return set()
    with open(filename, encoding="utf-8") as f:
        lines = f.readlines()
    kanal_set = set()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            extinf_line = line
            if i + 1 < len(lines):
                url_line = lines[i + 1].strip()
                anahtar = extract_channel_key(extinf_line, url_line)
                kanal_set.add(anahtar)
            i += 2
        else:
            i += 1
    return kanal_set

# Eski dosyadaki kanallar
eski_kanallar = parse_m3u(eski_dosya)
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
    yeni_bu_kaynak = 0
    kanallar_blok = []
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            extinf = line
            stream_url = lines[i + 1].strip() if i + 1 < len(lines) else ""
            anahtar = extract_channel_key(extinf, stream_url)
            if anahtar not in eski_kanallar:
                yeni_bu_kaynak += 1
            kanallar_blok.append((extinf, stream_url))
            i += 2
        else:
            i += 1

    if yeni_bu_kaynak > 0:
        group_title_info = f"[{source_name}] [ {yeni_bu_kaynak} yeni link eklendi {bugun} ]"
    else:
        group_title_info = f"[{source_name}] [ yeni link yok {bugun} ]"
    header_lines.append(f'#EXTINF:-1 group-title="{group_title_info}",\n{m3u_url}\n')
    all_channels.extend(kanallar_blok)

with open(birlesik_dosya, "w", encoding="utf-8") as outfile:
    for line in header_lines:
        outfile.write(line)
    for extinf, stream_url in all_channels:
        outfile.write(extinf + "\n")
        outfile.write(stream_url + "\n")
