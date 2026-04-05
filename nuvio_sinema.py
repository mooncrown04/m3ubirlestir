import requests
import os
import re

# --- AYARLAR ---
m3u_sources = [
    ("https://raw.githubusercontent.com/mooncrown04/m3ubirlestir/refs/heads/main/birlesik_sinema.m3u", "mooncrown"),
]

# ÇIKTI KLASÖRÜ: Tüm parçalar bu klasöre gidecek
OUTPUT_FOLDER = "nuvio_parcalari"
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

def normalize_for_alpha(s):
    if not s: return ""
    s = s.strip().lower()
    mapping = str.maketrans("ıİğĞüÜşŞöÖçÇ", "iigguussuocc")
    return s.translate(mapping)

def clean_name_only(raw_name):
    clean = re.split(r' (Aksiyon|Korku|Dram|Gerilim|Komedi|Macera|Polisiye|Biyografi|Müzik|Gizem|Bilim-Kurgu|Romantik|Belgesel|Western|Animasyon|Aile|Suç)--', raw_name)[0]
    clean = clean.split(' Aksiyon-')[0].split('--')[0].strip()
    year_match = re.search(r'(\d{4})', clean)
    if year_match:
        clean = clean.replace(year_match.group(1), "").replace("(", "").replace(")", "").strip()
    return ' '.join(clean.split())

# --- ANA MOTOR ---
dosya_gruplari = {} 
gorulen_url_ler = set()

for m3u_url, source_name in m3u_sources:
    try:
        print(f"[+] {source_name} indiriliyor...")
        req = requests.get(m3u_url, timeout=25)
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
                    name_raw = inf_parts[1].strip() if len(inf_parts) > 1 else "Bilinmeyen"
                    
                    temiz_isim = clean_name_only(name_raw)
                    arama_ismi = normalize_for_alpha(temiz_isim)
                    
                    # Harf Belirleme
                    if arama_ismi:
                        ilk = arama_ismi[0]
                        grup = "0_9_rakam" if ilk.isdigit() else (ilk if 'a' <= ilk <= 'z' else "diger")
                    else:
                        grup = "diger"

                    if grup not in dosya_gruplari: dosya_gruplari[grup] = []
                    dosya_gruplari[grup].append({"line": line, "name": temiz_isim, "url": url, "sort": arama_ismi})
                i += 2
            else: i += 1
    except Exception as e: print(f"Hata: {e}")

# --- KAYDETME ---
for grup, kalemler in dosya_gruplari.items():
    kalemler.sort(key=lambda x: x["sort"])
    # Klasör yolunu ekliyoruz: nuvio_parcalari/nuvio_a.m3u gibi
    dosya_yolu = os.path.join(OUTPUT_FOLDER, f"nuvio_{grup}.m3u")
    
    with open(dosya_yolu, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for item in kalemler:
            f.write(f"{item['line'].split(',')[0]},{item['name']}\n{item['url']}\n")
