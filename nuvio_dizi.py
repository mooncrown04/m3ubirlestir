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

BAKILMAYACAK_LINKLER = ["vidmody.com", "diziyou"]

def normalize_for_alpha(s):
    if not s: return ""
    s = s.strip().lower()
    mapping = str.maketrans("ıİğĞüÜşŞöÖçÇ", "iigguussuocc")
    return s.translate(mapping)

def clean_header_tags(header):
    """Gereksiz tüm etiketleri (logo, time, type) siler"""
    header = re.sub(r'\s?tvg-logo="[^"]*"', '', header)
    header = re.sub(r'\s?group-time="[^"]*"', '', header)
    header = re.sub(r'\s?type="video"', '', header)
    header = re.sub(r'\s+', ' ', header).strip()
    return header

def extract_clean_author(header):
    """Author kısmını sadeleştirir (Örn: [Zerk] -> Zerk)"""
    match = re.search(r'group-author="[^"]*\[([^\]]+)\]"', header)
    if match: return match.group(1).strip()
    simple_match = re.search(r'group-author="([^"]+)"', header)
    if simple_match: return simple_match.group(1).split()[-1].replace("]", "").replace("[", "")
    return "M3U"

def clean_name_for_output(raw_name):
    """
    Virgülden sonrasını temizler: Sadece 'Dizi Adı S01E01' bırakır.
    Bölüm isimlerini (Örn: - Pilot Bölüm) siler.
    """
    # Sezon/Bölüm kodunu yakala (S01E01 veya s01e01)
    match = re.search(r'(.*?\s?[Ss]\d+[Ee]\d+)', raw_name)
    if match:
        return match.group(1).strip()
    return raw_name.strip()

def clean_dizi_name_for_alpha(raw_name):
    """Dosya harf grubu belirlemek için sadece dizi adını alır"""
    clean = re.split(r' (S\d+E\d+|S\d+|Sezon|\d+\.\s?Sezon)', raw_name, flags=re.IGNORECASE)[0]
    return clean.strip()

# --- ANA MOTOR ---
dosya_gruplari = {}
gorulen_url_ler = set()

for m3u_url, source_name in m3u_sources:
    try:
        print(f"[+] {source_name} işleniyor...")
        req = requests.get(m3u_url, timeout=30)
        req.raise_for_status()
        lines = req.text.splitlines()
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("#EXTINF") and i + 1 < len(lines):
                url = lines[i+1].strip()
                
                # Domain filtresi
                if any(domain in url for domain in BAKILMAYACAK_LINKLER):
                    i += 2
                    continue

                if url not in gorulen_url_ler:
                    gorulen_url_ler.add(url)
                    
                    inf_parts = line.split(',', 1)
                    header_raw = inf_parts[0]
                    name_raw = inf_parts[1].strip() if len(inf_parts) > 1 else "Bilinmeyen"
                    
                    # 1. Header ve İsim Temizliği
                    clean_header = clean_header_tags(header_raw)
                    # YENİ: Virgülden sonrasını sadeleştir (Bölüm adını sil)
                    final_name = clean_name_for_output(name_raw)
                    
                    # 2. Author Temizliği
                    author_name = extract_clean_author(clean_header)
                    final_header = re.sub(r'group-author="[^"]+"', f'group-author="{author_name}"', clean_header)
                    
                    # 3. Harf Grubu Belirleme
                    dizi_adi_sade = clean_dizi_name_for_alpha(name_raw)
                    arama_ismi = normalize_for_alpha(dizi_adi_sade)
                    
                    if arama_ismi:
                        ilk = arama_ismi[0]
                        if ilk.isdigit(): grup = "0_9_rakam"
                        elif 'a' <= ilk <= 'z': grup = ilk
                        else: grup = "diger"
                    else: grup = "diger"

                    if grup not in dosya_gruplari: dosya_gruplari[grup] = []
                    dosya_gruplari[grup].append({
                        "header": final_header,
                        "name": final_name, # Sadeleşmiş isim
                        "url": url,
                        "sort": arama_ismi
                    })
                i += 2
            else: i += 1
    except Exception as e:
        print(f"Hata oluştu: {e}")

# --- KAYDETME ---
for grup, kalemler in dosya_gruplari.items():
    kalemler.sort(key=lambda x: x["sort"])
    dosya_adi = f"dizi_{grup}.m3u"
    dosya_yolu = os.path.join(OUTPUT_FOLDER, dosya_adi)
    
    with open(dosya_yolu, "w", encoding="utf-8", newline='\n') as f:
        f.write("#EXTM3U\n")
        for item in kalemler:
            f.write(f"{item['header']},{item['name']}\n{item['url']}\n")
    print(f"✅ {dosya_adi} maksimum sadeleştirme ile hazır.")
