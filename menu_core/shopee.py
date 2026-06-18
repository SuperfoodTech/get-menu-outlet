import json
import os
import sys
import requests
import pandas as pd
from pathlib import Path
from openpyxl import Workbook

from selenium.webdriver.chrome.options import Options

# Add shopee-omzet-automation to sys.path
AUTOMATION_DIR = Path("/mnt/DATA/Proyek/task-weekly/VB")
if str(AUTOMATION_DIR) not in sys.path:
    sys.path.insert(0, str(AUTOMATION_DIR))

from core import browser

# FORCE the profile directory to be weekly/data/chrome_profile without modifying browser.py
orig_add_argument = Options.add_argument
def custom_add_argument(self, argument):
    if "--user-data-dir=" in argument:
        argument = f"--user-data-dir=/mnt/DATA/Proyek/task-weekly/VB/data/chrome_profile"
        print(f"🔧 [PATCH] Mengalihkan user data dir ke: {argument}")
    orig_add_argument(self, argument)
Options.add_argument = custom_add_argument


SELLER_BASE = "https://foody.shopee.co.id"
IMG_BASE    = "https://down-id.img.susercontent.com/file"

class ShopeeClient:
    def __init__(self, tob_token: str, entity_id: str, extra_cookies: dict = None):
        self.tob_token     = tob_token
        self.extra_cookies = extra_cookies or {}
        self.entity_id     = entity_id or self.extra_cookies.get("shopee_foody_mid", "")
        self.session       = requests.Session()
        self.user_agent    = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"

    def _seller_headers(self, override_entity_id: str = None) -> dict:
        eid = override_entity_id or self.entity_id
        cookies = self.extra_cookies.copy()
        cookies["shopee_tob_token"]     = self.tob_token
        cookies["shopee_tob_entity_id"] = eid
        cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())

        return {
            "Host":           "foody.shopee.co.id",
            "Accept":         "application/json, text/plain, */*",
            "Content-Type":   "application/json",
            "User-Agent":     self.user_agent,
            "Cookie":         cookie_str,
            "X-Sf-Platform":  "2",
            "Operate-Source": "partnerapp",
            "Origin":         "https://partner.shopee.co.id",
            "Referer":        "https://partner.shopee.co.id/",
        }

    def get_store_dishes(self, store_id: str) -> list[dict]:
        url = f"{SELLER_BASE}/api/seller/store/dishes"
        try:
            resp = self.session.get(
                url,
                headers=self._seller_headers(override_entity_id=store_id),
                timeout=15,
            )
            data = resp.json()
            if data.get("code") == 0:
                return data.get("data", {}).get("catalogs", [])
            print(f"[Shopee API] get_store_dishes failed: code={data.get('code')}, msg={data.get('msg')}")
        except Exception as e:
            print(f"[Shopee API] get_store_dishes error: {e}")
        return []

    def get_store_option_groups(self, store_id: str, dish_ids: list = None) -> list[dict]:
        url = f"{SELLER_BASE}/api/seller/store/option-groups/search"
        payload = {"page_no": 1, "page_size": 100}
        if dish_ids:
            payload["filter"] = {"dish_ids": dish_ids}
        try:
            resp = self.session.post(
                url,
                json=payload,
                headers=self._seller_headers(override_entity_id=store_id),
                timeout=15,
            )
            data = resp.json()
            if data.get("code") == 0:
                return data.get("data", {}).get("option_groups", [])
            print(f"[Shopee API] get_store_option_groups failed: code={data.get('code')}, msg={data.get('msg')}")
        except Exception as e:
            print(f"[Shopee API] get_store_option_groups error: {e}")
        return []

def extract_shopee_menu(store_metadata: dict, output_dir: str):
    store_id = store_metadata['store_id']
    # Gunakan Merchant Name dari GSheet sebagai target_name untuk browser.py
    # Jika kosong atau nan, fallback ke nama_resto_final
    m_name = store_metadata.get('merchant_name', '')
    if not m_name or m_name.lower() == 'nan' or m_name == '-':
        target_name = store_metadata.get('nama_resto_final') or store_metadata.get('nama_outlet')
    else:
        target_name = m_name
        
    nama_pendek = store_metadata.get('nama_pendek') or target_name
    
    # 1. Start browser and switch to target merchant
    session_file = Path("/mnt/DATA/Proyek/task-weekly/VB/data/session.json")
    browser.set_session_file(session_file)
    
    # Load credentials if they exist
    username = "allvbadmin"
    password = "Shopee@321"
    creds_file = Path("/mnt/DATA/Proyek/task-weekly/VB/credentials.json")
    if creds_file.exists():
        try:
            creds = json.loads(creds_file.read_text())
            username = creds.get("shopee_username", username)
            password = creds.get("shopee_password", password)
        except:
            pass
            
    print(f"[*] Membuka browser (headless=True) dan memilih merchant: '{target_name}'...")
    session_data = browser.get_session(
        username=username,
        password=password,
        headless=True,
        close_browser=False,
        target_name=target_name,
        interactive=False
    )
    
    if not session_data or "driver" not in session_data:
        return False, "Gagal menginisialisasi browser atau memilih merchant."
        
    driver = session_data["driver"]
    
    try:
        print("[*] Memperbarui token autentikasi untuk merchant terpilih...")
        session = browser.refresh_tokens(driver, fallback_entity_id=store_id)
        if not session or "shopee_tob_token" not in session:
            return False, "Gagal memperbarui token autentikasi."
            
        tob_token = session["shopee_tob_token"]
        extra_cookies = session.get("extra_cookies", {})
        
        # Close browser immediately after getting tokens
        try:
            driver.quit()
        except:
            pass
            
        # 2. Initialize ShopeeClient
        client = ShopeeClient(
            tob_token=tob_token,
            entity_id=store_id,
            extra_cookies=extra_cookies
        )
        
        print(f"[*] Menarik data menu ShopeeFood untuk: {target_name} ({store_id})...")
        
        # Fetch catalogs and dishes
        catalogs = client.get_store_dishes(store_id)
        if not catalogs:
            return False, "Tidak ada data catalog/dishes yang ditemukan. Periksa session."
            
        print(f"[*] Ditemukan {len(catalogs)} kategori menu.")
        
        # 3. Pull all dishes
        all_dishes = []
        dish_ids_with_modifiers = []
        
        for cat in catalogs:
            cat_name = cat.get('name', 'Menu Lainnya')
            dishes = cat.get('dishes', [])
            for dish in dishes:
                dish_id = str(dish.get('id'))
                dish_name = dish.get('name', '')
                price_raw = dish.get('price', '0')
                list_price_raw = dish.get('list_price', '0')
                description = dish.get('description', '')
                available = dish.get('available', True)
                opt_group_count = dish.get('option_group_count', 0)
                sales_volume = dish.get('sales_volume', 0)
                picture = dish.get('picture', '')
                discount_pct = dish.get('discount_percentage', 0)
                
                # Format prices
                price = float(price_raw) / 100000.0
                list_price = float(list_price_raw) / 100000.0 if (list_price_raw and float(list_price_raw) > 0) else price
                
                # Promo formatting
                promo_val = ""
                if discount_pct > 0:
                    promo_val = f"{int(discount_pct / 100)}%"
                elif list_price > price:
                    promo_val = f"{int(round((list_price - price) / list_price * 100))}%"
                    
                available_str = "Tersedia" if available else "Habis"
                picture_url = f"{IMG_BASE}/{picture}" if picture else ""
                link_outlet = f"https://shopee.co.id/now-food/shop/{store_id}"
                
                dish_info = {
                    'link_outlet': link_outlet,
                    'nama_panjang': target_name,
                    'nama_pendek': nama_pendek,
                    'store_id': store_id,
                    'nama_kategori': cat_name,
                    'nama_item': dish_name,
                    'jumlah_terjual': sales_volume,
                    'opt_group_count': opt_group_count,
                    'deskripsi_item': description,
                    'harga_sebelum_promo': list_price,
                    'harga_setelah_promo': price,
                    'promo': promo_val,
                    'ketersediaan': available_str,
                    'link_foto': picture_url,
                    'dish_id': dish_id,
                    'jumlah_modifier_group': 0,
                    'jumlah_modifier': 0
                }
                all_dishes.append(dish_info)
                
                if opt_group_count > 0:
                    dish_ids_with_modifiers.append(dish_id)

        print(f"[*] Total {len(all_dishes)} item ditemukan.")
        print(f"[*] Menarik modifier untuk {len(dish_ids_with_modifiers)} item yang memiliki topping/opsi...")
        
        # 4. Pull all modifiers for dishes that have them
        modifier_rows = []
        
        for d_idx, dish_id in enumerate(dish_ids_with_modifiers):
            dish_obj = next((d for d in all_dishes if d['dish_id'] == dish_id), None)
            if not dish_obj:
                continue
                
            opt_groups = client.get_store_option_groups(store_id, dish_ids=[dish_id])
            
            dish_obj['jumlah_modifier_group'] = len(opt_groups)
            total_modifiers_count = 0
            
            for group in opt_groups:
                opt_group_info = group.get('option_group', {})
                group_name = opt_group_info.get('name', '').strip()
                select_min = opt_group_info.get('select_min', 0)
                select_max = opt_group_info.get('select_max', 0)
                options = group.get('options', [])
                
                total_modifiers_count += len(options)
                tipe_modifier = "Pilihan Tunggal" if select_max == 1 else "Pilihan Ganda"
                
                for opt in options:
                    opt_name = opt.get('name', '')
                    opt_price = float(opt.get('price', '0')) / 100000.0
                    opt_available = opt.get('available', True)
                    opt_available_str = "Tersedia" if opt_available else "Habis"
                    
                    modifier_rows.append({
                        'link_outlet': dish_obj['link_outlet'],
                        'nama_panjang': target_name,
                        'nama_pendek': nama_pendek,
                        'store_id': store_id,
                        'nama_item': dish_obj['nama_item'],
                        'nama_modifier_group': group_name,
                        'nama_modifier': opt_name,
                        'tipe_modifier': tipe_modifier,
                        'minimal': select_min,
                        'maksimal': select_max,
                        'harga_modifier': opt_price,
                        'ketersediaan_modifier': opt_available_str
                    })
            
            dish_obj['jumlah_modifier'] = total_modifiers_count
            
        # 5. Build output dataframes
        item_cols = [
            'Link outlet', 'Nama panjang', 'Nama pendek (ShopeeFood)', 'Store ID',
            'Nama kategori', 'Nama item', 'Jumlah terjual', 'Jumlah modifier group',
            'Jumlah modifier', 'Deskripsi item', 'Harga item sebelum promo (harga coret)',
            'Harga item setelah promo (harga coret)', 'Nominal atau persentase promo (harga coret)',
            'Ketersediaan item', 'Link foto'
        ]
        
        item_data = []
        for d in all_dishes:
            item_data.append([
                d['link_outlet'], d['nama_panjang'], d['nama_pendek'], d['store_id'],
                d['nama_kategori'], d['nama_item'], d['jumlah_terjual'], d['jumlah_modifier_group'],
                d['jumlah_modifier'], d['deskripsi_item'], d['harga_sebelum_promo'],
                d['harga_setelah_promo'], d['promo'], d['ketersediaan'], d['link_foto']
            ])
            
        df_items = pd.DataFrame(item_data, columns=item_cols)
        
        mod_cols = [
            'Link outlet', 'Nama panjang', 'Nama pendek (ShopeeFood)', 'Store ID',
            'Nama item', 'Nama modifier group', 'Nama modifier', 'Tipe modifier',
            'Minimal', 'Maksimal', 'Harga modifier', 'Ketersediaan modifier'
        ]
        
        mod_data = []
        for m in modifier_rows:
            mod_data.append([
                m['link_outlet'], m['nama_panjang'], m['nama_pendek'], m['store_id'],
                m['nama_item'], m['nama_modifier_group'], m['nama_modifier'], m['tipe_modifier'],
                m['minimal'], m['maksimal'], m['harga_modifier'], m['ketersediaan_modifier']
            ])
            
        df_mods = pd.DataFrame(mod_data, columns=mod_cols)
        
        # Write to files
        os.makedirs(output_dir, exist_ok=True)
        
        import re
        def clean_name(s):
            cleaned = "".join(c for c in s if c.isalnum() or c in (' ', '_', '-')).rstrip()
            return cleaned.replace(' ', '_')
            
        safe_merchant = clean_name(target_name)
        branch_raw = store_metadata.get('brand') or store_metadata.get('nama_resto_final') or store_metadata.get('nama_outlet') or ""
        safe_branch = clean_name(branch_raw)
        
        if safe_branch.lower() == safe_merchant.lower() or not safe_branch:
            combined_name = safe_merchant
        else:
            combined_name = f"{safe_merchant}_{safe_branch}"
            
        combined_name = re.sub(r'_+', '_', combined_name)
        
        items_csv_path = os.path.join(output_dir, f"shopee_items_{combined_name}_{store_id}.csv")
        mods_csv_path = os.path.join(output_dir, f"shopee_modifiers_{combined_name}_{store_id}.csv")
        excel_path = os.path.join(output_dir, f"shopee_menu_{combined_name}_{store_id}.xlsx")
        
        df_items.to_csv(items_csv_path, index=False)
        df_mods.to_csv(mods_csv_path, index=False)
        
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            df_items.to_excel(writer, sheet_name='Items', index=False)
            df_mods.to_excel(writer, sheet_name='Modifiers', index=False)
            
        return True, {
            'items_csv': items_csv_path,
            'mods_csv': mods_csv_path,
            'excel': excel_path,
            'items_count': len(df_items),
            'mods_count': len(df_mods)
        }
    except Exception as e:
        try:
            driver.quit()
        except:
            pass
        return False, f"Error selama ekstraksi menu: {e}"
