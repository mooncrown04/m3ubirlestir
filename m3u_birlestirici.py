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
eski_kayitlar_klasoru = "eski_kayitlar"  # Her kaynak için ayrı eski dosya tutarız

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

def get_previous_header_info(eski_dosya):
    # Önceki başlık satırı ve tarihini al
    if not os.path.exists(eski_dosya):
        return None, None
    with open(eski_dosya, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#EXTINF:-1 group-title="):
                m = re.search(r"\[(.*?)\]\s*\[(.*?)\s*(\d{4}-\d{2}-\d{2})\s*\]", line)
                if m:
                    # m.group(2) kısmı "Yeni Link Yok" veya "X Yeni Link Eklendi"
                    return m.group(2).strip(), m.group(3).strip()
    return None, None

bugun = datetime.now().strftime("%Y-%m-%d")
header_lines = ["#EXTM3U\n"]
all_channels = []

for m3u_url, source_name in m3u_sources:
    # Kaynak için eski kayıt dosyası
    eski_dosya = os.path.join(eski_kayitlar_klasoru, f"{source_name}.m3u")
    # Eski kanallar
    if os.path.exists(eski_dosya):
        with open(eski_dosya, "r", encoding="utf-8") as f:
            eski_lines = f.readlines()
        eski_kanallar = parse_m3u_lines(eski_lines)
    else:
        eski_kanallar = set()

    # Önceki başlık türü ve tarihini bul
    onceki_bilgi, onceki_tarih = get_previous_header_info(eski_dosya)

    try:
        response = requests.get(m3u_url, timeout=20)
        response.raise_for_status()
    except Exception as e:
        print(f"{m3u_url} alınamadı: {e}")
        continue

    lines = response.text.splitlines()
    yeni_kanallar = parse_m3u_lines(lines)
    yeni_bu_kaynak = len(yeni_kanallar - eski_kanallar)

    # Bilgi satırı ve tarih
    if yeni_bu_kaynak > 0:
        group_title_info = f"[{source_name}] [ {yeni_bu_kaynak} Yeni Link Eklendi  {bugun} ]"
        kullanilacak_tarih = bugun
    else:
        # Önceki başlık ve tarihi koru
        if onceki_bilgi and onceki_tarih:
            if onceki_bilgi == "Yeni Link Yok":
                group_title_info = f"[{source_name}] [ Yeni Link Yok {onceki_tarih} ]"
            else:
                group_title_info = f"[{source_name}] [ {onceki_bilgi} {onceki_tarih} ]"
            kullanilacak_tarih = onceki_tarih
        else:
            group_title_info = f"[{source_name}] [ Yeni Link Yok {bugun} ]"
            kullanilacak_tarih = bugun

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
        f.write(f'#EXTINF:-1 group-title="{group_title_info}",\n{m3u_url}\n')
        for extinf, stream_url in zip(lines[::2], lines[1::2]):
            f.write(extinf.strip() + "\n")
            f.write(stream_url.strip() + "\n")

with open(birlesik_dosya, "w", encoding="utf-8") as outfile:
    for line in header_lines:
        outfile.write(line)
    for extinf, stream_url in all_channels:
        outfile.write(extinf + "\n")
        outfile.write(stream_url + "\n")
