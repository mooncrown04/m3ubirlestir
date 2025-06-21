import requests

# Birleştirilecek M3U linklerini buraya ekle
m3u_urls = [
    "https://raw.githubusercontent.com/Zerk1903/zerkfilm/refs/heads/main/Filmler.m3u",
    "https://raw.githubusercontent.com/Lunedor/iptvTR/refs/heads/main/FilmArsiv.m3u"
]
m3u_titles = [
    "Zerk1903",
    "Lunedor"
]
merged_content = ""
for url in m3u_urls:
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        merged_content += response.text.strip() + "\n"
    except Exception as e:
        print(f"{url} alınamadı: {e}")

with open("birlesik.m3u", "w", encoding="utf-8") as outfile:
    outfile.write("#EXTM3U\n")
    for m3u_url, title in zip(m3u_links, m3u_titles):
        response = requests.get(m3u_url)
        lines = response.text.splitlines()
        for line in lines:
            if line.startswith("#EXTINF"):
                if 'group-title="' in line:
                    # Var olan group-title'ı değiştir
                    import re
                    yeni_satir = re.sub(r'group-title=".*?"', f'group-title="{title}"', line)
                else:
                    yeni_satir = line.replace("#EXTINF:-1", f'#EXTINF:-1 group-title="{title}"')
                outfile.write(yeni_satir + "\n")
            elif not line.startswith("#EXTM3U"):
                outfile.write(line + "\n")
