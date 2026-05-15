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
# ÖNEMLİ: Burada tam eşleşme mantığı devreye girecek. 
# "KANAL 7" yazdığında "KANAL 7 AVRUPA"yı almaması için "==" kontrolü eklendi.
OZEL_FILTRELER = {
    "Ulusal Kanallar": ["TRT 1", "ATV", "KANAL D", "SHOW TV", "NOW TV", "STAR TV", "TV 8","TV 8.5","BEYAZ TV", "TEVE 2", "A2", "TELE 1", "SHOWTURK", "KANAL 7"],
    "SPOR": ["BEIN SPORTS 1","HT SPOR","TIVIBU SPOR","SPOR","TRT 3 SPOR","","TARAFTAR", "A SPOR", "S SPORT","FUTBOL TV","TRT SPOR"],
    "HABER": ["HALK TV", "TV 100", "SÖZCÜ TV", "CNN TÜRK","NTV","NEO HABER","HABER GLOBAL", "TRT HABER"],
    "BELGESEL": ["NATGEO CHANNEL","NAT GEO WILD","TLC", "NEO HABER","PERSIANA TURKIYE","DMAX","CGTN BELGESEL", "BELGESEL TV"],
    "MÜZİK": ["KRAL POP TV","POWERTÜRK TV","POWER TV", "NUMBER ONE TURK","NUMBER 1 DAMAR","MED MUZIK"],
}

# --- 2. KATEGORİ MAPPING ---
CATEGORY_MAPPING = {
    "haber": "HABER",
    "ulusal": "ULUSAL KANALAR",
    "sport": "SPOR KANALLARI",
    "spor": "SPOR",
    "movie": "SİNEMA & DİZİ",
    "film": "SİNEMA & DİZİ",
    "belgesel": "BELGESEL",
    "MÜZIK-DIĞER": "MÜZİK",
    "cocuk": "ÇOCUK & AİLE",
    "kids": "ÇOCUK & AİLE"
}

# --- 3. KANAL İSİM MAPPING ---
# Gelen karmaşık isimleri senin istediğin tertemiz isimlere çevirir.
# Örnek: "tv8 hd" gelirse "TV 8" yapar.
CHANNEL_NAME_MAPPING = {
    "BEIN SPORTS 1 TURKEY":"BEIN SPORTS 1",
    "TV8": "TV 8","TV8 HD": "TV 8","TV 8 HD": "TV 8",
    "NOW": "NOW TV","NOW HD": "NOW TV",
    "TRT1": "TRT 1","TRT 1 HD": "TRT 1",
    "KANALD": "KANAL D",
    "STAR": "STAR TV","360": "360 TV",
    "CNN TURK": "CNN TÜRK",
    "KANAL7": "KANAL 7","KANAL 7 HD": "KANAL 7"
}

# --- 4. KAYNAKLAR (URL ve Yazar Bilgisi) ---
# Format: (URL, YAZAR_ISMI)
M3U_SOURCES = [
    ('https://raw.githubusercontent.com/smartgmr/cdn/refs/heads/main/Perfect.m3u', "smartgmr"),
    ('https://raw.githubusercontent.com/Mertcantv/Mertcan/refs/heads/main/%C4%B0zle2.m3u', "Mertcantv"),
    ('https://raw.githubusercontent.com/primatzeka/kurbaga/main/NeonSpor/NeonSpor.m3u', "NeonSpor"),
    ('https://tinyurl.com/TVCANLI', "TVCANLI")
]

PRIORITY_GROUPS = list(OZEL_FILTRELER.keys())

@dataclass
class Channel:
    name: str
    category: str
    url: str
    author: str  # Kanalın hangi kaynaktan geldiğini tutar
    logo: str = ""

def normalize_channel_identity(name: str):
    """İsimleri temizler ve Mapping listesine göre sabitler."""
    name = re.sub(r'[\[\(].*?[\]\)]', '', name)
    patterns = [r'\bHD\b', r'\bSD\b', r'\bFHD\b', r'\b4K\b', r'\bYedek\b', r'\bBackup\b', r'\bHEVC\b']
    for p in patterns:
        name = re.sub(p, '', name, flags=re.IGNORECASE)
    
    clean_name = ' '.join(name.split()).strip().upper()

    # Mapping kontrolü (Örn: "TV8" -> "TV 8")
    for ham, duzgun in CHANNEL_NAME_MAPPING.items():
        if clean_name == ham.upper():
            return duzgun.upper()
    
    return clean_name

def clean_category(raw_cat: str, channel_name: str) -> str:
    upper_name = channel_name.upper()
    
    # BİREBİR EŞLEŞME KONTROLÜ (Kanal 7 Avrupa'yı engellemek için)
    for hedef_kategori, kanallar in OZEL_FILTRELER.items():
        for kanal in kanallar:
            if upper_name == kanal.upper(): # 'in' yerine '==' kullanıldı
                return hedef_kategori

    if not raw_cat: return "Genel"
    raw_cat_lower = raw_cat.lower()
    for anahtar, hedef_isim in CATEGORY_MAPPING.items():
        if anahtar in raw_cat_lower:
            return hedef_isim

    clean = re.sub(r'[|\[\(].*?[|\]\)]', '', raw_cat) 
    clean = clean.replace(':', '').strip()
    return clean.title() if clean else "Genel"

def get_channel_internal_priority(channel_name: str, category: str) -> int:
    """Kanalın kendi kategorisi içindeki sıra numarasını döndürür (Birebir eşleşme)."""
    if category in OZEL_FILTRELER:
        search_list = OZEL_FILTRELER[category]
        upper_name = channel_name.upper()
        for i, target_name in enumerate(search_list):
            if upper_name == target_name.upper(): # Tam eşleşme
                return i 
    return 999 

def get_group_priority(category_name: str) -> int:
    try:
        return PRIORITY_GROUPS.index(category_name)
    except ValueError:
        return 999

def parse_m3u(m3u_content: str, author_name: str) -> List[Channel]:
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
            channels.append(Channel(
                name=std_name, 
                category=std_category, 
                url=url, 
                author=author_name, 
                logo=logo_url.strip()
            ))
            seen_urls.add(url)
    return channels

async def check_url(sem, session, ch):
    async with sem:
        try:
            async with session.get(ch.url, timeout=TIMEOUT, allow_redirects=True) as response:
                if response.status == 200:
                    # Bazı paneller hata sayfasını 200 ile döner, onları engelle:
                    ctype = response.headers.get('Content-Type', '').lower()
                    if 'text/html' in ctype: return None
                    logging.info(f"OK: {ch.name} (Kaynak: {ch.author})")
                    return ch
        except:
            pass
        return None

async def main():
    async with aiohttp.ClientSession(headers={'User-Agent': USER_AGENT}) as session:
        all_channels = []
        global_seen_urls = set()
        logo_map = {} 
        
        for url, author in M3U_SOURCES:
            logging.info(f"İndiriliyor: {url} | Kaynak: {author}")
            try:
                async with session.get(url, timeout=15) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        found = parse_m3u(text, author)
                        for ch in found:
                            if ch.url not in global_seen_urls:
                                if ch.name not in logo_map and ch.logo:
                                    logo_map[ch.name] = ch.logo
                                all_channels.append(ch)
                                global_seen_urls.add(ch.url)
            except Exception as e:
                logging.error(f"Hata ({author}): {e}")

        if not all_channels: return

        sem = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        tasks = [check_url(sem, session, ch) for ch in all_channels]
        results = await asyncio.gather(*tasks)
        alive_channels = [c for c in results if c]

        if alive_channels:
            # --- SIRALAMA ---
            alive_channels.sort(key=lambda x: (
                get_group_priority(x.category), 
                get_channel_internal_priority(x.name, x.category), 
                x.name
            ))
            
            with open("birlesik_tv.m3u", "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                for ch in alive_channels:
                    final_logo = logo_map.get(ch.name, ch.logo)
                    # group-author etiketi her kanalın satırına eklendi
                    f.write(f'#EXTINF:-1 group-title="{ch.category}" group-author="{ch.author}" tvg-logo="{final_logo}",{ch.name}\n')
                    f.write(f"{ch.url}\n")
            
            logging.info(f"BİTTİ! Kaynak bazlı (group-author) ayrıştırma tamamlandı.")

if __name__ == "__main__":
    asyncio.run(main())
