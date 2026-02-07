# cogs/aquarium.py
from __future__ import annotations
import discord
from discord.ext import commands
import time
from typing import Dict, Any

# =================================
# Constants
# =================================
EMBED_COLOR = 0x00A9E0  # Deep Sky Blue
HOURLY_INCOME_RATE = 0.05  # 5% of fish value per hour

# Aquarium capacity by level
AQUARIUM_CAPACITY = {
    1: 2,
    5: 3,
    10: 4,
    20: 5,
}

def get_aquarium_capacity(level: int) -> int:
    """Gets the user's aquarium capacity based on their level."""
    cap = 0  # Start with a default capacity of 0
    # Sort the level requirements to ensure correct progressive checking
    for lvl_req in sorted(AQUARIUM_CAPACITY.keys()):
        if level >= lvl_req:
            cap = AQUARIUM_CAPACITY[lvl_req]
        else:
            # Since the levels are sorted, we can stop once the user's level is too low
            break
    return cap

class AquariumCog(commands.Cog, name="Thủy Cung"):
    """Nuôi cá kiếm tiền offline    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # =================================
    # Helper Methods
    # =================================
    def _get_full_fish_details(self, user_id: int) -> Dict[str, Any]:
        """Returns a dict mapping fish_id to the full fish object."""
        all_fishes = self.bot.data.get_fish_objects(user_id)
        return {f["id"]: f for f in all_fishes}

    # =================================
    # Main Command Group
    # =================================
    @commands.hybrid_group(
        name="aqua",
        aliases=["thuycung"],
        help="Quản lý thủy cung của bạn. Nuôi cá để kiếm tiền thụ động!",
        invoke_without_command=True
    )
    async def aqua(self, ctx: commands.Context):
        """Displays the user's aquarium, fish, and pending income."""
        user_id = ctx.author.id
        level = self.bot.data.get_level(user_id)
        capacity = get_aquarium_capacity(level)
        
        aquarium_data = self.bot.data.get_aquarium(user_id)
        fish_details_map = self._get_full_fish_details(user_id)

        # Build emoji map
        fish_emoji_map = {}
        try:
            from cogs.fish import FISH_POOLS
        except ImportError:
            try:
                from fish import FISH_POOLS
            except ImportError:
                FISH_POOLS = {}
        if FISH_POOLS:
            for pool in FISH_POOLS.values():
                for f in pool:
                    fish_emoji_map[f.get("name", "")] = f.get("emoji", "")
        try:
            from game_config import WEATHER_CONFIG
            for w in WEATHER_CONFIG.values():
                for f in w.get("special_fish", []):
                    fish_emoji_map[f.get("name", "")] = f.get("emoji", "")
        except Exception:
            pass
        
        total_earnings = 0
        fish_lines = []

        if not aquarium_data:
            fish_lines.append("🌊 *Thủy cung của bạn trống trơn...*")
        else:
            current_time = int(time.time())
            for fish_id, data in aquarium_data.items():
                fish = fish_details_map.get(fish_id)
                if not fish:
                    continue

                added_at = data.get("added_at", current_time)
                minutes_passed = (current_time - added_at) // 60
                hours_passed = minutes_passed / 60
                earnings = int(fish.get("sell_price", 0) * HOURLY_INCOME_RATE * hours_passed)
                total_earnings += earnings
                
                fname = fish.get('name', 'Unknown')
                emo = fish_emoji_map.get(fname, "🐠")
                fish_lines.append(
                    f"{emo} **{fname}** (`{fish['id']}`) - Thu nhập: **{earnings:,}** coins"
                )

        # Decorative Embed
        embed = discord.Embed(
            title=f"🌊 Thủy Cung của {ctx.author.display_name} 🌊",
            description=f"Đây là nơi bạn nuôi những con cá quý giá nhất của mình.\n"
                        f"**Sức chứa:** {len(aquarium_data)} / {capacity}\n"
                        f"**Tổng thu nhập chờ:** `{total_earnings:,}` coins",
            color=EMBED_COLOR
        )
        embed.add_field(
            name="🐟 Cá trong hồ 🐟",
            value="\n".join(fish_lines) or "Trống!",
            inline=False
        )
        embed.set_footer(text="🌿 Gõ `/aqua add/remove <mã_cá>` | `/aqua collect` để thu hoạch 🌿")

        await ctx.send(embed=embed)

    @aqua.command(name="add", help="Thêm một con cá vào thủy cung. VD: `/aqua add 4g7d`")
    async def aqua_add(self, ctx: commands.Context, fish_id: str):
        """Adds a fish to the aquarium."""
        user_id = ctx.author.id
        level = self.bot.data.get_level(user_id)
        capacity = get_aquarium_capacity(level)
        
        aquarium_data = self.bot.data.get_aquarium(user_id)

        if len(aquarium_data) >= capacity:
            await ctx.send(f"❌ **Lỗi:** Thủy cung của bạn đã đầy! (Tối đa {capacity} con). Hãy lên cấp để mở rộng.")
            return

        if fish_id in aquarium_data:
            await ctx.send("❌ **Lỗi:** Con cá này đã ở trong thủy cung rồi.")
            return

        fish_details_map = self._get_full_fish_details(user_id)
        if fish_id not in fish_details_map:
            await ctx.send("❌ **Lỗi:** Không tìm thấy con cá với mã này trong kho của bạn.")
            return

        fish = fish_details_map[fish_id]
        if fish.get("rarity") == "trash":
            await ctx.send("❌ **Lỗi:** Rác không thể thả vào thủy cung!")
            return

        current_time = int(time.time())
        aquarium_data[fish_id] = {"added_at": current_time}
        await self.bot.data.set_aquarium(user_id, aquarium_data)

        await ctx.send(f"✅ **Thành công!** Bạn đã thêm cá **{fish_details_map[fish_id]['name']}** (`{fish_id}`) vào thủy cung.")

    @aqua.command(name="remove", aliases=["rm"], help="Lấy một con cá ra khỏi thủy cung. VD: `/aqua remove 4g7d`")
    async def aqua_remove(self, ctx: commands.Context, fish_id: str):
        """Removes a fish from the aquarium."""
        user_id = ctx.author.id
        aquarium_data = self.bot.data.get_aquarium(user_id)

        if fish_id not in aquarium_data:
            await ctx.send("❌ **Lỗi:** Con cá này không có trong thủy cung.")
            return
            
        fish_details_map = self._get_full_fish_details(user_id)
        fish_name = fish_details_map.get(fish_id, {}).get("name", "Không rõ")

        del aquarium_data[fish_id]
        await self.bot.data.set_aquarium(user_id, aquarium_data)
        
        await ctx.send(f"✅ **Thành công!** Bạn đã lấy cá **{fish_name}** (`{fish_id}`) ra khỏi thủy cung. Nó đã được trả về kho đồ.")

    @aqua.command(name="collect", help="Thu hoạch tất cả tiền từ cá trong thủy cung.")
    async def aqua_collect(self, ctx: commands.Context):
        """Collects all generated income from the aquarium."""
        user_id = ctx.author.id
        aquarium_data = self.bot.data.get_aquarium(user_id)
        
        if not aquarium_data:
            await ctx.send("❌ **Lỗi:** Thủy cung của bạn trống, không có gì để thu hoạch.")
            return

        fish_details_map = self._get_full_fish_details(user_id)
        
        total_earnings = 0
        current_time = int(time.time())
        
        for fish_id, data in aquarium_data.items():
            fish = fish_details_map.get(fish_id)
            if not fish:
                continue

            added_at = data.get("added_at", current_time)
            minutes_passed = (current_time - added_at) // 60
            
            if minutes_passed < 1:
                continue

            hours_passed = minutes_passed / 60
            earnings = int(fish.get("sell_price", 0) * HOURLY_INCOME_RATE * hours_passed)
            total_earnings += earnings
            
            # Reset the timer for this fish
            aquarium_data[fish_id]["added_at"] = current_time

        if total_earnings <= 0:
            await ctx.send("🐠 Dường như chưa có thu nhập nào mới. Hãy chờ thêm một chút!")
            return

        # Update the database
        await self.bot.data.set_aquarium(user_id, aquarium_data)
        await self.bot.data.add_money(user_id, total_earnings)

        await ctx.send(f"🎉 **Thành công!** Bạn đã thu hoạch được **{total_earnings:,}** coins từ thủy cung!")


async def setup(bot: commands.Bot):
    await bot.add_cog(AquariumCog(bot))