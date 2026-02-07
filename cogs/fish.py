# cogs/fish.py
import random
import asyncio
import discord
import time
import uuid
from discord.ext import commands
from typing import Dict

# ---- Thử import cấu hình chung (nếu có) ----
try:
    from game_config import (
        ROD_TIERS, MAX_ROD_LEVEL, BASE_CHALLENGE, XP_PER_CATCH, FISH_POOLS,
        RARITY_DISPLAY, RARITY_COLORS, WEATHER_CONFIG, GEM_SETTINGS,
        FISHING_CONFIG, BASE_LUCK,
        PRICE_PER_KG_BY_RARITY, WEIGHT_BY_RARITY, WEIGHT_CLASS_BOUNDS, WEIGHT_CLASS_NAMES, WEIGHT_CLASS_PROBS, WEIGHT_CLASS_PCT_RANGES
    )
except Exception:
    # Fallback cấu hình mặc định nếu chưa tạo game_config.py
    ROD_TIERS = {
        1: {"name": "Cần Tre",        "cost": 0,     "bonus": 0, "len_add": 0, "timeout_sub": 0.0},
        2: {"name": "Cần Gỗ",         "cost": 500,   "bonus": 1, "len_add": 2, "timeout_sub": 0.5},
        3: {"name": "Cần Sắt",        "cost": 2000,  "bonus": 2, "len_add": 4, "timeout_sub": 1.0},
        4: {"name": "Cần Carbon",     "cost": 8000,  "bonus": 3, "len_add": 6, "timeout_sub": 1.5},
        5: {"name": "Cần Huyền Thoại","cost": 25000, "bonus": 4, "len_add": 8, "timeout_sub": 2.0},
    }
    MAX_ROD_LEVEL = max(ROD_TIERS)
    FISH_POOLS = {}
    RARITY_DISPLAY = {"common": "Common", "uncommon": "Uncommon", "rare": "Rare", "epic": "Epic"}
    RARITY_COLORS  = {"common": 0x95A5A6, "uncommon": 0x2ECC71, "rare": 0x3498DB, "epic": 0xF1C40F}
    WEATHER_CONFIG = {}
    BASE_CHALLENGE = {"len_min": 4, "len_max": 5, "timeout": 5.0}
    XP_PER_CATCH = 20
    GEM_SETTINGS = {"gem_per_rarity": {"epic": 1}, "aurora_multiplier": 2, "daily_min": 1, "daily_max": 3, "sell_item_gems_default": 1}
    FISHING_CONFIG = {
        "trash":     {"base_weight": 10000, "luck_factor": 0.0},
        "common":    {"base_weight": 5000,  "luck_factor": 0.1},
        "uncommon":  {"base_weight": 2500,  "luck_factor": 0.5},
        "rare":      {"base_weight": 1000,  "luck_factor": 1.0},
        "epic":      {"base_weight": 500,   "luck_factor": 2.0},
        "legendary": {"base_weight": 100,   "luck_factor": 5.0},
        "mythical":  {"base_weight": 10,    "luck_factor": 15.0},
    }
    BASE_LUCK = 1
    PRICE_PER_KG_BY_RARITY = {"trash": 5, "common": 10, "uncommon": 30, "rare": 120, "epic": 500}
    WEIGHT_BY_RARITY = {"common": (0.2, 1.5), "uncommon": (0.5, 3.0), "rare": (1.0, 6.0), "epic": (2.0, 10.0)}
    WEIGHT_CLASS_BOUNDS = [0.0, 1.0, 3.0, 7.0, 9999.0]
    WEIGHT_CLASS_NAMES = ["tiny", "normal", "huge", "gigantic"]
    WEIGHT_CLASS_PROBS = {"tiny": 0.15, "normal": 0.60, "huge": 0.23, "gigantic": 0.02}  # fallback probs

# ===== Cấu hình thử thách (emoji) =====
EMO_D = "<:D_:1469386519784587489>"
EMO_F = "<:F_:1469386706753945803>"
EMO_J = "<:J_:1469386607357333504>"
EMO_K = "<:K_:1469386724646850804>"
EMO_SET = [EMO_D, EMO_F, EMO_J, EMO_K]
# Shiny constants
SHINY_BASE = 0.001  # 0.1% base chance
SPARKLE = "✨"  # emoji lấp lánh hiển thị trước emoji cá
SHINY_SELL_MULT = 20  # giá bán gấp 20 lần
# SPECIAL_VS_NORMAL_SCALE: hệ số để giảm tỉ lệ xuất hiện của cá thời tiết so với một con cá 'bình thường' trong cùng độ hiếm.
# Nếu muốn cá thời tiết ít xuất hiện hơn, giảm giá trị này xuống (ví dụ 0.8), nếu muốn tăng thì nâng lên.
SPECIAL_VS_NORMAL_SCALE = 0.8

MAP_EMO_TO_CHAR = {
    EMO_D: "d",
    EMO_F: "f",
    EMO_J: "j",
    EMO_K: "k",
}

def gen_challenge(n_min: int, n_max: int):
    """Sinh chuỗi emoji và đáp án tương ứng."""
    n = random.randint(n_min, n_max)
    chosen = [random.choice(EMO_SET) for _ in range(n)]
    display = " - ".join(chosen)
    expected = "".join(MAP_EMO_TO_CHAR[e] for e in chosen)
    return display, expected

def normalize_letters(s: str) -> str:
    """Chuẩn hóa input: chỉ giữ d/f/j/k, bỏ khoảng trắng, lower."""
    s = s.lower()
    return "".join(c for c in s if c in ("d", "f", "j", "k"))


class FishCog(commands.Cog, name="Fishing"):
    """Lệnh câu cá cơ bản"""
    # --- Helper for weighted fish selection ---
    def pick_fish_by_rate(self, rarity):
        pool = FISH_POOLS.get(rarity, []) if isinstance(FISH_POOLS, dict) else []
        if not pool:
            # fallback placeholder nếu không có định nghĩa cá cho bậc rarity
            return {
                "name": f"{RARITY_DISPLAY.get(rarity, rarity.title())} Fish",
                "emoji": "",
                "price_per_kg": PRICE_PER_KG_BY_RARITY.get(rarity, 10),
                "rate": 1
            }
        weights = [float(f.get("rate", 1)) for f in pool]
        return random.choices(pool, weights=weights, k=1)[0]

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.current_weather = None
        self.weather_task = None
        self.weather_end_time = 0

    @commands.Cog.listener()
    async def on_ready(self):
        # start weather watcher once bot is ready
        if not self.weather_task:
            self.weather_task = asyncio.create_task(self._weather_watcher())

    def cog_unload(self):
        # cancel background task on unload
        try:
            if self.weather_task:
                self.weather_task.cancel()
        except Exception:
            pass

    async def _weather_watcher(self):
        while True:
            try:
                self._set_new_weather()
            except Exception:
                pass
            # Chọn thời lượng dựa trên thời tiết hiện tại
            duration = 60
            if self.current_weather:
                duration = int(WEATHER_CONFIG.get(self.current_weather, {}).get("duration", 60))
            self.weather_end_time = time.time() + duration
            await asyncio.sleep(duration)

    def _set_new_weather(self):
        # Chọn thời tiết mới dựa trên tỉ lệ trong WEATHER_CONFIG
        if not WEATHER_CONFIG:
            # không có cấu hình thời tiết → vô hiệu hoá
            self.current_weather = None
            return
        weather_types = list(WEATHER_CONFIG.keys())
        rates = [float(WEATHER_CONFIG.get(w, {}).get("rate", 0)) for w in weather_types]
        # Nếu tất cả weights đều 0, bỏ qua việc chọn
        if not any(rates):
            self.current_weather = None
            return
        self.current_weather = random.choices(weather_types, weights=rates, k=1)[0]

    def get_current_weather(self):
        if not self.current_weather:
            self._set_new_weather()
        return self.current_weather, WEATHER_CONFIG.get(self.current_weather, {})

    @commands.hybrid_command(
        name="fish",
        aliases=["f"],
        help="Câu cá: Gõ đúng chuỗi emoji (dfjk) trong thời gian giới hạn."
    )
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.user)  # cooldown theo user
    @commands.max_concurrency(1, per=commands.BucketType.user, wait=True)  # hàng đợi theo user
    async def fish(self, ctx: commands.Context):
        # Check inventory limit
        if hasattr(self.bot, "data"):
            try:
                current_fish = self.bot.data.get_fish_objects(ctx.author.id)
                if len(current_fish) >= 40:
                    msg = "🚫 **Kho cá đã đầy (40/40)!**\nBạn cần bán bớt cá bằng lệnh `/sell` hoặc `/sellall` trước khi câu tiếp."
                    if ctx.interaction:
                        await ctx.send(msg, ephemeral=True)
                    else:
                        await ctx.send(msg)
                    return
            except Exception:
                pass

        # 1) Lấy cấp cần & tính độ khó + số cá thưởng
        lvl = 1
        if hasattr(self.bot, "data"):
            try:
                lvl = self.bot.data.get_rod_level(ctx.author.id)
            except Exception:
                pass
        tier = ROD_TIERS.get(lvl, ROD_TIERS[1])

        base_min = int(BASE_CHALLENGE["len_min"])
        base_max = int(BASE_CHALLENGE["len_max"])
        base_timeout = float(BASE_CHALLENGE["timeout"])

        # Áp dụng buffs từ item đang trang bị
        try:
            equipped = []
            if hasattr(self.bot, "data"):
                equipped = self.bot.data.get_equipped_items(ctx.author.id)
        except Exception:
            equipped = []
        try:
            from game_items import ITEMS as GAME_ITEMS
        except Exception:
            GAME_ITEMS = {}

        total_timeout_add = 0.0
        total_len_sub = 0
        # Buffs from equipped items (convert fish_flat -> luck, handled later)
        if equipped and GAME_ITEMS:
            for it in equipped:
                g = GAME_ITEMS.get(it, {})
                buffs = g.get("buffs", {}) if g else {}
                total_timeout_add += float(buffs.get("timeout_add", 0.0))
                total_len_sub += int(buffs.get("len_sub", 0))
        # Buffs from pets (passive)
        try:
            from game_pets import PETS as GAME_PETS
        except Exception:
            GAME_PETS = {}
        try:
            pets = []
            if hasattr(self.bot, "data"):
                pets = self.bot.data.get_active_pets(ctx.author.id)
        except Exception:
            pets = []
        if pets and GAME_PETS:
            for pid in pets:
                p = GAME_PETS.get(pid, {})
                buffs = p.get("buffs", {}) if p else {}
                total_timeout_add += float(buffs.get("timeout_add", 0.0))
                total_len_sub += int(buffs.get("len_sub", 0))

        effective_len_add = max(0, int(tier["len_add"]) - total_len_sub)
        n_min = base_min + effective_len_add
        n_max = base_max + effective_len_add
        timeout = max(1.5, base_timeout - float(tier["timeout_sub"]) + float(total_timeout_add))  # không thấp hơn 1.5s
        # Single-catch mechanic: always catch one fish per success. Legacy "bonus"/"fish_flat" removed.
        fish_count = 1

        # Áp dụng buff từ thời tiết (không còn tăng số cá; chỉ hỗ trợ các buff khác như 'shiny_mult' / 'gem_mult')
        try:
            w_key_tmp, w_info_tmp = self.get_current_weather()
        except Exception:
            w_key_tmp, w_info_tmp = None, {}

        # Lưu thông tin weather dùng lại sau để xử lý shiny và special fish
        try:
            w_key, w_info = self.get_current_weather()
        except Exception:
            w_key, w_info = None, {}
        weather_shiny_mult = float(w_info.get('buff', {}).get('shiny_mult', 1)) if isinstance(w_info, dict) else 1
        weather_specials = w_info.get('special_fish', []) if isinstance(w_info, dict) else []

        # --- Compute Luck (Moved up for display) ---
        def _safe_float(v, default=0.0):
            try:
                return float(v)
            except Exception:
                return default

        # Compute luck & weight multiplier
        luck = float(BASE_LUCK) # Start from BASE_LUCK
        user_weight_mult = 1.0

        def _apply_w_mult(curr, props):
            try:
                val = float(props.get('weight_mult', 0))
                if val > 0:
                    return curr * val
            except:
                pass
            return curr

        try:
            # Items
            eq = []
            if hasattr(self.bot, "data"):
                eq = self.bot.data.get_equipped_items(ctx.author.id)
            try:
                from game_items import ITEMS as GAME_ITEMS
            except Exception:
                GAME_ITEMS = {}
            for it in eq:
                g = GAME_ITEMS.get(it, {})
                buffs = g.get('buffs', {}) if g else {}
                luck += _safe_float(buffs.get('luck', 0))
                user_weight_mult = _apply_w_mult(user_weight_mult, buffs)
            # Pets
            try:
                from game_pets import PETS as GAME_PETS
            except Exception:
                GAME_PETS = {}
            pets = []
            try:
                if hasattr(self.bot, "data"):
                    pets = self.bot.data.get_active_pets(ctx.author.id)
            except Exception:
                pets = []
            for pid in pets:
                p = GAME_PETS.get(pid, {})
                buffs = p.get('buffs', {}) if p else {}
                luck += _safe_float(buffs.get('luck', 0))
                user_weight_mult = _apply_w_mult(user_weight_mult, buffs)
            # Rod
            try:
                if hasattr(self.bot, "data"):
                    rl = self.bot.data.get_rod_level(ctx.author.id)
                    rod_data = ROD_TIERS.get(rl, {})
                    luck += _safe_float(rod_data.get('luck', 0))
                    user_weight_mult = _apply_w_mult(user_weight_mult, rod_data)
            except Exception:
                pass
            # Weather-provided luck buff (if any)
            try:
                luck += _safe_float(w_info.get('buff', {}).get('luck', 0))
            except Exception:
                pass
        except Exception:
            pass


        # 2) Tạo thử thách
        challenge_emojis, expected_letters = gen_challenge(n_min, n_max)

        demo = f"{EMO_D}=d  {EMO_F}=f  {EMO_J}=j  {EMO_K}=k"
        embed = discord.Embed(
            title="🎣 Thử thách câu cá",
            description=(
                f"**{ctx.author.display_name}**\n"
                f"Trong **{timeout:.1f}s**, hãy nhập **chỉ** các chữ cái **dfjk** đúng với chuỗi emoji sau (theo thứ tự):\n"
                f"{challenge_emojis}\n"
            ),
            color=0xE67E22,
        )
        bonus_parts = []
        if total_timeout_add:
            bonus_parts.append(f"+{total_timeout_add:.1f}s time")
        if total_len_sub:
            bonus_parts.append(f"-{int(total_len_sub)} len")
        # show current rod & user's luck in footer
        try:
            footer_luck = f" | Luck hiện tại: {luck:.2f}"
        except Exception:
            footer_luck = ""
        embed.set_footer(text=f"Cấp cần: Lv.{lvl} — {tier['name']}{footer_luck}")
        
        # Xử lý hiển thị thử thách (Ephemeral nếu là Slash Command)
        if ctx.interaction:
            guide_msg = await ctx.send(embed=embed, ephemeral=True)
        else:
            # Text command: Xóa lệnh gọi và gửi tin nhắn thường
            try:
                await ctx.message.delete()
            except Exception:
                pass
            guide_msg = await ctx.send(embed=embed)

        # 3) Chờ input trong thời gian 'timeout'
        def check(m: discord.Message) -> bool:
            return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id

        try:
            reply: discord.Message = await self.bot.wait_for("message", timeout=timeout, check=check)
        except asyncio.TimeoutError:
            await ctx.send(f"⏰ {ctx.author.mention} Quá chậm! Cá đã bơi mất!")
            return

        user_letters = normalize_letters(reply.content)

        # 4) Kiểm tra kết quả
        if user_letters != expected_letters:
            await ctx.send(f"❌ {ctx.author.mention} Nhập sai chuỗi, cá đã bơi mất!")
            return

        # --- THUẬT TOÁN CÂU CÁ MỚI (Weighted Random + Luck) ---
        rarities = []
        final_weights = []
        
        for r, cfg in FISHING_CONFIG.items():
            base = cfg.get("base_weight", 0)
            factor = cfg.get("luck_factor", 0)
            # Công thức: Weight_Cuối = Base * (1 + (Luck * Factor / 100))
            w = base * (1 + (luck * factor / 100.0))
            rarities.append(r)
            final_weights.append(w)
            
        # Chọn ngẫu nhiên theo trọng số
        picked_rarity = random.choices(rarities, weights=final_weights, k=1)[0]
        
        # Tính phần trăm hiển thị (cho debug/log)
        total_w = sum(final_weights)
        perc = {r: (w / total_w) * 100 for r, w in zip(rarities, final_weights)}

        # Determine if a weather special overrides
        selected_special = None
        if weather_specials:
            for s in weather_specials:
                try:
                    if s.get('rarity') != picked_rarity:
                        continue
                    pool_len = max(1, len(FISH_POOLS.get(picked_rarity, [])))
                    avg_normal = 1.0 / pool_len
                    specified = s.get('chance', None)
                    if specified is None:
                        chance = avg_normal * SPECIAL_VS_NORMAL_SCALE
                    else:
                        chance = min(float(specified), avg_normal * 0.95)
                    if random.random() < float(chance):
                        selected_special = s
                        break
                except Exception:
                    continue

        fish_name = None
        fish_emoji = ""
        fish_entry = None
        is_shiny = False
        if selected_special:
            fish_name = selected_special.get('name')
            fish_emoji = selected_special.get('emoji', '')
            # treat special as normal capture (no shiny)
        else:
            fish_entry = self.pick_fish_by_rate(picked_rarity)
            fish_name = fish_entry.get('name')
            fish_emoji = fish_entry.get('emoji', '')
            # shiny chance
            fish_shiny_mult = float(fish_entry.get('shiny_mult', 1.0))
            shiny_chance = float(SHINY_BASE) * fish_shiny_mult * weather_shiny_mult
            is_shiny = random.random() < shiny_chance

        # Determine weight class by probability
        try:
            probs = [WEIGHT_CLASS_PROBS.get(n, 0) for n in WEIGHT_CLASS_NAMES]
            wc = random.choices(WEIGHT_CLASS_NAMES, weights=probs, k=1)[0]
        except Exception:
            wc = random.choice(WEIGHT_CLASS_NAMES)

        # Determine a base_weight (kg) for the fish: per-fish override 'base_weight' (expected integer),
        # otherwise derive from rarity default range midpoint.
        try:
            source = fish_entry if fish_entry else (selected_special if selected_special else {})
            if source and (source.get('base_weight') is not None):
                base_w = float(source.get('base_weight'))
            else:
                wmin, wmax = WEIGHT_BY_RARITY.get(picked_rarity, (0.5, 2.0))
                base_w = (float(wmin) + float(wmax)) / 2.0
        except Exception:
            base_w = 1.0

        # Percent ranges per class: try to get from config, otherwise use defaults
        try:
            pct_ranges = WEIGHT_CLASS_PCT_RANGES
        except Exception:
            pct_ranges = {
                'tiny': (0.5, 0.7),
                'normal': (0.9, 1.1),
                'huge': (1.5, 2.5),
                'gigantic': (5.0, 7.0),
            }

        try:
            pmin, pmax = pct_ranges.get(wc, (0.9, 1.1))
            weight = round(base_w * random.uniform(float(pmin), float(pmax)), 2)
        except Exception:
            weight = round(base_w * random.uniform(0.9, 1.1), 2)

        # Apply weather weight multiplier if present (e.g., storm/rain buffs)
        try:
            w_mult = float(w_info.get('buff', {}).get('weight_mult', 1.0)) if isinstance(w_info, dict) else 1.0
            weight = round(weight * w_mult * user_weight_mult, 2)
        except Exception:
            pass

        # Price computation: allow per-fish override
        try:
            price_per_kg = (fish_entry.get('price_per_kg') if fish_entry and fish_entry.get('price_per_kg') is not None else (selected_special.get('price_per_kg') if selected_special and selected_special.get('price_per_kg') is not None else PRICE_PER_KG_BY_RARITY.get(picked_rarity, 10)))
        except Exception:
            price_per_kg = PRICE_PER_KG_BY_RARITY.get(picked_rarity, 10)
        sell_price = int(price_per_kg * weight * (SHINY_SELL_MULT if is_shiny else 1))

        # Build fish object and persist
        fish_obj = {
            "id": str(uuid.uuid4()),
            "name": fish_name,
            "rarity": picked_rarity,
            "weight": weight,
            "weight_class": wc,
            "price_per_kg": price_per_kg,
            "sell_price": sell_price,
            "caught_at": int(time.time()),
            "shiny": bool(is_shiny),
        }
        try:
            if hasattr(self.bot, "data"):
                await self.bot.data.add_caught_fish(ctx.author.id, fish_obj)
        except Exception:
            pass

        dropped_item_ids = []
        # Very small chance to drop an item like before
        try:
            try:
                from game_items import ITEMS as GAME_ITEMS
            except Exception:
                GAME_ITEMS = {}
            drop_chance = 0.00036
            if GAME_ITEMS and random.random() < drop_chance:
                item_id = random.choice(list(GAME_ITEMS.keys()))
                try:
                    if hasattr(self.bot, "data"):
                        await self.bot.data.add_item(ctx.author.id, item_id)
                except Exception:
                    pass
                dropped_item_ids.append(item_id)
        except Exception:
            pass

        # Prepare breakdowns for display (single-catch result)
        try:
            breakdown_normal = {picked_rarity: {}}
            breakdown_shiny = {picked_rarity: {}}
            if is_shiny:
                breakdown_shiny[picked_rarity][fish_name] = 1
            else:
                breakdown_normal[picked_rarity][fish_name] = 1
        except Exception:
            breakdown_normal = {picked_rarity: {fish_name: 1}} if not is_shiny else {picked_rarity: {}}
            breakdown_shiny = {picked_rarity: {fish_name: 1}} if is_shiny else {picked_rarity: {}}

        # Award XP once per successful catch (không tính theo số cá)
        try:
            xp_amount = int(XP_PER_CATCH)
        except Exception:
            xp_amount = 20
        try:
            # dispatch sự kiện để cog riêng xử lý XP / level
            if hasattr(self.bot, "dispatch"):
                self.bot.dispatch("fish_caught", ctx.author.id, xp_amount, ctx.channel.id)
        except Exception:
            pass

        # --- GEMS: tính gem trao thưởng theo độ hiếm và thời tiết (ví dụ: epic -> gem)
        gems_awarded = 0
        try:
            gp = GEM_SETTINGS.get('gem_per_rarity', {}) if isinstance(GEM_SETTINGS, dict) else {}
            for r in breakdown_normal.keys():
                cnt = sum(breakdown_normal.get(r, {}).values()) + sum(breakdown_shiny.get(r, {}).values())
                gems_awarded += cnt * int(gp.get(r, 0))
            # Nếu thời tiết aurora hoặc có gem multiplier trong buff thì áp dụng
            w_key, w_info = self.get_current_weather()
            wm = 1
            try:
                wm = int(w_info.get('buff', {}).get('gem_mult', GEM_SETTINGS.get('aurora_multiplier', 1)))
            except Exception:
                wm = int(GEM_SETTINGS.get('aurora_multiplier', 1))
            gems_awarded = int(gems_awarded * wm)
            if gems_awarded > 0 and hasattr(self.bot, 'data'):
                await self.bot.data.add_gems(ctx.author.id, gems_awarded)
        except Exception:
            gems_awarded = 0

        # 6) Render kết quả bắt được
        # Tạo map tên cá -> emoji để hiển thị emoji trong kết quả
        FISH_EMO_MAP: Dict[str, str] = {}
        for pool in FISH_POOLS.values():
            for f in pool:
                FISH_EMO_MAP[f.get("name", "")] = f.get("emoji", "")
        # Thêm cá đặc biệt vào map emoji
        for w in WEATHER_CONFIG.values():
            for f in w.get("special_fish", []):
                FISH_EMO_MAP[f.get("name", "")] = f.get("emoji", "")

        def fmt_bucket_normal_shiny(normal_bucket: Dict[str, int], shiny_bucket: Dict[str, int], use_emoji: bool = True) -> str:
            # Combine and show shiny first with sparkle emoji, then normal. Optionally suppress fish emoji for compact display.
            names = set(list(normal_bucket.keys()) + list(shiny_bucket.keys()))
            if not names:
                return "_Trống_"
            parts = []
            for n in sorted(names):
                s = shiny_bucket.get(n, 0)
                g = normal_bucket.get(n, 0)
                em = FISH_EMO_MAP.get(n, "")
                # shiny entries
                if s > 0:
                    if em and use_emoji:
                        parts.append(f"{SPARKLE}{em} ×{s}")
                    else:
                        parts.append(f"{SPARKLE}{n} ×{s}")
                # normal entries
                if g > 0:
                    if em and use_emoji:
                        parts.append(f"{em} ×{g}")
                    else:
                        parts.append(f"{n} ×{g}")
            return ", ".join(parts)

        # Compute totals and rarity lines for display
        try:
            total_caught = sum(sum(b.values()) for b in breakdown_normal.values()) + sum(sum(b.values()) for b in breakdown_shiny.values())
        except Exception:
            total_caught = 1
        rarity_lines = []
        for r in FISHING_CONFIG.keys():
            nb = breakdown_normal.get(r, {})
            sb = breakdown_shiny.get(r, {})
            if nb or sb:
                rarity_lines.append(
                    f"**{RARITY_DISPLAY.get(r, r.title())}** ({perc.get(r, 0.0):.1f}%): {fmt_bucket_normal_shiny(nb, sb, use_emoji=False)}"
                )

        # Hiển thị thời tiết hiện tại
        weather_name, weather_info = self.get_current_weather()
        weather_display = weather_info.get("name", weather_name)
        color = 0x58D68D

        # Fish summary
        try:
            caught = fish_obj
            em = FISH_EMO_MAP.get(caught.get('name', ''), '')
            shiny_mark = SPARKLE if caught.get('shiny') else ''
            fish_summary = f"{shiny_mark}{em} **{caught.get('name')}** — {RARITY_DISPLAY.get(caught.get('rarity'), caught.get('rarity'))} | {caught.get('weight')}kg ({caught.get('weight_class')}) | Giá ước tính: **{caught.get('sell_price'):,}** coins"
        except Exception:
            fish_summary = "_Không có dữ liệu con cá_"

        # Chuẩn bị nội dung embed; thêm thông tin item rớt nếu có
        description_text = f"Thời tiết: **{weather_display}**\n\n**Cá bạn câu được:**\n{fish_summary}\n\n" + "\n".join(rarity_lines)
        if dropped_item_ids:
            try:
                from game_items import ITEMS as GAME_ITEMS
            except Exception:
                GAME_ITEMS = {}
            for item_id in dropped_item_ids:
                it = GAME_ITEMS.get(item_id, {})
                disp = f"{it.get('emoji','')} {it.get('name', item_id)}" if it else item_id
                description_text += f"\n**Cổ vật** (??): {disp}"
        # Thông báo thêm gem nếu có
        try:
            if 'gems_awarded' in locals() and gems_awarded > 0:
                description_text += f"\n💎 **Gems nhận được:** {gems_awarded}"
        except Exception:
            pass

        result = discord.Embed(
            title=f"🎣 Thành công! **{ctx.author.display_name}** đã câu được **{total_caught}** con",
            description=description_text,
            color=color
        )
        result.set_footer(text=f"Cần: Lv.{lvl} — {tier['name']}")
        # Gửi kết quả công khai vào kênh (để không bị ẩn nếu dùng Slash Command)
        await ctx.channel.send(embed=result)

    @commands.hybrid_command(name="weather", help="Xem thời tiết hiện tại và các thông tin liên quan (buff / special fish).")
    async def weather(self, ctx: commands.Context):
        # Hiển thị weather hiện tại (key, tên hiển thị, duration, rate, buff, special fish list)
        key, info = self.get_current_weather()
        name = info.get('name', key)
        rate = info.get('rate', 'N/A')
        buff = info.get('buff', {}) if isinstance(info, dict) else {}
        specials = info.get('special_fish', []) if isinstance(info, dict) else []

        # Visuals mapping (Emoji & Color)
        visuals = {
            "clear":  {"emoji": "☀️", "color": 0xF1C40F},
            "rain":   {"emoji": "🌧️", "color": 0x3498DB},
            "storm":  {"emoji": "⛈️", "color": 0x8E44AD},
            "fog":    {"emoji": "🌫️", "color": 0x95A5A6},
            "meteor": {"emoji": "🌠", "color": 0xE67E22},
            "aurora": {"emoji": "🌌", "color": 0x1ABC9C},
        }
        vis = visuals.get(key, {"emoji": "🌦️", "color": 0x3498DB})

        # Compute normalized rate as percent of total weather weights (rate / sum of all rates)
        try:
            rate_val = float(rate)
            try:
                total_rate = sum(float(v.get('rate', 0)) for v in WEATHER_CONFIG.values())
            except Exception:
                total_rate = 0.0
            if total_rate and total_rate > 0:
                rate_disp = f"{(rate_val / total_rate) * 100:.1f}%"
            else:
                rate_disp = f"{rate_val*100:.1f}%" if 0 <= rate_val <= 1 else f"{rate_val:.2f}"
        except Exception:
            rate_disp = str(rate)

        if self.weather_end_time and self.weather_end_time > time.time():
            duration_display = f"<t:{int(self.weather_end_time)}:R>"
        else:
            duration_display = "Đang chuyển đổi..."

        embed = discord.Embed(title=f"{vis['emoji']} Thời tiết: {name}", description=f"Hiện tại đang là **{name}**.", color=vis['color'])
        
        # Info field with buffs
        info_txt = f"⏱️ **Kết thúc:** {duration_display}\n📊 **Tỉ lệ:** {rate_disp}"
        if buff:
            buff_parts = []
            if 'luck' in buff: buff_parts.append(f"🍀 Luck: +{buff['luck']}")
            if 'weight_mult' in buff: buff_parts.append(f"⚖️ Weight: x{buff['weight_mult']}")
            if 'shiny_mult' in buff: buff_parts.append(f"✨ Shiny: x{buff['shiny_mult']}")
            if 'gem_mult' in buff: buff_parts.append(f"💎 Gem: x{buff['gem_mult']}")
            if buff_parts:
                info_txt += "\n\n**✨ Hiệu ứng (Buffs):**\n" + "\n".join([f"> {b}" for b in buff_parts])
        
        embed.add_field(name="ℹ️ Thông tin chung", value=info_txt, inline=False)

        # Special fish breakdown: compute per-catch probability while this weather is active
        if specials:
            # Group by rarity
            sp_by_rarity = {}
            for s in specials:
                r = s.get('rarity')
                sp_by_rarity.setdefault(r, []).append(s)

            total_base_weight = sum(cfg.get('base_weight', 0) for cfg in FISHING_CONFIG.values())
            sp_lines = []
            for rarity, arr in sp_by_rarity.items():
                n_same = len(arr)
                pool = FISH_POOLS.get(rarity, [])
                pool_len = len(pool)
                for s in arr:
                    # chance when rarity chosen (either explicit or auto-derived from pool size)
                    raw_ch = s.get('chance')
                    if raw_ch is None:
                        raw_ch = (SPECIAL_VS_NORMAL_SCALE / pool_len) if pool_len else 0.0
                    # Probability of picking this rarity
                    base_w = FISHING_CONFIG.get(rarity, {}).get('base_weight', 0)
                    p_r = (base_w / total_base_weight) if total_base_weight else 0.0
                    # Given that rarity was chosen, we select one special uniformly among same-rarity specials, then apply its chance
                    per_catch_prob = p_r * (1.0 / n_same) * raw_ch
                    sp_lines.append(f"> {s.get('emoji','')} **{s.get('name')}** ({rarity}) — `{per_catch_prob*100:.3f}%`")
            embed.add_field(name="🐟 Cá đặc biệt", value="\n".join(sp_lines), inline=False)
        else:
            embed.add_field(name="🐟 Cá đặc biệt", value="> *Không có cá đặc biệt trong thời tiết này.*", inline=False)

        await ctx.send(embed=embed, ephemeral=True if ctx.interaction else False)

    @commands.hybrid_command(name="testluck", help="Test tỷ lệ câu cá với Luck tùy chỉnh (Simulation).")
    async def testluck(self, ctx, luck_val: float = 0.0, trials: int = 10000):
        """Chạy thử nghiệm thuật toán câu cá với chỉ số Luck nhất định."""
        results = {r: 0 for r in FISHING_CONFIG.keys()}
        
        # Pre-calculate weights for speed
        rarities = []
        weights = []
        for r, cfg in FISHING_CONFIG.items():
            base = cfg["base_weight"]
            factor = cfg["luck_factor"]
            w = base * (1 + (luck_val * factor / 100.0))
            rarities.append(r)
            weights.append(w)
            
        # Run simulation
        picks = random.choices(rarities, weights=weights, k=trials)
        for p in picks:
            results[p] += 1
            
        lines = [f">>Simulation (Luck={luck_val}, Trials={trials})<<"]
        for r in FISHING_CONFIG.keys():
            count = results[r]
            p = (count / trials) * 100
            lines.append(f"{r.capitalize():<10}: {count:<5} ({p:.2f}%)")
            
        await ctx.send("```\n" + "\n".join(lines) + "\n```")

    @fish.error
    async def fish_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏳ Chờ **{error.retry_after:.1f}s** rồi câu tiếp nhé!", delete_after=3)
        elif isinstance(error, commands.MaxConcurrencyReached):
            await ctx.send("⏳ Đang xử lý lệnh trước của bạn, vui lòng đợi...", delete_after=3)
        else:
            await ctx.send("❌ Lỗi khi câu cá, thử lại sau.")


async def setup(bot: commands.Bot):
    await bot.add_cog(FishCog(bot))