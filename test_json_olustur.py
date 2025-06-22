import os
import json

kayit_json_dir = "kayit_json"
ana_kayit_json = os.path.join(kayit_json_dir, "birlesik_links.json")

if not os.path.exists(kayit_json_dir):
    os.makedirs(kayit_json_dir)

veri = {"test_key": {"tarih": "2025-06-22", "tarih_saat": "2025-06-22 14:00:00"}}

with open(ana_kayit_json, "w", encoding="utf-8") as f:
    json.dump(veri, f, ensure_ascii=False, indent=2)

print("Kayit dosyası oluşturuldu:", ana_kayit_json)
