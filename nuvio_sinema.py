import requests
import os
import re
from collections import Counter

# --- AYARLAR ---
m3u_sources = [
    ("https://raw.githubusercontent.com/mooncrown04/m3ubirlestir/refs/heads/main/birlesik_sinema.m3u", "mooncrown"),
]

birlesik_dosya = "nuvio_sinema.m3u"

def normalize_url(url):
    return url.strip().rstrip('/')

def clean_name_minimal(raw_name):
    # Türleri ve -- işaretlerini temizle
    clean = re.split(r' (Aksiyon|Korku|Dram|Gerilim|Komedi|Macera|Polisiye|Biyografi|Müzik|Gizem|Bilim-Kurgu|Romantik|Belgesel|Western|Animasyon|Aile|Suç)--', raw_name)[0]
    clean = clean.split(' Aksiyon-')[0].split('--')[0].strip()
    
    # Yılı bul ve isimden ayır (Eklenti ismin içinde yılı sevmez, ultraClean her şeyi birleştirir)
    year = ""
    year_match = re.search(r'(\d{4})', clean)
    if year_match:
        year = year_match.group(1)
        clean = clean.replace(year, "").replace("(", "").replace(")", "").strip()
    
    clean = ' '.join(clean.split())
    return clean, year

# --- ANA MOTOR ---
hepsi_gecici = []
gorulen_url_ler = set()

for m3u_url, source_name in m3u_sources:
    try:
        print(f"[+] {source_name} indiriliyor...")
        req = requests.get(m3u_url, timeout=25)
        req.raise_for_status()
        lines = req.text.splitlines()
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("#EXTINF") and i + 1 < len(lines):
                url = lines[i+1].strip()
                norm_url = normalize_url(url)
                if norm_url not in gorulen_url_ler:
                    gorulen_url_ler.add(norm_url)
                    name_match = re.search(r',([^,]*)$', line)
                    raw_name = name_match.group(1).strip() if name_match else "Bilinmeyen"
                    hepsi_gecici.append({"raw": raw_name, "url": url})
                i += 2
            else: i += 1
    except Exception as e: print(f"⚠️ Hata: {e}")

if hepsi_gecici:
    with open(birlesik_dosya, "w", encoding="utf-8", newline='\n') as f:
        f.write("#EXTM3U\n")
        for item in hepsi_gecici:
            t_isim, t_yil = clean_name_minimal(item["raw"])
            
            # TYPE VIDEO DAHİL HER ŞEYİ SİLDİK
            # Sadece year bıraktık çünkü eklenti (JS) puanlama yaparken year="2024" arıyor.
            # Eğer bu da fazla gelirse bunu da silebiliriz ama puan düşer.
            if t_yil:
                header = f'#EXTINF:-1 year="{t_yil}"'
            else:
                header = f'#EXTINF:-1'
            
            f.write(f"{header},{t_isim}\n")
            f.write(f"{item['url'].strip()}\n")

print(f"✅ İşlem tamam! '{birlesik_dosya}' artık kuş gibi hafif.")
