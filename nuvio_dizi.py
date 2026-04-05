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

def get_season_num(name_raw):
    """İsmin içinden sezon numarasını çeker (S02 -> 2, 2. Sezon -> 2)"""
    # S01, s01, S1 formatlarını ara
    match = re.search(r'[Ss](\d+)', name_raw)
    if match:
        return int(match.group(1))
    # '2. Sezon' veya '2 Sezon' formatlarını ara
    match_alt = re.search(r'(\d+)\.?\s?Sezon', name_raw, re.I)
    if match_alt:
        return int(match_alt.group(1))
    return 1 # Hiçbir şey bulamazsa varsayılan Sezon 1

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
    """Virgülden sonrasını temizler: Sadece 'Dizi Adı S01E01' bırakır."""
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
                    final_name = clean_name_for_output(name_raw)
                    
                    # 2. Author Temizliği
                    author_name = extract_clean_author(clean_header)
                    final_header = re.sub(r'group-author="[^"]+"', f'group-author="{author_name}"', clean_header)
                    
                    # 3. SEZON VE HARF GRUBU (PARÇALAMA MANTIĞI)
                    sezon_num = get_season_num(name_raw)
                    dizi_adi_sade = clean_dizi_name_for_alpha(name_raw)
                    arama_ismi = normalize_for_alpha(dizi_adi_sade)
                    
                    if arama_ismi:
                        ilk = arama_ismi[0]
                        harf_grubu = "0_9_rakam" if ilk.isdigit() else (ilk if 'a' <= ilk <= 'z' else "diger")
                        # Önemli: Dosya anahtarı Harf + Sezon (Örn: b_s1)
                        grup_anahtari = f"{harf_grubu}_s{sezon_num}"
                    else:
                        grup_anahtari = "diger"

                    if grup_anahtari not in dosya_gruplari:
                        dosya_gruplari[grup_anahtari] = []
                    
                    dosya_gruplari[grup_anahtari].append({
                        "header": final_header,
                        "name": final_name,
                        "url": url,
                        "sort": arama_ismi
                    })
                i += 2
            else: i += 1
    except Exception as e:
        print(f"Hata oluştu: {e}")

# --- KAYDETME ---
print("-" * 30)
for grup_id, kalemler in dosya_gruplari.items():
    kalemler.sort(key=lambda x: x["sort"])
    dosya_adi = f"dizi_{grup_id}.m3u"
    dosya_yolu = os.path.join(OUTPUT_FOLDER, dosya_adi)
    
    with open(dosya_yolu, "w", encoding="utf-8", newline='\n') as f:
        f.write("#EXTM3U\n")
        for item in kalemler:
            f.write(f"{item['header']},{item['name']}\n{item['url']}\n")
    print(f"✅ {dosya_adi} oluşturuldu. ({len(kalemler)} link)")
