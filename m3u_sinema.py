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

# --- İSİM TEMİZLEME VE YIL AYIKLAMA SİHİRBAZI ---
def clean_and_extract(raw_name):
    """
    Girdi: (🌟8.0)Marslı :The Martian(Macera-Dram-Bilim-Kurgu)(2015)
    Çıktı: ('Marslı :The Martian', '2015')
    """
    # 1. Önce Yılı (4 hane) bul ve ayır
    year_match = re.search(r'\((\d{4})\)', raw_name)
    year = year_match.group(1) if year_match else ""
    
    # 2. Tüm parantez içlerini sil (Yıl, Puan, Türler dahil hepsi gider)
    # Örn: (🌟8.0) ve (Macera...) ve (2015) silinir.
    clean_name = re.sub(r'\(.*?\)', '', raw_name)
    
    # 3. Köşeli parantezleri sil [Zerk]
    clean_name = re.sub(r'\[.*?\]', '', clean_name)
    
    # 4. Alt tireleri boşluk yap ve fazla boşlukları temizle
    clean_name = clean_name.replace("_", " ").replace("🌟", "").strip()
    clean_name = ' '.join(clean_name.split())
    
    # 5. Eğer isim ":" ile bitiyorsa veya garip kalmışsa temizle
    clean_name = clean_name.strip(" :")
    
    return clean_name, year

def safe_extract_channel_key(extinf_line, url_line):
    clean_line = re.sub(r'logo="([^"]+?)"', lambda m: f'logo="{m.group(1).replace(",", "%2C")}"', extinf_line)
    match = re.search(r',([^,]*)$', clean_line)
    channel_name = match.group(1).strip() if match else 'Bilinmeyen Film'
    return (channel_name, url_line.strip())

# --- METADATA İŞLEME (TEMİZ VE TAGLI) ---
def process_metadata(extinf_line, source_name, add_time, year_val, is_new=False, is_duplicate=False):
    # Temel video tipi
    if 'type="video"' not in extinf_line:
        extinf_line = extinf_line.replace("#EXTINF:-1", '#EXTINF:-1 type="video"')
    
    # 1. YEAR TAGI (Ayrı bir veri olarak ekleniyor)
    if year_val:
        if 'year=' in extinf_line:
            extinf_line = re.sub(r'year="[^"]*"', f'year="{year_val}"', extinf_line)
        else:
            extinf_line = re.sub(r',', f' year="{year_val}",', extinf_line, count=1)

    # 2. GROUP-AUTHOR (Kaynak ve Kopya Durumu)
    prefix = ""
    if is_new: prefix += "✨YENİ "
    if is_duplicate: prefix += f"{KOPYA_IKONU} "
    status_label = f"{prefix}[{source_name}]".strip()
    
    if 'group-author=' in extinf_line:
        extinf_line = re.sub(r'group-author="[^"]*"', f'group-author="{status_label}"', extinf_line)
    else:
        extinf_line = re.sub(r',', f' group-author="{status_label}",', extinf_line, count=1)
    
    # 3. GROUP-TIME (Kalıcı Tarih)
    clean_time = add_time.replace(" ", "_")
    if 'group-time=' in extinf_line:
        extinf_line = re.sub(r'group-time="[^"]*"', f'group-time="{clean_time}"', extinf_line)
    else:
        extinf_line = re.sub(r',', f' group-time="{clean_time}",', extinf_line, count=1)
    
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
                if url not in gorulen_url_ler:
                    gorulen_url_ler.add(url)
                    key_data = safe_extract_channel_key(extinf, url)
                    hepsi_gecici.append((key_data, extinf, url, source_name))
                i += 2
            else: i += 1
    except Exception as e: print(f"⚠️ Hata: {source_name} -> {e}")

if len(hepsi_gecici) > 0:
    # Kopya kontrolü için isimleri normalize et
    isim_sayaci = Counter([clean_and_extract(item[0][0])[0].lower() for item in hepsi_gecici])
    
    with open(birlesik_dosya, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for (key, extinf, url, src) in hepsi_gecici:
            # 1. İsmi temizle, yılı yakala
            temiz_isim, film_yili = clean_and_extract(key[0])
            is_dup = isim_sayaci[temiz_isim.lower()] > 1
            
            # 2. Kayıt kontrolü
            dict_key = f"{key[0]}|{url}"
            if dict_key in ana_link_dict:
                t_tarih, t_full = ana_link_dict[dict_key]["tarih"], ana_link_dict[dict_key]["tarih_saat"]
            else:
                ana_link_dict[dict_key] = {"tarih": today, "tarih_saat": now_full}
                t_tarih, t_full = today, now_full

            fark = (today_obj - datetime.strptime(t_tarih, "%Y-%m-%d")).days
            
            # 3. Metadata'yı yaz (Year tagı dahil)
            extinf = process_metadata(extinf, src, t_full, film_yili, is_new=(fark < 30), is_duplicate=is_dup)
            
            # 4. Virgülden sonra SADECE temiz isim kalsın (Yıl yok!)
            extinf = re.sub(r',.*', f',{temiz_isim}', extinf)
            
            f.write(extinf + "\n" + url + "\n")

    with open(ana_kayit_json, "w", encoding="utf-8") as f:
        json.dump(ana_link_dict, f, ensure_ascii=False, indent=2)

print(f"✅ Başarılı! Çıktı formatı: ... year=\"{film_yili}\" ... ,{temiz_isim}")
