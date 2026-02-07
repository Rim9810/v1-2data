# cogs/economy.py
from __future__ import annotations
import discord
from discord.ext import commands
from typing import Dict, Optional
from discord.ui import View, Select

import time
import random

# ---- Thử import cấu hình cần câu nếu có ----
try:
    from game_config import ROD_TIERS, MAX_ROD_LEVEL, GEM_SETTINGS, PRICE_PER_KG_BY_RARITY
except Exception:
    # Fallback mặc định nếu chưa có game_config.py
    ROD_TIERS = {
        1: {"name": "Cần Tre",        "cost": 0,     "bonus": 0, "len_add": 0, "timeout_sub": 0.0},
        2: {"name": "Cần Gỗ",         "cost": 500,   "bonus": 1, "len_add": 2, "timeout_sub": 0.5},
        3: {"name": "Cần Sắt",        "cost": 2000,  "bonus": 2, "len_add": 4, "timeout_sub": 1.0},
        4: {"name": "Cần Carbon",     "cost": 8000,  "bonus": 3, "len_add": 6, "timeout_sub": 1.5},
        5: {"name": "Cần Huyền Thoại","cost": 25000, "bonus": 4, "len_add": 8, "timeout_sub": 2.0},
    }
    MAX_ROD_LEVEL = max(ROD_TIERS)
    GEM_SETTINGS = {"gem_per_rarity": {"epic": 1}, "aurora_multiplier": 2, "daily_min": 1, "daily_max": 3, "sell_item_gems_default": 1}
    PRICE_PER_KG_BY_RARITY = {"common": 10, "uncommon": 30, "rare": 120, "epic": 500}

# Thứ tự & tiêu đề bậc
RARITY_ORDER  = ["trash", "common", "uncommon", "rare", "epic", "legendary", "mythical", "unreal"]
RARITY_TITLE  = {"trash": "🗑️ Trash", "common": "⚪ Common", "uncommon": "🟢 Uncommon", "rare": "🔵 Rare", "epic": "🔶 Epic", "legendary": "🏆 Legendary", "mythical": "🔮 Mythical", "unreal": "🛸 Unreal"}

# Bảng giá theo bậc (chỉnh ở đây) — use PRICE_PER_KG_BY_RARITY if present in config
RARITY_PRICES: Dict[str, int] = {
    "trash": 5,
    "common": 10,
    "uncommon": 30,
    "rare": 120,
    "epic": 500,
    "legendary": 2000,
    "mythical": 10000,
    "unreal": 100000,
}



EMBED_COLOR = 0x2ECC71  # xanh lá


class ShopView(View):
    def __init__(self, ctx, cog):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.cog = cog
        self.message = None

    @discord.ui.select(
        placeholder="🔻 Chọn danh mục cửa hàng...",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label="Cần câu (Rods)", description="Nâng cấp cần câu để câu cá xịn hơn", emoji="🎣", value="rods"),
            discord.SelectOption(label="Trứng Pet (Eggs)", description="Mua trứng để ấp pet", emoji="🥚", value="eggs"),
            discord.SelectOption(label="Vật phẩm (Items)", description="Mua các vật phẩm hỗ trợ", emoji="🎒", value="items"),
        ]
    )
    async def callback(self, interaction: discord.Interaction, select: Select):
        # Không dùng defer ở đây để có thể dùng response.send_message(ephemeral=True)
        val = select.values[0]
        
        if val == "rods":
            await self.cog.rods(self.ctx, interaction)
        elif val == "eggs":
            egg_cog = self.ctx.bot.get_cog('Pet')
            if egg_cog:
                await egg_cog.eggshop(self.ctx, interaction)
            else:
                await interaction.response.send_message("❌ Hệ thống trứng chưa được cấu hình.", ephemeral=True)
        elif val == "items":
            await self.cog.items_shop(self.ctx, interaction)

    async def on_timeout(self):
        if self.message:
            for child in self.children:
                child.disabled = True
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

class EconomyCog(commands.Cog, name="Economy"):
    """Cơ chế ví tiền & bán cá + SHOP cần câu (logic bán/rod ở đây, DataManager chỉ CRUD)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------- Helpers ----------
    def _sum_bucket(self, bucket: Dict[str, int]) -> int:
        return sum(bucket.values()) if bucket else 0

    def _normalize_inv(self, inv: Dict[str, Dict[str, int]]) -> Dict[str, Dict[str, int]]:
        """Đảm bảo luôn có đủ 4 bậc trong inventory (common/uncommon/rare/epic)."""
        return {
            "common": dict(inv.get("common", {})),
            "uncommon": dict(inv.get("uncommon", {})),
            "rare": dict(inv.get("rare", {})),
            "epic": dict(inv.get("epic", {})),
            "legendary": dict(inv.get("legendary", {})),
            "mythical": dict(inv.get("mythical", {})),
            "unreal": dict(inv.get("unreal", {})),
        }

    def _clean_zero(self, bucket: Dict[str, int]) -> Dict[str, int]:
        """Xoá item có số lượng 0."""
        return {k: v for k, v in bucket.items() if v > 0}

    # ---------- Commands: Wallet ----------
    @commands.hybrid_command(name="bal", aliases=["balance", "money"], help="Xem số tiền: /bal [@user]")
    @commands.cooldown(1, 10, commands.BucketType.user)  # ⏱️ 10 giây / người dùng
    async def balance(self, ctx: commands.Context, member: discord.Member | None = None):
        user = member or ctx.author
        if not hasattr(self.bot, "data"):
            await ctx.send("❌ Chưa cấu hình DataManager (bot.data).")
            return
        money = self.bot.data.get_balance(user.id)
        embed = discord.Embed(
            title=f"💰 Số dư của {user.display_name}",
            description=f"**{money:,}** coins",
            color=EMBED_COLOR,
        )
        # show gems if available
        try:
            gems = self.bot.data.get_gems(user.id)
            embed.add_field(name="💎 Gems", value=f"**{gems}**", inline=True)
        except Exception:
            pass
        if user.avatar:
            embed.set_thumbnail(url=user.avatar.url)
        await ctx.send(embed=embed)


    # ---------- Commands: SELL ----------
    @commands.hybrid_command(
        name="sell",
        help="Bán cá/item: /sell <rarity|item|all> [amount]. VD: /sell common all",
    )
    @commands.cooldown(1, 10, commands.BucketType.user)  # ⏱️ 10 giây / người dùng
    async def sell(self, ctx: commands.Context, arg1: str = None, arg2: str = None, arg3: str = None):
        """Unified sell command supporting:
           - `zsell <rarity> <amount|all>`
           - `zsell all` -> sells everything (alias for sellall)
           - `zsell item <id> <amount|all>` -> sells items
        """
        args = [x for x in [arg1, arg2, arg3] if x is not None]
        if not hasattr(self.bot, "data"):
            await ctx.send("❌ Chưa cấu hình DataManager (bot.data).")
            return
        if not args:
            await ctx.send("❗ Dùng: `/sell <common|uncommon|rare> <số lượng|all>` hoặc `/sell all` hoặc `/sell item <id> <số lượng|all>`")
            return

        raw_key = args[0]
        key = raw_key.lower()
        # sell all
        if key == "all":
            return await self.sellall(ctx)
        # If the argument looks like a fish-id (4 alnum), delegate to sellfish
        if isinstance(raw_key, str) and len(raw_key) == 4 and raw_key.isalnum():
            # call sell by id
            return await self.sellfish(ctx, fish_id=raw_key)
        # sell item
        if key == "item":
            if len(args) < 2:
                await ctx.send("❗ Dùng: `/sell item <item_id> <số lượng|all>`")
                return
            item_id = args[1]
            amount = args[2] if len(args) > 2 else None
            return await self.sellitem(ctx, item_id, amount)

        # Otherwise treat as rarity sale
        r = key
        amount = args[1] if len(args) > 1 else None
        if r not in RARITY_ORDER:
            await ctx.send("❌ Bậc không hợp lệ. Dùng các bậc: " + ", ".join(RARITY_ORDER))
            return

        if amount is None:
            await ctx.send("❗ Dùng: `/sell <common|uncommon|rare> <số lượng|all>`")
            return

        # Prefer new object-based inventory if present
        try:
            fish_objs = self.bot.data.get_fish_objects(ctx.author.id)
        except Exception:
            fish_objs = []

        if fish_objs:
            # Filter by rarity
            avail = [f for f in fish_objs if f.get('rarity') == r]
            current_total = len(avail)
            if current_total <= 0:
                await ctx.send("📦 Không có cá trong bậc này để bán.")
                return
            if amount.lower() == 'all':
                to_sell = current_total
            else:
                try:
                    to_sell = max(1, int(amount))
                except Exception:
                    await ctx.send("❌ Số lượng không hợp lệ. Dùng số nguyên hoặc `all`.")
                    return
            # Sell highest value first
            avail_sorted = sorted(avail, key=lambda x: int(x.get('sell_price', 0)), reverse=True)
            sel = avail_sorted[:to_sell]
            if not sel:
                await ctx.send("😿 Không bán được con nào.")
                return

            earned = 0
            sold_ids = []
            for f in sel:
                earned += int(f.get('sell_price', 0))
                sold_ids.append(f.get('id'))
            # Remove sold fishes
            for fid in sold_ids:
                try:
                    await self.bot.data.remove_fish_by_id(ctx.author.id, fid)
                except Exception:
                    pass
            new_bal = await self.bot.data.add_money(ctx.author.id, earned)

            # Gems
            gems_awarded = 0
            try:
                gp = GEM_SETTINGS.get('gem_per_rarity', {}) if isinstance(GEM_SETTINGS, dict) else {}
                gems_awarded = sum(int(gp.get(r, 0)) for _ in sel)
                if gems_awarded > 0 and hasattr(self.bot, 'data'):
                    await self.bot.data.add_gems(ctx.author.id, gems_awarded)
            except Exception:
                gems_awarded = 0

            # Build response
            lines = [f"- {f.get('name')} ({f.get('weight')}kg) → **{int(f.get('sell_price')):,}** coins" for f in sel]
            desc = f"Đã bán **{len(sel)}** con {r} và nhận **{earned:,}** coins."
            if gems_awarded:
                desc += f"\n💎 Gems: **{gems_awarded}**"
            desc += "\n\n" + "\n".join(lines)
            await ctx.send(embed=discord.Embed(title="🏷️ Bán cá thành công", description=desc, color=EMBED_COLOR))
            return

        # Fallback: legacy inventory model (counts)
        price_per = int(RARITY_PRICES.get(r, 0))
        if price_per <= 0:
            await ctx.send("❌ Bậc này chưa có giá hoặc giá = 0.")
            return

        inv = self._normalize_inv(self.bot.data.get_inventory(ctx.author.id))
        try:
            shiny_inv = self._normalize_inv(self.bot.data.get_shiny_inventory(ctx.author.id))
        except Exception:
            shiny_inv = {"common": {}, "uncommon": {}, "rare": {}, "epic": {}}
        bucket = dict(inv.get(r, {}))
        shiny_bucket = dict(shiny_inv.get(r, {}))
        current_total = self._sum_bucket(bucket) + self._sum_bucket(shiny_bucket)
        if current_total <= 0:
            await ctx.send("📦 Không có cá trong bậc này để bán.")
            return

        if amount.lower() == "all":
            to_sell = current_total
            sell_all_mode = True
        else:
            try:
                to_sell = max(1, int(amount))
                sell_all_mode = False
            except Exception:
                await ctx.send("❌ Số lượng không hợp lệ. Dùng số nguyên hoặc `all`.")
                return

        sold = 0
        breakdown: Dict[str, tuple[int, int]] = {}
        names = sorted(set(list(bucket.keys()) + list(shiny_bucket.keys())))
        for name in names:
            normal_cnt = int(bucket.get(name, 0))
            shiny_cnt = int(shiny_bucket.get(name, 0))
            avail = normal_cnt + shiny_cnt
            if avail <= 0:
                continue
            if sell_all_mode:
                take = avail
            else:
                remain = to_sell - sold
                if remain <= 0:
                    break
                take = min(avail, remain)

            take_normal = min(normal_cnt, take)
            take_shiny = max(0, take - take_normal)

            bucket[name] = normal_cnt - take_normal
            shiny_bucket[name] = shiny_cnt - take_shiny
            breakdown[name] = (take_normal, take_shiny)
            sold += (take_normal + take_shiny)

        if sold <= 0:
            await ctx.send("😿 Không bán được con nào.")
            return

        inv[r] = self._clean_zero(bucket)
        shiny_inv[r] = self._clean_zero(shiny_bucket)
        await self.bot.data.set_inventory(ctx.author.id, inv)
        await self.bot.data.set_shiny_inventory(ctx.author.id, shiny_inv)

        SHINY_MULT = 20
        earned = 0
        for name, (n_sold, s_sold) in breakdown.items():
            earned += n_sold * price_per
            earned += s_sold * price_per * SHINY_MULT
        new_bal = await self.bot.data.add_money(ctx.author.id, earned)

        gems_awarded = 0
        try:
            gp = GEM_SETTINGS.get('gem_per_rarity', {}) if isinstance(GEM_SETTINGS, dict) else {}
            gems_awarded = sold * int(gp.get(r, 0))
            if gems_awarded > 0 and hasattr(self.bot, 'data'):
                new_gems = await self.bot.data.add_gems(ctx.author.id, gems_awarded)
        except Exception:
            gems_awarded = 0

        def fmt_breakdown(bd: Dict[str, tuple[int, int]]) -> str:
            parts = []
            for nm in sorted(bd.keys()):
                n_s, s_s = bd[nm]
                if s_s > 0:
                    parts.append(f"✨{nm} ×{s_s}")
                if n_s > 0:
                    parts.append(f"{nm} ×{n_s}")
            return ", ".join(parts)

        details = fmt_breakdown(breakdown) or f"(Tổng {sold})"
        embed = discord.Embed(
            title="💱 Bán cá thành công",
            description=(
                f"Bậc: **{r.capitalize()}**\n"
                f"Đã bán: **{sold}** con\n"
                f"Thu được: **{earned:,}** coins\n"
                f"Số dư mới: **{new_bal:,}** coins"
            ),
            color=EMBED_COLOR
        )
        embed.add_field(name="Chi tiết", value=details, inline=False)
        if gems_awarded > 0:
            embed.add_field(name="💎 Gems nhận được", value=f"**{gems_awarded}**", inline=True)
        await ctx.send(embed=embed)
    @commands.hybrid_command(name="sellall", help="Bán toàn bộ cá trong kho (những bậc có giá > 0).")
    @commands.cooldown(1, 20, commands.BucketType.user)  # ⏱️ 20 giây / người dùng
    async def sellall(self, ctx: commands.Context):
        """Bán toàn bộ mọi bậc có giá > 0; các bậc không có giá sẽ được giữ nguyên."""
        if not hasattr(self.bot, "data"):
            await ctx.send("❌ Chưa cấu hình DataManager (bot.data).")
            return

        # Prefer object model if available
        try:
            all_fish = self.bot.data.get_fish_objects(ctx.author.id)
        except Exception:
            all_fish = []

        try:
            aquarium_data = self.bot.data.get_aquarium(ctx.author.id)
            aquarium_ids = set(aquarium_data.keys())
        except Exception:
            aquarium_ids = set()

        sold_total = 0
        earned_total = 0
        breakdown_rarity: Dict[str, int] = {}
        sold_ids = []

        if all_fish:
            # Group by rarity and sell fishes but KEEP top-3 highest sell_price per rarity
            for r in RARITY_ORDER:
                group = [f for f in all_fish if f.get('rarity') == r]
                if not group:
                    continue
                # Filter sellable fishes (sell_price > 0) AND NOT IN AQUARIUM
                sellable = [f for f in group if int(f.get('sell_price', 0)) > 0 and f.get('id') not in aquarium_ids]
                if not sellable:
                    continue
                # Sell ALL sellable fish (no top 3 protection)
                to_sell = sellable
                sold_count = len(to_sell)
                earned_total += sum(int(f.get('sell_price', 0)) for f in to_sell)
                sold_total += sold_count
                breakdown_rarity[r] = sold_count
                sold_ids.extend([f.get('id') for f in to_sell])
            if sold_total <= 0:
                await ctx.send("📦 Không có gì để bán (hoặc tất cả cá đang ở trong thủy cung).")
                return
            # Remove sold fish
            for fid in sold_ids:
                try:
                    await self.bot.data.remove_fish_by_id(ctx.author.id, fid)
                except Exception:
                    pass
            new_bal = await self.bot.data.add_money(ctx.author.id, earned_total)
            # Gems
            gems_awarded = 0
            try:
                gp = GEM_SETTINGS.get('gem_per_rarity', {}) if isinstance(GEM_SETTINGS, dict) else {}
                for r, cnt in breakdown_rarity.items():
                    gems_awarded += cnt * int(gp.get(r, 0))
                if gems_awarded > 0 and hasattr(self.bot, 'data'):
                    await self.bot.data.add_gems(ctx.author.id, gems_awarded)
            except Exception:
                gems_awarded = 0

            # Only include rarities with sold counts
            lines = [f"- {RARITY_TITLE[r]}: **{cnt}** con" for r, cnt in breakdown_rarity.items()]
            embed = discord.Embed(title="🏷️ Bán toàn bộ kho", description="\n".join(lines) + f"\n\nTổng thu: **{earned_total:,}** coins", color=EMBED_COLOR)
            if gems_awarded:
                embed.add_field(name="💎 Gems", value=f"**{gems_awarded}**", inline=True)
            await ctx.send(embed=embed)
            return

        # Fallback to legacy model
        inv = self._normalize_inv(self.bot.data.get_inventory(ctx.author.id))

        new_inv = {"common": {}, "uncommon": {}, "rare": {}, "epic": {}}
        new_shiny_inv = {"common": {}, "uncommon": {}, "rare": {}, "epic": {}}  # will write back remaining shinies

        # Lấy cả shiny inventory
        try:
            shiny_inv = self._normalize_inv(self.bot.data.get_shiny_inventory(ctx.author.id))
        except Exception:
            shiny_inv = {"common": {}, "uncommon": {}, "rare": {}, "epic": {}}

        sold_total = 0
        earned_total = 0
        breakdown_rarity = {}

        for r in RARITY_ORDER:
            bucket = inv.get(r, {})
            s_bucket = shiny_inv.get(r, {})
            count_r = self._sum_bucket(bucket) + self._sum_bucket(s_bucket)
            if count_r <= 0:
                continue

            price_per = int(RARITY_PRICES.get(r, 0))
            if price_per <= 0:
                # Không có giá → giữ nguyên kho bậc này (kể cả shiny)
                new_inv[r] = dict(bucket)
                new_shiny_inv[r] = dict(s_bucket)
                continue

            # Keep up to 3 highest-value fishes (prefers shinies as they are worth more)
            keep_limit = 3
            if count_r <= keep_limit:
                # nothing to sell
                new_inv[r] = dict(bucket)
                new_shiny_inv[r] = dict(s_bucket)
                continue

            # Build list of units (unit_price, name, is_shiny)
            units = []
            for name, cnt in bucket.items():
                for _ in range(int(cnt)):
                    units.append((price_per, name, False))
            for name, cnt in s_bucket.items():
                for _ in range(int(cnt)):
                    units.append((price_per * 20, name, True))
            # Sort ascending → cheapest first; we'll sell cheapest to preserve top values
            units.sort(key=lambda x: x[0])
            to_sell = len(units) - keep_limit
            sold_count = 0
            earned_here = 0
            sold_names_normal = {}
            sold_names_shiny = {}
            # take first to_sell units
            for i in range(to_sell):
                up, nm, is_sh = units[i]
                earned_here += int(up)
                sold_count += 1
                if is_sh:
                    sold_names_shiny[nm] = sold_names_shiny.get(nm, 0) + 1
                else:
                    sold_names_normal[nm] = sold_names_normal.get(nm, 0) + 1

            # subtract sold quantities from buckets
            for nm, rem in sold_names_normal.items():
                bucket[nm] = max(0, int(bucket.get(nm, 0)) - rem)
            for nm, rem in sold_names_shiny.items():
                s_bucket[nm] = max(0, int(s_bucket.get(nm, 0)) - rem)

            sold_total += sold_count
            earned_total += earned_here
            breakdown_rarity[r] = sold_count
            # write back remaining buckets
            new_inv[r] = self._clean_zero(bucket)
            new_shiny_inv[r] = self._clean_zero(s_bucket)

        if sold_total <= 0:
            await ctx.send("📦 Kho trống hoặc các bậc có giá = 0, không có gì để bán.")
            return

        # Ghi inventory mới & cộng tiền (bao gồm cập nhật shiny inventory)
        await self.bot.data.set_inventory(ctx.author.id, new_inv)
        await self.bot.data.set_shiny_inventory(ctx.author.id, new_shiny_inv)
        new_bal = await self.bot.data.add_money(ctx.author.id, earned_total)

        lines = [f"- {RARITY_TITLE[r]}: **{cnt}** con" for r, cnt in breakdown_rarity.items()]
        embed = discord.Embed(
            title="🧹 Bán toàn bộ kho",
            description="\n".join(lines) if lines else "(Không rõ bậc)",
            color=EMBED_COLOR
        )
        embed.add_field(name="Tổng cá đã bán", value=f"**{sold_total}**", inline=True)
        embed.add_field(name="Tổng thu", value=f"**{earned_total:,}** coins", inline=True)
        embed.add_field(name="Số dư mới", value=f"**{new_bal:,}** coins", inline=True)
        await ctx.send(embed=embed)

    # ---------- Commands: RODS SHOP ----------
    @commands.hybrid_command(name="pay", aliases=["transfer", "give"], help="Chuyển tiền: /pay @user <số lượng|all>")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def pay(self, ctx: commands.Context, member: discord.Member | None = None, amount: str | None = None):
        if not hasattr(self.bot, "data"):
            await ctx.send("❌ Chưa cấu hình DataManager (bot.data).")
            return
        if member is None or amount is None:
            await ctx.send("❗ Dùng: `/pay @user <số lượng|all>`")
            return
        if member.bot:
            await ctx.send("❌ Không thể chuyển cho bot.")
            return
        if member.id == ctx.author.id:
            await ctx.send("❌ Không thể chuyển tiền cho chính bạn.")
            return

        # Parse amount
        bal = self.bot.data.get_balance(ctx.author.id)
        if amount.lower() == "all":
            amt = bal
        else:
            try:
                amt = int(amount)
            except Exception:
                await ctx.send("❌ Số lượng không hợp lệ. Dùng số nguyên dương hoặc `all`.")
                return

        if amt <= 0:
            await ctx.send("❌ Số lượng phải lớn hơn 0.")
            return
        if bal < amt:
            await ctx.send(f"💸 Bạn không đủ tiền. Số dư: **{bal:,}** coins.")
            return

        # Thực hiện chuyển tiền (trừ trước, rồi cộng)
        sender_new_bal = await self.bot.data.add_money(ctx.author.id, -amt)
        recipient_new_bal = await self.bot.data.add_money(member.id, amt)

        embed = discord.Embed(
            title="💸 Chuyển tiền thành công",
            description=f"Đã chuyển **{amt:,}** coins cho **{member.display_name}**",
            color=EMBED_COLOR
        )
        embed.add_field(name="Số dư bạn", value=f"**{sender_new_bal:,}** coins", inline=True)
        embed.add_field(name=f"Số dư {member.display_name}", value=f"**{recipient_new_bal:,}** coins", inline=True)
        await ctx.send(embed=embed)

    async def rods(self, ctx: commands.Context, interaction: discord.Interaction = None):
        """Internal: show rods shop (was a command before)."""
        if not hasattr(self.bot, "data"):
            await ctx.send("❌ Chưa cấu hình DataManager (bot.data).")
            return

        try:
            cur = self.bot.data.get_rod_level(ctx.author.id)
            max_owned = self.bot.data.get_max_rod_level(ctx.author.id)
        except Exception:
            await ctx.send("❌ DataManager chưa hỗ trợ rod_level / max_rod_level. Hãy thêm get_rod_level/get_max_rod_level.")
            return

        lines = []
        for lv in range(1, MAX_ROD_LEVEL + 1):
            t = ROD_TIERS[lv]
            parts = []
            if int(t.get('cost', 0)) > 0:
                parts.append(f"{int(t.get('cost')):,} coins")
            if int(t.get('gem_cost', 0)) > 0:
                parts.append(f"{int(t.get('gem_cost'))} gems")
            cost = "Miễn phí" if not parts else " / ".join(parts)
            # Ký hiệu trạng thái theo sở hữu & trạng thái
            if lv == cur:
                mark = "⭐"  # đang dùng
            elif lv <= max_owned:
                mark = "✅"  # đã sở hữu
            elif lv == max_owned + 1:
                mark = "🛒"  # cấp tiếp theo có thể mua
            else:
                mark = "🔒"  # khóa (phải nâng từng cấp)
            rod_luck = float(t.get('luck', 0.0))
            lines.append(
                f"{mark} **Lv.{lv} — {t['name']}** | Giá: **{cost}** | "
                f"Luck (từ cần): **+{rod_luck:.2f}** | Độ khó: **+{t['len_add']} ký tự**, **-{t['timeout_sub']}s** thời gian"
            )

        embed = discord.Embed(
            title=f"🎣 Cửa hàng Cần Câu — Cấp hiện tại: Lv.{cur} ({ROD_TIERS[cur]['name']})",
            description="\n".join(lines),
            color=0x3498DB
        )
        embed.set_footer(text="Nâng cấp dùng: /buy rod")
        if interaction:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await ctx.send(embed=embed)

    # Đã loại bỏ lệnh rodupgrade, giữ lại hàm để buy rod sử dụng nội bộ
    async def rodupgrade(self, ctx: commands.Context):
        if not hasattr(self.bot, "data"):
            await ctx.send("❌ Chưa cấu hình DataManager (bot.data).")
            return

        try:
            max_owned = self.bot.data.get_max_rod_level(ctx.author.id)
        except Exception:
            await ctx.send("❌ DataManager chưa hỗ trợ max_rod_level. Hãy thêm get_max_rod_level/set_max_rod_level.")
            return

        if max_owned >= MAX_ROD_LEVEL:
            await ctx.send("🥇 Bạn đã sở hữu **cấp cao nhất**. Không thể mua thêm.")
            return

        nxt = max_owned + 1
        tier = ROD_TIERS[nxt]
        gem_cost = int(tier.get('gem_cost', 0))
        coin_cost = int(tier.get('cost', 0))

        # If this tier requires gems, use gems; otherwise use coins
        bought_with = "coins"
        if gem_cost > 0:
            try:
                gems = self.bot.data.get_gems(ctx.author.id)
            except Exception:
                gems = 0
            if gems < gem_cost:
                await ctx.send(f"💎 Bạn cần **{gem_cost:,}** gems để mua Lv.{nxt} ({tier['name']}), bạn có **{gems}** gems.")
                return
            await self.bot.data.add_gems(ctx.author.id, -gem_cost)
            bought_with = f"{gem_cost} gems"
        else:
            bal = self.bot.data.get_balance(ctx.author.id)
            if bal < coin_cost:
                await ctx.send(f"💸 Thiếu tiền! Cần **{coin_cost:,}** coins để mua Lv.{nxt} ({tier['name']}), bạn còn **{bal:,}** coins.")
                return
            await self.bot.data.add_money(ctx.author.id, -coin_cost)

        # Cập nhật sở hữu + trang bị
        await self.bot.data.set_max_rod_level(ctx.author.id, nxt)
        await self.bot.data.set_rod_level(ctx.author.id, nxt)

        rod_luck = float(tier.get('luck', 0.0))
        embed = discord.Embed(
            title="🛠️ Nâng cấp cần câu thành công!",
            description=(
                f"Cấp mới: **Lv.{nxt} — {tier['name']}**\n"
                f"Thanh toán: **{bought_with}**\n"
                f"Luck (từ cần): **+{rod_luck:.2f}**\n"
                f"Tăng độ khó: **+{tier['len_add']} ký tự**, **-{tier['timeout_sub']}s** thời gian"
            ),
            color=0x1ABC9C
        )
        await ctx.send(embed=embed)

    async def buyitem(self, ctx: commands.Context, item_id: str | None = None, amount: str | None = "1"):
        """Mua item chỉ bằng gems: /buyitem <id> <số lượng=1>"""
        if not hasattr(self.bot, "data"):
            await ctx.send("❌ Chưa cấu hình DataManager (bot.data).")
            return
        if not item_id:
            await ctx.send("❗ Dùng: `/buyitem <id> <số lượng=1>`")
            return
        try:
            from game_items import ITEMS as GAME_ITEMS
        except Exception:
            GAME_ITEMS = {}
        itm = GAME_ITEMS.get(item_id)
        if not itm:
            await ctx.send("❌ Item không tồn tại.")
            return
        try:
            n = int(amount)
            n = max(1, n)
        except Exception:
            await ctx.send("❌ Số lượng không hợp lệ.")
            return
        try:
            cur_gems = self.bot.data.get_gems(ctx.author.id)
        except Exception:
            cur_gems = 0
        price_g = int(itm.get('buy_gems', 0))
        if price_g <= 0:
            await ctx.send("❌ Item này không có giá mua bằng gems.")
            return
        total = price_g * n
        if cur_gems < total:
            await ctx.send(f"💎 Bạn không đủ gems. Cần **{total}**, bạn có **{cur_gems}**.")
            return
        await self.bot.data.add_gems(ctx.author.id, -total)
        for _ in range(n):
            await self.bot.data.add_item(ctx.author.id, item_id)
        await ctx.send(f"✅ Đã mua `{item_id}` ×{n} bằng **gems**.")

    @commands.hybrid_command(name="buy", help="Mua: /buy egg <tier> | /buy rod | /buy item <id> <qty>")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def buy(self, ctx: commands.Context, arg1: str = None, arg2: str = None, arg3: str = None):
        args = [x for x in [arg1, arg2, arg3] if x is not None]
        if not args:
            await ctx.send("❗ Dùng: `/buy egg <tier>` hoặc `/buy rod` hoặc `/buy item <id> <số lượng>`")
            return
        sub = args[0].lower()
        if sub in ("egg", "eggs"):
            tier = None
            if len(args) > 1:
                try:
                    tier = int(args[1])
                except Exception:
                    tier = None
            egg_cog = self.bot.get_cog('Pet')
            if egg_cog:
                return await egg_cog.buyegg(ctx, tier)
            else:
                await ctx.send("❌ Hệ thống trứng chưa được cấu hình.")
                return
        if sub in ("rod", "rodupgrade"):
            return await self.rodupgrade(ctx)
        if sub in ("item", "items"):
            if len(args) < 2:
                await ctx.send("❗ Dùng: `zbuy item <id> <số lượng=1>`")
                return
            item_id = args[1]
            amount = args[2] if len(args) > 2 else "1"
            return await self.buyitem(ctx, item_id, amount)

    async def sellitem(self, ctx: commands.Context, item_id: str | None = None, amount: str | None = None):
        if not hasattr(self.bot, "data"):
            await ctx.send("❌ Chưa cấu hình DataManager (bot.data).")
            return
        if not item_id or not amount:
            await ctx.send("❗ Dùng: `/sellitem <item_id> <số lượng|all>`")
            return


        try:
            from game_items import ITEMS as GAME_ITEMS
        except Exception:
            GAME_ITEMS = {}
        if item_id not in GAME_ITEMS:
            await ctx.send("❌ Item không tồn tại.")
            return
        itm = GAME_ITEMS[item_id]
        if not itm.get('sellable', False):
            await ctx.send("❌ Item này không thể bán.")
            return
        user_items = self.bot.data.get_items(ctx.author.id)
        cur = int(user_items.get(item_id, 0))
        if cur <= 0:
            await ctx.send("📦 Bạn không có item này để bán.")
            return
        if amount.lower() == 'all':
            to_sell = cur
        else:
            try:
                to_sell = max(1, int(amount))
            except Exception:
                await ctx.send("❌ Số lượng không hợp lệ.")
                return
        if to_sell > cur:
            await ctx.send(f"❌ Bạn chỉ có **{cur}** cái.")
            return

        # Tính gem sẽ nhận và yêu cầu xác nhận
        gem_each = int(itm.get('sell_gems', GEM_SETTINGS.get('sell_item_gems_default', 1)))
        total_gems = gem_each * to_sell
        confirm_embed = discord.Embed(
            title="❗ Xác nhận bán item",
            description=(
                f"Bạn sắp bán **`{item_id}`** ×**{to_sell}** và nhận **{total_gems}** gems.\n"
                "Nhấn ✅ để xác nhận hoặc ❌ để huỷ (30s)."
            ),
            color=EMBED_COLOR
        )
        cm = await ctx.send(embed=confirm_embed)
        for e in ("✅", "❌"):
            try:
                await cm.add_reaction(e)
            except Exception:
                pass

        def _check(reaction, user):
            return user.id == ctx.author.id and reaction.message.id == cm.id and str(reaction.emoji) in ("✅", "❌")

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=_check)
        except Exception:
            try:
                await cm.clear_reactions()
            except Exception:
                pass
            await ctx.send("⏳ Hết thời gian xác nhận — giao dịch đã bị huỷ.")
            return

        if str(reaction.emoji) != "✅":
            try:
                await cm.delete()
            except Exception:
                pass
            await ctx.send("❌ Giao dịch đã bị huỷ.")
            return

        # Thực hiện bán: trừ item và cộng gems
        ok = await self.bot.data.remove_item(ctx.author.id, item_id, to_sell)
        if not ok:
            await ctx.send("❌ Không thể hoàn tất giao dịch.")
            return
        new_gems = 0
        try:
            new_gems = await self.bot.data.add_gems(ctx.author.id, total_gems)
        except Exception:
            pass
        try:
            await cm.clear_reactions()
        except Exception:
            pass
        embed = discord.Embed(title="🏷️ Bán item thành công", description=(f"Đã bán `{item_id}` ×{to_sell}"), color=EMBED_COLOR)
        embed.add_field(name="Gems nhận được", value=f"**{total_gems}** (tổng: **{new_gems}**)", inline=True)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="sellfish", aliases=["sellid","sell_by_id"], help="Bán 1 con cá theo id: /sellfish <id>")
    async def sellfish(self, ctx: commands.Context, fish_id: str | None = None):
        if not hasattr(self.bot, "data"):
            await ctx.send("❌ Chưa cấu hình DataManager (bot.data).")
            return
        if not fish_id:
            await ctx.send("❗ Dùng: `/sellfish <fish-id>` — tìm id bằng `/fishes`")
            return
        try:
            fish_objs = self.bot.data.get_fish_objects(ctx.author.id)
        except Exception:
            fish_objs = []
        found = None
        for f in fish_objs:
            if f.get('id') == fish_id:
                found = f
                break
        if not found:
            await ctx.send("❌ Không tìm thấy fish với id đó trong kho của bạn.")
            return
        price = int(found.get('sell_price', 0))
        if price <= 0:
            await ctx.send("❌ Con cá này không có giá bán (sell_price = 0).")
            return
        # Confirm
        confirm = discord.Embed(title="❗ Xác nhận bán cá", description=(f"Bạn sắp bán **{found.get('name')}** — **{price:,}** coins. Nhấn ✅ để xác nhận hoặc ❌ để huỷ (30s)."), color=EMBED_COLOR)
        cm = await ctx.send(embed=confirm)
        for e in ("✅","❌"):
            try:
                await cm.add_reaction(e)
            except Exception:
                pass

        def _check(reaction, user):
            return user.id == ctx.author.id and reaction.message.id == cm.id and str(reaction.emoji) in ("✅","❌")

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=_check)
        except Exception:
            try:
                await cm.clear_reactions()
            except Exception:
                pass
            await ctx.send("⏳ Hết thời gian xác nhận — giao dịch đã bị huỷ.")
            return

        if str(reaction.emoji) != "✅":
            try:
                await cm.delete()
            except Exception:
                pass
            await ctx.send("❌ Giao dịch đã bị huỷ.")
            return

        # Do sell
        try:
            ok = await self.bot.data.remove_fish_by_id(ctx.author.id, fish_id)
        except Exception:
            ok = False
        if not ok:
            await ctx.send("❌ Không thể bán con cá này (lỗi hệ thống).")
            return
        new_bal = await self.bot.data.add_money(ctx.author.id, price)
        gems_awarded = 0
        try:
            gp = GEM_SETTINGS.get('gem_per_rarity', {}) if isinstance(GEM_SETTINGS, dict) else {}
            gems_awarded = int(gp.get(found.get('rarity'), 0))
            if gems_awarded > 0:
                await self.bot.data.add_gems(ctx.author.id, gems_awarded)
        except Exception:
            gems_awarded = 0
        # Response
        desc = f"Đã bán **{found.get('name')}** và nhận **{price:,}** coins. Số dư mới: **{new_bal:,}**"
        if gems_awarded:
            desc += f"\n💎 Gems: **{gems_awarded}**"
        await ctx.send(embed=discord.Embed(title="🏷️ Bán cá thành công", description=desc, color=EMBED_COLOR))

    @commands.hybrid_command(name="daily", aliases=["claim"], help="Nhận quà hằng ngày (coins + gems)")
    async def daily(self, ctx: commands.Context):
        if not hasattr(self.bot, "data"):
            await ctx.send("❌ Chưa cấu hình DataManager (bot.data).")
            return
        now = int(time.time())
        last = self.bot.data.get_last_daily(ctx.author.id)
        if now - int(last) < 86400:
            remaining = 86400 - (now - int(last))
            hrs = remaining // 3600
            mins = (remaining % 3600) // 60
            await ctx.send(f"⏳ Bạn đã nhận daily. Hãy đợi {hrs}h{mins}m để nhận lại.")
            return
        coins = random.randint(100, 400)
        gems = random.randint(int(GEM_SETTINGS.get('daily_min', 1)), int(GEM_SETTINGS.get('daily_max', 3)))
        await self.bot.data.add_money(ctx.author.id, coins)
        await self.bot.data.add_gems(ctx.author.id, gems)
        await self.bot.data.set_last_daily(ctx.author.id, now)
        embed = discord.Embed(title="🎁 Daily nhận thành công!", description=(f"Bạn nhận được **{coins:,}** coins và **{gems}** gems."), color=0xF39C12)
        await ctx.send(embed=embed)

    async def items_shop(self, ctx: commands.Context, interaction: discord.Interaction = None):
        """Hiển thị shop vật phẩm."""
        try:
            from game_items import ITEMS as GAME_ITEMS
        except Exception:
            GAME_ITEMS = {}
        
        lines = []
        for iid, info in GAME_ITEMS.items():
            # Chỉ hiện item có thể mua (có buy_gems)
            buy_g = info.get('buy_gems')
            if not buy_g:
                continue
            
            name = info.get('name', iid)
            emoji = info.get('emoji', '')
            desc = info.get('desc', 'Không có mô tả')
            
            lines.append(f"> {emoji} **{name}** (`{iid}`)\n> 📝 *{desc}*\n> 💎 Giá: **{buy_g}** gems")
            
        if not lines:
            await ctx.send("❌ Hiện không có vật phẩm nào được bán.")
            return
            
        embed = discord.Embed(
            title="🎒 Cửa Hàng Vật Phẩm",
            description="Sử dụng lệnh `/buy item <id> <số lượng>` để mua.\n\n" + "\n\n".join(lines),
            color=0x95A5A6
        )
        if interaction:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await ctx.send(embed=embed)

    @commands.hybrid_command(name="shop", help="Mở cửa hàng (chọn bằng menu)")
    async def shop(self, ctx: commands.Context):
        embed = discord.Embed(
            title="🏪 Trung Tâm Mua Sắm",
            description="Chào mừng bạn đến với cửa hàng! Hãy chọn danh mục bên dưới để xem chi tiết.",
            color=0x9B59B6
        )
        embed.add_field(name="🎣 Cần câu", value="Nâng cấp công cụ câu cá", inline=True)
        embed.add_field(name="🥚 Trứng Pet", value="Mua trứng ấp thú cưng", inline=True)
        embed.add_field(name="🎒 Vật phẩm", value="Các món đồ hỗ trợ", inline=True)
        embed.set_footer(text="Chọn danh mục từ menu bên dưới 👇")

        view = ShopView(ctx, self)
        msg = await ctx.send(embed=embed, view=view)
        view.message = msg

    # ---------- Cooldown error handler chung ----------
    @balance.error
    @sell.error
    @sellall.error
    @pay.error
    @daily.error
    @shop.error
    async def economy_errors(self, ctx: commands.Context, error: Exception):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"⏳ Bạn phải chờ **{error.retry_after:.1f}s** trước khi dùng lại lệnh này.",
                delete_after=3
            )
        else:
            raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(EconomyCog(bot))