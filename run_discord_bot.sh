#!/usr/bin/env bash
# =============================================================================
#  Menu Outlet Extractor — Discord Bot
#  Double-click untuk menjalankan bot
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Jika di-double-click dari file manager, buka terminal baru ───────────────
if [ -z "$TERM" ] || [ "$TERM" = "dumb" ]; then
    for TE in gnome-terminal xterm konsole xfce4-terminal mate-terminal lxterminal; do
        if command -v "$TE" &>/dev/null; then
            case "$TE" in
                gnome-terminal) exec gnome-terminal -- bash "$0" ;;
                xfce4-terminal) exec xfce4-terminal -e "bash \"$0\"" ;;
                konsole)        exec konsole -e bash "$0" ;;
                *)              exec "$TE" -e bash "$0" ;;
            esac
        fi
    done
fi

# ── Warna ─────────────────────────────────────────────────────────────────────
R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'
C='\033[0;36m'; W='\033[1;37m'; D='\033[2m'; NC='\033[0m'
LINE="${D}────────────────────────────────────────────────────────────${NC}"

clear

# ── Banner ────────────────────────────────────────────────────────────────────
echo -e "${C}"
echo "   __  __                  ___        _   _      _   "
echo "  |  \/  |___ _ _ _  _    / _ \ _  _| |_| |___ | |_  "
echo "  | |\/| / -_) ' \ || |  | (_) | || |  _| / -_)|  _| "
echo "  |_|  |_\___|_||_\_,_|   \___/ \_,_|\__|_\___| \__| "
echo -e "${NC}"
echo -e "${W}              Menu Extractor Pipeline — Discord Bot${NC}"
echo -e "${D}              powered by discord.py${NC}"
echo ""
echo -e "$LINE"

# ── Cek uv ───────────────────────────────────────────────────────────────────
if ! command -v uv &>/dev/null; then
    echo -e "\n${R}✖  'uv' tidak ditemukan.${NC}"
    echo -e "   Install dengan:\n   ${Y}curl -LsSf https://astral.sh/uv/install.sh | sh${NC}\n"
    read -rp "   Tekan ENTER untuk keluar …" ; exit 1
fi

echo ""
echo -e "  ${G}✔  Konfigurasi OK${NC}"
echo ""
echo -e "$LINE"
echo ""
echo -e "  ${W}🚀 Menjalankan Discord bot…${NC}"
echo -e "  ${D}   Tekan Ctrl+C untuk menghentikan${NC}"
echo ""
echo -e "$LINE"
echo ""

# ── Jalankan bot ──────────────────────────────────────────────────────────────
cd "$SCRIPT_DIR" || exit 1
uv run python discord_bot.py

echo ""
echo -e "$LINE"
echo -e "\n  ${Y}Bot dihentikan.${NC}"
echo ""
echo -e "  ${D}Tekan ENTER untuk menutup …${NC}"
read -r
