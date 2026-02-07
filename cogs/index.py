import discord
from discord.ext import commands

try:
    from game_pets import PETS as GAME_PETS, EGG_TIERS
except Exception:
    GAME_PETS = {}
    EGG_TIERS = {}

try:
    from game_config import FISH_POOLS, WEATHER_CONFIG, RARITY_DISPLAY
except Exception:
    try:
        from cogs.fish import FISH_POOLS as FISH_POOLS
    except Exception:
        try:
            from fish import FISH_POOLS as FISH_POOLS
        except Exception:
            FISH_POOLS = {}
    WEATHER_CONFIG = {}
    RARITY_DISPLAY = {"trash": "Trash", "common": "Common", "uncommon": "Uncommon", "rare": "Rare", "epic": "Epic", "legendary": "Legendary", "mythical": "Mythical", "unreal": "Unreal"}

# Định nghĩa thứ tự độ hiếm đầy đủ để đồng bộ
RARITY_ORDER = ["trash", "common", "uncommon", "rare", "epic", "legendary", "mythical", "unreal"]


class IndexCog(commands.Cog, name="Index"):
    """Tra cứu dữ liệu game: pets, fishes, ..."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="index", aliases=["idx"], help="Tra cứu dữ liệu: `/index pets` | `/index pet <id>` | `/index fishes`")
    async def index(self, ctx: commands.Context, section: str | None = None, *, arg: str | None = None):
        # Xác định xem có nên gửi tin nhắn ẩn không (nếu là slash command)
        ephemeral = True if ctx.interaction else False

        if not section:
            await ctx.send("❗ Dùng: `/index <pets|pet|fishes|items|item>` — ví dụ `/index pets` hoặc `/index pet p3_a` hoặc `/index items`")
            return
        sec = section.lower()

        # PETS list
        if sec in ("pets", "petlist"):
            if not GAME_PETS:
                await ctx.send("_Chưa có định nghĩa pet._", ephemeral=ephemeral)
                return
            
            # Group by rarity for Select Menu
            by_rarity = {}
            for pid, p in GAME_PETS.items():
                r = p.get('rarity', 'common')
                by_rarity.setdefault(r, []).append((pid, p))

            class PetRaritySelect(discord.ui.Select):
                def __init__(self, data):
                    self.data = data
                    options = []
                    for k in RARITY_ORDER:
                        if k in data:
                            label = RARITY_DISPLAY.get(k, k.title())
                            options.append(discord.SelectOption(label=label, value=k))
                    super().__init__(placeholder="🔻 Chọn độ hiếm...", min_values=1, max_values=1, options=options)

                async def callback(self, interaction: discord.Interaction):
                    val = self.values[0]
                    group = self.data.get(val, [])
                    lines = []
                    for pid, p in sorted(group, key=lambda x: x[0]):
                        lines.append(f"`{pid}` {p.get('emoji','')} **{p.get('name','?')}** — {p.get('desc','')}")
                    
                    r_title = RARITY_DISPLAY.get(val, val.title())
                    embed = discord.Embed(title=f"🐾 Danh sách Pet — {r_title}", description="\n".join(lines), color=0xB2FFDA)
                    await interaction.response.edit_message(embed=embed)

            class PetView(discord.ui.View):
                def __init__(self, data):
                    super().__init__(timeout=60)
                    self.add_item(PetRaritySelect(data))

            embed = discord.Embed(title="🐾 Danh sách Pet", description="Chọn độ hiếm từ menu bên dưới để xem chi tiết.", color=0xB2FFDA)
            await ctx.send(embed=embed, view=PetView(by_rarity), ephemeral=ephemeral)
            return

        # PET detail
        if sec == "pet":
            if not arg:
                await ctx.send("❗ Dùng: `/index pet <id>`")
                return
            pet_id = arg.strip()
            p = GAME_PETS.get(pet_id)
            if not p:
                await ctx.send(f"❌ Không tìm thấy pet `{pet_id}`.")
                return
            em = p.get('emoji','')
            name = p.get('name', pet_id)
            desc = p.get('desc', '')
            buffs = p.get('buffs', {})
            bparts = []
            if buffs.get('luck'):
                bparts.append(f"+{float(buffs.get('luck')):.2f} luck")
            if buffs.get('timeout_add'):
                bparts.append(f"+{float(buffs.get('timeout_add')):.1f}s time")
            if buffs.get('len_sub'):
                bparts.append(f"-{int(buffs.get('len_sub'))} len")
            if buffs.get('xp_flat'):
                bparts.append(f"+{int(buffs.get('xp_flat'))} XP")
            if buffs.get('extra_slot'):
                bparts.append(f"+{int(buffs.get('extra_slot'))} extra slot")
            if buffs.get('weight_mult'):
                bparts.append(f"x{float(buffs.get('weight_mult')):.2f} weight")
            rarity = p.get('rarity','')
            embed = discord.Embed(title=f"{em} {name} — `{pet_id}`", description=desc, color=0xB2FFDA)
            if bparts:
                embed.add_field(name="Buffs", value=", ".join(bparts), inline=False)
            if rarity:
                embed.set_footer(text=f"Rarity: {rarity}")
            await ctx.send(embed=embed, ephemeral=ephemeral)
            return

        # Items list & detail
        if sec in ("items", "itemlist"):
            try:
                from game_items import ITEMS as ITEMS
            except Exception:
                ITEMS = {}
            if not ITEMS:
                await ctx.send("_Chưa có định nghĩa item._")
                return
            
            class ItemSelect(discord.ui.Select):
                def __init__(self, items_data):
                    self.items_data = items_data
                    options = []
                    for iid, it in sorted(items_data.items()):
                        label = it.get('name', iid)
                        emoji = it.get('emoji') or None
                        desc = (it.get('desc') or "Không có mô tả")[:90]
                        options.append(discord.SelectOption(label=label, value=iid, emoji=emoji, description=desc))
                    super().__init__(placeholder="🎒 Chọn vật phẩm để xem chi tiết...", min_values=1, max_values=1, options=options)

                async def callback(self, interaction: discord.Interaction):
                    iid = self.values[0]
                    it = self.items_data.get(iid)
                    if not it:
                        return
                    
                    em = it.get('emoji','')
                    name = it.get('name', iid)
                    buffs = it.get('buffs', {})
                    bparts = [f"{k}: {v}" for k, v in buffs.items()]
                    
                    embed = discord.Embed(title=f"{em} {name} — `{iid}`", color=0xFFD700)
                    if bparts:
                        embed.add_field(name="Hiệu ứng (Buffs)", value=", ".join(bparts), inline=False)
                    if it.get('desc'):
                        embed.description = it.get('desc')
                    
                    await interaction.response.edit_message(embed=embed)

            class ItemView(discord.ui.View):
                def __init__(self, items_data):
                    super().__init__(timeout=60)
                    self.add_item(ItemSelect(ITEMS))

            embed = discord.Embed(title="🎒 Danh sách Vật Phẩm", description="Chọn vật phẩm bên dưới để xem thông tin chi tiết.", color=0xFFD700)
            await ctx.send(embed=embed, view=ItemView(ITEMS), ephemeral=ephemeral)
            return

        if sec == "item":
            if not arg:
                await ctx.send("❗ Dùng: `/index item <id>`")
                return
            item_id = arg.strip()
            try:
                from game_items import ITEMS as ITEMS
            except Exception:
                ITEMS = {}
            it = ITEMS.get(item_id)
            if not it:
                await ctx.send(f"❌ Không tìm thấy item `{item_id}`.")
                return
            em = it.get('emoji','')
            name = it.get('name', item_id)
            buffs = it.get('buffs', {})
            bparts = []
            for k, v in buffs.items():
                bparts.append(f"{k}: {v}")
            embed = discord.Embed(title=f"{em} {name} — `{item_id}`", color=0xFFD700)
            if bparts:
                embed.add_field(name="Buffs", value=", ".join(bparts), inline=False)
            if it.get('desc'):
                embed.description = it.get('desc')
            await ctx.send(embed=embed, ephemeral=ephemeral)
            return

        # Fishes list (paginated): page 1 = common..epic, page 2 = legendary+ (with weight & price details)
        if sec in ("fishes", "fish", "f"):
            if not FISH_POOLS:
                await ctx.send("_Chưa có định nghĩa cá._")
                return
            # Attempt to get price/weight config for extra info
            try:
                from game_config import PRICE_PER_KG_BY_RARITY as PRICE_BY_RARITY, WEIGHT_BY_RARITY as WEIGHT_BY_RARITY
            except Exception:
                PRICE_BY_RARITY = {}
                WEIGHT_BY_RARITY = {}

            # Gather weather-only specials grouped by (name, rarity)
            ws_map = {}
            for w_key, w_info in WEATHER_CONFIG.items():
                for s in w_info.get('special_fish', []):
                    k = (s.get('name'), s.get('rarity'))
                    if k not in ws_map:
                        ws_map[k] = {'emoji': s.get('emoji', ''), 'weathers': [], 'chance': s.get('chance')}
                    ws_map[k]['weathers'].append(w_info.get('name', w_key))

            # Build per-rarity lines for Select Menu
            by_rarity = {}
            
            for r in RARITY_ORDER:
                # Bỏ độ hiếm trash trong index fishes theo yêu cầu
                if r == "trash":
                    continue

                arr = FISH_POOLS.get(r, [])
                lines = []
                for f in arr:
                    # base weight (fallback to rarity midpoint)
                    if f.get('base_weight') is not None:
                        bw = float(f.get('base_weight'))
                    else:
                        wmin, wmax = WEIGHT_BY_RARITY.get(r, (0.5, 2.0))
                        bw = (float(wmin) + float(wmax)) / 2.0
                    # price per kg (per-fish override > rarity default > fallback 10)
                    price_pk = int(f.get('price_per_kg') if f.get('price_per_kg') is not None else PRICE_BY_RARITY.get(r, 10))
                    est_sell = int(price_pk * bw)
                    # two-line format: name line, then detail line below
                    lines.append(f"{f.get('emoji','')} {f.get('name','?')}")
                    lines.append(f"Weight: {bw} kg | Price: {price_pk:,} coins/kg | Est: ≈ {est_sell:,} coins")
                # append weather-only fishes for this rarity using two-line format
                for (name, rr), info in ws_map.items():
                    if rr == r:
                        lines.append(f"{info.get('emoji','')} {name}")
                        lines.append(f"Weather-only: {', '.join(info.get('weathers'))}")
                if lines:
                    by_rarity[r] = lines

            if not by_rarity:
                await ctx.send("_Không có cá để hiển thị._", ephemeral=ephemeral)
                return

            class FishRaritySelect(discord.ui.Select):
                def __init__(self, data):
                    self.data = data
                    options = []
                    for k in RARITY_ORDER:
                        if k == "trash":
                            continue
                        if k in data:
                            label = RARITY_DISPLAY.get(k, k.title())
                            options.append(discord.SelectOption(label=label, value=k))
                    super().__init__(placeholder="🔻 Chọn độ hiếm...", min_values=1, max_values=1, options=options)

                async def callback(self, interaction: discord.Interaction):
                    val = self.values[0]
                    lines = self.data.get(val, [])
                    r_title = RARITY_DISPLAY.get(val, val.title())
                    embed = discord.Embed(title=f"🐟 Danh sách cá — {r_title}", description="\n".join(lines), color=0x58D68D)
                    await interaction.response.edit_message(embed=embed)

            class FishView(discord.ui.View):
                def __init__(self, data):
                    super().__init__(timeout=60)
                    self.add_item(FishRaritySelect(data))

            embed = discord.Embed(title="🐟 Danh sách cá", description="Chọn độ hiếm từ menu bên dưới để xem chi tiết.", color=0x58D68D)
            await ctx.send(embed=embed, view=FishView(by_rarity), ephemeral=ephemeral)
            return

        await ctx.send("❌ Phần truy vấn không hợp lệ. Dùng: `/index pets` | `/index pet <id>` | `/index fishes`")

async def setup(bot: commands.Bot):
    await bot.add_cog(IndexCog(bot))
