# 🍜 Superfood Tech — Menu & Modifier Extractor Pipeline

Pipeline otomatisasi untuk mengekstrak data **menu** dan **modifier** dari platform food delivery (**GoFood**, **Shopee Food**, **GrabFood**) menggunakan Playwright & Selenium.

---

## 📁 Struktur Direktori

```
Menu Outlet/
├── cli.py                          # ← Entry point utama (jalankan ini)
├── login_gofood.py                 # Browser login & interceptor API GoFood
├── run.sh                          # Script praktis untuk menjalankan pipeline
├── pyproject.toml                  # Dependency management (uv)
├── uv.lock
├── .env                            # Environment variables (token, dll.)
│
├── menu_core/                      # Core logic per-platform
│   ├── __init__.py
│   ├── sheets.py                   # Loader data outlet dari Google Sheets
│   ├── gofood.py                   # Ekstractor GoFood (Playwright)
│   ├── shopee.py                   # Ekstractor Shopee (Selenium)
│   └── grab.py                     # Ekstractor GrabFood (Playwright via GR/)
│
├── platforms/                      # Output hasil ekstraksi per platform
│   ├── gofood/
│   │   ├── outlets/                # Hasil CSV & Excel per outlet
│   │   ├── sessions/               # Session JSON login GoFood
│   │   ├── api_cache/              # Cache raw JSON dari Grab/GoFood API
│   │   └── data_to_get/            # Data referensi / hasil lama
│   ├── shopee/
│   │   ├── outlets/
│   │   ├── api_cache/
│   │   └── data_to_get/
│   └── grab/
│       └── outlets/
│
├── data/
│   └── master_merchants_cache.csv  # Cache lokal daftar merchant dari GSheets
│
├── scripts/                        # Helper & debug scripts
│   ├── debug_profile.py
│   ├── open_dashboard.py
│   ├── refresh_session.py
│   └── tests/
│       ├── test_menu.py
│       ├── test_login_lontar.py
│       └── test_list_merchants.py
│
└── GR/                             # Sub-project GrabFood (scraper engine)
    └── grab/
        └── grab_api_scraper.py     # ← Dipakai oleh menu_core/grab.py
```

---

## ⚙️ Setup Awal

### 1. Install dependencies dengan `uv`

```bash
# Buat virtual environment & install semua dependencies
uv sync

# Install Playwright browser (Chromium)
uv run python -m playwright install chromium
```

### 2. Konfigurasi `.env`

File `.env` di root project sudah berisi konfigurasi session GoFood. Pastikan token aktif sebelum menjalankan.

### 3. (Opsional) Konfigurasi `config.json`

Buat `config.json` di root project untuk mengatur mode browser:

```json
{
  "headless_grab": false,
  "headless_vb": false,
  "max_concurrency": 3
}
```

| Key | Default | Keterangan |
|-----|---------|------------|
| `headless_grab` | `true` | `false` = tampilkan browser GrabFood |
| `headless_vb` | `false` | Mode browser untuk Shopee |
| `max_concurrency` | `3` | Jumlah akun yang diproses paralel |

---

## 🚀 Cara Menjalankan

### Menggunakan `run.sh` (Direkomendasikan)

```bash
# Jadikan executable (cukup sekali)
chmod +x run.sh

./run.sh              # Mode interaktif — pilih platform & outlet secara manual
./run.sh gofood       # Langsung ekstraksi GoFood (semua outlet)
./run.sh shopee       # Langsung ekstraksi Shopee (semua outlet)
./run.sh grab         # Langsung ekstraksi GrabFood (semua outlet)
./run.sh update       # Paksa refresh daftar outlet dari Google Sheets
./run.sh help         # Tampilkan panduan
```

### Menggunakan Python langsung

```bash
# Aktifkan virtual environment
source .venv/bin/activate

# Jalankan CLI interaktif
python cli.py
```

---

## 🗂️ Sumber Data

Daftar outlet diambil dari **Google Sheets** secara otomatis dan di-cache lokal selama 1 jam di `data/master_merchants_cache.csv`.

- Filter otomatis berdasarkan kolom `Aplikasi` (GoFood / Shopee / Grab)
- Hanya outlet dengan `Status = Live` yang diproses
- Credentials (username/password) dibaca dari kolom sheet masing-masing platform

---

## 📊 Format Output

Setiap outlet menghasilkan 3 file di `platforms/{platform}/outlets/{nama_outlet}/`:

| File | Isi |
|------|-----|
| `{platform}_items_{nama}_{id}.csv` | Data item menu (satu baris = satu item) |
| `{platform}_modifiers_{nama}_{id}.csv` | Data modifier/varian per item |
| `{platform}_menu_{nama}_{id}.xlsx` | Excel dengan 2 sheet: **Items** + **Modifiers** |

### Kolom Item

| Kolom | Keterangan |
|-------|------------|
| Link outlet | URL halaman outlet di platform |
| Nama panjang | Nama resmi outlet |
| Store ID | ID unik outlet di platform |
| Nama kategori | Kategori menu |
| Nama item | Nama produk |
| Harga item sebelum promo | Harga normal (harga coret) |
| Harga item setelah promo | Harga jual aktif |
| Ketersediaan item | `Available` / `Sold Out` |
| Link foto | URL foto produk |

### Kolom Modifier

| Kolom | Keterangan |
|-------|------------|
| Nama item | Item induk modifier |
| Nama modifier group | Nama kelompok pilihan (misal: "Tingkat Kepedasan") |
| Nama modifier | Nama pilihan (misal: "Pedas Sedang") |
| Tipe modifier | `SINGLE` / `MULTIPLE` |
| Minimal / Maksimal | Jumlah pilihan min/max |
| Harga modifier | Harga tambahan modifier |

---

## 🔧 Platform Teknis

| Platform | Metode | Library |
|----------|--------|---------|
| **GoFood** | Playwright — intercept XHR API saat login dashboard | `playwright` |
| **Shopee Food** | Selenium — login portal, fetch API dari konteks browser | `selenium`, `undetected-chromedriver` |
| **GrabFood** | Playwright — login merchant.grab.com, fetch API `/food/merchant/v2/menu` | `playwright` (via `GR/grab/`) |

---

## 📡 API Referensi (Endpoints)

Untuk detail endpoints API yang digunakan serta cara *mapping* data (pemetaan dari response JSON API ke kolom Excel), silakan merujuk ke file **[API_DOCUMENTATION.md](API_DOCUMENTATION.md)**.

---

## 🔄 Alur Kerja

```
run.sh / cli.py
    │
    ├─ menu_core/sheets.py      → Ambil daftar outlet dari Google Sheets
    │
    ├─ [GoFood]
    │   ├─ menu_core/gofood.py  → Panggil login_gofood.py
    │   └─ login_gofood.py      → Buka browser, login, intercept API menu
    │
    ├─ [Shopee]
    │   └─ menu_core/shopee.py  → Login Shopee portal via Selenium
    │                              Fetch menu API dari dalam browser
    │
    └─ [Grab]
        └─ menu_core/grab.py    → Delegasi ke GR/grab/grab_api_scraper.py
                                   Login merchant.grab.com via Playwright
                                   Fetch /food/merchant/v2/menu API
```

---

## 📌 Catatan Penting

> **GoFood** — Session login disimpan di `platforms/gofood/sessions/`. Jika session expired, browser akan terbuka otomatis untuk login ulang.

> **Shopee** — Chrome profile disimpan di `data/chrome_profile`. Session reusable selama cookie belum expired.

> **GrabFood** — Credentials (username Grab Merchant) harus diisi di kolom **Nama Pengguna** / **Kata Sandi** pada Google Sheets untuk baris Grab.

> **Skip Otomatis** — Outlet yang sudah punya file hasil ekstraksi (`.csv`/`.xlsx`) akan di-skip secara otomatis saat memilih mode *"Hanya yang Belum Selesai"*.

---

## 🛠️ Troubleshooting

| Masalah | Solusi |
|---------|--------|
| `ModuleNotFoundError: playwright` | Jalankan `uv sync` lalu `uv run python -m playwright install chromium` |
| Session GoFood expired | Hapus file di `platforms/gofood/sessions/`, jalankan ulang |
| Cache GSheets stale | Jalankan `./run.sh update` |
| Grab credentials tidak ditemukan | Isi kolom "Nama Pengguna" & "Kata Sandi" di Google Sheet untuk baris Grab |
| Browser tidak muncul | Set `"headless_grab": false` di `config.json` |
