import requests
import os
import re

# --- AYARLAR ---
m3u_sources = [
    ("https://raw.githubusercontent.com/mooncrown04/m3ubirlestir/refs/heads/main/birlesik_sinema.m3u", "mooncrown"),
]

OUTPUT_FOLDER = "nuvio_parcalari"
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

def normalize_for_alpha(s):
    if not s: return ""
    s = s.strip().lower()
    mapping = str.maketrans("ıİğĞüÜşŞöÖçÇ", "iigguussuocc")
    return s.translate(mapping)

def clean_name_only(raw_name):
    # Tür takılarını temizle
    clean = re.split(r' (Aksiyon|Korku|Dram|Gerilim|Komedi|Macera|Polisiye|Biyografi|Müzik|Gizem|Bilim-Kurgu|Romantik|Belgesel|Western|Animasyon|Aile|Suç)--', raw_name)[0]
    clean = clean.split(' Aksiyon-')[0].split('--')[0].strip()
    year_match = re.search(r'(\d{4})', clean)
    if year_match:
        clean = clean.replace(year_match.group(1), "").replace("(", "").replace(")", "").strip()
    return ' '.join(clean.split())

def extract_clean_author(header):
    """group-author içindeki emoji ve gereksiz metinleri temizler."""
    match = re.search(r'group-author="([^"]+)"', header)
    if match:
        full_author = match.group(1)
        # Köşeli parantez içindeyse onu al (Zerk), değilse son kelimeyi al
        name_match = re.search(r'\[(.*?)\]', full_author)
        if name_match:
            return name_match.group(1).strip()
        # Eğer köşeli parantez yoksa emojileri ve "YENİ" gibi kelimeleri temizleyip son kelimeyi al
        clean_name = re.sub(r'[^\w\s]', '', full_author) # Emojileri temizle
        clean_name = clean_name.replace("YENİ", "").strip()
        return clean_name.split()[-1] if clean_name else "M3U"
    return "M3U"

# --- ANA MOTOR ---
dosya_gruplari = {} 
gorulen_url_ler = set()

for m3u_url, source_name in m3u_sources:
    try:
        print(f"[+] {source_name} işleniyor...")
        req = requests.get(m3u_url, timeout=25)
        req.raise_for_status()
        lines = req.text.splitlines()
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("#EXTINF") and i + 1 < len(lines):
                url = lines[i+1].strip()
                if "vidmody.com" in url:
                    i += 2
                    continue
                
                if url not in gorulen_url_ler:
                    gorulen_url_ler.add(url)
                    inf_parts = line.split(',', 1)
                    header_raw = inf_parts[0]
                    name_raw = inf_parts[1].strip() if len(inf_parts) > 1 else "Bilinmeyen"
                    
                    # 1. Kaynak İsmini Temizle (✨YENİ [Zerk] -> Zerk)
                    clean_author = extract_clean_author(header_raw)
                    
                    # 2. Header'ı güncelle (Yeni group-author formatı)
                    # Mevcut group-author'u silip yerine sadesini koyuyoruz
                    new_header = re.sub(r'group-author="[^"]+"', f'group-author="{clean_author}"', header_raw)
                    
                    temiz_isim = clean_name_only(name_raw)
                    arama_ismi = normalize_for_alpha(temiz_isim)
                    
                    if arama_ismi:
                        ilk = arama_ismi[0]
                        grup = "0_9_rakam" if ilk.isdigit() else (ilk if 'a' <= ilk <= 'z' else "diger")
                    else: grup = "diger"

                    if grup not in dosya_gruplari: dosya_gruplari[grup] = []
                    dosya_gruplari[grup].append({
                        "header": new_header,
                        "name": temiz_isim,
                        "url": url,
                        "sort": arama_ismi
                    })
                i += 2
            else: i += 1
    except Exception as e: print(f"Hata: {e}")

# --- KAYDETME ---
for grup, kalemler in dosya_gruplari.items():
    kalemler.sort(key=lambda x: x["sort"])
    dosya_yolu = os.path.join(OUTPUT_FOLDER, f"nuvio_{grup}.m3u")
    with open(dosya_yolu, "w", encoding="utf-8", newline='\n') as f:
        f.write("#EXTM3U\n")
        for item in kalemler:
            f.write(f"{item['header']},{item['name']}\n{item['url']}\n")
