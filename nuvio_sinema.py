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

def clean_name_only(raw_name):
    # Sadece isimdeki "Aksiyon--" gibi fazlalıkları temizler, diğer her şeyi bırakır.
    clean = re.split(r' (Aksiyon|Korku|Dram|Gerilim|Komedi|Macera|Polisiye|Biyografi|Müzik|Gizem|Bilim-Kurgu|Romantik|Belgesel|Western|Animasyon|Aile|Suç)--', raw_name)[0]
    clean = clean.split(' Aksiyon-')[0].split('--')[0].strip()
    
    # Yıl bilgisini isimden temizle (ama orijinal header içinde varsa dokunulmaz)
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
                
                # --- KRİTİK FİLTRE: vidmody.com içerenleri tamamen siler ---
                if "vidmody.com" in url:
                    i += 2
                    continue
                
                norm_url = normalize_url(url)
                if norm_url not in gorulen_url_ler:
                    gorulen_url_ler.add(norm_url)
                    
                    # Virgülün solundaki tüm bilgileri (group-title vb.) koru
                    inf_parts = line.split(',', 1)
                    header_raw = inf_parts[0]  # #EXTINF:-1 group-title="Sinema" vb.
                    name_raw = inf_parts[1].strip() if len(inf_parts) > 1 else "Bilinmeyen"
                    
                    hepsi_gecici.append({
                        "header": header_raw, 
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
            # Sadece ismi temizliyoruz, header'daki group-title vb. aynen kalıyor
            temiz_isim = clean_name_only(item["name"])
            
            f.write(f"{item['header']},{temiz_isim}\n")
            f.write(f"{item['url'].strip()}\n")

print(f"✅ İşlem tamam! Vidmody linkleri çıkarıldı, tüm metadata (grup/logo/etiket) korundu.")
