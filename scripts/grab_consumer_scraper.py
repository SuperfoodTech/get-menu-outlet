import re
import csv
import json
import time
import requests
import pandas as pd
from urllib.parse import urlparse, parse_qs

# Configuration
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQ3tLKBNXDqRgBw0mNhKZFxgvKx-JoiTDzm_s5Ix1cm7O6HCv4IvExOLR2HSRVaXSsx82V348mcr9X4/pub?output=csv&gid=0"
CURL_COMMAND = """
# GANTI DENGAN CURL DARI BROWSER
curl 'https://portal.grab.com/foodweb/guest/v2/merchants/6-CY2XVNBVTECBRE?latlng=-6.1767352,106.826504' \
  -H 'accept: application/json, text/plain, */*' \
  -H 'accept-language: id' \
  -b '_gcl_au=1.1.538004072.1781923643; _ga=GA1.1.1775046073.1781923649;' \
  -H 'origin: https://food.grab.com' \
  -H 'priority: u=1, i' \
  -H 'referer: https://food.grab.com/' \
  -H 'sec-ch-ua: "Not/A)Brand";v="99", "Chromium";v="148"' \
  -H 'sec-ch-ua-mobile: ?0' \
  -H 'sec-ch-ua-platform: "Linux"' \
  -H 'sec-fetch-dest: empty' \
  -H 'sec-fetch-mode: cors' \
  -H 'sec-fetch-site: same-site' \
  -H 'user-agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36'
"""

def parse_curl(curl_str):
    lines = curl_str.strip().split('\n')
    headers = {}
    url = None
    for line in lines:
        line = line.strip().rstrip('\\').strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('curl '):
            parts = line.split("'", 2)
            if len(parts) > 1:
                url = parts[1]
        elif line.startswith('-H '):
            parts = line[3:].strip("'").split(': ', 1)
            if len(parts) == 2:
                headers[parts[0].lower()] = parts[1]
        elif line.startswith('-b '):
            headers['cookie'] = line[3:].strip("'")
    return url, headers

def make_slug(name):
    name = str(name).lower()
    name = re.sub(r'[^a-z0-9\s-]', '', name)
    name = re.sub(r'[\s-]+', '-', name).strip('-')
    return name

def main():
    print("Membaca data dari Google Sheet...")
    df = pd.read_csv(SHEET_URL)
    
    # Filter GrabFood
    df_grab = df[df['Aplikasi'].str.contains('Grab', na=False, case=False)]
    print(f"Ditemukan {len(df_grab)} outlet GrabFood.")
    
    _, headers = parse_curl(CURL_COMMAND)
    if not headers:
        print("CURL tidak valid, harap masukkan curl yang benar di script.")
        return

    all_items = []
    
    for _, row in df_grab.iterrows():
        store_id = str(row['Store ID']).strip()
        resto_name = str(row['Nama Resto Final']).strip()
        
        if not store_id or store_id == 'nan':
            continue
            
        slug = make_slug(resto_name)
        link_outlet = f"https://food.grab.com/id/id/restaurant/{slug}/{store_id}"
        print(f"Memproses: {resto_name} ({store_id})")
        
        api_url = f"https://portal.grab.com/foodweb/guest/v2/merchants/{store_id}?latlng=-6.1767352,106.826504"
        
        try:
            resp = requests.get(api_url, headers=headers)
            if resp.status_code != 200:
                print(f"Gagal fetching {store_id}: {resp.status_code}")
                continue
                
            data = resp.json()
            merchant = data.get('merchant', {})
            categories = merchant.get('menu', {}).get('categories', [])
            
            for cat in categories:
                cat_name = cat.get('name', '')
                for item in cat.get('items', []):
                    item_name = item.get('name', '')
                    price_in_min = item.get('priceInMin', 0)
                    discounted_price_in_min = item.get('discountedPriceInMin', price_in_min)
                    
                    price = price_in_min / 100.0 if price_in_min else 0
                    discounted_price = discounted_price_in_min / 100.0 if discounted_price_in_min else price
                    
                    promo_val = price - discounted_price
                    
                    all_items.append({
                        "Link outlet": link_outlet,
                        "Nama panjang": resto_name,
                        "Store ID": store_id,
                        "Nama kategori": cat_name,
                        "Nama item": item_name,
                        "Harga item sebelum promo (harga coret)": price,
                        "Harga item setelah promo (harga coret)": discounted_price,
                        "Nominal atau persentase promo (harga coret)": promo_val,
                    })
        except Exception as e:
            print(f"Error memproses {store_id}: {e}")
            
        time.sleep(1)
        
    if all_items:
        out_df = pd.DataFrame(all_items)
        out_df.to_excel('grab_promo_data.xlsx', index=False)
        print(f"Selesai! Data disimpan ke grab_promo_data.xlsx ({len(all_items)} items)")

if __name__ == '__main__':
    main()
