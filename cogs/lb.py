# cogs/lb.py
from __future__ import annotations
import discord
from discord.ext import commands
from typing import Dict, Tuple, List, Optional, Any

EMBED_COLOR = 0x9B59B6  # Purple

class LeaderboardCog(commands.Cog, name="Leaderboard"):
    """Hiển thị bảng xếp hạng người chơi."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _read_all_users(self) -> Dict[str, Dict]:
        """Reads all user data from the DataManager."""
        try:
            # Prefer the public API if available
            if hasattr(self.bot.data, "read_all_users"):
                return self.bot.data.read_all_users()
        except Exception:
            pass
        # Fallback to the old method
        try:
            data = self.bot.data._read_sync()
            return data.get("USERS", {})
        except Exception:
            return {}

    async def _get_user_mention(self, user_id: int) -> str:
        """Gets a user mention, fetching the user if not in cache."""
        user = self.bot.get_user(user_id)
        if user is None:
            try:
                user = await self.bot.fetch_user(user_id)
            except discord.NotFound:
                return f"<Unknown User {user_id}>"
        return user.mention

    # =========================
    # Leaderboard: Most Expensive Fish
    # =========================
    def _make_fish_leaderboard(self, limit: int) -> List[Tuple[int, int, str]]:
        """
        Creates a leaderboard of users with the most expensive single fish.
        Returns a list of (user_id, sell_price, fish_name).
        """
        users = self._read_all_users()
        rows: List[Tuple[int, int, str, str]] = []  # (user_id, price, fish_name, fish_rarity)

        for uid_str, udata in users.items():
            user_fishes = udata.get("fishes", [])
            if not user_fishes:
                continue

            # Find the most expensive fish for the current user
            most_expensive_fish = max(user_fishes, key=lambda f: f.get("sell_price", 0))
            price = most_expensive_fish.get("sell_price", 0)

            if price > 0:
                try:
                    uid = int(uid_str)
                    rows.append((uid, price, most_expensive_fish.get("name", "Unknown Fish"), most_expensive_fish.get("rarity", "")))
                except ValueError:
                    continue
        
        # Sort by price descending
        rows.sort(key=lambda x: -x[1])
        return rows[:limit]

    # =========================
    # Leaderboard: Currency (Cash & Gems)
    # =========================
    def _make_currency_leaderboard(self, currency_type: str, limit: int) -> List[Tuple[int, int]]:
        """
        Creates a leaderboard for a given currency (wallet or gems).
        Returns a list of (user_id, amount).
        """
        users = self._read_all_users()
        rows: List[Tuple[int, int]] = []

        for uid_str, udata in users.items():
            amount = udata.get(currency_type, 0)
            if amount > 0:
                try:
                    uid = int(uid_str)
                    rows.append((uid, amount))
                except ValueError:
                    continue
        
        # Sort by amount descending
        rows.sort(key=lambda x: -x[1])
        return rows[:limit]
        
    @commands.hybrid_group(
        name="top",
        aliases=["lb"],
        help="Hiển thị bảng xếp hạng. Sử dụng `/top [fish|cash|gem]`.",
        invoke_without_command=True
    )
    async def top(self, ctx: commands.Context):
        """Main command for leaderboards."""
        embed = discord.Embed(
            title="🏆 Bảng xếp hạng",
            description="Sử dụng lệnh con để xem chi tiết:\n" 
                        "• `/top fish`: Top cá nhân có con cá đắt nhất.\n" 
                        "• `/top cash`: Top người chơi giàu nhất.\n" 
                        "• `/top gem`: Top người chơi nhiều gem nhất.",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)

    @top.command(name="fish", help="Bảng xếp hạng cá đắt nhất.")
    async def top_fish(self, ctx: commands.Context, limit: int = 10):
        """Bảng xếp hạng cá đắt nhất."""
        limit = max(1, min(limit, 25)) # Clamp limit
        rows = self._make_fish_leaderboard(limit)
        
        title = "🏆 Bảng Xếp Hạng Cá Đắt Nhất"
        if not rows:
            embed = discord.Embed(title=title, description="Chưa có ai câu được con cá nào.", color=EMBED_COLOR)
            await ctx.send(embed=embed)
            return

        lines = []
        for i, (uid, price, fish_name, fish_rarity) in enumerate(rows, start=1):
            mention = await self._get_user_mention(uid)
            lines.append(f"**{i}.** {mention} - **{fish_name}** ({fish_rarity}) - **{price:,}** coins")

        embed = discord.Embed(title=title, description="\n".join(lines), color=EMBED_COLOR)
        await ctx.send(embed=embed)

    @top.command(name="cash", aliases=["money"], help="Bảng xếp hạng người chơi giàu nhất.")
    async def top_cash(self, ctx: commands.Context, limit: int = 10):
        """Bảng xếp hạng người chơi giàu nhất."""
        limit = max(1, min(limit, 25)) # Clamp limit
        rows = self._make_currency_leaderboard("wallet", limit)

        title = "💰 Bảng Xếp Hạng Tiền Tệ"
        if not rows:
            embed = discord.Embed(title=title, description="Chưa có dữ liệu về tiền của người chơi.", color=EMBED_COLOR)
            await ctx.send(embed=embed)
            return

        lines = []
        for i, (uid, amount) in enumerate(rows, start=1):
            mention = await self._get_user_mention(uid)
            lines.append(f"**{i}.** {mention} — **{amount:,}** coins")

        embed = discord.Embed(title=title, description="\n".join(lines), color=EMBED_COLOR)
        await ctx.send(embed=embed)

    @top.command(name="gem", aliases=["gems"], help="Bảng xếp hạng người chơi nhiều gem nhất.")
    async def top_gem(self, ctx: commands.Context, limit: int = 10):
        """Bảng xếp hạng người chơi nhiều gem nhất."""
        limit = max(1, min(limit, 25)) # Clamp limit
        rows = self._make_currency_leaderboard("gems", limit)

        title = "💎 Bảng Xếp Hạng Gem"
        if not rows:
            embed = discord.Embed(title=title, description="Chưa có dữ liệu về gem của người chơi.", color=EMBED_COLOR)
            await ctx.send(embed=embed)
            return

        lines = []
        for i, (uid, amount) in enumerate(rows, start=1):
            mention = await self._get_user_mention(uid)
            lines.append(f"**{i}.** {mention} — **{amount:,}** gems")

        embed = discord.Embed(title=title, description="\n".join(lines), color=EMBED_COLOR)
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(LeaderboardCog(bot))