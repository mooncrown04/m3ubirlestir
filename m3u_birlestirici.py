import requests

# Birleştirilecek M3U linklerini buraya ekle
m3u_urls = [
    "https://raw.githubusercontent.com/Zerk1903/zerkfilm/refs/heads/main/Filmler.m3u",
    "https://raw.githubusercontent.com/Lunedor/iptvTR/refs/heads/main/FilmArsiv.m3u"
]

merged_content = ""
for url in m3u_urls:
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        merged_content += response.text.strip() + "\n"
    except Exception as e:
        print(f"{url} alınamadı: {e}")

with open("birlesik.m3u", "w", encoding="utf-8") as f:
    f.write(merged_content)
