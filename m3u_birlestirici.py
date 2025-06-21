
import requests
import os
import re
import json

m3u_sources = [("https://dl.dropbox.com/scl/fi/dj74gt6awxubl4yqoho07/github.m3u?rlkey=m7pzzvk27d94bkfl9a98tluai", "moon"),
    ("https://raw.githubusercontent.com/Zerk1903/zerkfilm/refs/heads/main/Filmler.m3u", "zerkfilm"),
    ("https://raw.githubusercontent.com/Lunedor/iptvTR/refs/heads/main/FilmArsiv.m3u", "iptvTR"),
]

birlesik_dosya = "birlesik.m3u"
eski_dosya = "birlesik_eski.m3u"
yeni_takip_json = "yeni_linkler.json"
YENI_MAX = 3  # Kaç döngüde "YENİ" etiketi tutulacak?

# link anahtarı: (group-title'sız #EXTINF + url)
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

# Yeni/Eski sayaçlarını oku
if os.path.exists(yeni_takip_json):
    with open(yeni_takip_json, "r", encoding="utf-8") as jf:
        yeni_dict = json.load(jf)
else:
    yeni_dict = {}

# Sayaç arttırma işlemi için yeni dict (link anahtarını stringleştiriyoruz)
def anahtar2str(anahtar):
    return anahtar[0] + "||" + anahtar[1]

def str2anahtar(s):
    k, v = s.split("||", 1)
    return (k, v)

# Yeni dosya oluştur
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

                # Eğer yeni eklendiyse
                if anahtar not in eski_kanallar:
                    yeni_kanal_say += 1
                    # Bu linkin sayacını yükselt (veya başlat)
                    count = yeni_dict.get(anahtar_str, 0) + 1
                    yeni_dict_tmp[anahtar_str] = count
                    # group-title varsa sonuna [iptvTR YENİ] ekle
                    yeni_group_title = orijinal_group_title.strip()
                    if yeni_group_title:
                        yeni_group_title += f" [{source_name} YENİ]"
                    else:
                        yeni_group_title = f"[{source_name} YENİ]"
                    yeni_extinf = re.sub(r'group-title="[^"]*"', f'group-title="{yeni_group_title}"', extinf)
                    if 'group-title="' not in yeni_extinf:
                        yeni_extinf = extinf.replace("#EXTINF:-1", f'#EXTINF:-1 group-title="{yeni_group_title}"')
                else:
                    # Eski bir linkse
                    count = yeni_dict.get(anahtar_str, 0)
                    if count > 0:
                        count += 1
                        if count > YENI_MAX:
                            # YENİ etiketi YENİSİZ'e döner
                            yeni_group_title = orijinal_group_title
                            if yeni_group_title:
                                # Sonunda [iptvTR YENİ] varsa, [iptvTR] yap
                                yeni_group_title = re.sub(rf'\[{source_name} YENİ\]', f'[{source_name}]', yeni_group_title)
                            yeni_dict_tmp[anahtar_str] = 0  # sayacı sıfırla
                        else:
                            # YENİ etiketi devam
                            yeni_group_title = orijinal_group_title
                            if yeni_group_title and f"[{source_name} YENİ]" not in yeni_group_title:
                                yeni_group_title += f" [{source_name} YENİ]"
                            yeni_dict_tmp[anahtar_str] = count
                        yeni_extinf = re.sub(r'group-title="[^"]*"', f'group-title="{yeni_group_title}"', extinf)
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

# Sayaçları kaydet
with open(yeni_takip_json, "w", encoding="utf-8") as jf:
    json.dump(yeni_dict_tmp, jf, ensure_ascii=False, indent=2)

print(f"Toplam kanal: {toplam_kanal_say}")
print(f"Yeni eklenen kanal: {yeni_kanal_say}")
