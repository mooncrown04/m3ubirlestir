import requests
import os
import re

# --- AYARLAR ---
m3u_sources = [
    ("https://raw.githubusercontent.com/mooncrown04/m3ubirlestir/refs/heads/main/birlesik_sinema.m3u", "mooncrown"),
]

# Çıktı klasörü (Ana dizini kirletmemek için)
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
    # Yıl bilgisini temizle
    year_match = re.search(r'(\d{4})', clean)
    if year_match:
        clean = clean.replace(year_match.group(1), "").replace("(", "").replace(")", "").strip()
    return ' '.join(clean.split())

# --- ANA MOTOR ---
dosya_gruplari = {} 
gorulen_url_ler = set()

for m3u_url, source_name in m3u_sources:
    try:
        print(f"[+] {source_name} indiriliyor ve parçalanıyor...")
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
                    
                    temiz_isim = clean_name_only(name_raw)
                    arama_ismi = normalize_for_alpha(temiz_isim)
                    
                    # Harf Belirleme (a, b, c... 0_9_rakam veya diger)
                    if arama_ismi:
                        ilk = arama_ismi[0]
                        if ilk.isdigit(): grup = "0_9_rakam"
                        elif 'a' <= ilk <= 'z': grup = ilk
                        else: grup = "diger"
                    else: grup = "diger"

                    if grup not in dosya_gruplari: dosya_gruplari[grup] = []
                    dosya_gruplari[grup].append({
                        "header": header_raw,
                        "name": temiz_isim,
                        "url": url,
                        "sort": arama_ismi
                    })
                i += 2
            else: i += 1
    except Exception as e: print(f"Hata: {e}")

# --- KAYDETME ---
print("-" * 30)
for grup, kalemler in dosya_gruplari.items():
    kalemler.sort(key=lambda x: x["sort"])
    dosya_adi = f"nuvio_{grup}.m3u"
    dosya_yolu = os.path.join(OUTPUT_FOLDER, dosya_adi)
    
    with open(dosya_yolu, "w", encoding="utf-8", newline='\n') as f:
        f.write("#EXTM3U\n")
        for item in kalemler:
            f.write(f"{item['header']},{item['name']}\n{item['url']}\n")
    print(f"✅ {dosya_adi} -> {OUTPUT_FOLDER}/ klasörüne eklendi.")
