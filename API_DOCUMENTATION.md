# 📡 Dokumentasi API & Data Mapping (Menu Outlet)

Dokumen ini menjelaskan *endpoints* internal yang dihubungi oleh masing-masing aplikator serta cara pemetaan (*mapping*) dari struktur *JSON response* ke kolom-kolom Excel yang dihasilkan (`Items` dan `Modifiers`).

---

## 1. GoFood (Intersepsi via GoBiz Dashboard)

Scraper GoFood bekerja dengan menggunakan Playwright untuk memonitor trafik jaringan (*network interception*) saat browser masuk ke dalam dashboard GoBiz.

### Endpoints
- **Menu Items**: `GET https://app.gobiz.com/gofood/merchant/v1/restaurants/{store_id}/menus`
- **Modifiers/Variants**: `GET https://app.gobiz.com/gofood/merchant/v1/restaurants/{store_id}/variant_categories`

### Mapping Kolom `Items`
- **Nama kategori**: Diambil dari properti `name` pada tiap *array element* `menus`.
- **Nama item**: Diambil dari `name` di dalam array `menu_items`.
- **Deskripsi item**: Diambil dari `description` di dalam `menu_items`.
- **Harga sebelum promo**: Diambil dari `price`.
- **Harga setelah promo**: Diambil dari `promotion.discounted_price` atau `promotion.promo_price` (jika ada promo aktif).
- **Nominal/Persentase promo**: Diambil dari `promotion.discount_percentage` atau dikalkulasi dari perbedaan harga.
- **Ketersediaan item**: Dianggap "Tersedia" jika `active: true` dan `in_stock: true`.
- **Link foto**: Diambil dari `image_cover.url` atau `image`.
- **Jumlah modifier group**: Total array pada properti `variant_category_ids`.
- **Jumlah modifier**: Dihitung total *variants* yang ada di dalam referensi masing-masing `variant_category_ids`.

### Mapping Kolom `Modifiers`
- **Nama modifier group**: Diambil dari `name` di dalam *response endpoint* variant_categories.
- **Nama modifier**: Diambil dari `name` di dalam list `variants`.
- **Tipe modifier**: Jika rule `max_quantity` == 1 maka "Pilihan Tunggal", selain itu "Pilihan Ganda".
- **Minimal / Maksimal**: Diambil dari `rules.selection.min_quantity` dan `rules.selection.max_quantity`.
- **Harga modifier**: Diambil dari `price` di dalam data `variants`.
- **Ketersediaan modifier**: "Tersedia" jika `active: true` dan `in_stock: true`.

---

## 2. ShopeeFood (Fetch via Shopee Partner API)

Scraper Shopee mengambil *cookie* (terutama `shopee_tob_token`) dari sesi login Selenium, kemudian memanggil API ShopeeFood dari konteks request lokal.

### Endpoints
- **Katalog & Menu**: `GET https://foody.shopee.co.id/api/seller/store/dishes`
- **Modifiers (Option Groups)**: `POST https://foody.shopee.co.id/api/seller/store/option-groups/search`
  *(Dikirimkan payload `{"filter": {"dish_ids": [...]}}` untuk menarik modifier)*
- **Switch Merchant Portal**: `POST https://api.partner.shopee.co.id/nb/mss/web-api/PartnerAccountServer/SwitchPortal`

### Mapping Kolom `Items`
- **Nama kategori**: Diambil dari properti `name` di dalam object list `catalogs`.
- **Nama item**: Diambil dari `name` di array `dishes`.
- **Jumlah terjual**: Diambil dari properti `sales_volume`.
- **Deskripsi item**: Diambil dari `description`.
- **Harga sebelum promo**: Diambil dari properti `list_price` (dibagi 100.000 untuk konversi ke nominal Rp).
- **Harga setelah promo**: Diambil dari `price` (dibagi 100.000).
- **Nominal/Persentase promo**: Diambil dari `discount_percentage`.
- **Ketersediaan item**: Dianggap "Tersedia" jika properti `available` mengembalikan nilai boolean `true`.
- **Link foto**: Digabungkan menggunakan *base URL* gambar milik Shopee (`https://down-id.img.susercontent.com/file/`) + properti `picture`.

### Mapping Kolom `Modifiers`
- **Nama modifier group**: Diambil dari `option_group.name`.
- **Nama modifier**: Diambil dari array `options`, parameter `name`.
- **Tipe modifier**: Jika `select_max` == 1 maka "Pilihan Tunggal", selain itu "Pilihan Ganda".
- **Minimal / Maksimal**: Diambil dari `option_group.select_min` dan `option_group.select_max`.
- **Harga modifier**: Diambil dari `price` pada array options (dibagi 100.000).
- **Ketersediaan modifier**: Dianggap "Tersedia" jika nilai parameter `available: true`.

---

## 3. GrabFood (Fetch via Grab Merchant Portal)

Scraper GrabFood menggunakan engine internal pada direktori `GR/grab/` menggunakan library `Playwright` untuk bypass login portal, lalu mengeksekusi request ke API Endpoint Grab Merchant.

### Endpoints
- **Single Outlet Menu**: `GET https://api.grab.com/food/merchant/v2/menu`
- **Daftar Menu Groups (Multi-Outlet)**: `GET https://api.grab.com/food/merchant/v1/menu-groups?isWithItemPhotoCount=true`
- **Multi-Outlet/Group Menu Detail**: `GET https://api.grab.com/food/merchant/v2/menu-groups/menu?menuGroupID={store_id}`

### Mapping Kolom `Items`
*(Struktur JSON GrabFood memiliki struktur data bertingkat / nested object yang diparsing ke format flat list oleh grab_api_scraper)*
- **Nama kategori**: Diambil dari data list `categories` pada API.
- **Nama item**: Diambil dari properti `name` di dalam objek `items`.
- **Jumlah terjual**: Tidak dikembalikan oleh API (dibiarkan kosong / 0).
- **Deskripsi item**: Diambil dari properti `description`.
- **Harga sebelum promo**: Diambil dari nilai `priceInMinorUnit` (dibagi unit decimal, biasanya 100).
- **Harga setelah promo**: Jika ada promo, nilainya digantikan dengan hitungan diskon yang dikembalikan API Grab.
- **Ketersediaan item**: Diambil dari status `availableStatus` (contoh: "AVAILABLE" -> Tersedia, "UNAVAILABLE" -> Habis).
- **Link foto**: Diambil dari link image di array `photos` di dalam objek item.

### Mapping Kolom `Modifiers`
- **Nama modifier group**: Diambil dari properti `name` pada level struktur `modifierGroups`.
- **Nama modifier**: Diambil dari properti `name` di level array `modifiers`.
- **Tipe modifier**: Ditentukan dengan kombinasi nilai `minSelection` dan `maxSelection`.
- **Minimal / Maksimal**: Dari `minSelection` dan `maxSelection` pada group properties.
- **Harga modifier**: Dari nilai penambahan harga / `priceInMinorUnit` di dalam modifier.
- **Ketersediaan modifier**: "Tersedia" jika property `availableStatus` berstatus "AVAILABLE".
