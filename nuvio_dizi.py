import requests
import os
import re

# --- AYARLAR ---
m3u_sources = [
    ("https://raw.githubusercontent.com/mooncrown04/m3ubirlestir/refs/heads/main/birlesik_diziler.m3u", "MoOnCrOwN"),
]

OUTPUT_FOLDER = "nuvio_dizi_parcalari"
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

# SİLİNECEK (İSTENMEYEN) DOMAİNLER
BAKILMAYACAK_LINKLER = ["vidmody.com", "diziyou"]

def normalize_for_alpha(s):
    if not s: return ""
    s = s.strip().lower()
    mapping = str.maketrans("ıİğĞüÜşŞöÖçÇ", "iigguussuocc")
    return s.translate(mapping)

def extract_clean_author(header):
    """group-author="📺 YENİ DİZİ [Zerk]" -> Zerk (Sadece ismi alır)"""
    match = re.search(r'group-author="[^"]*\[([^\]]+)\]"', header)
    if match:
        return match.group(1).strip()
    simple_match = re.search(r'group-author="([^"]+)"', header)
    if simple_match:
        return simple_match.group(1).split()[-1].replace("]", "").replace("[", "")
    return "M3U"

def clean_dizi_name_for_alpha(raw_name):
    """Harf tespiti için sadece dizi adını çeker"""
    clean = re.split(r' (S\d+E\d+|S\d+|Sezon|\d+\.\s?Sezon)', raw_name, flags=re.IGNORECASE)[0]
    return clean.strip()

# --- ANA MOTOR ---
dosya_gruplari = {}
gorulen_url_ler = set()

for m3u_url, source_name in m3u_sources:
    try:
        print(f"[+] {source_name} dizileri işleniyor...")
        req = requests.get(m3u_url, timeout=30)
        req.raise_for_status()
        lines = req.text.splitlines()
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("#EXTINF") and i + 1 < len(lines):
                url = lines[i+1].strip()
                
                # --- FİLTRELEME BAŞLANGICI ---
                # Link vidmody veya diziyou içeriyorsa tamamen atla
                if any(domain in url for domain in BAKILMAYACAK_LINKLER):
                    i += 2
                    continue
                # -----------------------------

                if url not in gorulen_url_ler:
                    gorulen_url_ler.add(url)
                    
                    inf_parts = line.split(',', 1)
                    header_raw = inf_parts[0]
                    name_raw = inf_parts[1].strip() if len(inf_parts) > 1 else "Bilinmeyen"
                    
                    # 1. Kaynak Temizliği
                    clean_author = extract_clean_author(header_raw)
                    new_header = re.sub(r'group-author="[^"]+"', f'group-author="{clean_author}"', header_raw)
                    
                    # 2. Harf Belirleme
                    dizi_adi_sade = clean_dizi_name_for_alpha(name_raw)
                    arama_ismi = normalize_for_alpha(dizi_adi_sade)
                    
                    if arama_ismi:
                        ilk = arama_ismi[0]
                        if ilk.isdigit(): grup = "0_9_rakam"
                        elif 'a' <= ilk <= 'z': grup = ilk
                        else: grup = "diger"
                    else:
                        grup = "diger"

                    if grup not in dosya_gruplari: dosya_gruplari[grup] = []
                    dosya_gruplari[grup].append({
                        "header": new_header,
                        "name": name_raw,
                        "url": url,
                        "sort": arama_ismi
                    })
                i += 2
            else: i += 1
    except Exception as e:
        print(f"Hata oluştu: {e}")

# --- KAYDETME ---
print("-" * 30)
for grup, kalemler in dosya_gruplari.items():
    kalemler.sort(key=lambda x: x["sort"])
    dosya_adi = f"dizi_{grup}.m3u"
    dosya_yolu = os.path.join(OUTPUT_FOLDER, dosya_adi)
    
    with open(dosya_yolu, "w", encoding="utf-8", newline='\n') as f:
        f.write("#EXTM3U\n")
        for item in kalemler:
            f.write(f"{item['header']},{item['name']}\n{item['url']}\n")
    print(f"✅ {dosya_adi} hazır (Gereksiz linkler elendi).")
