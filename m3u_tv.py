# --- ÇOKLU KATEGORİ VE FİLTRE AYARI ---
OZEL_FILTRELER = {
    "HABER": ["HABER GLOBAL", "HALK TV", "TGRT HABER", "SÖZCÜ TV", "NTV"],
    "Ulusal Kanallar": ["TRT 1", "KANAL D", "SHOW TV", "NOW", "TEVE 2"],
}

# --- OTOMATİK KATEGORİ DÜZELTME ---
# Eğer kanal ismi filtrelere takılmazsa, orijinal kategori ismini buna göre düzeltir.
CATEGORY_MAPPING = {
    "haber": "Haberler",
    "ulusal": "Ulusal Kanallar",
    "sport": "Spor",
    "spor": "Spor",
    "movie": "Sinema",
    "film": "Sinema",
    "belgesel": "Belgesel",
    "cocuk": "Çocuk & Aile",
    "kids": "Çocuk & Aile"
}

def clean_category(raw_cat: str, channel_name: str) -> str:
    upper_name = channel_name.upper()
    
    # 1. ADIM: Kanal ismi üzerinden özel filtre kontrolü (En öncelikli)
    for hedef_kategori, kelimeler in OZEL_FILTRELER.items():
        for kelime in kelimeler:
            if kelime.upper() in upper_name:
                return hedef_kategori

    # 2. ADIM: Orijinal kategori ismini temizle ve Map üzerinden düzelt
    if not raw_cat: return "Genel"
    
    # Orijinal kategoriyi küçük harfe çevirip temizleyelim
    raw_cat_lower = raw_cat.lower()
    
    # Mapping kontrolü (Örn: Orijinal kategori "CANLI HABER" ise içinde "haber" var mı?)
    for anahtar, hedef_isim in CATEGORY_MAPPING.items():
        if anahtar in raw_cat_lower:
            return hedef_isim

    # 3. ADIM: Hiçbirine uymazsa sadece gereksiz karakterleri silip bırak
    clean = re.sub(r'[|\[\(].*?[|\]\)]', '', raw_cat) 
    clean = clean.replace(':', '').strip()
    return clean.title() if clean else "Genel"
