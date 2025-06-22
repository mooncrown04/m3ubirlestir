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
        return set(), {}
    with open(filename, encoding="utf-8") as f:
        lines = f.readlines()
    kanal_set = set()
    group_title_dict = {}
    last_extinf = None
    last_group_title = ""
    for line in lines:
        line = line.strip()
        if line.startswith("#EXTINF"):
            last_extinf = line
            m = re.search(r'group-title="(.*?)"', line)
            last_group_title = m.group(1) if m else ""
        elif last_extinf and line and not line.startswith("#"):
            extinf_core = re.sub(r'group-title="[^"]*"', '', last_extinf)
            anahtar = (extinf_core.strip(), line)
            kanal_set.add(anahtar)
            group_title_dict[anahtar] = last_group_title
            last_extinf = None
    return kanal_set, group_title_dict

# Eski dosyadan mevcut linkleri ve group-title'ları al
eski_kanallar, eski_group_titles = parse_m3u(eski_dosya)

# Yeni eklenenlerin tarihini oku
if os.path.exists(yeni_takip_json):
    with open(yeni_takip_json, "r", encoding="utf-8") as jf:
        yeni_dict = json.load(jf)
else:
    yeni_dict = {}

def anahtar2str(anahtar):
    return anahtar[0] + "||" + anahtar[1]

def str2anahtar(s):
    k, v = s.split("||", 1)
    return (k, v)

bugun = datetime.now().strftime("%Y-%m-%d")

with open(birlesik_dosya, "w", encoding="utf-8") as outfile:
    outfile.write("#EXTM3U\n")
    toplam_kanal_say = 0
    yeni_kanal_say = 0
    yeni_dict_tmp = {}

    for m3u_url, source_name in m3u_sources:
        try:
            response = requests.get(m3u_url, timeout=20)
            response.raise_for_status()
        except Exception as e:
            print(f"{m3u_url} alınamadı: {e}")
            continue

        lines = response.text.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("#EXTINF"):
                extinf = line
                stream_url = lines[i + 1].strip() if i + 1 < len(lines) else ""
                extinf_core = re.sub(r'group-title="[^"]*"', '', extinf)
                anahtar = (extinf_core.strip(), stream_url)
                anahtar_str = anahtar2str(anahtar)
                toplam_kanal_say += 1

                # Orijinal group-title'ı bul
                m = re.search(r'group-title="(.*?)"', extinf)
                orijinal_group_title = m.group(1) if m else ""

                if anahtar not in eski_kanallar:
                    # yeni link
                    yeni_kanal_say += 1
                    tarih = bugun
                    yeni_dict_tmp[anahtar_str] = tarih
                    yeni_group_title = orijinal_group_title.strip()
                    if yeni_group_title:
                        yeni_group_title += f" [{source_name} {tarih}]"
                    else:
                        yeni_group_title = f"[{source_name} {tarih}]"
                    yeni_extinf = re.sub(r'group-title="[^"]*"', f'group-title="{yeni_group_title}"', extinf)
                    if 'group-title="' not in yeni_extinf:
                        yeni_extinf = extinf.replace("#EXTINF:-1", f'#EXTINF:-1 group-title="{yeni_group_title}"')
                else:
                    # eski link, eski tarih ve eski group-title korunacak
                    tarih = yeni_dict.get(anahtar_str, "")
                    if tarih:
                        yeni_dict_tmp[anahtar_str] = tarih
                    eski_group_title = eski_group_titles.get(anahtar, "")
                    if eski_group_title:
                        # eski group-title'ı doğrudan kullan
                        yeni_extinf = re.sub(r'group-title="[^"]*"', f'group-title="{eski_group_title}"', extinf)
                        if 'group-title="' not in yeni_extinf:
                            yeni_extinf = extinf.replace("#EXTINF:-1", f'#EXTINF:-1 group-title="{eski_group_title}"')
                    else:
                        yeni_extinf = extinf

                outfile.write(yeni_extinf + "\n")
                if i + 1 < len(lines) and not lines[i + 1].startswith("#"):
                    outfile.write(stream_url + "\n")
                i += 2
            elif not line.startswith("#EXTM3U"):
                outfile.write(line + "\n")
                i += 1
            else:
                i += 1

# Tarihleri kaydet
with open(yeni_takip_json, "w", encoding="utf-8") as jf:
    json.dump(yeni_dict_tmp, jf, ensure_ascii=False, indent=2)

print(f"Toplam kanal: {toplam_kanal_say}")
print(f"Yeni eklenen kanal: {yeni_kanal_say}")
