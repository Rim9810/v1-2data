import asyncio
import logging
import traceback
import sys
import os
from pathlib import Path

import discord
from discord.ext import commands

# Fix lỗi Event Loop của Motor/Asyncio trên Windows
if os.name == 'nt':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Ensure local package imports work regardless of CWD / execution mode
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

try:
    from data_manager import DataManager
except Exception:
    # fallback when running as package
    try:
        from .data_manager import DataManager
    except Exception:
        # last resort: import using importlib
        import importlib.util
        spec = importlib.util.spec_from_file_location('data_manager', BASE_DIR / 'data_manager.py')
        dm = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(dm) 
        DataManager = dm.DataManager

# ===== BẢO MẬT: Lấy token từ biến môi trường =====
#   PowerShell:  setx DISCORD_TOKEN "PASTE_TOKEN"
#   bash/zsh:    export DISCORD_TOKEN="PASTE_TOKEN"

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError(
        "Thiếu TOKEN. Hãy set biến môi trường, KHÔNG hard-code token trong source."
    )

# ===== Logging =====
logging.basicConfig(
    level=logging.INFO,  # đổi DEBUG nếu muốn chi tiết hơn
    format="%(asctime)s | %(levelname)-7s | %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("bot")

# ===== Bot & Intents =====
# Mặc định prefix của bot (viết thường). Bot sẽ chấp nhận cả dạng chữ hoa tương ứng.
DEFAULT_PREFIX = "z"

async def get_prefix(bot, message):
    """Trả về callable prefix chấp nhận cả chữ thường và chữ hoa, đồng thời vẫn cho phép mention."""
    default = DEFAULT_PREFIX
    if message.guild and hasattr(bot, "data"):
        try:
            custom = bot.data.get_guild_prefix(message.guild.id)
            if custom:
                return commands.when_mentioned_or(custom, custom.upper())(bot, message)
        except Exception:
            pass
    # commands.when_mentioned_or trả về một callable phù hợp với API của discord.py
    return commands.when_mentioned_or(default.lower(), default.upper())(bot, message)

intents = discord.Intents.default()
intents.message_content = True  # nhớ bật trong Developer Portal
bot = commands.Bot(command_prefix=get_prefix, intents=intents)

BASE_DIR = Path(__file__).resolve().parent
bot.data = DataManager(BASE_DIR / "data" / "fishing_data.json")

# ===== Global Check: Channel Restriction =====
@bot.check
async def check_channel_allowlist(ctx: commands.Context):
    """Kiểm tra xem lệnh có được dùng ở kênh này không."""
    # Luôn cho phép DM hoặc nếu user là Owner/Admin (tùy chọn, ở đây ta bắt buộc theo config)
    if not ctx.guild:
        return True
    
    if not hasattr(bot, "data"):
        return True

    allowed_ids = bot.data.get_allowed_channels(ctx.guild.id)
    # Nếu danh sách rỗng -> cho phép tất cả
    if not allowed_ids:
        return True
    
    return ctx.channel.id in allowed_ids

@bot.command(name="sync", help="Đồng bộ lệnh Slash Command (Owner only)")
@commands.is_owner()
async def sync(ctx: commands.Context, spec: str | None = None):
    """
    Đồng bộ lệnh Slash.
    /sync -> Đồng bộ global (chậm, ~1h)
    /sync . -> Đồng bộ guild hiện tại (nhanh)
    /sync ^ -> Xóa lệnh guild hiện tại
    """
    if spec == ".":
        msg = await ctx.send(f"⏳ Đang đồng bộ vào guild **{ctx.guild.name}**...")
        # Copy lệnh global vào guild hiện tại để hiện ngay lập tức (tránh delay 1h của global)
        ctx.bot.tree.copy_global_to(guild=ctx.guild)
        synced = await ctx.bot.tree.sync(guild=ctx.guild)
        await msg.edit(content=f"✅ Đã đồng bộ **{len(synced)}** lệnh vào guild này.")
    elif spec == "^":
        ctx.bot.tree.clear_commands(guild=ctx.guild)
        await ctx.bot.tree.sync(guild=ctx.guild)
        await ctx.send(f"🧹 Đã xóa lệnh trong guild **{ctx.guild.name}**.")
    else:
        msg = await ctx.send("⏳ Đang đồng bộ **Global** (có thể mất tới 1h)...")
        synced = await ctx.bot.tree.sync()
        await msg.edit(content=f"✅ Đã đồng bộ **{len(synced)}** lệnh Global.")

@sync.error
async def sync_error(ctx, error):
    if isinstance(error, commands.NotOwner):
        await ctx.send("⛔ Bạn không phải Owner của bot này (chỉ người tạo bot mới dùng được lệnh sync).")
    else:
        await ctx.send(f"❌ Lỗi sync: {error}")

@bot.event
async def on_ready():
    log.info(f"✅ Đăng nhập như: {bot.user} (ID: {bot.user.id})")
    log.info(f"🚀 Prefix hiện tại: {DEFAULT_PREFIX}")
    # In link mời bot có quyền Slash Command để tiện kiểm tra
    invite = discord.utils.oauth_url(bot.user.id, permissions=discord.Permissions(8), scopes=("bot", "applications.commands"))
    log.info(f"🔗 Invite Link (Admin + Slash): {invite}")
    # In danh sách Cog đã add thành công
    if bot.cogs:
        log.info("Cogs đã load: " + ", ".join(sorted(bot.cogs.keys())))
    else:
        log.warning("Chưa có Cog nào được load.")

    # [QUAN TRỌNG] Khởi tạo kết nối và tải dữ liệu từ MongoDB vào RAM
    await bot.data.initialize()

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # Nếu người dùng chỉ mention bot (không kèm lệnh), bot sẽ trả lời prefix
    if bot.user in message.mentions and message.content.strip() in (f"<@{bot.user.id}>", f"<@!{bot.user.id}>"):
        await message.reply(f"👋 Xin chào! Prefix của mình là `{DEFAULT_PREFIX}` (hoặc bạn có thể dùng `/` cho lệnh Slash).")

    await bot.process_commands(message)

async def load_extensions():
    """Load tất cả file .py trong thư mục cogs/ và chỉ in COGs không load được."""
    cogs_dir = BASE_DIR / "cogs"
    if not cogs_dir.exists():
        log.warning(f"Không tìm thấy thư mục cogs: {cogs_dir}")
        return

    failures = []
    for py in cogs_dir.glob("*.py"):
        if py.name == "__init__.py":
            continue
        ext = f"cogs.{py.stem}"
        try:
            await bot.load_extension(ext)
            # intentionally silent on success
        except Exception as e:
            # collect failure and stacktrace for later reporting
            failures.append((ext, e, traceback.format_exc()))

    if failures:
        log.error("❌ Có lỗi khi load một số COGs:")
        for ext, e, tb in failures:
            log.error(f"- {ext}: {e}")
            # print full traceback to stdout for easier grep in terminal
            print(tb)
async def main():
    async with bot:
        await load_extensions()
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
