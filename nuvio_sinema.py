import requests
import os
import re

# --- AYARLAR ---
m3u_sources = [
    ("https://raw.githubusercontent.com/mooncrown04/m3ubirlestir/refs/heads/main/birlesik_sinema.m3u", "mooncrown"),
]

birlesik_dosya = "nuvio_sinema.m3u"

def normalize_url(url):
    return url.strip().rstrip('/')

def clean_header_tags(header):
    """
    Belirtilen tagları (type, group-author, group-time, tvg-logo, group-title) 
    ve değerlerini header içinden siler.
    """
    # Silinmesi istenen anahtar kelimeler
    targets = ["type", "group-author", "group-time", "tvg-logo", "group-title"]
    
    for target in targets:
        # Örn: group-title="Sinema" veya type=movie yapılarını temizler
        # [^\s"]+ -> tırnaksız değerler için, "[^"]*" -> tırnaklı değerler için
        pattern = rf'\b{target}=(?:"[^"]*"|[^\s]+)'
        header = re.sub(pattern, "", header)
    
    # Fazla boşlukları temizle ve başı/sonu kırp
    header = ' '.join(header.split())
    return header

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
hepsi_gecici = []
gorulen_url_ler = set()

for m3u_url, source_name in m3u_sources:
    try:
        print(f"[+] {source_name} indiriliyor...")
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
                
                norm_url = normalize_url(url)
                if norm_url not in gorulen_url_ler:
                    gorulen_url_ler.add(norm_url)
                    
                    inf_parts = line.split(',', 1)
                    header_raw = inf_parts[0]
                    name_raw = inf_parts[1].strip() if len(inf_parts) > 1 else "Bilinmeyen"
                    
                    # HEADER TEMİZLEME BURADA YAPILIYOR
                    temiz_header = clean_header_tags(header_raw)
                    
                    hepsi_gecici.append({
                        "header": temiz_header, 
                        "name": name_raw, 
                        "url": url
                    })
                i += 2
            else: i += 1
    except Exception as e: print(f"⚠️ Hata: {e}")

if hepsi_gecici:
    with open(birlesik_dosya, "w", encoding="utf-8", newline='\n') as f:
        f.write("#EXTM3U\n")
        for item in hepsi_gecici:
            temiz_isim = clean_name_only(item["name"])
            f.write(f"{item['header']},{temiz_isim}\n")
            f.write(f"{item['url'].strip()}\n")

print(f"✅ İşlem tamam! Belirtilen taglar silindi ve Vidmody linkleri çıkarıldı.")
