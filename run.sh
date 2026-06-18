#!/bin/bash
# ==========================================================
#  run.sh — Superfood Tech | Menu & Modifier Extractor
#  Usage:
#    bash run.sh           → mode interaktif (default)
#    bash run.sh gofood    → langsung ke GoFood (semua outlet)
#    bash run.sh shopee    → langsung ke Shopee (semua outlet)
#    bash run.sh grab      → langsung ke Grab (semua outlet)
#    bash run.sh update    → paksa download ulang data dari GSheets
#    bash run.sh help      → tampilkan bantuan
# ==========================================================

# ─── Warna terminal ───────────────────────────────────────
BOLD="\033[1m"
CYAN="\033[36m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
RESET="\033[0m"
DIM="\033[2m"

# ─── Direktori script ─────────────────────────────────────
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$BASE/.venv"
PYTHON="$VENV/bin/python"
CLI="$BASE/cli.py"

# ─── Banner ───────────────────────────────────────────────
print_banner() {
    [ -t 1 ] && clear || true
    echo -e "\033[90m=================================================================${RESET}"
    echo -e "  ${BOLD}${CYAN}      SUPERFOOD TECH — MENU & MODIFIER EXTRACTOR PIPELINE${RESET}"
    echo -e "\033[90m=================================================================${RESET}"
    echo ""
}

# ─── Periksa .venv ────────────────────────────────────────
check_venv() {
    if [ ! -f "$PYTHON" ]; then
        echo -e "  ${RED}✗ Virtual environment tidak ditemukan di .venv/${RESET}"
        echo -e "  ${YELLOW}→ Jalankan: uv sync${RESET}"
        exit 1
    fi
    PYTHON_VER=$("$PYTHON" --version 2>&1)
    echo -e "  ${DIM}Python  : $PYTHON_VER${RESET}"
    echo -e "  ${DIM}Env     : $VENV${RESET}"
    echo -e "  ${DIM}Waktu   : $(date '+%Y-%m-%d %H:%M:%S')${RESET}"
    echo ""
}

# ─── Main ─────────────────────────────────────────────────
MODE="${1:-interactive}"

print_banner
check_venv

case "$MODE" in

    # ── Mode Interaktif (default) ─────────────────────────
    interactive|"")
        echo -e "  ${GREEN}▶ Memulai mode interaktif...${RESET}"
        echo ""
        "$PYTHON" "$CLI"
        ;;

    # ── Mode per-platform langsung ────────────────────────
    gofood|shopee|grab)
        PLATFORM="$(echo "$MODE" | awk '{print toupper(substr($0,1,1)) substr($0,2)}')"
        echo -e "  ${GREEN}▶ Memulai ekstraksi ${BOLD}${PLATFORM}${RESET}${GREEN} (semua outlet)...${RESET}"
        echo ""
        "$PYTHON" "$CLI" --platform "$MODE" --batch
        ;;

    # ── Paksa refresh cache GSheets ───────────────────────
    update)
        echo -e "  ${YELLOW}▶ Memperbarui cache data dari Google Sheets...${RESET}"
        echo ""
        "$PYTHON" - <<PYEOF
import sys, os
sys.path.insert(0, "$BASE")
from menu_core.sheets import get_master_df
df = get_master_df(force_download=True)
print(f"  \033[32m✓ Cache diperbarui: {len(df)} baris dimuat dari GSheets.\033[0m")
PYEOF
        echo ""
        echo -e "  ${DIM}Jalankan './run.sh' untuk mulai ekstraksi.${RESET}"
        ;;

    # ── Bantuan ───────────────────────────────────────────
    help|--help|-h)
        echo -e "  ${BOLD}PENGGUNAAN:${RESET}"
        echo ""
        echo -e "    ${CYAN}bash run.sh${RESET}            Mode interaktif (pilih platform & outlet)"
        echo -e "    ${CYAN}bash run.sh gofood${RESET}     Jalankan langsung GoFood (semua outlet)"
        echo -e "    ${CYAN}bash run.sh shopee${RESET}     Jalankan langsung Shopee (semua outlet)"
        echo -e "    ${CYAN}bash run.sh grab${RESET}       Jalankan langsung Grab   (semua outlet)"
        echo -e "    ${CYAN}bash run.sh update${RESET}     Paksa refresh data dari Google Sheets"
        echo -e "    ${CYAN}bash run.sh help${RESET}       Tampilkan bantuan ini"
        echo ""
        echo -e "  ${BOLD}OUTPUT:${RESET}"
        echo -e "    ${DIM}platforms/gofood/outlets/<nama>/  → hasil GoFood (.csv & .xlsx)${RESET}"
        echo -e "    ${DIM}platforms/shopee/outlets/<nama>/  → hasil Shopee (.csv & .xlsx)${RESET}"
        echo -e "    ${DIM}platforms/grab/outlets/<nama>/    → hasil Grab   (.csv & .xlsx)${RESET}"
        echo ""
        echo -e "  ${BOLD}TIPS:${RESET}"
        echo -e "    ${DIM}Buat executable sekali: chmod +x run.sh${RESET}"
        echo -e "    ${DIM}Lalu jalankan dengan : ./run.sh${RESET}"
        echo ""
        ;;

    # ── Tidak dikenal ─────────────────────────────────────
    *)
        echo -e "  ${RED}✗ Argumen tidak dikenal: '$MODE'${RESET}"
        echo -e "  ${DIM}Gunakan: bash run.sh help${RESET}"
        exit 1
        ;;
esac
