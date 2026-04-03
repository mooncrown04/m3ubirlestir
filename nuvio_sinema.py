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
    """
    Nuvio JS motorundaki 'ultraClean' mantığına hazırlık yapar.
    """
    # 1. Tür bilgilerini ve sonundaki -- kısımlarını temizle
    clean_name = re.split(r' (Aksiyon|Korku|Dram|Gerilim|Komedi|Macera|Polisiye|Biyografi|Müzik|Gizem|Bilim-Kurgu|Romantik|Belgesel|Western|Animasyon|Aile|Suç)--', raw_name)[0]
    clean_name = clean_name.split(' Aksiyon-')[0].split('--')[0].strip()
    
    # 2. Yılı ayıkla (Eklenti year="" etiketinden okuyacak)
    year = ""
    year_match = re.search(r'(\d{4})', clean_name)
    if year_match:
        found_num = year_match.group(1)
        if 1920 <= int(found_num) <= 2027:
            year = found_num
            # Yılı isimden çıkarıyoruz ki eklenti sadece harfleri eşleştirsin
            clean_name = clean_name.replace(found_num, "").replace("(", "").replace(")", "").strip()

    # 3. Fazla boşlukları al
    clean_name = ' '.join(clean_name.split())
    return clean_name, year

# --- ANA MOTOR ---
tr_tz = timezone(timedelta(hours=3))
now_tr = datetime.now(tr_tz)
today = now_tr.strftime("%Y-%m-%d")

ana_link_dict = {}
if os.path.exists(ana_kayit_json):
    with open(ana_kayit_json, "r", encoding="utf-8") as f:
        ana_link_dict = json.load(f)

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
                    # İsim virgülden sonradır
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
            temiz_isim, film_yili = clean_and_extract(item["raw"])
            
            # JSON Kayıt (Yeni film kontrolü için)
            dict_key = f"{item['raw']}|{item['url']}"
            if dict_key not in ana_link_dict:
                ana_link_dict[dict_key] = {"tarih": today}
            
            # JS MOTORU İÇİN GEREKLİ PARAMETRELER (EN SADE HALİ)
            # 1. type="video" -> JS içindeki mediaType kontrolü için
            # 2. year="2024"  -> JS içindeki (m3uYear === targetYear) kontrolü için
            meta = ['#EXTINF:-1', 'type="video"']
            if film_yili:
                meta.append(f'year="{film_yili}"')
            
            # Satırı Yazdır (Virgülden sonra sadece isim)
            f.write(f"{' '.join(meta)},{temiz_isim}\n")
            f.write(f"{item['url'].strip()}\n")

    with open(ana_kayit_json, "w", encoding="utf-8") as f:
        json.dump(ana_link_dict, f, ensure_ascii=False, indent=2)

print(f"✅ Nuvio JS Motoru ile tam uyumlu {birlesik_dosya} oluşturuldu.")
