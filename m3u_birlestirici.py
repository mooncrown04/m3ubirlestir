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
eski_kayitlar_klasoru = "eski_kayitlar"  # Her kaynak için ayrı eski dosya tutulacak

if not os.path.exists(eski_kayitlar_klasoru):
    os.makedirs(eski_kayitlar_klasoru)

def extract_channel_key(extinf_line, url_line):
    match = re.match(r'#EXTINF:.*?,(.*)', extinf_line)
    channel_name = match.group(1).strip() if match else ''
    url = url_line.strip()
    return (channel_name, url)

def parse_m3u_lines(lines):
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

def read_lines(filename):
    if not os.path.exists(filename):
        return []
    with open(filename, encoding="utf-8") as f:
        return f.readlines()

bugun = datetime.now().strftime("%Y-%m-%d")
header_lines = ["#EXTM3U\n"]
all_channels = []

for m3u_url, source_name in m3u_sources:
    # Kaynak için eski kayıt dosyası
    eski_dosya = os.path.join(eski_kayitlar_klasoru, f"{source_name}.m3u")
    eski_lines = read_lines(eski_dosya)
    eski_kanallar = parse_m3u_lines(eski_lines)

    try:
        response = requests.get(m3u_url, timeout=20)
        response.raise_for_status()
    except Exception as e:
        print(f"{m3u_url} alınamadı: {e}")
        continue

    lines = response.text.splitlines()
    yeni_kanallar = parse_m3u_lines(lines)

    # YENİ EKLENENLERİ BUL
    yeni_eklenen_kanallar = yeni_kanallar - eski_kanallar
    yeni_bu_kaynak = len(yeni_eklenen_kanallar)

    # Bilgi satırı
    if yeni_bu_kaynak > 0:
        group_title_info = f"[{source_name}] [ {yeni_bu_kaynak} Yeni Link Eklendi  {bugun} ]"
    else:
        group_title_info = f"[{source_name}] [ Yeni Link Yok {bugun} ]"

    header_lines.append(f'#EXTINF:-1 group-title="{group_title_info}",\n{m3u_url}\n')

    # Kanalları toplu olarak ekle
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            extinf = line
            stream_url = lines[i + 1].strip() if i + 1 < len(lines) else ""
            all_channels.append((extinf, stream_url))
            i += 2
        else:
            i += 1

    # Güncel listeyi eski dosyaya yaz (bir sonraki çalışmaya hazırlık)
    with open(eski_dosya, "w", encoding="utf-8") as f:
        for extinf, stream_url in zip(lines[::2], lines[1::2]):
            f.write(extinf.strip() + "\n")
            f.write(stream_url.strip() + "\n")

with open(birlesik_dosya, "w", encoding="utf-8") as outfile:
    for line in header_lines:
        outfile.write(line)
    for extinf, stream_url in all_channels:
        outfile.write(extinf + "\n")
        outfile.write(stream_url + "\n")
