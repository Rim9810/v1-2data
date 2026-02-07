# cogs/profile.py
from __future__ import annotations
import discord
from discord.ext import commands
from typing import Dict

# ---- Thử import cấu hình cần câu và XP (nếu có) ----
try:
    from game_config import ROD_TIERS, MAX_ROD_LEVEL, BASE_XP_PER_LEVEL
except Exception:
    # Fallback cấu hình mặc định nếu chưa có game_config.py
    ROD_TIERS = {
        1: {"name": "Cần Tre",        "cost": 0,     "bonus": 0, "len_add": 0, "timeout_sub": 0.0},
        2: {"name": "Cần Gỗ",         "cost": 500,   "bonus": 1, "len_add": 2, "timeout_sub": 0.5},
        3: {"name": "Cần Sắt",        "cost": 2000,  "bonus": 2, "len_add": 4, "timeout_sub": 1.0},
        4: {"name": "Cần Carbon",     "cost": 8000,  "bonus": 3, "len_add": 6, "timeout_sub": 1.5},
        5: {"name": "Cần Huyền Thoại","cost": 25000, "bonus": 4, "len_add": 8, "timeout_sub": 2.0},
    }
    MAX_ROD_LEVEL = max(ROD_TIERS)
    BASE_XP_PER_LEVEL = 100

EMBED_COLOR = 0x00ADB5  # xanh teal

RARITY_ORDER = ["trash", "common", "uncommon", "rare", "epic", "legendary", "mythical", "unreal"]
RARITY_TITLE = {"trash": "🗑️ Trash", "common": "⚪ Common", "uncommon": "🟢 Uncommon", "rare": "🔵 Rare", "epic": "🔶 Epic", "legendary": "🏆 Legendary", "mythical": "🔮 Mythical", "unreal": "🛸 Unreal"}

class ProfileCog(commands.Cog, name="Profile"):
    """Hiển thị hồ sơ người chơi."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Helpers
    def _sum_bucket(self, bucket: Dict[str, int]) -> int:
        return sum(bucket.values()) if bucket else 0

    def _sum_all(self, inv: Dict[str, Dict[str, int]]) -> Dict[str, int]:
        return {r: self._sum_bucket(inv.get(r, {})) for r in RARITY_ORDER}

    @commands.hybrid_command(
        name="profile",
        aliases=["me", "stats"],
        help="Hiển thị hồ sơ: /profile [@user] — cá theo bậc, tổng cá, số dư, avatar và cần câu đang dùng."
    )
    async def profile(self, ctx: commands.Context, member: discord.Member | None = None):
        # 1) Chọn đối tượng: mặc định là chính bạn
        target = member or ctx.author

        # 2) Đảm bảo DataManager sẵn sàng
        if not hasattr(self.bot, "data"):
            await ctx.send("❌ Chưa cấu hình DataManager (bot.data).")
            return

        # 3) Lấy inventory, số dư, cấp cần — bao gồm cả shiny
        inv = self.bot.data.get_inventory(target.id)
        shiny = {}
        try:
            shiny = self.bot.data.get_shiny_inventory(target.id)
        except Exception:
            shiny = {"common": {}, "uncommon": {}, "rare": {}, "epic": {}}
        # tính tổng bao gồm cả shiny
        def sum_both(inv_map, shiny_map):
            return {r: self._sum_bucket(inv_map.get(r, {})) + self._sum_bucket(shiny_map.get(r, {})) for r in RARITY_ORDER}
            
        sums = sum_both(inv, shiny)
        # Include fish objects (new model) in totals
        try:
            fish_objs = self.bot.data.get_fish_objects(target.id)
        except Exception:
            fish_objs = []
        total_all = sum(sums.values()) + len(fish_objs)
        balance = self.bot.data.get_balance(target.id)

        # Lấy cấp cần; nếu DataManager chưa có rod_level → mặc định Lv.1
        try:
            rod_level = self.bot.data.get_rod_level(target.id)
        except Exception:
            rod_level = 1
        tier = ROD_TIERS.get(rod_level, ROD_TIERS[1])

        # 4) Tạo nội dung hiển thị
        # Tạo map tên cá -> emoji để hiển thị (dùng cho cả normal & shiny)
        FISH_EMO_MAP: Dict[str, str] = {}
        try:
            from game_config import FISH_POOLS, WEATHER_CONFIG
            for pool in FISH_POOLS.values():
                for f in pool:
                    FISH_EMO_MAP[f.get('name','')] = f.get('emoji','')
            for w in WEATHER_CONFIG.values():
                for f in w.get('special_fish', []):
                    FISH_EMO_MAP[f.get('name','')] = f.get('emoji','')
        except Exception:
            pass

        def fmt_bucket(normal_bucket: Dict[str, int], shiny_bucket: Dict[str, int]) -> str:
            names = set(list(normal_bucket.keys()) + list(shiny_bucket.keys()))
            if not names:
                return "_Trống_"
            parts = []
            for n in sorted(names):
                s = shiny_bucket.get(n, 0)
                g = normal_bucket.get(n, 0)
                em = FISH_EMO_MAP.get(n, "")
                if s > 0:
                    if em:
                        parts.append(f"✨{em} ×{s}")
                    else:
                        parts.append(f"✨{n} ×{s}")
                if g > 0:
                    if em:
                        parts.append(f"{em} ×{g}")
                    else:
                        parts.append(f"{n} ×{g}")
            return ", ".join(parts)

        # 5) Embed
        title = f"👤 Hồ sơ của {target.display_name}"
        subtitle = f"Tổng cá: **{total_all}**"
        embed = discord.Embed(title=title, description=subtitle, color=EMBED_COLOR)

        if target.avatar:
            embed.set_thumbnail(url=target.avatar.url)

        # 💰 Tiền tệ
        embed.add_field(name="💰 Số dư", value=f"**{balance:,}** coins", inline=False)

        # 📈 Cấp & XP
        try:
            lvl = self.bot.data.get_level(target.id)
            xp = self.bot.data.get_xp(target.id)
            need = BASE_XP_PER_LEVEL * lvl
        except Exception:
            lvl = 1
            xp = 0
            need = BASE_XP_PER_LEVEL
        embed.add_field(name="📈 Cấp", value=f"**Lv.{lvl}** — **{xp:,}** XP / **{need:,}** XP", inline=False)

        # 🎣 Cần câu đang dùng (cấp + tên + hiệu ứng)
        rod_luck = float(tier.get('luck', 0.0))
        rod_line = (
            f"**Lv.{rod_level} — {tier['name']}**\n"
            f"- Luck (từ cần): **+{rod_luck:.2f}**\n"
            f"- Tăng độ khó: **+{tier['len_add']} ký tự**, **-{tier['timeout_sub']}s** thời gian"
        )
        embed.add_field(name="🎣 Cần câu đang dùng", value=rod_line, inline=False)

        # Vật phẩm & Cổ vật
        try:
            equipped = self.bot.data.get_equipped_items(target.id)
            items = self.bot.data.get_items(target.id)
        except Exception:
            equipped = []
            items = {}

        # Tải thông tin item để hiển thị emoji nếu có
        try:
            from game_items import ITEMS as GAME_ITEMS
        except Exception:
            GAME_ITEMS = {}
        # Tải thông tin pet
        try:
            from game_pets import PETS as GAME_PETS
        except Exception:
            GAME_PETS = {}

        def _fmt_buffs(buffs: dict) -> str:
            parts = []
            if not buffs:
                return ""
            if buffs.get("luck"):
                parts.append(f"+{float(buffs.get('luck')):.2f} luck")
            if buffs.get("timeout_add"):
                parts.append(f"+{float(buffs.get('timeout_add')):.1f}s")
            if buffs.get("len_sub"):
                parts.append(f"-{int(buffs.get('len_sub'))} kí tự")
            if buffs.get("xp_flat"):
                parts.append(f"+{int(buffs.get('xp_flat'))} XP")
            if buffs.get("rare_pct"):
                parts.append(f"+{float(buffs.get('rare_pct'))*100:.0f}% rare")
            return ", ".join(parts)

        if equipped:
            eq_lines = []
            total_buffs = {"luck": 0.0, "timeout_add": 0.0, "len_sub": 0, "xp_flat": 0, "rare_pct": 0.0}
            for it in equipped:
                gd = GAME_ITEMS.get(it, {})
                em = gd.get("emoji", "")
                display_name = gd.get("name", it)
                buffs = gd.get("buffs", {})
                eq_lines.append(f"{em} {display_name} — { _fmt_buffs(buffs) }" if _fmt_buffs(buffs) else (f"{em} {display_name}" if em else display_name))
                # aggregate
                total_buffs["luck"] += float(buffs.get("luck", 0.0))
                total_buffs["timeout_add"] += float(buffs.get("timeout_add", 0.0))
                total_buffs["len_sub"] += int(buffs.get("len_sub", 0))
                total_buffs["xp_flat"] += int(buffs.get("xp_flat", 0))
                total_buffs["rare_pct"] += float(buffs.get("rare_pct", 0.0))
                wm = float(buffs.get("weight_mult", 0.0))
                if wm > 0:
                    total_buffs["weight_mult"] *= wm
            embed.add_field(name="🧰 Đang trang bị", value="\n".join(eq_lines), inline=False)
        else:
            total_buffs = {"luck": 0.0, "timeout_add": 0.0, "len_sub": 0, "xp_flat": 0, "rare_pct": 0.0, "weight_mult": 1.0}
        try:
            active_pets = self.bot.data.get_active_pets(target.id)
        except Exception:
            active_pets = []
        if active_pets:
            pet_lines = []
            for pid in active_pets:
                pd = GAME_PETS.get(pid, {})
                pet_lines.append(f"{pd.get('emoji','')} `{pid}` — {pd.get('name', pid)}")
                pb = pd.get('buffs', {})
                total_buffs['luck'] += float(pb.get('luck', 0.0))
                total_buffs['timeout_add'] += float(pb.get('timeout_add', 0.0))
                total_buffs['len_sub'] += int(pb.get('len_sub', 0))
                total_buffs['xp_flat'] += int(pb.get('xp_flat', 0))
                total_buffs['rare_pct'] += float(pb.get('rare_pct', 0.0))
                wm = float(pb.get("weight_mult", 0.0))
                if wm > 0:
                    total_buffs["weight_mult"] *= wm
            embed.add_field(name="🐾 Pet đang sử dụng", value="\n".join(pet_lines), inline=False)

        # show aggregate bonuses
        agg_parts = []
        if total_buffs.get("luck"):
            agg_parts.append(f"+{total_buffs['luck']:.2f} luck")
        if total_buffs["timeout_add"]:
            agg_parts.append(f"+{total_buffs['timeout_add']:.1f}s")
        if total_buffs["len_sub"]:
            agg_parts.append(f"-{total_buffs['len_sub']} kí tự")
        if total_buffs["xp_flat"]:
            agg_parts.append(f"+{total_buffs['xp_flat']} XP")
        if total_buffs["rare_pct"]:
            agg_parts.append(f"+{total_buffs['rare_pct']*100:.0f}% rare")
        if total_buffs["weight_mult"] != 1.0:
            agg_parts.append(f"x{total_buffs['weight_mult']:.2f} weight")
        if agg_parts:
            embed.add_field(name="✨ Bonus đang có", value=", ".join(agg_parts), inline=False)
        embed.set_footer(text=f"Yêu cầu bởi {ctx.author.display_name}")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="level", aliases=["xp", "lvl"], help="Xem cấp & XP: /level [@user]")
    async def level(self, ctx: commands.Context, member: discord.Member | None = None):
        user = member or ctx.author
        if not hasattr(self.bot, "data"):
            await ctx.send("❌ Chưa cấu hình DataManager (bot.data).")
            return
        lvl = self.bot.data.get_level(user.id)
        xp = self.bot.data.get_xp(user.id)
        need = BASE_XP_PER_LEVEL * lvl
        embed = discord.Embed(
            title=f"📈 Cấp của {user.display_name}",
            description=f"**Lv.{lvl}** — **{xp:,}** XP / **{need:,}** XP",
            color=EMBED_COLOR,
        )
        if user.avatar:
            embed.set_thumbnail(url=user.avatar.url)
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_fish_caught(self, user_id: int, xp_gain: int, channel_id: int):
        """Xử lý sự kiện khi người chơi bắt cá thành công (được dispatch từ `fish` cog)."""
        if not hasattr(self.bot, "data"):
            return

        # Xem equipped items để áp dụng buff (nếu có)
        try:
            equipped = self.bot.data.get_equipped_items(user_id)
        except Exception:
            equipped = []

        # Tính tổng bonus XP từ các item trang bị
        total_xp_gain = xp_gain
        if equipped:
            try:
                from game_items import ITEMS as GAME_ITEMS
            except Exception:
                GAME_ITEMS = {}
            for it in equipped:
                it_def = GAME_ITEMS.get(it, {})
                buffs = it_def.get("buffs", {}) if it_def else {}
                xp_flat = int(buffs.get("xp_flat", 0)) if buffs else 0
                total_xp_gain += xp_flat
        # Pets active can also give xp
        try:
            from game_pets import PETS as GAME_PETS
        except Exception:
            GAME_PETS = {}
        try:
            active_pets = self.bot.data.get_active_pets(user_id)
        except Exception:
            active_pets = []
        if active_pets and GAME_PETS:
            for pid in active_pets:
                pdef = GAME_PETS.get(pid, {})
                buffs = pdef.get("buffs", {}) if pdef else {}
                xp_flat = int(buffs.get("xp_flat", 0)) if buffs else 0
                total_xp_gain += xp_flat

        # Thêm XP (đã cộng bonus)
        try:
            await self.bot.data.add_xp(user_id, total_xp_gain)
        except Exception:
            return

        # Tính & xử lý lên cấp (XP dư sẽ chuyển sang level sau)
        total_xp = self.bot.data.get_xp(user_id)
        cur_level = self.bot.data.get_level(user_id)
        start_level = cur_level
        leveled = 0
        total_gems_reward = 0

        while total_xp >= BASE_XP_PER_LEVEL * cur_level:
            total_xp -= BASE_XP_PER_LEVEL * cur_level
            cur_level += 1
            leveled += 1
            total_gems_reward += cur_level * 15

        if leveled > 0:
            # Cập nhật level & XP còn dư & Gems
            try:
                await self.bot.data.set_level(user_id, cur_level)
                await self.bot.data.set_xp(user_id, total_xp)
                if total_gems_reward > 0:
                    await self.bot.data.add_gems(user_id, total_gems_reward)
            except Exception:
                pass

            # Kiểm tra các mốc mở khóa
            unlocks = []
            if start_level < 5 and cur_level >= 5:
                unlocks.append("🔓 **Trang bị vật phẩm** (Item Slot)")
                unlocks.append("🌊 **Thủy cung** (Sức chứa: 3)")
            if start_level < 10 and cur_level >= 10:
                unlocks.append("🐾 **Ô Pet thứ 3**")
                unlocks.append("🌊 **Thủy cung** (Sức chứa: 4)")
            if start_level < 20 and cur_level >= 20:
                unlocks.append("🌊 **Thủy cung** (Sức chứa: 5)")

            # Thông báo ở kênh đã bắt cá (hoặc DM nếu kênh không tồn tại)
            channel = self.bot.get_channel(channel_id)
            member = self.bot.get_user(user_id)
            title = "🎉 Lên cấp!"
            desc = f"<@{user_id}> vừa lên **Lv.{cur_level}**!\n\n💎 Phần thưởng: **+{total_gems_reward}** gems"
            if unlocks:
                desc += "\n\n**Cơ chế mới mở khóa:**\n" + "\n".join([f"- {u}" for u in unlocks])
            embed = discord.Embed(title=title, description=desc, color=EMBED_COLOR)
            if channel:
                try:
                    await channel.send(embed=embed)
                except Exception:
                    pass
            elif member:
                try:
                    await member.send(embed=embed)
                except Exception:
                    pass


async def setup(bot: commands.Bot):
    await bot.add_cog(ProfileCog(bot))