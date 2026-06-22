#!/usr/bin/env python3
"""
Discord Bot — Menu Outlet Extractor
Dibuat ulang dalam Python (discord.py) untuk menggantikan versi Node.js.
"""

import os
import sys
import json
import logging
import asyncio
import subprocess
from pathlib import Path

# Instalasi dependensi otomatis
try:
    import discord
    from discord import app_commands
    from discord.ext import commands
    from dotenv import load_dotenv
except ImportError:
    print("Menginstal discord.py dan python-dotenv...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "discord.py>=2.3", "python-dotenv"])
    import discord
    from discord import app_commands
    from discord.ext import commands
    from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s")
log = logging.getLogger("discord_bot")

# Coba muat .env dari discord-bot/ jika ada, jika tidak dari root
SRC_DIR = Path(__file__).parent
dotenv_path = SRC_DIR / "discord-bot" / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path)
else:
    load_dotenv(SRC_DIR / ".env")

BOT_TOKEN = os.getenv("DISCORD_TOKEN")
CLI_PATH = SRC_DIR / "cli.py"

outlets_cache = None

def fetch_outlets():
    """Mengambil list outlet dari cli.py via --list-json dan menyimpannya di cache"""
    global outlets_cache
    if outlets_cache:
        return outlets_cache
    try:
        proc = subprocess.run([sys.executable, str(CLI_PATH), "--list-json"], capture_output=True, text=True)
        if proc.returncode == 0:
            import re
            match = re.search(r'\{"gofood":.*"shopee":.*\]\}', proc.stdout)
            if match:
                outlets_cache = json.loads(match.group(0))
            else:
                outlets_cache = json.loads(proc.stdout)
            return outlets_cache
    except Exception as e:
        log.error("Failed to parse --list-json: %s", e)
    return None

class ConfirmView(discord.ui.View):
    def __init__(self, platform: str, outlet: str, cabang: str):
        super().__init__(timeout=300)
        self.platform = platform
        self.outlet = outlet
        self.cabang = cabang
        
    @discord.ui.button(label="✅ Jalankan Pipeline", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="⏳ **Menyiapkan pipeline...**", embeds=[], view=None)
        
        cmd = [sys.executable, str(CLI_PATH), "--platform", self.platform, "--outlet", self.outlet, "--cabang", self.cabang]
        log.info("Running Pipeline: %s", " ".join(cmd))
        subprocess.Popen(cmd, cwd=str(SRC_DIR))
        
        await interaction.edit_original_response(content=f"🚀 **Pipeline Menu Extractor sedang berjalan di background!**\n\nPlatform: **{self.platform.upper()}**\nOutlet: **{self.outlet}**\nCabang: **{self.cabang}**\n\nCek log server atau Google Drive Anda.")

    @discord.ui.button(label="❌ Batal", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="🛑 **Operasi dibatalkan.**", embeds=[], view=None)

class CabangSelect(discord.ui.Select):
    def __init__(self, platform: str, outlet: str):
        self.platform = platform
        self.outlet_name = outlet
        outlets = fetch_outlets() or {}
        
        if platform == "all":
            available = outlets.get("gofood", []) + outlets.get("grab", []) + outlets.get("shopee", [])
        else:
            available = outlets.get(platform, [])
            
        branches = set()
        for o in available:
            name = o.get("nama_resto_final") or o.get("nama_outlet") or o.get("merchant_name")
            if name == outlet:
                branch = o.get("brand") or o.get("cabang")
                if branch: branches.add(branch)
                    
        arr = list(branches)[:23]
        options = [
            discord.SelectOption(label="Semua Cabang", value="all", emoji="🏢"),
            discord.SelectOption(label="Hanya Cabang Baru (Belum Ditarik)", value="new", emoji="✨")
        ]
        
        for b in arr:
            options.append(discord.SelectOption(label=b[:100], value=b[:100]))
            
        super().__init__(placeholder="Pilih Cabang", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        cabang = self.values[0]
        view = ConfirmView(self.platform, self.outlet_name, cabang)
        embed = discord.Embed(title="📋 Konfirmasi Penarikan Menu", description="Periksa data di bawah. Jika sudah sesuai, klik **Jalankan Pipeline**.", color=0xFFA500)
        embed.add_field(name="Platform", value=self.platform.upper(), inline=True)
        embed.add_field(name="Outlet", value=self.outlet_name, inline=True)
        embed.add_field(name="Cabang", value=cabang, inline=True)
        await interaction.response.edit_message(embed=embed, view=view)

class CabangSelectView(discord.ui.View):
    def __init__(self, platform: str, outlet: str):
        super().__init__(timeout=300)
        self.add_item(CabangSelect(platform, outlet))

class OutletSelect(discord.ui.Select):
    def __init__(self, platform: str):
        self.platform = platform
        outlets = fetch_outlets() or {}
        
        if platform == "all":
            available = outlets.get("gofood", []) + outlets.get("grab", []) + outlets.get("shopee", [])
        else:
            available = outlets.get(platform, [])
            
        unique = set()
        for o in available:
            name = o.get("nama_resto_final") or o.get("nama_outlet") or o.get("merchant_name")
            if name: unique.add(name)
            
        arr = list(unique)[:24]
        options = [discord.SelectOption(label="Semua Outlet", value="all", emoji="🏢")]
        for u in arr:
            options.append(discord.SelectOption(label=u[:100], value=u[:100]))
            
        super().__init__(placeholder="Pilih Outlet", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        outlet = self.values[0]
        if outlet == "all":
            view = ConfirmView(self.platform, outlet, "all")
            embed = discord.Embed(title="📋 Konfirmasi Penarikan Menu", description="Periksa data di bawah. Jika sudah sesuai, klik **Jalankan Pipeline**.", color=0xFFA500)
            embed.add_field(name="Platform", value=self.platform.upper(), inline=True)
            embed.add_field(name="Outlet", value=outlet, inline=True)
            embed.add_field(name="Cabang", value="all", inline=True)
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            view = CabangSelectView(self.platform, outlet)
            embed = discord.Embed(title="Pilih Cabang", description=f"Platform: **{self.platform.upper()}**\nOutlet: **{outlet}**\nSilakan pilih cabang yang ingin diproses.", color=0x5865F2)
            await interaction.response.edit_message(embed=embed, view=view)

class OutletSelectView(discord.ui.View):
    def __init__(self, platform: str):
        super().__init__(timeout=300)
        self.add_item(OutletSelect(platform))

class PlatformSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="GoFood", value="gofood", emoji="🔴"),
            discord.SelectOption(label="GrabFood", value="grab", emoji="🟢"),
            discord.SelectOption(label="ShopeeFood", value="shopee", emoji="🟠"),
            discord.SelectOption(label="Semua Aplikasi", value="all", emoji="🌟")
        ]
        super().__init__(placeholder="Pilih Aplikasi/Platform", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        platform = self.values[0]
        view = OutletSelectView(platform)
        embed = discord.Embed(title="Pilih Outlet", description=f"Platform terpilih: **{platform.upper()}**\nSilakan pilih Outlet.", color=0x5865F2)
        await interaction.response.edit_message(embed=embed, view=view)

class PlatformSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(PlatformSelect())


intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.tree.command(name="ekstrak", description="Mulai Menu Extractor Pipeline")
async def cmd_ekstrak(interaction: discord.Interaction):
    fetch_outlets()
    view = PlatformSelectView()
    embed = discord.Embed(title="Aplikasi / Platform", description="Silakan pilih platform yang ingin ditarik datanya.", color=0x5865F2)
    await interaction.response.send_message(embed=embed, view=view)

@bot.event
async def on_ready():
    await bot.tree.sync()
    log.info("="*50)
    log.info("Bot online: %s (ID: %s)", bot.user, bot.user.id)
    log.info("="*50)

def main():
    if not BOT_TOKEN:
        log.error("❌ DISCORD_TOKEN tidak ditemukan di .env atau discord-bot/.env!")
        sys.exit(1)
    
    log.info("🚀 Memulai bot...")
    bot.run(BOT_TOKEN, log_handler=None)

if __name__ == "__main__":
    main()
