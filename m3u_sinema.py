import requests
import os
import re
import json
from datetime import datetime, timedelta, timezone
from collections import Counter

# --- AYARLAR ---
m3u_sources = [
	("https://raw.githubusercontent.com/mooncrown04/m3ubirlestir/refs/heads/main/filtrelisinema.js", "MoOnCrOwN"),
    ("https://tinyurl.com/2ao2rans", "powerboard"),
    ("https://raw.githubusercontent.com/Zerk1903/zerkfilm/refs/heads/main/Filmler.m3u", "Zerk"),
    ("https://raw.githubusercontent.com/Lunedor/iptvTR/refs/heads/main/FilmArsiv.m3u", "Lunedor"),    
]

birlesik_dosya = "birlesik_sinema.m3u"
kayit_json_dir = "kayit_json_sinema"
ana_kayit_json = os.path.join(kayit_json_dir, "birlesik_sinema_links.json")
KOPYA_IKONU = "🔄"

if not os.path.exists(kayit_json_dir):
    os.makedirs(kayit_json_dir)

def normalize_url(url):
    return url.strip().rstrip('/')

# --- HİBRİT İSİM TEMİZLEME VE YIL AYIKLAMA ---
def clean_and_extract(raw_name):
    clean_name = re.split(r' (Aksiyon|Korku|Dram|Gerilim|Komedi|Macera|Polisiye|Biyografi|Müzik|Gizem|Bilim-Kurgu|Romantik|Belgesel|Western|Animasyon|Aile|Suç)--', raw_name)[0]
    clean_name = clean_name.split(' Aksiyon-')[0].split('--')[0].strip()
    
    year = ""
    year_match = re.search(r'(?:\s|[\(\[])(\d{4})[\)\]]?$', clean_name)
    
    if year_match:
        found_num = year_match.group(1)
        val = int(found_num)
        if 1920 <= val <= 2027:
            year = found_num
            clean_name = re.sub(r'[\(\[]?' + found_num + r'[\)\]]?$', '', clean_name).strip()

    clean_name = clean_name.replace("_", " ").replace("🌟", "").replace(":", "").replace("🔥", "").strip()
    clean_name = ' '.join(clean_name.split())
    
    return clean_name, year

# --- METADATA İŞLEME (ORİJİNAL GROUP-TITLE KORUMALI) ---
def process_metadata(extinf_line, source_name, add_time, year_val, is_new=False, is_duplicate=False):
    # Logoyu orijinal satırdan çek
    logo_match = re.search(r'tvg-logo="([^"]*)"', extinf_line)
    logo = logo_match.group(1) if logo_match else ""
    
    # ORİJİNAL group-title'ı ÇEK: Eğer varsa al, yoksa boş bırak
    title_match = re.search(r'group-title="([^"]*)"', extinf_line)
    original_title = title_match.group(1) if title_match else ""
    
	
	# --- KRİTİK NOKTA: Mevcut group-author var mı kontrol et ---
    author_match = re.search(r'group-author="([^"]*)"', extinf_line)
    if author_match:
        # Eğer zaten bir author varsa, onu bozma, aynen kullan
        status_label = author_match.group(1)
    else:
        # Eğer yoksa, yeni etiketi oluştur (✨YENİ [Kaynak] gibi)
        prefix = ""
        if is_new: prefix += "✨YENİ "
        if is_duplicate: prefix += f"{KOPYA_IKONU} "
        status_label = f"{prefix}[{source_name}]".strip()

    clean_time = add_time.replace(" ", "_")

    parts = [
        '#EXTINF:-1',
        'type="video"',
        f'group-time="{clean_time}"',
        f'group-author="{status_label}"', # Burası artık mevcut olanı korur
        f'tvg-logo="{logo}"',
        f'group-title="{original_title}"'
    ]
    
    if year_val:
        parts.append(f'year="{year_val}"')
    
    return " ".join(parts).strip()
	
   

# --- ANA MOTOR ---
tr_tz = timezone(timedelta(hours=3)) 
now_tr = datetime.now(tr_tz)
today = now_tr.strftime("%Y-%m-%d")
now_full = now_tr.strftime("%Y-%m-%d %H:%M:%S")
today_obj = datetime.strptime(today, "%Y-%m-%d")

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
                extinf = line
                url = lines[i + 1].strip()
                norm_url = normalize_url(url)
                
                if norm_url not in gorulen_url_ler:
                    gorulen_url_ler.add(norm_url)
                    name_match = re.search(r',([^,]*)$', extinf)
                    raw_name = name_match.group(1).strip() if name_match else "Bilinmeyen Film"
                    hepsi_gecici.append({"raw": raw_name, "ext": extinf, "url": url, "src": source_name})
                i += 2
            else: i += 1
    except Exception as e: print(f"⚠️ {source_name} hatası: {e}")

if hepsi_gecici:
    isim_sayaci = Counter([clean_and_extract(item["raw"])[0].lower() for item in hepsi_gecici])
    
    with open(birlesik_dosya, "w", encoding="utf-8", newline='\n') as f:
        f.write("#EXTM3U\n")
        for item in hepsi_gecici:
            temiz_isim, film_yili = clean_and_extract(item["raw"])
            is_dup = isim_sayaci[temiz_isim.lower()] > 1
            
            dict_key = f"{item['raw']}|{item['url']}"
            if dict_key in ana_link_dict:
                t_tarih, t_full = ana_link_dict[dict_key]["tarih"], ana_link_dict[dict_key]["tarih_saat"]
            else:
                ana_link_dict[dict_key] = {"tarih": today, "tarih_saat": now_full}
                t_tarih, t_full = today, now_full

            fark = (today_obj - datetime.strptime(t_tarih, "%Y-%m-%d")).days
            
            # Metadata Header'ı oluştur
            yeni_header = process_metadata(item["ext"], item["src"], t_full, film_yili, (fark < 30), is_dup)
            
            # Karakter temizliği
            temiz_isim_final = temiz_isim.strip().replace('\xa0', ' ')
            
            # Yazım
            f.write(f"{yeni_header},{temiz_isim_final}\n")
            f.write(f"{item['url'].strip()}\n")

    with open(ana_kayit_json, "w", encoding="utf-8") as f:
        json.dump(ana_link_dict, f, ensure_ascii=False, indent=2)

print(f"✅ Bitti! Orijinal group-title verileri korunarak '{birlesik_dosya}' oluşturuldu.")
