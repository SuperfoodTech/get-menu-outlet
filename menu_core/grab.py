"""
menu_core/grab.py
=================
GrabFood Menu Extractor — menggunakan logik dari GR/grab/grab_api_scraper.py
Mengambil menu & modifier per-outlet via Playwright (login) + Grab API dari dalam
konteks browser.
"""

import asyncio
import json
import logging
import os
import re
import sys
from pathlib import Path

import pandas as pd

# ─── Path setup ──────────────────────────────────────────────────────────────
# Tambahkan GR/grab ke sys.path agar bisa import grab_api_scraper
_THIS_DIR = Path(__file__).parent.parent          # /mnt/DATA/Proyek/Menu Outlet
_GR_GRAB  = _THIS_DIR / "GR" / "grab"

if str(_GR_GRAB) not in sys.path:
    sys.path.insert(0, str(_GR_GRAB))

try:
    from grab_api_scraper import (
        run_api_download_for_portal,
        parse_menu,
        validate_credentials,
    )
    _SCRAPER_OK = True
except ImportError as _e:
    _SCRAPER_OK = False
    _SCRAPER_ERR = str(_e)

# ─── Logger ───────────────────────────────────────────────────────────────────
logger = logging.getLogger("GrabExtractor")
if not logger.handlers:
    _h = logging.StreamHandler(sys.stdout)
    _h.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)


# ─── Column definitions ───────────────────────────────────────────────────────
ITEM_COLS = [
    "Link outlet", "Nama panjang", "Store ID",
    "Nama kategori", "Nama item", "Jumlah terjual",
    "Jumlah modifier group", "Jumlah modifier", "Deskripsi item",
    "Harga item sebelum promo (harga coret)",
    "Harga item setelah promo (harga coret)",
    "Nominal atau persentase promo (harga coret)",
    "Ketersediaan item", "Link foto",
]
MOD_COLS = [
    "Link outlet", "Nama panjang", "Store ID",
    "Nama item", "Nama modifier group", "Nama modifier", "Tipe modifier",
    "Minimal", "Maksimal", "Harga modifier", "Ketersediaan modifier",
]


def _clean(name: str) -> str:
    return "".join(c for c in str(name).lower() if c.isalnum())


def _matches(row: dict, store_id: str, outlet_name: str) -> bool:
    """Cocokkan baris JSON hasil scraper dengan outlet target."""
    row_sid = str(row.get("Store ID", "")).strip()
    if row_sid and store_id and row_sid.lower() == store_id.lower():
        return True
    row_clean  = _clean(row.get("Nama panjang", ""))
    tgt_clean  = _clean(outlet_name)
    return bool(row_clean and tgt_clean and
                (row_clean in tgt_clean or tgt_clean in row_clean))


def _add_short_name_col(rows: list[dict], short_name: str) -> list[dict]:
    """Sisipkan kolom 'Nama pendek (GrabFood)' setelah 'Nama panjang'."""
    out = []
    for r in rows:
        r2 = dict(r)
        r2.setdefault("Nama pendek (GrabFood)", short_name or r2.get("Nama panjang", ""))
        out.append(r2)
    return out


def _build_dataframes(
    items_raw: list[dict],
    mods_raw:  list[dict],
    store_id:  str,
    outlet_name: str,
    short_name:  str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Filter, tambah kolom pendek, kembalikan (df_items, df_mods)."""
    matched_items = [r for r in items_raw if _matches(r, store_id, outlet_name)]
    matched_mods  = [r for r in mods_raw  if _matches(r, store_id, outlet_name)]

    # Fallback jika tidak ada kecocokan — ambil semua
    if not matched_items:
        matched_items = items_raw
        matched_mods  = mods_raw

    matched_items = _add_short_name_col(matched_items, short_name)
    matched_mods  = _add_short_name_col(matched_mods,  short_name)

    def to_df(rows, cols):
        if not rows:
            return pd.DataFrame(columns=cols)
        df = pd.DataFrame(rows)
        for c in cols:
            if c not in df.columns:
                df[c] = ""
        return df[cols]

    return to_df(matched_items, ITEM_COLS), to_df(matched_mods, MOD_COLS)


def _save_outputs(
    df_items: pd.DataFrame,
    df_mods:  pd.DataFrame,
    output_dir: str,
    outlet_name: str,
    store_id: str,
) -> dict:
    """Simpan CSV + Excel ke output_dir, kembalikan dict info."""
    os.makedirs(output_dir, exist_ok=True)

    def safe_fn(s):
        return re.sub(r"_+", "_", "".join(
            c if c.isalnum() or c in (" ", "_", "-") else "_"
            for c in str(s)
        ).strip().replace(" ", "_"))

    base = safe_fn(outlet_name)
    if store_id:
        base = f"{base}_{store_id}"

    excel_f   = os.path.join(output_dir, f"grab_menu_{base}.xlsx")

    with pd.ExcelWriter(excel_f, engine="openpyxl") as w:
        df_items.to_excel(w, sheet_name="Items",     index=False)
        df_mods.to_excel(w,  sheet_name="Modifiers", index=False)

    return {
        "excel":       excel_f,
        "items_count": len(df_items),
        "mods_count":  len(df_mods),
    }


async def _async_extract(store_metadata: dict, output_dir: str):
    """Async entry point: login Grab → fetch menu API → parse → simpan."""
    store_id    = store_metadata.get("store_id", "")
    outlet_name = (store_metadata.get("nama_resto_final") or
                   store_metadata.get("nama_outlet") or
                   store_metadata.get("merchant_name") or "Unknown")
    short_name  = store_metadata.get("nama_pendek") or outlet_name

    # Ambil credentials dari store_metadata (diisi oleh sheets.py grab columns)
    username = store_metadata.get("grab_username") or store_metadata.get("user") or ""
    password = store_metadata.get("grab_password") or store_metadata.get("pwd")  or ""

    if not username or not password:
        return False, (
            "Kredensial Grab (grab_username / grab_password) tidak ditemukan "
            "di metadata outlet. Pastikan kolom 'Nama Pengguna' dan 'Kata Sandi' "
            "untuk Grab sudah diisi di Google Sheet."
        )

    is_valid, err = validate_credentials(username, password)
    if not is_valid:
        return False, f"Kredensial tidak valid: {err}"

    # Config headless dari config.json project root (turun dari GR)
    headless = True
    config_path = _THIS_DIR / "config.json"
    if config_path.exists():
        try:
            import json as _json
            headless = _json.loads(config_path.read_text()).get("headless_grab", True)
        except Exception:
            pass

    print(f"[*] Menjalankan GrabFood scraper untuk: {outlet_name} ({store_id})")
    print(f"    Username  : {username}")
    print(f"    Headless  : {headless}")

    # Gunakan Playwright mode (run_api_download_for_portal)
    downloaded_file, err = await run_api_download_for_portal(username, password)
    if not downloaded_file:
        return False, f"Scraper GrabFood gagal: {err}"

    with open(downloaded_file, "r", encoding="utf-8") as f:
        scraped = json.load(f)

    items_raw = scraped.get("items", [])
    mods_raw  = scraped.get("modifiers", [])

    df_items, df_mods = _build_dataframes(
        items_raw, mods_raw, store_id, outlet_name, short_name
    )

    result = _save_outputs(df_items, df_mods, output_dir, outlet_name, store_id)

    print(f"   ✅ Berhasil! {result['items_count']} item, {result['mods_count']} modifier.")
    return True, result


def extract_grab_menu(store_metadata: dict, output_dir: str):
    """
    Synchronous entry point — dipanggil dari cli.py.
    Menjalankan async scraper di dalam event loop baru.
    """
    if not _SCRAPER_OK:
        return False, (
            f"Gagal mengimpor GrabFood scraper dari GR/grab: {_SCRAPER_ERR}. "
            f"Pastikan direktori GR/grab ada dan dependensinya sudah diinstal."
        )

    store_id    = store_metadata.get("store_id", "")
    outlet_name = (store_metadata.get("nama_resto_final") or
                   store_metadata.get("nama_outlet") or "")

    print(f"\n[GrabFood Menu Extractor]")
    print(f"[-] Target Outlet : {outlet_name} ({store_id})")

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                _async_extract(store_metadata, output_dir)
            )
        finally:
            loop.close()
    except KeyboardInterrupt:
        return False, "Dibatalkan oleh pengguna."
    except Exception as e:
        return False, f"Error tidak terduga: {e}"
