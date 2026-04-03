import requests
import os
import re
import json
from datetime import datetime, timedelta, timezone
from collections import Counter

# --- AYARLAR ---
m3u_sources = [
    ("https://raw.githubusercontent.com/Lunedor/iptvTR/refs/heads/main/FilmArsiv.m3u", "Lunedor"),
    ("https://raw.githubusercontent.com/Zerk1903/zerkfilm/refs/heads/main/Filmler.m3u", "Zerk"),
    ("https://tinyurl.com/2ao2rans", "powerboard"),
]

birlesik_dosya = "birlesik_sinema.m3u"
kayit_json_dir = "kayit_json_sinema"
ana_kayit_json = os.path.join(kayit_json_dir, "birlesik_sinema_links.json")
KOPYA_IKONU = "🔄"

if not os.path.exists(kayit_json_dir):
    os.makedirs(kayit_json_dir)

def normalize_url(url):
    return url.strip().rstrip('/')

# --- İSİM TEMİZLEME VE YIL AYIKLAMA (GELİŞTİRİLDİ) ---
def clean_and_extract(raw_name):
    # Hem (2016) hem [2016] formatını yakalar
    year_match = re.search(r'[\(\[](\d{4})[\)\]]', raw_name)
    year = year_match.group(1) if year_match else ""
    
    # Parantezleri ve içindekileri siler
    clean_name = re.sub(r'[\(\[].*?[\)\]]', '', raw_name)
    # Özel karakterleri ve alt çizgileri temizler
    clean_name = clean_name.replace("_", " ").replace("🌟", "").replace(":", "").strip()
    # Çift boşlukları tek boşluğa indirir
    clean_name = ' '.join(clean_name.split())
    return clean_name, year

def process_metadata(extinf_line, source_name, add_time, year_val, is_new=False, is_duplicate=False):
    # 1. Type Etiketi
    if 'type="video"' not in extinf_line:
        extinf_line = extinf_line.replace("#EXTINF:-1", '#EXTINF:-1 type="video"')
    
    # 2. YEAR TAGI (JS'nin Dangal'ı bulması için en kritik yer burası)
    # Mevcut bir year tagı varsa güncelle, yoksa type'dan sonraya ekle
    if year_val:
        if 'year="' in extinf_line:
            extinf_line = re.sub(r'year="[^"]*"', f'year="{year_val}"', extinf_line)
        else:
            extinf_line = extinf_line.replace('type="video"', f'type="video" year="{year_val}"')

    # 3. Etiket ve Zaman Bilgileri
    prefix = ""
    if is_new: prefix += "✨YENİ "
    if is_duplicate: prefix += f"{KOPYA_IKONU} "
    status_label = f"{prefix}[{source_name}]".strip()
    
    # Author ve Time etiketlerini güvenli şekilde enjekte et
    for tag, val in [("group-author", status_label), ("group-time", add_time.replace(" ", "_"))]:
        if f'{tag}="' in extinf_line:
            extinf_line = re.sub(f'{tag}="[^"]*"', f'{tag}="{val}"', extinf_line)
        else:
            extinf_line = extinf_line.replace('type="video"', f'type="video" {tag}="{val}"')
    
    return extinf_line

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
        print(f"[+] {source_name} çekiliyor...")
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
                    # Orijinal ismi virgülden sonra yakala
                    name_match = re.search(r',([^,]*)$', extinf)
                    raw_name = name_match.group(1).strip() if name_match else "Bilinmeyen Film"
                    hepsi_gecici.append({"raw": raw_name, "ext": extinf, "url": url, "src": source_name})
                i += 2
            else: i += 1
    except Exception as e: print(f"⚠️ Hata: {source_name} -> {e}")

if hepsi_gecici:
    # Kopya kontrolü için temiz isimleri say
    isim_sayaci = Counter([clean_and_extract(item["raw"])[0].lower() for item in hepsi_gecici])
    
    # UTF-8 ve Linux satır sonu ile dosyayı aç (JS uyumu için çok önemli)
    with open(birlesik_dosya, "w", encoding="utf-8", newline='\n') as f:
        f.write("#EXTM3U\n")
        for item in hepsi_gecici:
            temiz_isim, film_yili = clean_and_extract(item["raw"])
            is_dup = isim_sayaci[temiz_isim.lower()] > 1
            
            # Kayıt Kontrolü
            dict_key = f"{item['raw']}|{item['url']}"
            if dict_key in ana_link_dict:
                t_tarih, t_full = ana_link_dict[dict_key]["tarih"], ana_link_dict[dict_key]["tarih_saat"]
            else:
                ana_link_dict[dict_key] = {"tarih": today, "tarih_saat": now_full}
                t_tarih, t_full = today, now_full

            fark = (today_obj - datetime.strptime(t_tarih, "%Y-%m-%d")).days
            
            # Metadata işleme
            yeni_extinf = process_metadata(item["ext"], item["src"], t_full, film_yili, is_new=(fark < 30), is_duplicate=is_dup)
            
            # Sondaki ismi tertemiz yap (Virgülden sonrasını güncelle)
            yeni_extinf = re.sub(r',[^,]*$', f',{temiz_isim}', yeni_extinf)
            
            f.write(yeni_extinf + "\n" + item["url"] + "\n")

    with open(ana_kayit_json, "w", encoding="utf-8") as f:
        json.dump(ana_link_dict, f, ensure_ascii=False, indent=2)

print(f"✅ Başarılı! {len(gorulen_url_ler)} benzersiz film eklendi.")
