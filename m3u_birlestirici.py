import requests
import os
import re
import json
from datetime import datetime

m3u_sources = [
    ("https://raw.githubusercontent.com/Lunedor/iptvTR/refs/heads/main/FilmArsiv.m3u", "Lunedor"),
    ("https://tinyurl.com/2ao2rans", "powerboard"),
]

birlesik_dosya = "birlesik.m3u"
kayit_json_dir = "kayit_json"
ana_kayit_json = os.path.join(kayit_json_dir, "birlesik_links.json")

if not os.path.exists(kayit_json_dir):
    os.makedirs(kayit_json_dir)

def extract_channel_key(extinf_line, url_line):
    """EXTINF satırından ve URL'den kanal anahtarını çıkarır."""
    match = re.match(r'#EXTINF:.*?,(.*)', extinf_line)
    channel_name = match.group(1).strip() if match else ''
    url = url_line.strip()
    return (channel_name, url)

def parse_m3u_lines(lines):
    """M3U satırlarını ayrıştırarak kanal listesi oluşturur."""
    kanal_list = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            extinf_line = line
            if i + 1 < len(lines):
                url_line = lines[i + 1].strip()
                kanal_list.append((extract_channel_key(extinf_line, url_line), extinf_line, url_line))
            i += 2
        else:
            i += 1
    return kanal_list

def load_json(filename):
    """JSON dosyasını yükler."""
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"⚠️ {filename} bozuk veya geçersiz JSON içeriyor. Boş sözlük döndürülüyor.")
            return {}
    return {}

def save_json(data, filename):
    """Veriyi JSON dosyasına kaydeder."""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def format_tr_date(date_str):
    """YYYY-MM-DD formatındaki tarihi DD.MM.YYYY formatına dönüştürür."""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{d.day}.{d.month}.{d.year}"

def format_tr_datehour(date_str):
    """YYYY-MM-DD HH:MM:SS formatındaki tarihi DD.MM.YYYY HH:MM formatına dönüştürür."""
    d = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    return f"{d.day}.{d.month}.{d.year} {d.hour:02d}:{d.minute:02d}"

def ensure_group_title(extinf_line, source_name):
    """EXTINF satırında group-title yoksa ekler, varsa kaynağı ekler."""
    # group-title'ı bul
    m = re.search(r'group-title="([^"]*)"', extinf_line)
    if m:
        original_group = m.group(1)
        # Eğer kaynak adı zaten group-title içinde yoksa ekle
        if f"[{source_name}]" not in original_group:
            new_group_title = f'{original_group}[{source_name}]'
            return re.sub(r'group-title="[^"]*"', f'group-title="{new_group_title}"', extinf_line)
        return extinf_line # Zaten varsa değiştirmeden döndür
    else:
        # group-title yoksa ekle
        parts = extinf_line.split(" ", 1)
        if len(parts) == 2:
            prefix, rest = parts
            return f'{prefix} group-title="[{source_name}]" {rest}'
        else:
            # Sadece #EXTINF ve isim varsa
            return f'{extinf_line.strip()} group-title="[{source_name}]"'


def get_original_group_title(extinf_line):
    """EXTINF satırından orijinal group-title'ı çıkarır."""
    m = re.search(r'group-title="([^"]*)"', extinf_line)
    if m:
        return m.group(1)
    return None

# Güncel tarih ve saat bilgileri
today = datetime.now().strftime("%Y-%m-%d")
now_full = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
today_obj = datetime.strptime(today, "%Y-%m-%d")

# Mevcut kayıt dosyasını yükle
ana_link_dict = load_json(ana_kayit_json)

# Tüm kaynaklardan gelen yeni ve eski kanalları toplamak için listeler
tum_yeni_kanallar = [] # (key, extinf, url, eklenme_tarihi, eklenme_tarihi_saat, source_name)
tum_eski_kanallar = [] # (key, extinf, url, eklenme_tarihi, eklenme_tarihi_saat, source_name)

for m3u_url, source_name in m3u_sources:
    try:
        print(f"[+] {m3u_url} indiriliyor...")
        req = requests.get(m3u_url, timeout=20)
        req.raise_for_status() # HTTP hataları için istisna fırlatır
    except requests.exceptions.RequestException as e:
        print(f"❌ {m3u_url} alınamadı: {e}")
        continue
    
    lines = req.text.splitlines()
    kanal_list = parse_m3u_lines(lines)

    for (key, extinf, url) in kanal_list:
        dict_key = f"{key[0]}|{key[1]}"
        extinf_with_group = ensure_group_title(extinf, source_name) # group-title'ı ekle/güncelle

        if dict_key in ana_link_dict:
            # Kanal zaten kayıtlı, eski kanal olarak işaretle
            ilk_tarih = ana_link_dict[dict_key]["tarih"]
            ilk_tarih_saat = ana_link_dict[dict_key]["tarih_saat"]
            tum_eski_kanallar.append((key, extinf_with_group, url, ilk_tarih, ilk_tarih_saat, source_name))
        else:
            # Kanal yeni, kayıt defterine ekle ve yeni kanal olarak işaretle
            ana_link_dict[dict_key] = {"tarih": today, "tarih_saat": now_full}
            tum_yeni_kanallar.append((key, extinf_with_group, url, today, now_full, source_name))

# Birleşik M3U dosyasını yazma
with open(birlesik_dosya, "w", encoding="utf-8") as outfile:
    outfile.write("#EXTM3U\n")

    # Önce tüm yeni kanalları yaz
    for (key, extinf, url, eklenme_tarihi, eklenme_tarihi_saat, source_name) in tum_yeni_kanallar:
        ilk_ad = key[0]
        saat_str = format_tr_datehour(eklenme_tarihi_saat)
        group_title = f'[YENİ] [{source_name}]' # Yeni eklenenler için özel grup
        kanal_isim = f'{ilk_ad} [{saat_str}]'
        
        # group-title'ı güncelle
        extinf_final = re.sub(r'group-title="[^"]*"', f'group-title="{group_title}"', extinf)
        # Kanal ismini güncelle
        extinf_final = re.sub(r',.*', f',{kanal_isim}', extinf_final)
        
        outfile.write(extinf_final + "\n")
        outfile.write(url + "\n")

    # Sonra tüm eski kanalları yaz
    for (key, extinf, url, eklenme_tarihi, eklenme_tarihi_saat, source_name) in tum_eski_kanallar:
        ilk_ad = key[0]
        tarih_obj = datetime.strptime(eklenme_tarihi, "%Y-%m-%d")
        tarih_str = format_tr_date(eklenme_tarihi)
        
        # 1 ay (30 gün) kontrolü
        if (today_obj - tarih_obj).days < 30: # Eğer 30 günden az geçmişse hala "YENİ" olarak kabul et
            saat_str = format_tr_datehour(eklenme_tarihi_saat)
            new_group_title = f'[YENİ] [{source_name}]' # Hala yeni grubunda kalsın
            kanal_isim = f'{ilk_ad} [{saat_str}]'
        else:
            # 30 günden fazla geçmişse orijinal grubuna dönsün veya kaynak adı eklensin
            original_group = get_original_group_title(extinf)
            if original_group and f"[{source_name}]" not in original_group:
                new_group_title = f'{original_group}[{source_name}]'
            else:
                new_group_title = f'[{source_name}]' # Sadece kaynak adı, eğer orijinal grup yoksa veya zaten içeriyorsa
            kanal_isim = ilk_ad # Orijinal kanal ismi

        # group-title'ı güncelle
        extinf_final = re.sub(r'group-title="[^"]*"', f'group-title="{new_group_title}"', extinf)
        # Kanal ismini güncelle
        extinf_final = re.sub(r',.*', f',{kanal_isim}', extinf_final)
        
        outfile.write(extinf_final + "\n")
        outfile.write(url + "\n")

# Kayıt dosyasını güncelle
save_json(ana_link_dict, ana_kayit_json)
print(f"Kayıt dosyası güncellendi: {ana_kayit_json}")
print(f"\n✅ {len(tum_yeni_kanallar) + len(tum_eski_kanallar)} kanal başarıyla birleştirildi → {birlesik_dosya}")
