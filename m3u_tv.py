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
    "Ulusal Kanallar": ["TRT 1", "ATV", "KANAL D", "SHOW TV", "NOW TV", "STAR TV", "TV8", "TEVE 2"],
    "SPOR KANALLARI": ["BEIN", "SPOR", "TARAFTAR", "EXXEN", "S SPORT", "EUROSPORT"],
    "HABER": ["HABER GLOBAL", "HALK TV", "TGRT HABER", "SÖZCÜ TV", "NTV"],
   
}

# --- 2. KATEGORİ MAPPING ---
CATEGORY_MAPPING = {
    "haber": "HABER",
    "ulusal": "Ulusal Kanallar",
    "sport": "SPOR KANALLARI",
    "spor": "SPOR KANALLARI",
    "movie": "SİNEMA & DİZİ",
    "film": "SİNEMA & DİZİ",
    "belgesel": "BELGESEL",
    "cocuk": "ÇOCUK & AİLE",
    "kids": "ÇOCUK & AİLE"
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
            if kelime.upper() in upper_name:
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
    name = re.sub(r'[\[\(].*?[\]\)]', '', name)
    patterns = [r'\bHD\b', r'\bSD\b', r'\bFHD\b', r'\b4K\b', r'\bYedek\b', r'\bBackup\b', r'\bHEVC\b']
    for p in patterns:
        name = re.sub(p, '', name, flags=re.IGNORECASE)
    return ' '.join(name.split()).strip().upper()

def get_channel_internal_priority(channel_name: str, category: str) -> int:
    """Kanalın kendi kategorisi içindeki sıra numarasını döndürür."""
    if category in OZEL_FILTRELER:
        search_list = OZEL_FILTRELER[category]
        upper_name = channel_name.upper()
        for i, keyword in enumerate(search_list):
            if keyword.upper() in upper_name:
                return i  # Liste sırasını (0, 1, 2...) döndürür (En öncelikli)
    return 999  # Listede yoksa en sona atar

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
                if response.status == 200:
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
            # 1. Kategori önceliği (PRIORITY_GROUPS)
            # 2. Kategori içi kanal önceliği (Liste sırasına göre)
            # 3. Aynı öncelikteyse alfabetik isim
            alive_channels.sort(key=lambda x: (
                get_group_priority(x.category), 
                get_channel_internal_priority(x.name, x.category), 
                x.name
            ))
            
            with open("birlesik_tv.m3u", "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                for ch in alive_channels:
                    final_logo = logo_map.get(ch.name, ch.logo)
                    f.write(f'#EXTINF:-1 group-title="{ch.category}" tvg-logo="{final_logo}",{ch.name}\n')
                    f.write(f"{ch.url}\n")
            
            logging.info(f"BİTTİ! {len(alive_channels)} kanal hem kategori hem kanal bazlı sıralandı.")

if __name__ == "__main__":
    asyncio.run(main())
