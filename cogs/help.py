# cogs/help.py
import discord
from discord.ext import commands
from discord.ui import Select, View

# Cấu hình Emoji cho từng danh mục (Cog)
COG_EMOJIS = {
    "Fishing": "🎣",
    "Inventory": "🎒",
    "Economy": "💰",
    "Thủy Cung": "🌊",
    "Leaderboard": "🏆",
    "Profile": "👤",
    "Pet": "🐾",
    "Index": "🔍",
    "Help": "ℹ️",
    "Admin": "🛡️"
}

class HelpSelect(Select):
    def __init__(self, bot: commands.Bot, mapping: dict, prefix: str):
        self.bot = bot
        self.mapping = mapping
        self.prefix = prefix
        
        options = [
            discord.SelectOption(
                label="Trang chủ",
                description="Quay lại màn hình chính",
                emoji="🏠",
                value="home"
            )
        ]
        
        # Tạo option cho từng Cog
        for cog_name, commands_list in sorted(mapping.items()):
            if not commands_list:
                continue
            
            # Lấy emoji tương ứng, mặc định là 📂
            emoji = COG_EMOJIS.get(cog_name, "📂")
            
            # Lấy mô tả ngắn của Cog (dòng đầu tiên trong docstring)
            cog = bot.get_cog(cog_name)
            description = (cog.__doc__ or "Không có mô tả.").split("\n")[0][:95]
            
            options.append(discord.SelectOption(
                label=cog_name,
                description=description,
                emoji=emoji,
                value=cog_name
            ))

        super().__init__(
            placeholder="Chọn danh mục lệnh để xem chi tiết...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        value = self.values[0]
        
        if value == "home":
            embed = self.view.home_embed
        else:
            cog = self.bot.get_cog(value)
            if not cog:
                await interaction.response.send_message("❌ Đã xảy ra lỗi, không tìm thấy danh mục này.", ephemeral=True)
                return
            
            commands_list = self.mapping[value]
            embed = discord.Embed(
                title=f"{COG_EMOJIS.get(value, '')} Danh sách lệnh: {value}",
                description=f"Các lệnh thuộc nhóm **{value}**.",
                color=0x3498DB
            )
            
            for cmd in commands_list:
                # Bỏ qua lệnh ẩn
                if cmd.hidden:
                    continue
                
                # Tạo chữ ký lệnh (signature)
                # Hybrid command thường có slash, ta ưu tiên hiển thị dạng prefix cho dễ hiểu hoặc cả hai
                is_hybrid = isinstance(cmd, (commands.HybridCommand, commands.HybridGroup))
                cmd_prefix = "/" if is_hybrid else self.prefix
                
                # Lấy mô tả lệnh
                desc = (cmd.help or "Chưa có mô tả.").split("\n")[0]
                
                # Format: `/lenh <thamso>`
                # cmd.signature tự động tạo chuỗi tham số <arg> [opt]
                signature = f"{cmd_prefix}{cmd.name} {cmd.signature}".strip()
                
                embed.add_field(
                    name=f"{COG_EMOJIS.get(value, '')} {cmd.name}",
                    value=f"**`{signature}`**\n{desc}",
                    inline=False
                )
                
                # Nếu là Group (như config), hiển thị thêm các lệnh con
                if isinstance(cmd, commands.Group):
                    for sub in sorted(cmd.commands, key=lambda c: c.name):
                        if sub.hidden:
                            continue
                        
                        sub_desc = (sub.help or "Chưa có mô tả.").split("\n")[0]
                        sub_sig = f"{cmd_prefix}{cmd.name} {sub.name} {sub.signature}".strip()
                        
                        embed.add_field(
                            name=f"╰ {sub.name}",
                            value=f"**`{sub_sig}`**\n{sub_desc}",
                            inline=False
                        )

            embed.set_footer(text=f"Tổng cộng: {len([c for c in commands_list if not c.hidden])} lệnh")

        await interaction.response.edit_message(embed=embed)


class HelpView(View):
    def __init__(self, bot: commands.Bot, mapping: dict, home_embed: discord.Embed, prefix: str):
        super().__init__(timeout=120)
        self.home_embed = home_embed
        self.add_item(HelpSelect(bot, mapping, prefix))

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

class HelpCog(commands.Cog, name="Help"):
    """Hệ thống hướng dẫn sử dụng Bot."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._original_help_command = bot.help_command
        bot.help_command = None # Tắt help mặc định

    def cog_unload(self):
        self.bot.help_command = self._original_help_command

    @commands.hybrid_command(name="help", description="Xem danh sách hướng dẫn sử dụng Bot.")
    async def help(self, ctx: commands.Context):
        """Hiển thị menu hướng dẫn tương tác."""
        mapping = {}
        for cog_name, cog in self.bot.cogs.items():
            cmds = cog.get_commands()
            visible_cmds = [c for c in cmds if not c.hidden]
            if visible_cmds:
                mapping[cog_name] = visible_cmds

        embed = discord.Embed(
            title="🤖 Hướng dẫn sử dụng Bot",
            description=(
                "Chào mừng bạn! Dưới đây là hệ thống lệnh của Bot.\n"
                "Hãy **chọn một danh mục** từ menu bên dưới để xem chi tiết."
            ),
            color=0x2ECC71
        )
        if self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)
        
        total_cmds = sum(len(v) for v in mapping.values())
        embed.add_field(name="📊 Thống kê", value=f"**{len(mapping)}** Danh mục\n**{total_cmds}** Lệnh", inline=True)
        embed.add_field(name="💡 Mẹo", value="Dùng `/` để xem gợi ý lệnh nhanh hơn!", inline=True)

        # Xác định prefix hiển thị (nếu dùng slash command thì fallback về "/")
        display_prefix = ctx.clean_prefix
        if ctx.interaction:
            display_prefix = "/"

        view = HelpView(self.bot, mapping, embed, display_prefix)
        await ctx.send(embed=embed, view=view)

async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))