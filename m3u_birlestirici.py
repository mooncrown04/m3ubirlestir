
import requests
import os

m3u_sources = [
     ("https://dl.dropbox.com/scl/fi/dj74gt6awxubl4yqoho07/github.m3u?rlkey=m7pzzvk27d94bkfl9a98tluai", "moon"),
    ("https://raw.githubusercontent.com/Zerk1903/zerkfilm/refs/heads/main/Filmler.m3u", "zerkfilm"),
    ("https://raw.githubusercontent.com/Lunedor/iptvTR/refs/heads/main/FilmArsiv.m3u", "iptvTR"),
]

birlesik_dosya = "birlesik.m3u"
eski_dosya = "birlesik_eski.m3u"

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
            # group-title'ı görmezden gel, kalan EXTINF ve URL'yi anahtar olarak al
            import re
            extinf_core = re.sub(r'group-title="[^"]*"', '', last_extinf)
            kanal_set.add((extinf_core.strip(), line))
            last_extinf = None
    return kanal_set

eski_kanallar = parse_m3u(eski_dosya)

with open(birlesik_dosya, "w", encoding="utf-8") as outfile:
    outfile.write("#EXTM3U\n")
    yeni_kanal_say = 0
    toplam_kanal_say = 0

    for m3u_url, source_name in m3u_sources:
        try:
            response = requests.get(m3u_url, timeout=10)
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
                import re
                extinf_core = re.sub(r'group-title="[^"]*"', '', extinf)
                anahtar = (extinf_core.strip(), stream_url)
                toplam_kanal_say += 1

                if anahtar not in eski_kanallar:
                    group_title = f'group-title="[{source_name} YENİ]"'
                    yeni_kanal_say += 1
                else:
                    group_title = f'group-title="[{source_name}]"'

                # Eski group-title'ı silip yenisini ekle
                if 'group-title="' in extinf:
                    yeni_extinf = re.sub(r'group-title="[^"]*"', group_title, extinf)
                else:
                    yeni_extinf = extinf.replace("#EXTINF:-1", f'#EXTINF:-1 {group_title}')
                outfile.write(yeni_extinf + "\n")
                if i + 1 < len(lines) and not lines[i + 1].startswith("#"):
                    outfile.write(stream_url + "\n")
                i += 2
            elif not line.startswith("#EXTM3U"):
                outfile.write(line + "\n")
                i += 1
            else:
                i += 1

print(f"Toplam kanal: {toplam_kanal_say}")
print(f"Yeni eklenen kanal: {yeni_kanal_say}")
print(f"Yeni eklenen kanal: {yeni_kanal_say}")
print(f"Yeni eklenen kanal: {yeni_kanal_say}")
