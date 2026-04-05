import requests
import os
import re

# --- AYARLAR ---
m3u_sources = [
    ("https://raw.githubusercontent.com/mooncrown04/m3ubirlestir/refs/heads/main/birlesik_sinema.m3u", "mooncrown"),
]

# Gruplandırma için harf aralıkları
# Not: Grupları ismin ilk harfinin normalize edilmiş haline göre belirliyoruz.
GURUPLAR = {
    "0-9_Rakam": r'^[0-9]',
    "A-D_Arasi": r'^[a-d]',
    "E-J_Arasi": r'^[e-j]',
    "K-P_Arasi": r'^[k-p]',
    "R-Z_Arasi": r'^[r-z]',
}

def normalize_for_alpha(s):
    """Harf grubunu bulmak için ismi geçici olarak İngilizce karakterlere çevirir."""
    if not s: return ""
    s = s.strip().lower()
    mapping = str.maketrans("ıİğĞüÜşŞöÖçÇ", "iigguussuocc")
    return s.translate(mapping)

def normalize_url(url):
    return url.strip().rstrip('/')

def clean_header_tags(header):
    targets = ["type", "group-author", "group-time", "tvg-logo", "group-title"]
    for target in targets:
        pattern = rf'\b{target}=(?:"[^"]*"|[^\s]+)'
        header = re.sub(pattern, "", header)
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
dosya_gruplari = {key: [] for key in GURUPLAR}
dosya_gruplari["Diger"] = []

gorulen_url_ler = set()

for m3u_url, source_name in m3u_sources:
    try:
        print(f"[+] {source_name} indiriliyor ve işleniyor...")
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
                    
                    temiz_header = clean_header_tags(header_raw)
                    temiz_isim = clean_name_only(name_raw)
                    
                    # Alfabetik kontrol için ismin en temiz halini al (i/ı dönüşümü yapılmış)
                    arama_ismi = normalize_for_alpha(temiz_isim)
                    
                    item = {
                        "header": temiz_header, 
                        "name": temiz_isim, 
                        "url": url
                    }

                    # --- ALFABETİK BÖLME MANTIĞI ---
                    matched = False
                    if arama_ismi:
                        for grup_adi, pattern in GURUPLAR.items():
                            if re.match(pattern, arama_ismi):
                                dosya_gruplari[grup_adi].append(item)
                                matched = True
                                break
                    
                    if not matched:
                        dosya_gruplari["Diger"].append(item)

                i += 2
            else: i += 1
    except Exception as e: print(f"⚠️ Hata: {e}")

# --- DOSYALARI KAYDETME ---
print("-" * 30)
for grup_adi, kalemler in dosya_gruplari.items():
    # Dosya isimlerini JS koduyla uyumlu hale getiriyoruz
    dosya_yolu = f"nuvio_sinema_{grup_adi.lower().replace('-', '_')}.m3u"
    
    with open(dosya_yolu, "w", encoding="utf-8", newline='\n') as f:
        f.write("#EXTM3U\n")
        if kalemler:
            for item in kalemler:
                f.write(f"{item['header']},{item['name']}\n")
                f.write(f"{item['url'].strip()}\n")
            print(f"✅ {dosya_yolu} oluşturuldu. ({len(kalemler)} film)")
        else:
            # Boş olsa bile dosyayı oluştur ki JS hata vermesin
            print(f"ℹ️ {grup_adi} boş, boş dosya oluşturuldu.")

print("-" * 30)
print("🚀 Tüm bölme ve temizleme işlemleri başarıyla tamamlandı!")
