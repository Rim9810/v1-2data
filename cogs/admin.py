# cogs/admin.py
import discord
from discord.ext import commands

class AdminCog(commands.Cog, name="Admin"):
    """Các lệnh cấu hình Server (Dành cho Moderator)"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context):
        # Chỉ cho phép dùng các lệnh trong Cog này nếu có quyền quản lý server
        if not ctx.guild:
            return False
        return ctx.author.guild_permissions.manage_guild

    @commands.hybrid_command(name="setprefix", help="Đổi prefix của bot trong server này.")
    async def setprefix(self, ctx: commands.Context, new_prefix: str):
        """Thay đổi prefix lệnh (VD: /setprefix !)."""
        if not hasattr(self.bot, "data"):
            await ctx.send("❌ Lỗi hệ thống dữ liệu.")
            return

        if len(new_prefix) > 5:
            await ctx.send("❌ Prefix quá dài (tối đa 5 ký tự).")
            return

        await self.bot.data.set_guild_prefix(ctx.guild.id, new_prefix)
        await ctx.send(f"✅ Đã đổi prefix server thành: **{new_prefix}**\n(Bạn vẫn có thể dùng Mention hoặc `z` mặc định).")

    @commands.hybrid_group(name="config", aliases=["conf"], help="Cấu hình kênh cho phép bot hoạt động (allow/remove/list).")
    async def config(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @config.command(name="allow", help="Cho phép bot hoạt động tại kênh hiện tại (hoặc kênh chỉ định).")
    async def config_allow(self, ctx: commands.Context, channel: discord.TextChannel | None = None):
        target = channel or ctx.channel
        if not hasattr(self.bot, "data"):
            return
        
        await self.bot.data.add_allowed_channel(ctx.guild.id, target.id)
        
        # Lấy danh sách để hiển thị
        allowed = self.bot.data.get_allowed_channels(ctx.guild.id)
        mentions = [f"<#{cid}>" for cid in allowed]
        
        embed = discord.Embed(
            title="✅ Đã thêm kênh cho phép",
            description=f"Bot hiện chỉ hoạt động tại:\n" + ", ".join(mentions),
            color=0x2ECC71
        )
        await ctx.send(embed=embed)

    @config.command(name="remove", aliases=["block"], help="Cấm bot hoạt động tại kênh chỉ định (xóa khỏi allowlist).")
    async def config_remove(self, ctx: commands.Context, channel: discord.TextChannel | None = None):
        target = channel or ctx.channel
        if not hasattr(self.bot, "data"):
            return

        removed = await self.bot.data.remove_allowed_channel(ctx.guild.id, target.id)
        if removed:
            allowed = self.bot.data.get_allowed_channels(ctx.guild.id)
            if not allowed:
                desc = "Danh sách trống. Bot sẽ hoạt động ở **tất cả** các kênh."
            else:
                desc = "Bot hiện chỉ hoạt động tại:\n" + ", ".join([f"<#{cid}>" for cid in allowed])
            
            embed = discord.Embed(title=f"🚫 Đã xóa {target.name} khỏi danh sách", description=desc, color=0xE74C3C)
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"⚠️ Kênh {target.mention} không có trong danh sách cho phép.")

    @config.command(name="list", help="Xem danh sách các kênh bot được phép hoạt động.")
    async def config_list(self, ctx: commands.Context):
        if not hasattr(self.bot, "data"):
            return
        allowed = self.bot.data.get_allowed_channels(ctx.guild.id)
        
        if not allowed:
            await ctx.send("🌐 Bot đang hoạt động ở **tất cả** các kênh (chưa thiết lập giới hạn).")
        else:
            embed = discord.Embed(
                title="Danh sách kênh cho phép",
                description=", ".join([f"<#{cid}>" for cid in allowed]),
                color=0x3498DB
            )
            await ctx.send(embed=embed)

    @config.command(name="reset", help="Xóa toàn bộ cấu hình kênh (Bot sẽ hoạt động ở mọi nơi).")
    async def config_reset(self, ctx: commands.Context):
        if not hasattr(self.bot, "data"):
            return
        
        await self.bot.data.clear_allowed_channels(ctx.guild.id)
        await ctx.send("🔄 Đã đặt lại. Bot hiện hoạt động ở **tất cả** các kênh.")

    @setprefix.error
    @config.error
    async def admin_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("⛔ Bạn cần quyền **Manage Server** để dùng lệnh này.")

async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))