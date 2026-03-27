import requests
import os
import re
import json
from datetime import datetime
import pytz # pip install pytz komutuyla yüklenmiş olmalı

# Yapılandırma
m3u_sources = [
    ("https://raw.githubusercontent.com/Lunedor/iptvTR/refs/heads/main/FilmArsiv.m3u", "Lunedor"),
    ("https://tinyurl.com/2ao2rans", "powerboard"),
    # Buraya daha fazla kaynak ekleyebilirsin
]

birlesik_dosya = "birlesik.m3u"
kayit_json_dir = "kayit_json"
ana_kayit_json = os.path.join(kayit_json_dir, "birlesik_links.json")

# Klasör kontrolü
if not os.path.exists(kayit_json_dir):
    os.makedirs(kayit_json_dir)

def safe_extract_channel_key(extinf_line, url_line):
    """Logodaki virgüllerden etkilenmeden kanal ismini ve URL'yi çıkarır."""
    # Logo URL'si içindeki virgülleri korumaya al (virgülü %2C yap)
    clean_line = re.sub(r'logo="([^"]+?)"', lambda m: f'logo="{m.group(1).replace(",", "%2C")}"', extinf_line)
    
    # En sondaki virgülden sonrasını (kanal adını) al
    match = re.search(r',([^,]*)$', clean_line)
    channel_name = match.group(1).strip() if match else 'Bilinmeyen Kanal'
    
    # Kanal adındaki alt tireleri temizle
    channel_name = channel_name.replace("_", " ").strip()
    return (channel_name, url_line.strip())

def parse_m3u_lines(lines):
    """M3U satırlarını ayrıştırır."""
    kanal_list = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF") and i + 1 < len(lines):
            extinf_line = line
            url_line = lines[i + 1].strip()
            key_data = safe_extract_channel_key(extinf_line, url_line)
            kanal_list.append((key_data, extinf_line, url_line))
            i += 2
        else:
            i += 1
    return kanal_list

def load_json(filename):
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_json(data, filename):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Zaman Ayarları (Türkiye Saat Dilimi)
tr_tz = pytz.timezone("Europe/Istanbul")
now_tr = datetime.now(tr_tz)
today = now_tr.strftime("%Y-%m-%d")
now_full = now_tr.strftime("%Y-%m-%d %H:%M:%S")
today_obj = datetime.strptime(today, "%Y-%m-%d")

# Mevcut kayıtları yükle
ana_link_dict = load_json(ana_kayit_json)

tum_yeni_kanallar = []
tum_eski_kanallar = []
gorulen_url_ler = set() # Duplicate (Kopya) kontrolü için

print("🔄 İşlem başlıyor...")

for m3u_url, source_name in m3u_sources:
    try:
        print(f"[+] {source_name} indiriliyor...")
        req = requests.get(m3u_url, timeout=20)
        req.raise_for_status()
    except Exception as e:
        print(f"❌ {source_name} alınamadı: {e}")
        continue
    
    lines = req.text.splitlines()
    kanal_list = parse_m3u_lines(lines)

    for (key, extinf, url) in kanal_list:
        # KOPYA KONTROLÜ: Eğer bu URL daha önce bu çalışmada eklendiyse atla
        if url in gorulen_url_ler:
            continue
        gorulen_url_ler.add(url)

        dict_key = f"{key[0]}|{url}" # Anahtar olarak isim + url kullanıyoruz
        
        if dict_key in ana_link_dict:
            # Eski kanal
            ilk_tarih = ana_link_dict[dict_key]["tarih"]
            ilk_tarih_saat = ana_link_dict[dict_key]["tarih_saat"]
            tum_eski_kanallar.append((key, extinf, url, ilk_tarih, ilk_tarih_saat, source_name))
        else:
            # Yeni kanal
            ana_link_dict[dict_key] = {"tarih": today, "tarih_saat": now_full}
            tum_yeni_kanallar.append((key, extinf, url, today, now_full, source_name))

# Dosyaya Yazma
with open(birlesik_dosya, "w", encoding="utf-8") as outfile:
    outfile.write("#EXTM3U\n")

    # Yeni Kanallar (Grup: [YENİ])
    for (key, extinf, url, eklenme_tarihi, eklenme_tarihi_saat, source_name) in tum_yeni_kanallar:
        saat_dt = datetime.strptime(eklenme_tarihi_saat, "%Y-%m-%d %H:%M:%S")
        saat_str = saat_dt.strftime("%d.%m.%Y %H:%M")
        
        # EXTINF Manipülasyonu
        extinf = re.sub(r'group-title="[^"]*"', f'group-title="✨YENİ [{source_name}]"', extinf)
        extinf = re.sub(r',.*', f',{key[0]} [{saat_str}]', extinf)
        
        outfile.write(extinf + "\n" + url + "\n")

    # Eski Kanallar
    for (key, extinf, url, eklenme_tarihi, eklenme_tarihi_saat, source_name) in tum_eski_kanallar:
        tarih_obj = datetime.strptime(eklenme_tarihi, "%Y-%m-%d")
        fark_gun = (today_obj - tarih_obj).days
        
        if fark_gun < 30:
            # 30 günden azsa hala yeni sayılır
            saat_dt = datetime.strptime(eklenme_tarihi_saat, "%Y-%m-%d %H:%M:%S")
            saat_str = saat_dt.strftime("%d.%m.%Y %H:%M")
            extinf = re.sub(r'group-title="[^"]*"', f'group-title="✨YENİ [{source_name}]"', extinf)
            extinf = re.sub(r',.*', f',{key[0]} [{saat_str}]', extinf)
        else:
            # Normal kanal (Orijinal grubunu koru veya kaynak ekle)
            m_group = re.search(r'group-title="([^"]*)"', extinf)
            org_group = m_group.group(1) if m_group else source_name
            new_group = f"{org_group} [{source_name}]" if source_name not in org_group else org_group
            
            extinf = re.sub(r'group-title="[^"]*"', f'group-title="{new_group}"', extinf)
            extinf = re.sub(r',.*', f',{key[0]}', extinf)

        outfile.write(extinf + "\n" + url + "\n")

save_json(ana_link_dict, ana_kayit_json)
print(f"\n✅ Toplam {len(gorulen_url_ler)} benzersiz kanal kaydedildi.")
