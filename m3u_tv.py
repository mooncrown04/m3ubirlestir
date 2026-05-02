import asyncio
import logging
import aiohttp
import re
from dataclasses import dataclass
from typing import List

# --- LOG AYARLARI ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- AYARLAR ---
TIMEOUT = 7 
MAX_CONCURRENT_REQUESTS = 30 
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'

# --- 1. ÖZEL FİLTRELER VE KATEGORİ İÇİ SIRALAMA ---
# Buradaki kanallar hem ilgili kategoriye atanır hem de KATEGORİ İÇİNDE en üstte görünür.
OZEL_FILTRELER = {
    "Ulusal Kanallar": ["TRT 1", "ATV", "KANAL D", "SHOW TV", "NOW TV", "STAR TV", "TV 8", "BEYAZ TV", "TEVE 2", "A2", "TELE 1", "SHOWTURK", "KANAL 7"],
    "SPOR KANALLARI": ["BEIN SPORTS", "SPOR", "TARAFTAR", "EXXEN", "S SPORT", "TRT SPOR", "EUROSPORT", "FIGHT"],
    "HABER": ["HALK TV", "TV 100", "SÖZCÜ TV", "NTV", "HABER GLOBAL", "TRT HABER", "A HABER", "CNNTURK"],
    "SİNEMA & DİZİ": ["SİNEMA", "MOVIE", "FILM", "DIZI", "TV+", "NETFLIX", "ACTION"],
    "BELGESEL": ["BELGESEL", "DOCUMENTARY", "NAT GEO", "DISCOVERY", "HISTORY"],
    "ÇOCUK & AİLE": ["TRT COCUK", "CARTOON", "DISNEY", "MINIKA", "KIDS"]
}

# --- 2. KATEGORİ MAPPING ---
# Gelen ham grup isimlerini (raw_cat) senin istediğin standart isimlere dönüştürür.
CATEGORY_MAPPING = {
    "haber": "HABER", "news": "HABER",
    "ulusal": "Ulusal Kanallar", "yerel": "Ulusal Kanallar", "genel": "Ulusal Kanallar",
    "sport": "SPOR KANALLARI", "spor": "SPOR KANALLARI",
    "movie": "SİNEMA & DİZİ", "film": "SİNEMA & DİZİ", "dizi": "SİNEMA & DİZİ",
    "belgesel": "BELGESEL", "doc": "BELGESEL",
    "cocuk": "ÇOCUK & AİLE", "kids": "ÇOCUK & AİLE", "aile": "ÇOCUK & AİLE",
    "müzik": "MÜZİK", "music": "MÜZİK"
}

# --- 3. KANAL İSİM MAPPING (YENİ) ---
# Farklı yazılan kanal isimlerini senin istediğin tek bir formata sokar.
# Önemli: Küçük harf yazsanız dahi normalize_channel_identity fonksiyonu bunu büyük harfe çevirip eşleştirir.
CHANNEL_NAME_MAPPING = {
    "TV8": "TV 8",
    "TV 8 HD": "TV 8",
    "TV8.5": "TV 8.5",
    "NOW": "NOW TV",
    "NOW HD": "NOW TV",
    "FOX": "NOW TV",
    "TRT1": "TRT 1",
    "TRT 1 HD": "TRT 1",
    "KANALD": "KANAL D",
    "SHOW": "SHOW TV",
    "STAR": "STAR TV",
    "BEIN SPORT 1": "BEIN SPORTS 1",
    "NTV HD": "NTV",
    "HABERGLOBAL": "HABER GLOBAL"
}

M3U_SOURCES = [
    'https://raw.githubusercontent.com/smartgmr/cdn/refs/heads/main/Perfect.m3u',
    'https://raw.githubusercontent.com/Mertcantv/Mertcan/refs/heads/main/%C4%B0zle2.m3u',
    'https://raw.githubusercontent.com/primatzeka/kurbaga/main/NeonSpor/NeonSpor.m3u',
    'https://tinyurl.com/TVCANLI'
]

# Kategorilerin genel (dosya genelindeki) sıralaması
PRIORITY_GROUPS = list(OZEL_FILTRELER.keys())

@dataclass
class Channel:
    name: str
    category: str
    url: str
    logo: str = ""

def clean_category(raw_cat: str, channel_name: str) -> str:
    upper_name = channel_name.upper()
    for hedef_kategori, kelimeler in OZEL_FILTRELER.items():
        for kelime in kelimeler:
            # Sadece tam kelime eşleşmesi (Regex \b) ile yanlış kategori atamasını önleriz
            if re.search(rf'\b{re.escape(kelime.upper())}\b', upper_name):
                return hedef_kategori

    if not raw_cat: return "Genel"
    raw_cat_lower = raw_cat.lower()
    for anahtar, hedef_isim in CATEGORY_MAPPING.items():
        if anahtar in raw_cat_lower:
            return hedef_isim

    clean = re.sub(r'[|\[\(].*?[|\]\)]', '', raw_cat) 
    clean = clean.replace(':', '').strip()
    return clean.title() if clean else "Genel"

def normalize_channel_identity(name: str):
    """
    Kanal ismini temizler, gereksiz ekleri (HD, SD, vb.) atar 
    ve CHANNEL_NAME_MAPPING üzerinden ismi sabitler.
    """
    # Parantez içlerini sil (Örn: [TR] veya (Yedek))
    name = re.sub(r'[\[\(].*?[\]\)]', '', name)
    
    # Kalite ve yedek ibarelerini temizle
    patterns = [r'\bHD\b', r'\bSD\b', r'\bFHD\b', r'\b4K\b', r'\bYedek\b', r'\bBackup\b', r'\bHEVC\b', r'\bUHD\b']
    for p in patterns:
        name = re.sub(p, '', name, flags=re.IGNORECASE)
    
    # Temizlenmiş ve büyük harfe çevrilmiş isim
    clean_name = ' '.join(name.split()).strip().upper()

    # --- KANAL İSİM MAPPING KONTROLÜ ---
    # Eğer bu temizlenmiş isim bizim mapping listemizde varsa, oradaki karşılığını döndürür.
    for ham_isim, duzgun_isim in CHANNEL_NAME_MAPPING.items():
        if clean_name == ham_isim.upper():
            return duzgun_isim.upper()

    return clean_name

def get_channel_internal_priority(channel_name: str, category: str) -> int:
    """Kanalın kendi kategorisi içindeki sıra numarasını döndürür."""
    if category in OZEL_FILTRELER:
        search_list = OZEL_FILTRELER[category]
        upper_name = channel_name.upper()
        for i, keyword in enumerate(search_list):
            if keyword.upper() in upper_name:
                return i 
    return 999 

def get_group_priority(category_name: str) -> int:
    try:
        return PRIORITY_GROUPS.index(category_name)
    except ValueError:
        return 999

def parse_m3u(m3u_content: str) -> List[Channel]:
    channels = []
    pattern = re.compile(
        r'#EXTINF:.*?(?:group-title|tvg-group)="([^"]*)".*?(?:tvg-logo)="([^"]*)".*?,([^\n\r]+)[\s\n\r]+(http[^\s\n\r]+)', 
        re.IGNORECASE | re.DOTALL
    )
    matches = pattern.findall(m3u_content)
    seen_urls = set()
    for match in matches:
        raw_group, logo_url, raw_name, url = match
        url = url.strip()
        if url in seen_urls: continue
        
        # Önce ismi normalize ediyoruz, sonra kategoriyi belirliyoruz
        std_name = normalize_channel_identity(raw_name)
        std_category = clean_category(raw_group, std_name)
        
        if std_name and url:
            channels.append(Channel(name=std_name, category=std_category, url=url, logo=logo_url.strip()))
            seen_urls.add(url)
    return channels

async def check_url(sem, session, ch):
    async with sem:
        try:
            async with session.get(ch.url, timeout=TIMEOUT, allow_redirects=True) as response:
                # Teknik Not: Sadece HTTP 200 yetmez, bazı paneller hata sayfası (text/html) döndürür.
                if response.status == 200:
                    content_type = response.headers.get('Content-Type', '').lower()
                    if 'text/html' in content_type:
                        return None
                    logging.info(f"OK: {ch.name}")
                    return ch
        except:
            pass
        return None

async def main():
    async with aiohttp.ClientSession(headers={'User-Agent': USER_AGENT}) as session:
        all_channels = []
        global_seen_urls = set()
        logo_map = {} 
        
        for url in M3U_SOURCES:
            logging.info(f"İndiriliyor: {url}")
            try:
                async with session.get(url, timeout=15) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        found = parse_m3u(text)
                        for ch in found:
                            if ch.url not in global_seen_urls:
                                # Logo Mapping: İlk bulunan logoyu hafızaya al
                                if ch.name not in logo_map and ch.logo:
                                    logo_map[ch.name] = ch.logo
                                all_channels.append(ch)
                                global_seen_urls.add(ch.url)
            except Exception as e:
                logging.error(f"Hata: {e}")

        if not all_channels: return

        sem = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        tasks = [check_url(sem, session, ch) for ch in all_channels]
        results = await asyncio.gather(*tasks)
        alive_channels = [c for c in results if c]

        if alive_channels:
            # --- GELİŞMİŞ SIRALAMA MANTIĞI ---
            # 1. Kategori önceliği (PRIORITY_GROUPS içindeki sırası)
            # 2. Kategori içi kanal önceliği (OZEL_FILTRELER listesindeki sırası)
            # 3. Aynı öncelikteyse alfabetik isim
            alive_channels.sort(key=lambda x: (
                get_group_priority(x.category), 
                get_channel_internal_priority(x.name, x.category), 
                x.name
            ))
            
            with open("birlesik_tv.m3u", "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                for ch in alive_channels:
                    # Kaydedilen isimlere göre logoyu map'ten çek
                    final_logo = logo_map.get(ch.name, ch.logo)
                    f.write(f'#EXTINF:-1 group-title="{ch.category}" tvg-logo="{final_logo}",{ch.name}\n')
                    f.write(f"{ch.url}\n")
            
            logging.info(f"BİTTİ! {len(alive_channels)} kanal başarıyla işlendi ve 'birlesik_tv.m3u' dosyasına kaydedildi.")

if __name__ == "__main__":
    asyncio.run(main())
