
import requests

# Her m3u linkine karşı bir isim
m3u_sources = [
    ("https://raw.githubusercontent.com/Zerk1903/zerkfilm/refs/heads/main/Filmler.m3u", "zerkfilm"),
    ("https://raw.githubusercontent.com/Lunedor/iptvTR/refs/heads/main/FilmArsiv.m3u", "iptvTR"),
    # ("link", "İstediğinBaşlık"),
]

with open("birlesik.m3u", "w", encoding="utf-8") as outfile:
    outfile.write("#EXTM3U\n")
    for m3u_url, source_name in m3u_sources:
        try:
            response = requests.get(m3u_url, timeout=10)
            response.raise_for_status()
        except Exception as e:
            print(f"{m3u_url} alınamadı: {e}")
            continue

        lines = response.text.splitlines()
        for line in lines:
            if line.startswith("#EXTINF"):
                # Eğer zaten group-title varsa değiştir, yoksa ekle
                if 'group-title="' in line:
                    import re
                    yeni_satir = re.sub(r'group-title=".*?"', f'group-title="{source_name}"', line)
                else:
                    yeni_satir = line.replace("#EXTINF:-1", f'#EXTINF:-1 group-title="{source_name}"')
                outfile.write(yeni_satir + "\n")
            elif not line.startswith("#EXTM3U"):
                outfile.write(line + "\n")
