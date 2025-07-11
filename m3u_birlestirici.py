import requests
import os
import re
import json
from datetime import datetime

m3u_sources = [
    ("https://raw.githubusercontent.com/Lunedor/iptvTR/refs/heads/main/FilmArsiv.m3u", "Lunedor"),
    ("https://tinyurl.com/2ao2rans", "powerboard"),
]

birlesik_dosya = "birlesik.m3u"
kayit_json_dir = "kayit_json"
ana_kayit_json = os.path.join(kayit_json_dir, "birlesik_links.json")

if not os.path.exists(kayit_json_dir):
    os.makedirs(kayit_json_dir)

def extract_channel_key(extinf_line, url_line):
    match = re.match(r'#EXTINF:.*?,(.*)', extinf_line)
    channel_name = match.group(1).strip() if match else ''
    url = url_line.strip()
    return (channel_name, url)

def parse_m3u_lines(lines):
    kanal_list = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            extinf_line = line
            if i + 1 < len(lines):
                url_line = lines[i + 1].strip()
                kanal_list.append((extract_channel_key(extinf_line, url_line), extinf_line, url_line))
            i += 2
        else:
            i += 1
    return kanal_list

def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json(data, filename):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def format_tr_date(date_str):
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{d.day}.{d.month}.{d.year}"

def format_tr_datehour(date_str):
    d = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    return f"{d.day}.{d.month}.{d.year} {d.hour:02d}:{d.minute:02d}"

def ensure_group_title(extinf_line, source_name):
    if 'group-title="' not in extinf_line:
        parts = extinf_line.split(" ", 1)
        if len(parts) == 2:
            prefix, rest = parts
            return f'{prefix} group-title="[{source_name}]" {rest}'
        else:
            return f'#EXTINF:-1 group-title="[{source_name}]",'
    return extinf_line

def get_original_group_title(extinf_line):
    m = re.search(r'group-title="([^"]*)"', extinf_line)
    if m:
        return m.group(1)
    return None

today = datetime.now().strftime("%Y-%m-%d")
now_full = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
today_obj = datetime.strptime(today, "%Y-%m-%d")

ana_link_dict = load_json(ana_kayit_json)

with open(birlesik_dosya, "w", encoding="utf-8") as outfile:
    outfile.write("#EXTM3U\n")
    for m3u_url, source_name in m3u_sources:
        try:
            req = requests.get(m3u_url, timeout=20)
            req.raise_for_status()
        except Exception as e:
            print(f"{m3u_url} alınamadı: {e}")
            continue
        lines = req.text.splitlines()
        kanal_list = parse_m3u_lines(lines)

        yeni_kanallar, eski_kanallar = [], []

        for (key, extinf, url) in kanal_list:
            dict_key = f"{key[0]}|{key[1]}"
            extinf = ensure_group_title(extinf, source_name)
            if dict_key in ana_link_dict:
                ilk_tarih = ana_link_dict[dict_key]["tarih"]
                ilk_tarih_saat = ana_link_dict[dict_key]["tarih_saat"]
                eski_kanallar.append((key, extinf, url, ilk_tarih, ilk_tarih_saat))
            else:
                ana_link_dict[dict_key] = {"tarih": today, "tarih_saat": now_full}
                yeni_kanallar.append((key, extinf, url, today, now_full))

        # Yeni kanallar
        for (key, extinf, url, eklenme_tarihi, eklenme_tarihi_saat) in yeni_kanallar:
            ilk_ad = key[0]
            saat_str = format_tr_datehour(eklenme_tarihi_saat)
            group_title = f'[YENİ] [{source_name}]'
            kanal_isim = f'{ilk_ad} [{saat_str}]'
            extinf_clean = re.sub(r'group-title="[^"]*"', f'group-title="{group_title}"', extinf)
            extinf_clean = re.sub(r',.*', f',{kanal_isim}', extinf_clean)
            outfile.write(extinf_clean + "\n")
            outfile.write(url + "\n")

        # Eski kanallar
        for (key, extinf, url, eklenme_tarihi, eklenme_tarihi_saat) in eski_kanallar:
            ilk_ad = key[0]
            tarih_obj = datetime.strptime(eklenme_tarihi, "%Y-%m-%d")
            tarih_str = format_tr_date(eklenme_tarihi)
            if (today_obj - tarih_obj).days >= 7:
                original_group = get_original_group_title(extinf)
                if original_group and f"[{source_name}]" not in original_group:
                    new_group_title = f'{original_group}[{source_name}]'
                else:
                    new_group_title = f'{source_name}'
                kanal_isim = f'{ilk_ad} [{tarih_str}]'
            else:
                saat_str = format_tr_datehour(eklenme_tarihi_saat)
                new_group_title = f'[YENİ] [{source_name}]'
                kanal_isim = f'{ilk_ad} [{saat_str}]'

            extinf_clean = re.sub(r'group-title="[^"]*"', f'group-title="{new_group_title}"', extinf)
            extinf_clean = re.sub(r',.*', f',{kanal_isim}', extinf_clean)
            outfile.write(extinf_clean + "\n")
            outfile.write(url + "\n")

save_json(ana_link_dict, ana_kayit_json)
print(f"Kayıt dosyası güncellendi: {ana_kayit_json}")
