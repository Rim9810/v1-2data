# cogs/bag.py
import discord
from discord.ext import commands
from discord.ui import View, Button

# Thử import cấu hình cần câu nếu có
try:
    from game_config import ROD_TIERS, MAX_ROD_LEVEL
except Exception:
    ROD_TIERS = {
        1: {"name": "Cần Tre"},
        2: {"name": "Cần Gỗ"},
        3: {"name": "Cần Sắt"},
        4: {"name": "Cần Carbon"},
        5: {"name": "Cần Huyền Thoại"},
    }
    MAX_ROD_LEVEL = max(ROD_TIERS)

RARITY_ORDER  = ["trash", "common", "uncommon", "rare", "epic", "legendary", "mythical", "unreal"]
RARITY_TITLE  = {"trash": "🗑️ Trash", "common": "⚪ Common", "uncommon": "🟢 Uncommon", "rare": "🔵 Rare", "epic": "🔶 Epic", "legendary": "🏆 Legendary", "mythical": "🔮 Mythical", "unreal": "🛸 Unreal"}
EMBED_COLOR   = 0xfedcdb  #pink

class BagCog(commands.Cog, name="Inventory"):
    """Kho đồ của bạn"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="bag",
        help="Xem kho đồ của bạn hoặc người khác: /bag [@user]",
        aliases=["inv", "inventory"]
    )
    async def bag(self, ctx: commands.Context, member: discord.Member | None = None):
        # 1) Chọn đối tượng xem kho
        target = member or ctx.author

        # 2) Lấy inventory từ DataManager
        if not hasattr(self.bot, "data"):
            await ctx.send("❌ Chưa cấu hình DataManager (bot.data).")
            return

        inv = self.bot.data.get_inventory(target.id)  # dict: rarity -> {fish_name: count}
        try:
            shiny_inv = self.bot.data.get_shiny_inventory(target.id)
        except Exception:
            shiny_inv = {"common": {}, "uncommon": {}, "rare": {}, "epic": {}}

        # Also merge fish objects (new model) into inventory display
        try:
            fish_objs = self.bot.data.get_fish_objects(target.id)
        except Exception:
            fish_objs = []

        # Build merged buckets where keys are in the form: "<R>|<weight_class>|<name>"
        merged_inv = {r: {} for r in RARITY_ORDER}
        merged_shiny = {r: {} for r in RARITY_ORDER}
        # Add legacy inventory counts into merged_inv
        for r, bucket in inv.items():
            initial = r[0].upper() if isinstance(r, str) and r else "?"
            for n, cnt in bucket.items():
                key = f"{initial}|normal|{n}"
                merged_inv.setdefault(r, {})
                merged_inv[r][key] = merged_inv[r].get(key, 0) + int(cnt)
        # Add legacy shiny counts
        for r, bucket in shiny_inv.items():
            initial = r[0].upper() if isinstance(r, str) and r else "?"
            for n, cnt in bucket.items():
                key = f"{initial}|normal|{n}"
                merged_shiny.setdefault(r, {})
                merged_shiny[r][key] = merged_shiny[r].get(key, 0) + int(cnt)
        # NOTE: we keep legacy counts in merged_inv/merged_shiny only (no duplication from fish objects)
        # Fish objects are handled separately when showing top-N by sell price.
        # (So nothing to do here; fish_objs will be used later.)

        # 3) Định dạng nội dung theo từng bậc — hiển thị riêng Thường và Shiny trên 2 dòng
        def fmt_bucket(normal_bucket: dict[str, int], shiny_bucket: dict[str, int]) -> str:
            # Build emoji map from fish pools and weather fish
            fish_emoji_map: dict[str, str] = {}
            try:
                from cogs.fish import FISH_POOLS as FP
            except Exception:
                try:
                    from fish import FISH_POOLS as FP
                except Exception:
                    FP = None
            if FP:
                for arr in FP.values():
                    for f in arr:
                        fish_emoji_map[f.get("name", "")] = f.get("emoji", "")
            # Thêm cá thời tiết từ WEATHER_CONFIG
            try:
                from game_config import WEATHER_CONFIG
            except Exception:
                WEATHER_CONFIG = {}
            for w in WEATHER_CONFIG.values():
                for wf in w.get("special_fish", []):
                    fish_emoji_map[wf.get("name", "")] = wf.get("emoji", "")

            def fmt_line(bucket: dict[str, int], shiny: bool = False) -> str:
                if not bucket:
                    return "_Trống_"
                parts: list[str] = []
                for meta in sorted(bucket.keys()):
                    cnt = bucket.get(meta, 0)
                    # meta format: INITIAL|weight_class|name
                    if "|" in meta:
                        try:
                            initial, wc, raw = meta.split("|", 2)
                        except Exception:
                            initial, wc, raw = "?", "normal", meta
                    else:
                        # legacy fallback: only name
                        initial, wc, raw = "?", "normal", meta
                    em = fish_emoji_map.get(raw, "")
                    if shiny:
                        if em:
                            parts.append(f"✨ ({wc}){em} ×{cnt}")
                        else:
                            parts.append(f"✨ ({wc}){raw} ×{cnt}")
                    else:
                        if em:
                            parts.append(f"({wc}){em} ×{cnt}")
                        else:
                            parts.append(f"({wc}){raw} ×{cnt}")
                return ", ".join(parts)

            normal_line = fmt_line(normal_bucket, shiny=False) if normal_bucket else ""
            shiny_line = fmt_line(shiny_bucket, shiny=True) if shiny_bucket else ""
            # If both empty, return placeholder
            if not normal_line and not shiny_line:
                return "_Trống_"
            # If both present, show both lines with labels; otherwise show only the one that exists
            if normal_line and shiny_line:
                return f"{normal_line}\n{shiny_line}"
            if normal_line:
                return f"{normal_line}"
            return f"{shiny_line}"

        title = f"🎒 Kho đồ của {target.display_name}"

        # 5) Tạo embed
        embed = discord.Embed(title=title, color=EMBED_COLOR)
        # Thumbnail là avatar của người xem
        if target.avatar:
            embed.set_thumbnail(url=target.avatar.url)

        # Build a name->emoji map for fish display (including weather specials)
        fish_emoji_map: dict[str, str] = {}
        try:
            from cogs.fish import FISH_POOLS as FP
        except Exception:
            try:
                from fish import FISH_POOLS as FP
            except Exception:
                FP = None
        if FP:
            for arr in FP.values():
                for f in arr:
                    fish_emoji_map[f.get("name", "")] = f.get("emoji", "")
        try:
            from game_config import WEATHER_CONFIG
        except Exception:
            WEATHER_CONFIG = {}
        for w in WEATHER_CONFIG.values():
            for wf in w.get("special_fish", []):
                fish_emoji_map[wf.get("name", "")] = wf.get("emoji", "")

        # Organize fish objects by rarity
        per_rarity_objs = {r: [] for r in RARITY_ORDER}
        for fobj in fish_objs:
            rr = (fobj.get("rarity") or "common").lower()
            per_rarity_objs.setdefault(rr, []).append(fobj)

        for r in RARITY_ORDER:
            lines: list[str] = []
            # Top 5 fish objects by sell_price
            objs = sorted(per_rarity_objs.get(r, []), key=lambda x: int(x.get("sell_price", 0)), reverse=True)
            for f in objs[:3]:
                em = fish_emoji_map.get(f.get("name", ""), "")
                shiny_mark = "✨" if f.get("shiny") else ""
                fid = f.get('id', '')
                lines.append(f"{shiny_mark}`{fid}` ({f.get('weight_class','normal')}) {em or f.get('name')} — {f.get('weight')}kg — **{int(f.get('sell_price',0)):,}** coins")

            if not lines:
                continue

            value = "\n".join(lines)
            embed.add_field(name=RARITY_TITLE[r], value=value, inline=False)

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

        if equipped:
            eq_lines = []
            try:
                lvl = self.bot.data.get_level(target.id)
            except Exception:
                lvl = 1
            # Policy: only 1 item allowed, requires Lv.5 or above to have any slot
            limit = 1 if lvl >= 5 else 0
            # thêm ô bonus từ pet (nếu có)
            try:
                from game_pets import PETS as GAME_PETS
            except Exception:
                GAME_PETS = {}
            try:
                pet_ids = self.bot.data.get_active_pets(target.id)
            except Exception:
                pet_ids = []
            if pet_ids and GAME_PETS:
                for pid in pet_ids:
                    pb = GAME_PETS.get(pid, {}).get("buffs", {})
                    limit += int(pb.get("extra_slot", 0))
            for idx, it in enumerate(equipped, start=1):
                gd = GAME_ITEMS.get(it, {})
                em = gd.get("emoji", "")
                display_name = gd.get("name", it)
                # Chỉ hiển thị emoji và tên trong phần xem kho (không hiển thị buffs)
                base = f"{em} {display_name}" if em else display_name
                eq_lines.append(f"{idx}. {base}")
            # Show slot summary at top
            eq_lines.insert(0, f"(Đang dùng {len(equipped)}/{limit} ô)")
        else:
            eq_lines = ["_Không có_"]

        # Chỉ hiển thị các ô đang sử dụng (không hiển thị toàn bộ vật phẩm ở đây)
        embed.add_field(name="🧰 Đang sử dụng", value="\n".join(eq_lines), inline=False)

        await ctx.send(embed=embed)

    @commands.hybrid_command(name="fishes", aliases=["listfishes", "listfish"], help="Liệt kê fish objects của bạn hoặc người khác: /fishes [@user]")
    async def fishes(self, ctx: commands.Context, member: discord.Member | None = None):
        target = member or ctx.author
        if not hasattr(self.bot, "data"):
            await ctx.send("❌ Chưa cấu hình DataManager (bot.data).")
            return
        try:
            fish_objs = self.bot.data.get_fish_objects(target.id)
        except Exception:
            fish_objs = []
        if not fish_objs:
            await ctx.send("_Không có fish objects (danh sách trống)_")
            return
        # Build emoji map
        fish_emoji_map: dict[str, str] = {}
        try:
            from game_config import FISH_POOLS, WEATHER_CONFIG
            for pool in FISH_POOLS.values():
                for f in pool:
                    fish_emoji_map[f.get('name','')] = f.get('emoji','')
            for w in WEATHER_CONFIG.values():
                for f in w.get('special_fish', []):
                    fish_emoji_map[f.get('name','')] = f.get('emoji','')
        except Exception:
            pass

        sorted_fishes = sorted(fish_objs, key=lambda x: int(x.get('sell_price',0)), reverse=True)
        per_page = 10
        pages = [sorted_fishes[i:i + per_page] for i in range(0, len(sorted_fishes), per_page)]

        class FishesView(discord.ui.View):
            def __init__(self, pages, target_name):
                super().__init__(timeout=60)
                self.pages = pages
                self.target_name = target_name
                self.current = 0

            def _get_embed(self):
                page_objs = self.pages[self.current]
                lines = []
                for f in page_objs:
                    em = fish_emoji_map.get(f.get('name',''), '')
                    shiny = '✨' if f.get('shiny') else ''
                    lines.append(f"`{f.get('id')}` — {shiny}[{(f.get('rarity') or 'common')[0].upper()}] ({f.get('weight_class')}) {em or f.get('name')} — {f.get('weight')}kg — {int(f.get('price_per_kg',0)):,} c/kg → **{int(f.get('sell_price',0)):,}**")
                
                embed = discord.Embed(title=f"🐟 Fish objects — {self.target_name}", description="\n".join(lines), color=EMBED_COLOR)
                embed.set_footer(text=f"Trang {self.current+1}/{len(self.pages)} • Tổng: {len(sorted_fishes)} con")
                return embed

            @discord.ui.button(label="◀️", style=discord.ButtonStyle.secondary)
            async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.current = (self.current - 1) % len(self.pages)
                await interaction.response.edit_message(embed=self._get_embed(), view=self)

            @discord.ui.button(label="▶️", style=discord.ButtonStyle.secondary)
            async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.current = (self.current + 1) % len(self.pages)
                await interaction.response.edit_message(embed=self._get_embed(), view=self)

        view = FishesView(pages, target.display_name)
        if len(pages) <= 1:
            for child in view.children:
                child.disabled = True
        await ctx.send(embed=view._get_embed(), view=view)

    @commands.hybrid_command(name="rod", aliases=["setrod", "equiprod"], help="Đổi cần câu: /rod <cấp|list> — 'list' hiển thị cấp đang dùng và cấp cao nhất đã sở hữu.")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def rod(self, ctx: commands.Context, level: str | None = None):
        """Gọi '/rod' để xem kho cần, '/rod <cấp>' để đổi cần."""
        if not hasattr(self.bot, "data"):
            await ctx.send("❌ Chưa cấu hình DataManager (bot.data).")
            return

        # Nếu không có tham số: hiển thị kho cần
        if level is None:
            try:
                cur = self.bot.data.get_rod_level(ctx.author.id)
                max_owned = self.bot.data.get_max_rod_level(ctx.author.id)
            except Exception:
                await ctx.send("❌ Không thể truy xuất thông tin cần câu. Hãy thử lại sau.")
                return

            embed = discord.Embed(
                title=f"🎣 Cần câu — Thông tin của {ctx.author.display_name}",
                color=EMBED_COLOR
            )
            embed.add_field(
                name="Đang dùng",
                value=f"**Lv.{cur}** — {ROD_TIERS.get(cur, {}).get('name', 'Unknown')}",
                inline=False,
            )
            embed.add_field(
                name="Đã sở hữu tối đa",
                value=f"**Lv.{max_owned}** — {ROD_TIERS.get(max_owned, {}).get('name', 'Unknown')}",
                inline=False,
            )
            owned_lines = []
            for lv in range(1, max_owned + 1):
                mark = "⭐" if lv == cur else "✅"
                owned_lines.append(f"{mark} Lv.{lv} — {ROD_TIERS.get(lv, {}).get('name', 'Unknown')}")
            embed.add_field(name="Các cấp đã sở hữu", value="\n".join(owned_lines) or "(Không có)", inline=False)

            await ctx.send(embed=embed)
            return

        # Nếu có tham số: thử parse cấp để đổi cần
        try:
            lvl = int(level)
        except Exception:
            await ctx.send("❌ Tham số không hợp lệ. Dùng số nguyên (cấp) hoặc bỏ trống để xem kho cần.")
            return

        if lvl < 1 or lvl > MAX_ROD_LEVEL:
            await ctx.send(f"❌ Cấp không hợp lệ. Hãy nhập số từ 1 tới {MAX_ROD_LEVEL}.")
            return

        try:
            cur = self.bot.data.get_rod_level(ctx.author.id)
            max_owned = self.bot.data.get_max_rod_level(ctx.author.id)
        except Exception:
            await ctx.send("❌ Không thể truy xuất thông tin cần câu. Hãy thử lại sau.")
            return

        if lvl == cur:
            await ctx.send(f"ℹ️ Bạn đang dùng **Lv.{cur}** rồi.")
            return
        if lvl > max_owned:
            await ctx.send(f"❌ Bạn chưa sở hữu **Lv.{lvl}**. Hãy dùng `/buy rod` để mua/nâng cấp (nếu đủ tiền). Cấp cao nhất bạn sở hữu: **Lv.{max_owned}**.")
            return

        await self.bot.data.set_rod_level(ctx.author.id, lvl)
        await ctx.send(f"✅ Đã đổi cần sang **Lv.{lvl} — {ROD_TIERS[lvl]['name']}**.")

    @commands.hybrid_command(name="equip", aliases=["eq"], help="Trang bị vật phẩm: `/equip <id|tên>`. Dùng `/unequip` để gỡ.")
    async def zequip(self, ctx: commands.Context, action: str | None = None, *, name: str | None = None):
        """Trang bị item/cổ vật (một người chỉ được dùng 1 item; không được trùng lặp).
        - `/equip <id|tên>`: trang bị 1 item (yêu cầu Lv.5)
        """
        if not hasattr(self.bot, "data"):
            await ctx.send("❌ Chưa cấu hình DataManager (bot.data).")
            return

        target_name = name or action
        if not target_name:
            await ctx.send("❗ Dùng: `/equip <id|tên>` để trang bị.")
            return

        try:
            from game_items import ITEMS as GAME_ITEMS
        except Exception:
            GAME_ITEMS = {}
        # Resolve input to item_id (accept id or exact display name)
        item_id = None
        if target_name in GAME_ITEMS:
            item_id = target_name
        else:
            for k, v in GAME_ITEMS.items():
                if v.get("name", "").lower() == target_name.lower():
                    item_id = k
                    break
        if not item_id:
            await ctx.send(f"❌ Không tìm thấy item **{target_name}** (dùng id hoặc tên chính xác).")
            return

        # Kiểm tra sở hữu
        items = self.bot.data.get_items(ctx.author.id)
        owned = items.get(item_id, 0)
        if owned <= 0:
            await ctx.send(f"❌ Bạn không có **{GAME_ITEMS.get(item_id, {}).get('name', item_id)}**.")
            return

        equipped = self.bot.data.get_equipped_items(ctx.author.id)
        # Tính giới hạn và yêu cầu cấp: base 1 nếu Lv>=5, cộng extra_slot từ pet active
        try:
            lvl = self.bot.data.get_level(ctx.author.id)
        except Exception:
            lvl = 1
        if lvl < 5:
            await ctx.send("⚠️ Bạn cần **Lv.5** trở lên để trang bị item.")
            return
        limit = 1
        # add pet extra slots
        try:
            from game_pets import PETS as GAME_PETS
        except Exception:
            GAME_PETS = {}
        try:
            pet_ids = self.bot.data.get_active_pets(ctx.author.id)
        except Exception:
            pet_ids = []
        if pet_ids and GAME_PETS:
            for pid in pet_ids:
                pb = GAME_PETS.get(pid, {}).get("buffs", {})
                limit += int(pb.get("extra_slot", 0))
        if len(equipped) >= limit:
            await ctx.send(f"⚠️ Bạn chỉ được trang bị tối đa **{limit}** item (bao gồm ô từ pet). Hãy bỏ item đang dùng trước khi trang bị item mới.")
            return
        # Không cho trang bị trùng lặp
        if item_id in equipped:
            await ctx.send(f"❌ **{GAME_ITEMS.get(item_id, {}).get('name', item_id)}** đã được trang bị. Không được trang bị trùng lặp.")
            return

        # Trang bị
        equipped.append(item_id)
        await self.bot.data.set_equipped_items(ctx.author.id, equipped)
        await ctx.send(f"✅ Đã trang bị **{GAME_ITEMS.get(item_id, {}).get('name', item_id)}**.")
        return

    @commands.hybrid_command(name="unequip", aliases=["ueq"], help="Bỏ trang bị theo ô: `/unequip <số ô|all>`")
    async def zunequip(self, ctx: commands.Context, slot: str | None = None):
        """Bỏ trang bị theo số ô (1-based index) hoặc `all` để bỏ tất cả."""
        if not hasattr(self.bot, "data"):
            await ctx.send("❌ Chưa cấu hình DataManager (bot.data).")
            return
        if not slot:
            await ctx.send("❗ Dùng: `/unequip <số ô|all>` (ví dụ `/unequip 1` hoặc `/unequip all`).")
            return
        equipped = self.bot.data.get_equipped_items(ctx.author.id)
        if slot.lower() == "all":
            await self.bot.data.set_equipped_items(ctx.author.id, [])
            await ctx.send("✅ Đã bỏ trang bị tất cả cổ vật.")
            return
        try:
            idx = int(slot)
        except Exception:
            await ctx.send("❌ Vui lòng chỉ định số ô (ví dụ: `/unequip 1`) hoặc `all`.")
            return
        if idx < 1 or idx > len(equipped):
            await ctx.send(f"❌ Ô **{idx}** không hợp lệ. Bạn hiện có **{len(equipped)}** ô đang dùng.")
            return
        item_id = equipped.pop(idx - 1)
        try:
            from game_items import ITEMS as GAME_ITEMS
        except Exception:
            GAME_ITEMS = {}
        await self.bot.data.set_equipped_items(ctx.author.id, equipped)
        await ctx.send(f"✅ Đã bỏ trang bị ô **{idx}** — **{GAME_ITEMS.get(item_id, {}).get('name', item_id)}**. Ô này đã được trả lại.")
        return

    @commands.hybrid_command(name="item", aliases=["items", "i"], help="Hiển thị tất cả vật phẩm đang sở hữu (kèm id) và các ô đang sử dụng")
    async def item(self, ctx: commands.Context):
        if not hasattr(self.bot, "data"):
            await ctx.send("❌ Chưa cấu hình DataManager (bot.data).")
            return
        try:
            items = self.bot.data.get_items(ctx.author.id)
            equipped = self.bot.data.get_equipped_items(ctx.author.id)
        except Exception:
            await ctx.send("❌ Không thể lấy thông tin vật phẩm.")
            return
        try:
            from game_items import ITEMS as GAME_ITEMS
        except Exception:
            GAME_ITEMS = {}

        embed = discord.Embed(title=f"🎒 Túi Đồ Của {ctx.author.display_name}", color=EMBED_COLOR)
        if ctx.author.avatar:
            embed.set_thumbnail(url=ctx.author.avatar.url)

        # Owned items
        if items:
            lines = []
            for item_id, cnt in items.items():
                gd = GAME_ITEMS.get(item_id, {})
                em = gd.get("emoji", "")
                display_name = gd.get("name", item_id)
                sell_g = gd.get('sell_gems')
                
                line = f"> `{item_id}` {em} **{display_name}** `x{cnt}`"
                if sell_g:
                    line += f" *(💎 {sell_g})*"
                lines.append(line)
            embed.add_field(name="📦 Kho Vật Phẩm", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="📦 Kho Vật Phẩm", value="> *Trống*", inline=False)

        # Equipped items
        if equipped:
            eq_lines = []
            for idx, it in enumerate(equipped, start=1):
                gd = GAME_ITEMS.get(it, {})
                em = gd.get("emoji", "")
                display_name = gd.get("name", it)
                eq_lines.append(f"> **#{idx}** {em} **{display_name}** (`{it}`)")
            embed.add_field(name="🛠️ Đang Trang Bị", value="\n".join(eq_lines), inline=False)
        else:
            embed.add_field(name="🛠️ Đang Trang Bị", value="> *Chưa trang bị vật phẩm nào*", inline=False)
        
        embed.set_footer(text="💡 Dùng /equip <id> để trang bị • /unequip <slot> để tháo")
        await ctx.send(embed=embed, ephemeral=True if ctx.interaction else False)

async def setup(bot: commands.Bot):
    await bot.add_cog(BagCog(bot))