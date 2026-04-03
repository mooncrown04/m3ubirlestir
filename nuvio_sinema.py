import requests
import os
import re
import json
from datetime import datetime, timedelta, timezone
from collections import Counter

# --- AYARLAR ---
m3u_sources = [
    ("https://raw.githubusercontent.com/mooncrown04/m3ubirlestir/refs/heads/main/birlesik_sinema.m3u", "mooncrown"),
]

birlesik_dosya = "nuvio_sinema.m3u"
kayit_json_dir = "kayit_json_nuvio"
ana_kayit_json = os.path.join(kayit_json_dir, "nuvio_sinema_links.json")

if not os.path.exists(kayit_json_dir):
    os.makedirs(kayit_json_dir)

def normalize_url(url):
    return url.strip().rstrip('/')

def clean_and_extract(raw_name):
    # İsim temizleme ve yıl ayıklama
    clean_name = re.split(r' (Aksiyon|Korku|Dram|Gerilim|Komedi|Macera|Polisiye|Biyografi|Müzik|Gizem|Bilim-Kurgu|Romantik|Belgesel|Western|Animasyon|Aile|Suç)--', raw_name)[0]
    clean_name = clean_name.split(' Aksiyon-')[0].split('--')[0].strip()
    
    year = ""
    year_match = re.search(r'(?:\s|[\(\[])(\d{4})[\)\]]?$', clean_name)
    if year_match:
        found_num = year_match.group(1)
        if 1920 <= int(found_num) <= 2027:
            year = found_num
            clean_name = re.sub(r'[\(\[]?' + found_num + r'[\)\]]?$', '', clean_name).strip()

    clean_name = clean_name.replace("_", " ").replace("🌟", "").replace(":", "").replace("🔥", "").strip()
    return ' '.join(clean_name.split()), year

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
                url = lines[i + 1].strip()
                norm_url = normalize_url(url)
                
                if norm_url not in gorulen_url_ler:
                    gorulen_url_ler.add(norm_url)
                    # Orijinal isim virgülden sonra gelir
                    name_match = re.search(r',([^,]*)$', line)
                    raw_name = name_match.group(1).strip() if name_match else "Bilinmeyen Film"
                    hepsi_gecici.append({"raw": raw_name, "url": url})
                i += 2
            else: i += 1
    except Exception as e: print(f"⚠️ Hata: {e}")

if hepsi_gecici:
    with open(birlesik_dosya, "w", encoding="utf-8", newline='\n') as f:
        f.write("#EXTM3U\n")
        for item in hepsi_gecici:
            temiz_isim, film_yili = clean_and_extract(item["raw"])
            
            # Yıl varsa ismin yanına ekle (Eklentinin filmi tanıması için en garanti yol budur)
            final_isim = f"{temiz_isim} ({film_yili})" if film_yili else temiz_isim
            
            # EN SADE SATIR: Sadece #EXTINF:-1 ve İsim
            f.write(f"#EXTINF:-1,{final_isim.strip()}\n")
            f.write(f"{item['url'].strip()}\n")

print(f"✅ Tamamlandı! En sade haliyle '{birlesik_dosya}' oluşturuldu.")
