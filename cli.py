#!/usr/bin/env python3
"""
=================================================================
  SUPERFOOD TECH — Unified Menu & Modifier Extractor Pipeline
  Interactive CLI for Shopee, Grab & GoFood
=================================================================
"""

import os
import sys
import time
import re
import glob
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory of menu_core to sys.path so imports work
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _BASE_DIR)
load_dotenv(os.path.join(_BASE_DIR, ".env"), override=True)

from menu_core.sheets import get_outlets_for_applicator
from menu_core.shopee import extract_shopee_menu
from menu_core.grab import extract_grab_menu, extract_grab_menu_manual
from menu_core.gofood import extract_gofood_menu
from menu_core.c5_generator import generate_c5_from_dir

RESET   = "\033[0m"
BOLD    = "\033[1m"
GREEN   = "\033[92m"
CYAN    = "\033[96m"
YELLOW  = "\033[93m"
RED     = "\033[91m"
MAGENTA = "\033[95m"
DIM     = "\033[2m"

def get_output_dir(applicator, clean_outlet):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if applicator == "gofood":
        return os.path.join(base_dir, "platforms", "gofood", "outlets", clean_outlet)
    elif applicator == "grab":
        return os.path.join(base_dir, "platforms", "grab", "outlets", clean_outlet)
    else:
        return os.path.join(base_dir, "platforms", "shopee", "outlets", clean_outlet)

def _try_upload_to_drive(output_dir: str, outlet_name: str, applicator: str = ""):
    """
    Upload semua file .xlsx dari output_dir ke Google Drive via AppScript.
    Struktur folder di Drive:
      <folder_induk> / <GR|S|GO> / <nama_outlet> / file.xlsx
    Hanya berjalan jika GDRIVE_APPSCRIPT_URL diisi di .env.
    """
    script_url = os.environ.get("GDRIVE_APPSCRIPT_URL", "").strip()
    if not script_url:
        return  # GDrive tidak dikonfigurasi, skip diam-diam

    folder_id = os.environ.get("GDRIVE_FOLDER_ID", "").strip() or None

    # Level 1: subfolder platform (GR / S / GO)
    platform_map = {"grab": "GR", "shopee": "S", "gofood": "GO"}
    platform_folder = platform_map.get(applicator.lower(), None)

    # Import uploader dari root
    try:
        from upload_to_gdrive import upload_file_to_gdrive
    except ImportError as e:
        print(f"  {YELLOW}[Drive] Gagal import uploader: {e}{RESET}")
        return

    # Kumpulkan hanya file output Excel (.xlsx)
    files = sorted(
        glob.glob(os.path.join(output_dir, "*.xlsx"))
    )
    if not files:
        return

    # Level 2: subfolder nama outlet
    outlet_folder = re.sub(r'[^\w\s-]', '', outlet_name).strip()
    path_label = f"{platform_folder}/{outlet_folder}" if platform_folder else outlet_folder
    print(f"  {CYAN}\U0001f4e4 Mengupload {len(files)} file ke Drive: {path_label}/{RESET}")
    ok = 0
    for fp in files:
        if upload_file_to_gdrive(
            fp, script_url, folder_id,
            sub_folder_name=platform_folder,
            outlet_folder_name=outlet_folder
        ):
            ok += 1
    if ok == len(files):
        print(f"  {GREEN}\u2713 Semua file ({ok}/{len(files)}) berhasil diunggah ke Drive.{RESET}")
    else:
        print(f"  {YELLOW}\u26a0 Hanya {ok}/{len(files)} file berhasil diunggah ke Drive.{RESET}")


def parse_multi_select(input_str, max_val):
    """
    Parses comma-separated values and ranges (e.g., "1,3,5-7")
    Returns a set of 0-based indices.
    """
    indices = set()
    parts = [p.strip() for p in input_str.split(',')]
    for part in parts:
        if not part:
            continue
        if '-' in part:
            try:
                start_str, end_str = part.split('-', 1)
                start = int(start_str.strip())
                end = int(end_str.strip())
                if start <= end:
                    for i in range(start, end + 1):
                        if 1 <= i <= max_val:
                            indices.add(i - 1)
            except ValueError:
                continue
        else:
            try:
                i = int(part)
                if 1 <= i <= max_val:
                    indices.add(i - 1)
            except ValueError:
                continue
    return sorted(list(indices))



def banner():
    print(f"\033[90m=================================================================\033[0m")
    print(f"  {BOLD}{CYAN}      SUPERFOOD TECH — MENU & MODIFIER EXTRACTOR PIPELINE{RESET}")
    print(f"\033[90m=================================================================\033[0m")
    print()

def clean_local_data():
    print(f"\n{BOLD}{YELLOW}=== BERSIHKAN DATA LOKAL ==={RESET}")
    print("Pilih data yang ingin dibersihkan:")
    print(f"  {GREEN}[1]{RESET} Semua file laporan Excel (.xlsx) di folder platforms/")
    print(f"  {GREEN}[2]{RESET} Cache API & Sesi (.json di downloads/, sessions/, api_cache/)")
    print(f"  {GREEN}[3]{RESET} Cache spreadsheet (master_merchants_cache.csv)")
    print(f"  {GREEN}[4]{RESET} Bersihkan SEMUA data di atas")
    print(f"  {YELLOW}[5]{RESET} Batal")
    print()
    
    choice = input(f"  {BOLD}Pilihan (misal: 1,3 atau '4' untuk semua / '5' untuk batal):{RESET} ").strip()
    if choice == "5":
        print("  Dibatalkan.")
        time.sleep(1)
        return
        
    if choice == "4":
        parsed_indices = [0, 1, 2]
    else:
        parsed_indices = parse_multi_select(choice, 3)
        
    if not parsed_indices:
        print(f"  {RED}Pilihan tidak valid.{RESET}")
        time.sleep(1.5)
        return
        
    import shutil
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cleaned_something = False
    
    if 0 in parsed_indices:
        print("[*] Membersihkan file Excel hasil penarikan (.xlsx)...")
        xlsx_count = 0
        for root, dirs, files in os.walk(os.path.join(base_dir, "platforms")):
            for file in files:
                if file.endswith(".xlsx"):
                    try:
                        os.remove(os.path.join(root, file))
                        xlsx_count += 1
                    except Exception as e:
                        pass
        # Also clean GR/grab/laporan/ if exists
        laporan_dir = os.path.join(base_dir, "GR", "grab", "laporan")
        if os.path.exists(laporan_dir):
            try:
                shutil.rmtree(laporan_dir)
                xlsx_count += 1
            except Exception:
                pass
        print(f"  ✓ Berhasil menghapus {xlsx_count} file .xlsx.")
        cleaned_something = True
        
    if 1 in parsed_indices:
        print("[*] Membersihkan cache API dan sesi (.json)...")
        json_count = 0
        
        # 1. downloads/
        downloads_dir = os.path.join(base_dir, "downloads")
        if os.path.exists(downloads_dir):
            for file in os.listdir(downloads_dir):
                if file.endswith(".json"):
                    try:
                        os.remove(os.path.join(downloads_dir, file))
                        json_count += 1
                    except Exception:
                        pass
                        
        # 2. sessions/
        sessions_dir = os.path.join(base_dir, "sessions")
        if os.path.exists(sessions_dir):
            for file in os.listdir(sessions_dir):
                if file.endswith(".json"):
                    try:
                        os.remove(os.path.join(sessions_dir, file))
                        json_count += 1
                    except Exception:
                        pass
                        
        # 3. platforms/gofood/api_cache/
        gofood_cache = os.path.join(base_dir, "platforms", "gofood", "api_cache")
        if os.path.exists(gofood_cache):
            for file in os.listdir(gofood_cache):
                if file.endswith(".json"):
                    try:
                        os.remove(os.path.join(gofood_cache, file))
                        json_count += 1
                    except Exception:
                        pass
                        
        print(f"  ✓ Berhasil menghapus {json_count} file cache .json.")
        cleaned_something = True
        
    if 2 in parsed_indices:
        print("[*] Membersihkan cache spreadsheet...")
        cache_file = os.path.join(base_dir, "data", "master_merchants_cache.csv")
        if os.path.exists(cache_file):
            try:
                os.remove(cache_file)
                print("  ✓ Berhasil menghapus cache spreadsheet.")
                cleaned_something = True
            except Exception as e:
                print(f"  Gagal menghapus cache spreadsheet: {e}")
        else:
            print("  Cache spreadsheet sudah bersih.")
            cleaned_something = True
            
    if cleaned_something:
        print(f"\n  {GREEN}✔ Pembersihan data lokal selesai!{RESET}")
    else:
        print(f"\n  {RED}Pilihan tidak valid.{RESET}")
    time.sleep(2)


def interactive_menu():
    state = "main_menu"
    all_outlets_data = {}
    unique_outlets = []
    parent_name = ""
    selected_applicators = []
    results = []
    selected_branches_data_temp = {}
    
    while True:
        if state == "main_menu":
            os.system('cls' if os.name == 'nt' else 'clear')
            banner()
            print(f"  {BOLD}Pilih Menu Utama:{RESET}")
            print(f"    {GREEN}[1]{RESET} Get Menu Data")
            print(f"    {YELLOW}[p]{RESET} Bersihkan Data Lokal")
            print(f"    {RED}[q]{RESET} Keluar")
            print()
            
            choice = input(f"  {BOLD}Pilihan (1/p/q):{RESET} ").strip().lower()
            if choice == "q":
                print("  Keluar.")
                sys.exit(0)
            elif choice == "p":
                clean_local_data()
                continue
            elif choice == "1":
                state = "load_all_outlets"
            else:
                print(f"  {RED}Pilihan tidak valid.{RESET}")
                time.sleep(1)
                

                
        elif state == "load_all_outlets":
            # Load from all 3 applicators silently to build the full list
            print("  [*] Memuat daftar outlet...")
            all_outlets_data = {}
            for app in ["shopee", "grab", "gofood"]:
                try:
                    outlets = get_outlets_for_applicator(app)
                    if outlets:
                        all_outlets_data[app] = outlets
                except Exception as e:
                    print(f"  {RED}[ERROR] Gagal memuat daftar outlet untuk {app.upper()}: {e}{RESET}")
            
            if not all_outlets_data:
                print(f"  {RED}[ERROR] Tidak ada outlet yang berhasil dimuat.{RESET}")
                time.sleep(2)
                state = "main_menu"
            else:
                unified_names = set()
                for app, outlets in all_outlets_data.items():
                    for o in outlets:
                        if o.get('nama_outlet'):
                            unified_names.add(o['nama_outlet'])
                unique_outlets = sorted(list(unified_names))
                state = "select_outlet"
                
        elif state == "select_outlet":
            os.system('cls' if os.name == 'nt' else 'clear')
            banner()
            print(f"  {BOLD}Pilih Nama Outlet:{RESET}")
            print(f"    {GREEN}[all]{RESET} Jalankan semua outlet dan cabang")
            print(f"    {GREEN}[new]{RESET} Jalankan HANYA outlet/cabang yang belum ditarik")
            for idx, name in enumerate(unique_outlets):
                print(f"    {GREEN}[{idx + 1:3d}]{RESET} {name}")
                
            print(f"    {YELLOW}[b  ]{RESET} Kembali ke Menu Utama")
            print()
            
            choice = input(f"  {BOLD}Pilih nomor outlet (misal: 1,3,5-7 atau 'all'/'new'/'b'):{RESET} ").strip()
            if choice.lower() == 'b':
                state = "main_menu"
            elif choice.lower() == 'all':
                # Grab everything
                selected_branches_data_temp = all_outlets_data
                state = "select_applicator_all"
            elif choice.lower() == 'new':
                # Filter locally right now
                filtered_data = {}
                for app, outlets in all_outlets_data.items():
                    filtered_outlets = []
                    for o in outlets:
                        raw_outlet = o.get('nama_outlet') or o.get('nama_resto_final') or o.get('merchant_name') or 'unknown'
                        clean_outlet = "".join(c for c in raw_outlet if c.isalnum() or c in (' ', '_', '-')).strip()
                        clean_outlet = re.sub(r'\s+', ' ', clean_outlet).lower()
                        output_dir = get_output_dir(app, clean_outlet)
                        is_processed = False
                        if os.path.exists(output_dir):
                            files = os.listdir(output_dir)
                            if any(f.endswith('.xlsx') for f in files):
                                is_processed = True
                        if not is_processed:
                            filtered_outlets.append(o)
                    if filtered_outlets:
                        filtered_data[app] = filtered_outlets
                
                if not filtered_data:
                    print(f"\n  {GREEN}Semua outlet sudah berhasil ditarik sebelumnya!{RESET}")
                    time.sleep(3)
                else:
                    selected_branches_data_temp = filtered_data
                    state = "select_applicator_all"
            else:
                parsed_indices = parse_multi_select(choice, len(unique_outlets))
                if parsed_indices:
                    if len(parsed_indices) == 1:
                        parent_name = unique_outlets[parsed_indices[0]]
                        selected_branches_data_temp = {app: [o for o in outlets if o.get('nama_outlet') == parent_name] for app, outlets in all_outlets_data.items()}
                        state = "select_applicator_single"
                    else:
                        # Multi-select
                        selected_branches_data_temp = {}
                        for app, outlets in all_outlets_data.items():
                            app_outlets = []
                            for idx in parsed_indices:
                                target_parent = unique_outlets[idx]
                                app_outlets.extend([o for o in outlets if o.get('nama_outlet') == target_parent])
                            if app_outlets:
                                selected_branches_data_temp[app] = app_outlets
                        state = "select_applicator_all"
                else:
                    print(f"  {RED}Pilihan tidak valid atau di luar jangkauan.{RESET}")
                    time.sleep(1)

        elif state.startswith("select_applicator_"):
            # Select applicator
            os.system('cls' if os.name == 'nt' else 'clear')
            banner()
            if state == "select_applicator_single":
                print(f"  {BOLD}Pilih Aplikator/Platform untuk '{parent_name}':{RESET}")
            else:
                print(f"  {BOLD}Pilih Aplikator/Platform:{RESET}")
                
            print(f"    {MAGENTA}[1]{RESET} ShopeeFood")
            print(f"    {GREEN}[2]{RESET} GrabFood")
            print(f"    {CYAN}[3]{RESET} GoFood")
            print(f"    {GREEN}[all]{RESET} Semua")
            print(f"    {YELLOW}[b]{RESET} Kembali")
            print()
            
            choice = input(f"  {BOLD}Pilihan (1/2/3/all/b):{RESET} ").strip().lower()
            if choice == "b":
                state = "select_outlet"
                continue
            elif choice == "4" or choice == "all":
                parsed_indices = [0, 1, 2]
            else:
                parsed_indices = parse_multi_select(choice, 3)
                
            if not parsed_indices:
                print(f"  {RED}Pilihan tidak valid.{RESET}")
                time.sleep(1)
                continue
                
            selected_applicators = []
            if 0 in parsed_indices: selected_applicators.append("shopee")
            if 1 in parsed_indices: selected_applicators.append("grab")
            if 2 in parsed_indices: selected_applicators.append("gofood")
            
            # Filter the branches temp to ONLY keep selected applicators
            filtered_branches_data = {}
            for app in selected_applicators:
                if app in selected_branches_data_temp and selected_branches_data_temp[app]:
                    filtered_branches_data[app] = selected_branches_data_temp[app]
            
            if not filtered_branches_data:
                print(f"  {RED}[ERROR] Outlet yang dipilih tidak memiliki data di aplikator yang Anda pilih.{RESET}")
                time.sleep(2)
                continue

            # Route based on previous mode
            if state == "select_applicator_single":
                # Single parent name selected. Are there multiple branches?
                max_branches = max(len(branches) for branches in filtered_branches_data.values())
                if max_branches == 1:
                    results = []
                    for app, branches in filtered_branches_data.items():
                        results.append((app, branches[0]))
                    state = "confirm"
                else:
                    # Collect branch names
                    unified_b_names = set()
                    for app, branches in filtered_branches_data.items():
                        for b in branches:
                            b_name = b.get('brand') or b.get('nama_resto_final') or b.get('merchant_name') or 'Cabang'
                            unified_b_names.add(b_name)
                    unique_branches = sorted(list(unified_b_names))
                    selected_branches_data_temp = filtered_branches_data  # Store for branch step
                    state = "select_branch"
            else:
                # "all" mode, skip branch selection
                results = []
                for app, outlets in filtered_branches_data.items():
                    results.append((app, outlets))
                state = "confirm_all"
                    
        elif state == "select_branch":
            os.system('cls' if os.name == 'nt' else 'clear')
            banner()
            app_str = " + ".join(a.upper() for a in selected_branches_data_temp.keys())
            print(f"  {BOLD}Pilih Cabang untuk '{parent_name}' pada {app_str}:{RESET}")
            print(f"    {GREEN}[all]{RESET} Jalankan semua cabang untuk outlet ini")
            print(f"    {GREEN}[new]{RESET} Jalankan HANYA cabang yang belum ditarik")
            
            for idx, b_name in enumerate(unique_branches):
                print(f"    {GREEN}[{idx + 1:3d}]{RESET} {b_name}")
                
            print(f"    {YELLOW}[b  ]{RESET} Kembali ke pemilihan aplikator")
            print()
            
            choice = input(f"  {BOLD}Pilih nomor cabang (misal: 1,3 atau 'all'/'new'/'b'):{RESET} ").strip()
            if choice.lower() == 'b':
                state = "select_applicator_single"
            elif choice.lower() == 'all':
                results = []
                for app, branches in selected_branches_data_temp.items():
                    results.append((app, branches))
                state = "confirm_all"
            elif choice.lower() == 'new':
                results = []
                for app, branches in selected_branches_data_temp.items():
                    filtered_branches = []
                    for b in branches:
                        raw_outlet = b.get('nama_outlet') or b.get('nama_resto_final') or b.get('merchant_name') or 'unknown'
                        clean_outlet = "".join(c for c in raw_outlet if c.isalnum() or c in (' ', '_', '-')).strip()
                        clean_outlet = re.sub(r'\s+', ' ', clean_outlet).lower()
                        output_dir = get_output_dir(app, clean_outlet)
                        is_processed = False
                        if os.path.exists(output_dir):
                            if any(f.endswith('.xlsx') for f in os.listdir(output_dir)):
                                is_processed = True
                        if not is_processed:
                            filtered_branches.append(b)
                    if filtered_branches:
                        results.append((app, filtered_branches))
                
                if not results:
                    print(f"\n  {GREEN}Semua cabang untuk outlet ini sudah berhasil ditarik sebelumnya!{RESET}")
                    time.sleep(3)
                else:
                    state = "confirm_all"
            else:
                parsed_indices = parse_multi_select(choice, len(unique_branches))
                if parsed_indices:
                    selected_b_names = [unique_branches[idx] for idx in parsed_indices]
                    if len(parsed_indices) == 1:
                        target_b_name = selected_b_names[0]
                        results = []
                        for app, branches in selected_branches_data_temp.items():
                            for b in branches:
                                b_name = b.get('brand') or b.get('nama_resto_final') or b.get('merchant_name') or 'Cabang'
                                if b_name == target_b_name:
                                    results.append((app, b))
                                    break
                        state = "confirm"
                    else:
                        results = []
                        for app, branches in selected_branches_data_temp.items():
                            app_branches = []
                            for b in branches:
                                b_name = b.get('brand') or b.get('nama_resto_final') or b.get('merchant_name') or 'Cabang'
                                if b_name in selected_b_names:
                                    app_branches.append(b)
                            if app_branches:
                                results.append((app, app_branches))
                        state = "confirm_all"
                else:
                    print(f"  {RED}Pilihan tidak valid atau di luar jangkauan.{RESET}")
                    time.sleep(1)
                    
        elif state == "confirm":
            os.system('cls' if os.name == 'nt' else 'clear')
            banner()
            app_str = " + ".join(app.upper() for app, _ in results)
            print(f"  {CYAN}{'─'*60}{RESET}")
            print(f"  Aplikator : {BOLD}{app_str}{RESET}")
            print(f"  Outlet    : {BOLD}{parent_name}{RESET}")
            print(f"  {CYAN}{'─'*60}{RESET}")
            print()
            print(f"  {BOLD}Konfirmasi tindakan:{RESET}")
            print(f"    {GREEN}[1]{RESET} Lanjutkan Tarik Menu")
            print(f"    {YELLOW}[2]{RESET} Kembali ke daftar outlet")
            print(f"    {RED}[3]{RESET} Batal dan Keluar")
            print()
            
            choice = input(f"  {BOLD}Pilihan (1/2/3):{RESET} ").strip()
            if choice == "1":
                break
            elif choice == "2":
                results = []
                state = "select_outlet"
            elif choice == "3":
                print("  Dibatalkan.")
                sys.exit(0)
            else:
                print(f"  {RED}Pilihan tidak valid.{RESET}")
                time.sleep(1)
                
        elif state == "confirm_all":
            os.system('cls' if os.name == 'nt' else 'clear')
            banner()
            
            app_str = " + ".join(app.upper() for app, _ in results)
            
            # Count unprocessed outlets
            total_selected = sum(len(outlets) for _, outlets in results)
            unprocessed_count = 0
            for app, outlets in results:
                for o in outlets:
                    raw_outlet = o.get('nama_outlet') or o.get('nama_resto_final') or o.get('merchant_name') or 'unknown'
                    clean_outlet = "".join(c for c in raw_outlet if c.isalnum() or c in (' ', '_', '-')).strip()
                    clean_outlet = re.sub(r'\s+', ' ', clean_outlet).lower()
                    
                    output_dir = get_output_dir(app, clean_outlet)
                    is_processed = False
                    if os.path.exists(output_dir):
                        if any(f.endswith('.xlsx') for f in os.listdir(output_dir)):
                            is_processed = True
                    if not is_processed:
                        unprocessed_count += 1
            
            print(f"  {CYAN}{'─'*60}{RESET}")
            print(f"  Aplikator : {BOLD}{app_str}{RESET}")
            print(f"  Mode      : {BOLD}{YELLOW}BATCH RUN (Massal){RESET}")
            print(f"  Total     : {BOLD}{total_selected} tarikan (gabungan semua aplikator){RESET}")
            print(f"  Belum Run : {BOLD}{GREEN}{unprocessed_count} tarikan{RESET}")
            print(f"  Sudah Run : {BOLD}{total_selected - unprocessed_count} tarikan (Skipped jika pilih [2]){RESET}")
            print(f"  Jeda      : {BOLD}Setiap 10 outlet akan dijeda 1 menit{RESET}")
            print(f"  {CYAN}{'─'*60}{RESET}")
            print()
            print(f"  {BOLD}Konfirmasi tindakan:{RESET}")
            print(f"    {GREEN}[1]{RESET} Lanjutkan Jalankan SEMUA (Overwrite)")
            print(f"    {GREEN}[2]{RESET} Lanjutkan Jalankan HANYA yang Belum Selesai ({unprocessed_count} tarikan)")
            print(f"    {YELLOW}[3]{RESET} Kembali ke daftar outlet")
            print(f"    {RED}[4]{RESET} Batal dan Keluar")
            print()
            
            choice = input(f"  {BOLD}Pilihan (1/2/3/4):{RESET} ").strip()
            if choice == "1":
                break
            elif choice == "2":
                filtered_results = []
                for app, outlets in results:
                    filtered_outlets = []
                    for o in outlets:
                        raw_outlet = o.get('nama_outlet') or o.get('nama_resto_final') or o.get('merchant_name') or 'unknown'
                        clean_outlet = "".join(c for c in raw_outlet if c.isalnum() or c in (' ', '_', '-')).strip()
                        clean_outlet = re.sub(r'\s+', ' ', clean_outlet).lower()
                        
                        output_dir = get_output_dir(app, clean_outlet)
                        is_processed = False
                        if os.path.exists(output_dir):
                            if any(f.endswith('.xlsx') for f in os.listdir(output_dir)):
                                is_processed = True
                        if not is_processed:
                            filtered_outlets.append(o)
                    if filtered_outlets:
                        filtered_results.append((app, filtered_outlets))
                
                if not filtered_results:
                    print(f"\n  {GREEN}Semua outlet dalam batch ini sudah berhasil ditarik sebelumnya!{RESET}")
                    time.sleep(3)
                    results = []
                    state = "select_outlet"
                else:
                    results = filtered_results
                    break
            elif choice == "3":
                results = []
                state = "select_outlet"
            elif choice == "4":
                print("  Dibatalkan.")
                sys.exit(0)
            else:
                print(f"  {RED}Pilihan tidak valid.{RESET}")
                time.sleep(1)
                
    return results



def main():
    import argparse
    parser = argparse.ArgumentParser(description="Menu Extractor CLI")
    parser.add_argument("--platform", type=str, help="Platform (gofood, grab, shopee, all)")
    parser.add_argument("--outlet", type=str, help="Nama outlet (exact match atau all)")
    parser.add_argument("--cabang", type=str, help="Nama cabang (exact match atau all)")
    parser.add_argument("--list-json", action="store_true", help="Dump outlets as JSON")
    args = parser.parse_args()

    if args.list_json:
        import json
        outlets = {
            "gofood": get_outlets_for_applicator("gofood"),
            "grab": get_outlets_for_applicator("grab"),
            "shopee": get_outlets_for_applicator("shopee")
        }
        print(json.dumps(outlets))
        sys.exit(0)

    results = []
    if args.platform:
        applicators = ["shopee", "grab", "gofood"] if args.platform.lower() == "all" else [args.platform.lower()]
        for app in applicators:
            outlets = get_outlets_for_applicator(app)
            if args.outlet and args.outlet.lower() != "all":
                outlets = [o for o in outlets if (o.get('nama_outlet') or '').lower() == args.outlet.lower() or (o.get('nama_resto_final') or '').lower() == args.outlet.lower()]
            
            outlet_groups = {}
            for o in outlets:
                name = o.get('nama_resto_final') or o.get('nama_outlet') or 'unknown'
                if name not in outlet_groups:
                    outlet_groups[name] = []
                outlet_groups[name].append(o)
            
            for name, branches in outlet_groups.items():
                if args.cabang and args.cabang.lower() != "all" and args.cabang.lower() != "new":
                    filtered = [b for b in branches if (b.get('brand') or b.get('cabang') or '').lower() == args.cabang.lower()]
                    if filtered:
                        results.append((app, filtered))
                elif args.cabang and args.cabang.lower() == "new":
                    filtered = []
                    for b in branches:
                        raw_outlet = b.get('nama_outlet') or b.get('nama_resto_final') or b.get('merchant_name') or 'unknown'
                        clean_outlet = "".join(c for c in raw_outlet if c.isalnum() or c in (' ', '_', '-')).strip()
                        clean_outlet = re.sub(r'\s+', ' ', clean_outlet).lower()
                        output_dir = get_output_dir(app, clean_outlet)
                        is_processed = False
                        if os.path.exists(output_dir):
                            if any(f.endswith('.xlsx') for f in os.listdir(output_dir)):
                                is_processed = True
                        if not is_processed:
                            filtered.append(b)
                    if filtered:
                        results.append((app, filtered))
                else:
                    results.append((app, branches))
    else:
        try:
            results = interactive_menu()
        except KeyboardInterrupt:
            print("\n  Dibatalkan oleh pengguna.")
            sys.exit(0)
        
    import re
    
    for applicator, outlet in results:
        if isinstance(outlet, list):
            total_outlets = len(outlet)
            print(f"\n{CYAN}=== MEMULAI PENARIKAN MENU MASSAL ({total_outlets} OUTLET) - {applicator.upper()} ==={RESET}")
            print(f"[*] Waktu mulai: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            success_count = 0
            fail_count = 0
            
            for idx, o in enumerate(outlet):
                raw_outlet = o.get('nama_outlet') or o.get('nama_resto_final') or o.get('merchant_name') or 'unknown'
                clean_outlet = "".join(c for c in raw_outlet if c.isalnum() or c in (' ', '_', '-')).strip()
                clean_outlet = re.sub(r'\s+', ' ', clean_outlet).lower()
                
                output_dir = get_output_dir(applicator, clean_outlet)
                os.makedirs(output_dir, exist_ok=True)
                
                name_to_show = o['brand'] or o['nama_resto_final'] or o['nama_outlet']
                print(f"\n{BOLD}[{idx + 1}/{total_outlets}] Memproses: {name_to_show} (ID: {o['store_id']}) - {applicator.upper()}{RESET}")
                
                success = False
                result_data = None
                
                if applicator == "grab":
                    # Retry up to 5 times for Grab, then offer manual mode
                    max_retries = 5
                    for attempt in range(1, max_retries + 1):
                        try:
                            success, result_data = extract_grab_menu(o, output_dir)
                        except Exception as e:
                            success = False
                            result_data = f"Exception occurred: {e}"
                        
                        if success:
                            break
                        
                        if attempt < max_retries:
                            print(f"  {YELLOW}[Retry] Percobaan {attempt}/{max_retries} gagal. Mencoba lagi dalam 5 detik...{RESET}")
                            print(f"  {DIM}  Info: {result_data}{RESET}")
                            time.sleep(5)
                        else:
                            print(f"\n  {RED}{BOLD}✘ Penarikan otomatis gagal setelah {max_retries}x percobaan.{RESET}")
                            print(f"  {DIM}  Info: {result_data}{RESET}")
                            print(f"\n  {YELLOW}Apakah Anda ingin login manual via browser?{RESET}")
                            print(f"    {GREEN}[y]{RESET} Ya, buka browser untuk login manual")
                            print(f"    {RED}[n]{RESET} Tidak, skip outlet ini")
                            manual_choice = input(f"  {BOLD}Pilihan (y/n):{RESET} ").strip().lower()
                            if manual_choice == 'y':
                                try:
                                    success, result_data = extract_grab_menu_manual(o, output_dir)
                                except Exception as e:
                                    success = False
                                    result_data = f"Exception manual: {e}"
                else:
                    try:
                        if applicator == "shopee":
                            success, result_data = extract_shopee_menu(o, output_dir)
                        elif applicator == "gofood":
                            success, result_data = extract_gofood_menu(o, output_dir)
                    except Exception as e:
                        success = False
                        result_data = f"Exception occurred: {e}"
                    
                if success and isinstance(result_data, dict):
                    success_count += 1
                    print(f"  {GREEN}✔ Berhasil! {result_data.get('items_count', 0)} item, {result_data.get('mods_count', 0)} modifier.{RESET}")
                    
                    # Generate C5 Excel format
                    c5_path = generate_c5_from_dir(output_dir, raw_outlet, applicator)
                    
                    _try_upload_to_drive(output_dir, raw_outlet, applicator)
                else:
                    fail_count += 1
                    print(f"  {RED}✘ Gagal: {result_data}{RESET}")
                    
                # Delay logic: 1 minute pause after every 10 outlets
                if (idx + 1) < total_outlets and (idx + 1) % 10 == 0:
                    print(f"\n{YELLOW}[BATCH] Selesai memproses 10 outlet. Menunggu jeda 1 menit sebelum batch berikutnya...{RESET}")
                    for remaining in range(60, 0, -1):
                        sys.stdout.write(f"\rMenunggu... {remaining} detik")
                        sys.stdout.flush()
                        time.sleep(1)
                    print(f"\r{GREEN}[BATCH] Jeda selesai. Melanjutkan penarikan...{RESET}\n")
                    
            print(f"\n{CYAN}=== PENARIKAN MENU MASSAL SELESAI - {applicator.upper()} ==={RESET}")
            print(f"  - Sukses : {GREEN}{success_count}{RESET}")
            print(f"  - Gagal  : {RED}{fail_count}{RESET}")
            
        else:
            print(f"\n{CYAN}=== MEMULAI PENARIKAN MENU - {applicator.upper()} ==={RESET}")
            print(f"[*] Waktu mulai: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            raw_outlet = outlet.get('nama_outlet') or outlet.get('nama_resto_final') or outlet.get('merchant_name') or 'unknown'
            clean_outlet = "".join(c for c in raw_outlet if c.isalnum() or c in (' ', '_', '-')).strip()
            clean_outlet = re.sub(r'\s+', ' ', clean_outlet).lower()
            
            output_dir = get_output_dir(applicator, clean_outlet)
            os.makedirs(output_dir, exist_ok=True)
            
            success = False
            result_data = None
            
            if applicator == "grab":
                # Retry up to 5 times for Grab, then offer manual mode
                max_retries = 5
                for attempt in range(1, max_retries + 1):
                    try:
                        success, result_data = extract_grab_menu(outlet, output_dir)
                    except Exception as e:
                        success = False
                        result_data = f"Exception occurred: {e}"
                    
                    if success:
                        break
                    
                    if attempt < max_retries:
                        print(f"\n  {YELLOW}[Retry] Percobaan {attempt}/{max_retries} gagal. Mencoba lagi dalam 5 detik...{RESET}")
                        print(f"  {DIM}  Info: {result_data}{RESET}")
                        time.sleep(5)
                    else:
                        print(f"\n  {RED}{BOLD}✘ Penarikan otomatis gagal setelah {max_retries}x percobaan.{RESET}")
                        print(f"  {DIM}  Info: {result_data}{RESET}")
                        print(f"\n  {YELLOW}Apakah Anda ingin login manual via browser?{RESET}")
                        print(f"    {GREEN}[y]{RESET} Ya, buka browser untuk login manual")
                        print(f"    {RED}[n]{RESET} Tidak, skip outlet ini")
                        manual_choice = input(f"  {BOLD}Pilihan (y/n):{RESET} ").strip().lower()
                        if manual_choice == 'y':
                            try:
                                success, result_data = extract_grab_menu_manual(outlet, output_dir)
                            except Exception as e:
                                success = False
                                result_data = f"Exception manual: {e}"
            elif applicator == "shopee":
                success, result_data = extract_shopee_menu(outlet, output_dir)
            elif applicator == "gofood":
                success, result_data = extract_gofood_menu(outlet, output_dir)
                
            if success and isinstance(result_data, dict):
                print(f"\n{GREEN}{BOLD}✔ PENARIKAN MENU BERHASIL!{RESET}")
                print(f"  - Total Item     : {result_data['items_count']}")
                print(f"  - Total Modifier : {result_data['mods_count']}")
                print(f"  - Hasil disimpan di directory: {output_dir}")
                
                # Generate C5 Excel format (ini sekaligus menghapus file raw)
                c5_path = generate_c5_from_dir(output_dir, raw_outlet, applicator)
                if c5_path:
                    print(f"    1. Excel C5 : {c5_path}")
                
                _try_upload_to_drive(output_dir, raw_outlet, applicator)
            else:
                print(f"\n{RED}{BOLD}✘ PENARIKAN MENU GAGAL / STUB{RESET}")
                if isinstance(result_data, str):
                    print(f"  Info: {result_data}")
            
if __name__ == "__main__":
    main()
