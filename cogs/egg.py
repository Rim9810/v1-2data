import asyncio
import time
import random
import discord
from discord.ext import commands
from uuid import uuid4

try:
    from game_pets import EGG_SHOP, EGG_TIERS, PETS, RARITY_WEIGHTS, EGG_LIMIT, RARITY_LETTER, RARITY_ORDER
except Exception:
    EGG_SHOP = {}
    EGG_TIERS = {}
    PETS = {}
    RARITY_WEIGHTS = {}
    EGG_LIMIT = 2
    RARITY_LETTER = {}
    RARITY_ORDER = []


class EggCog(commands.Cog, name="Pet"):
    """Nuôi thú cưng tăng các chỉ số"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._task = None

    @commands.Cog.listener()
    async def on_ready(self):
        if not self._task:
            self._task = asyncio.create_task(self._egg_watcher())

    def cog_unload(self):
        try:
            if self._task:
                self._task.cancel()
        except Exception:
            pass

    def _rarity_letter(self, rarity: str) -> str:
        """Return the single-letter representation for a rarity.
        Returns an empty string when rarity is missing/unknown so callers can
        conditionally omit the display."""
        if not rarity:
            return ""
        try:
            if RARITY_LETTER and rarity in RARITY_LETTER:
                return RARITY_LETTER[rarity]
        except Exception:
            pass
        return rarity[:1].upper()

    def _format_buffs(self, buffs: dict) -> str:
        if not buffs:
            return ""
        parts = []
        if buffs.get('luck'):
            parts.append(f"+{float(buffs.get('luck')):.2f} luck")
        if buffs.get('timeout_add'):
            parts.append(f"+{float(buffs.get('timeout_add')):.1f}s")
        if buffs.get('len_sub'):
            parts.append(f"-{int(buffs.get('len_sub'))} chữ")
        if buffs.get('xp_flat'):
            parts.append(f"+{int(buffs.get('xp_flat'))} XP")
        if buffs.get('extra_slot'):
            parts.append(f"+{int(buffs.get('extra_slot'))} slot đồ")
        if buffs.get('weight_mult'):
            parts.append(f"x{float(buffs.get('weight_mult')):.2f} weight")
        return " | ".join(parts)

    async def eggshop(self, ctx: commands.Context, interaction: discord.Interaction = None):
        """Internal: paginated egg shop — one page per tier. Uses Buttons."""
        if not EGG_SHOP:
            msg = "❌ Cửa hàng trứng chưa được định nghĩa."
            if interaction:
                await interaction.response.send_message(msg, ephemeral=True)
            else:
                await ctx.send(msg)
            return

        # Build pages: one page per tier
        pages = []
        tiers = sorted(EGG_SHOP.items())
        for tier, info in tiers:
            pets = EGG_TIERS.get(tier, [])
            # Build unique pet list preserving order
            seen = set()
            unique_pets = []
            for pid in pets:
                if pid in seen:
                    continue
                seen.add(pid)
                unique_pets.append(pid)

            # Compute rarity weights and total
            weights = []
            for pid in unique_pets:
                p = PETS.get(pid, {})
                r = p.get('rarity', 'common')
                w = float(RARITY_WEIGHTS.get(r, 1))
                weights.append(w)
            total = sum(weights) if weights else 0

            pet_lines = []
            for pid in unique_pets:
                p = PETS.get(pid, {})
                name = p.get('name', pid)
                emoji = p.get('emoji', '')
                rarity = p.get('rarity', 'common')
                r_letter = self._rarity_letter(rarity)
                rarity_display = f" [{r_letter}]" if r_letter else ""
                w = float(RARITY_WEIGHTS.get(rarity, 1))
                prob = (w / total * 100.0) if total > 0 else (100.0 / len(unique_pets) if unique_pets else 0)
                buff_str = self._format_buffs(p.get('buffs', {}))
                buff_display = f" [{buff_str}]" if buff_str else ""
                pet_lines.append(f"`{pid}`{rarity_display} {emoji} **{name}**{buff_display} — {prob:.2f}%")

            desc_lines = [f"**Tier {tier}** — **{info.get('price')}** coins • Ấp {info.get('time')}s"]
            if pet_lines:
                desc_lines.append("\n".join(pet_lines))
            else:
                desc_lines.append("_Không có pet trong tier này._")
            pages.append((tier, info, "\n\n".join(desc_lines)))

        # View Class for Pagination
        class EggShopView(discord.ui.View):
            def __init__(self, pages):
                super().__init__(timeout=60)
                self.pages = pages
                self.current = 0

            def _get_embed(self):
                tier, info, body = self.pages[self.current]
                em = discord.Embed(title=f"🥚 Cửa hàng trứng — Tier {tier} ({self.current+1}/{len(self.pages)})", description=body, color=0xFFD580)
                em.set_footer(text=f"Trang {self.current+1}/{len(self.pages)} • Dùng `/buy egg <tier>` để mua")
                return em

            @discord.ui.button(label="◀️ Trước", style=discord.ButtonStyle.secondary)
            async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.current = (self.current - 1) % len(self.pages)
                await interaction.response.edit_message(embed=self._get_embed(), view=self)

            @discord.ui.button(label="Sau ▶️", style=discord.ButtonStyle.secondary)
            async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.current = (self.current + 1) % len(self.pages)
                await interaction.response.edit_message(embed=self._get_embed(), view=self)

        view = EggShopView(pages)
        # Initial embed
        embed = view._get_embed()
        if interaction:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            await ctx.send(embed=embed, view=view)

    async def buyegg(self, ctx: commands.Context, tier: int | None = None):
        # Be robust: accept tier as int or str and validate against EGG_SHOP keys
        if tier is None:
            await ctx.send("❗ Dùng: `/buy egg <tier>` (ví dụ `/buy egg 1`). Dùng `/index pets` để xem danh sách pet.")
            return
        # find matching key in EGG_SHOP (support int keys or string keys)
        key = None
        try:
            ti = int(tier)
            for k in EGG_SHOP.keys():
                try:
                    if int(k) == ti:
                        key = k
                        break
                except Exception:
                    # fallback: direct equality
                    if k == ti or k == str(ti):
                        key = k
                        break
        except Exception:
            # Tier not integer-like, try direct membership
            if tier in EGG_SHOP:
                key = tier

        if key is None:
            # show available tiers and prices
            lines = [f"Tier {int(k)} — price: {v.get('price')} coins" for k, v in sorted(EGG_SHOP.items(), key=lambda x: int(x[0]) if isinstance(x[0], int) or (isinstance(x[0], str) and x[0].isdigit()) else x[0])]
            await ctx.send("❗ Tier không hợp lệ. Các tier sẵn có:\n" + "\n".join(lines))
            return

        if not hasattr(self.bot, "data"):
            await ctx.send("❌ Chưa cấu hình DataManager (bot.data).")
            return
        # Kiểm tra số trứng đang ấp của người chơi
        try:
            current_eggs = self.bot.data.get_eggs(ctx.author.id)
        except Exception:
            current_eggs = []
        if len(current_eggs) >= int(EGG_LIMIT):
            await ctx.send(f"❌ Bạn chỉ được ấp tối đa **{EGG_LIMIT}** trứng cùng lúc. Hãy chờ một trứng nở hoặc hủy trứng để mua thêm.")
            return

        info = EGG_SHOP[key]
        price = info.get("price")
        bal = self.bot.data.get_balance(ctx.author.id)
        if bal < price:
            await ctx.send(f"❌ Bạn cần **{price}** coins để mua trứng Tier {int(key)}. Bạn có: **{bal}**.")
            return
        # trừ tiền
        await self.bot.data.add_money(ctx.author.id, -price)
        egg_id = uuid4().hex
        hatch_at = int(time.time() + int(info.get("time", 0)))
        await self.bot.data.add_egg(ctx.author.id, {"id": egg_id, "tier": int(key), "hatch_at": hatch_at, "bought_at": int(time.time())})
        await ctx.send(f"✅ Đã mua trứng **Tier {int(key)}**. Trứng sẽ nở <t:{hatch_at}:R>. Dùng lệnh `/egg` để xem tiến trình ấp (nhớ `/hatch` để ấp) nhé!")

    @commands.hybrid_command(name="egg", aliases=["eggs"], help="Xem trứng của bạn (đang ấp)")
    async def myeggs(self, ctx: commands.Context):
        if not hasattr(self.bot, "data"):
            await ctx.send("❌ Chưa cấu hình DataManager (bot.data).")
            return
        eggs = self.bot.data.get_eggs(ctx.author.id)
        if not eggs:
            await ctx.send("_Bạn không có trứng nào đang ấp._")
            return
        lines = []
        now = int(time.time())
        for idx, e in enumerate(eggs, start=1):
            hatch_at = int(e.get("hatch_at", 0))
            egg_id = e.get("id", "")
            if hatch_at <= now:
                lines.append(f"{idx}. **Tier {e.get('tier')}** — **Có thể ấp trứng!!** — `{egg_id}`")
            else:
                lines.append(f"{idx}. **Tier {e.get('tier')}** — nở <t:{hatch_at}:R> — `{egg_id}`")
        embed = discord.Embed(title=f"🥚 Trứng của {ctx.author.display_name} — Đang ấp {len(eggs)}/{EGG_LIMIT}", description="\n".join(lines), color=0xFFD580)
        embed.set_footer(text="Dùng `/hatch <số thứ tự|all>` để mở trứng đã chín.")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="hatch", help="Mở trứng đã chín: `/hatch <số thứ tự|all>`")
    async def hatch(self, ctx: commands.Context, idx: str | None = None):
        """Mở trứng đã đủ lớn theo số thứ tự (1-based) hoặc `all` để mở tất cả trứng đã chín."""
        if not hasattr(self.bot, "data"):
            await ctx.send("❌ Chưa cấu hình DataManager (bot.data).")
            return
        eggs = self.bot.data.get_eggs(ctx.author.id)
        if not eggs:
            await ctx.send("_Bạn không có trứng nào đang ấp._")
            return
        now = int(time.time())
        if not idx:
            await ctx.send("❗ Dùng: `/hatch <số thứ tự|all>` — ví dụ `/hatch 1` hoặc `/hatch all`.")
            return
        # Hatch all ready eggs
        if isinstance(idx, str) and idx.lower() == "all":
            ready = [(i, e) for i, e in enumerate(eggs, start=1) if int(e.get("hatch_at", 0)) <= now]
            if not ready:
                await ctx.send("⌛ Không có trứng nào có thể ấp để nở.")
                return
            results = []
            for i, e in ready:
                r = await self._hatch_one(ctx.author.id, e)
                if r:
                    results.append(r)
            # Aggregate duplicate pets and format output
            agg: dict = {}
            for chosen, name, emoji, rarity, prob, egg_id in results:
                if chosen not in agg:
                    agg[chosen] = {"name": name, "emoji": emoji, "rarity": rarity, "prob": prob, "count": 0}
                agg[chosen]["count"] += 1
            lines = []
            for chosen, info in agg.items():
                count = info["count"]
                buff_str = self._format_buffs(PETS.get(chosen, {}).get('buffs', {}))
                buff_display = f" [{buff_str}]" if buff_str else ""
                count_display = f" ×{count}" if count > 1 else ""
                rarity_letter = self._rarity_letter(info.get("rarity", ""))
                rarity_display = f" — Độ hiếm: [{rarity_letter}]" if rarity_letter else ""
                lines.append(f"🥚 Trứng đã nở: {info['emoji']} **{info['name']}** (`{chosen}`){count_display}{buff_display}{rarity_display} — Tỉ lệ: {info['prob']:.2f}%")
            await ctx.send("\n".join(lines))
            return
        # Hatch a single egg by index
        try:
            n = int(idx)
        except Exception:
            await ctx.send("❌ Tham số không hợp lệ. Dùng số thứ tự trứng (ví dụ `/hatch 1`) hoặc `all`.")
            return
        if n < 1 or n > len(eggs):
            await ctx.send(f"❌ Số thứ tự trứng không hợp lệ. Có {len(eggs)} trứng.")
            return
        egg = eggs[n - 1]
        if int(egg.get("hatch_at", 0)) > now:
            await ctx.send("⌛ Trứng này chưa chín. Hãy chờ đến thời gian nở.")
            return
        res = await self._hatch_one(ctx.author.id, egg)
        if not res:
            await ctx.send("❌ Lỗi khi nở trứng, thử lại sau.")
            return
        chosen, name, emoji, rarity, prob, egg_id = res
        buff_str = self._format_buffs(PETS.get(chosen, {}).get('buffs', {}))
        buff_display = f" [{buff_str}]" if buff_str else ""
        rarity_letter = self._rarity_letter(rarity)
        rarity_display = f" — Độ hiếm: [{rarity_letter}]" if rarity_letter else ""
        await ctx.send(f"🥚 Trứng đã nở: {emoji} **{name}** (`{chosen}`){buff_display}{rarity_display} — Tỉ lệ: {prob:.2f}%")

    async def _hatch_one(self, user_id: int, egg: dict):
        """Hatch một trứng: chọn pet, thêm pet cho user, xóa trứng, trả về (pet_id, name, emoji, rarity, prob, egg_id) hoặc None nếu lỗi."""
        tier = int(egg.get("tier", 1))
        choices = EGG_TIERS.get(tier, [])
        if not choices:
            choices = list(PETS.keys())
        # Tính trọng số theo rarity
        weights = []
        for pid in choices:
            p = PETS.get(pid, {})
            r = p.get("rarity", "common")
            w = float(RARITY_WEIGHTS.get(r, 1))
            weights.append(w)
        total = sum(weights)
        if total <= 0:
            chosen = random.choice(choices)
            prob = 100.0 / len(choices)
        else:
            chosen = random.choices(choices, weights=weights, k=1)[0]
            weight_chosen = weights[choices.index(chosen)]
            prob = (weight_chosen / total) * 100.0
        try:
            await self.bot.data.add_pet(int(user_id), chosen)
            await self.bot.data.remove_egg(int(user_id), egg.get("id"))
        except Exception:
            return None
        # Notify via DM if possible
        try:
            p = PETS.get(chosen, {})
            name = p.get("name", chosen)
            emoji = p.get("emoji", "")
            rarity = p.get("rarity", "")
            buff_str = self._format_buffs(p.get('buffs', {}))
            buff_display = f" [{buff_str}]" if buff_str else ""
            rarity_letter = self._rarity_letter(rarity)
            rarity_display = f" — Độ hiếm: [{rarity_letter}]" if rarity_letter else ""
            msg = f"🥚 Trứng của bạn đã nở! Bạn nhận được **{emoji} {name}** (`{chosen}`){buff_display}{rarity_display} — Tỉ lệ: {prob:.2f}%"
            user = self.bot.get_user(int(user_id))
            if user:
                await user.send(msg)
        except Exception:
            # ignore DM errors
            pass
        return (chosen, name, emoji, rarity, prob, egg.get("id"))

    @commands.hybrid_command(name="pet", aliases=["pets"], help="Xem pet của người chơi: `/pet [@user]` (mặc định: bạn)")
    async def show_pets(self, ctx: commands.Context, member: discord.Member | None = None):
        if not hasattr(self.bot, "data"):
            await ctx.send("❌ Chưa cấu hình DataManager (bot.data).")
            return

        target = member or ctx.author
        is_self = target.id == ctx.author.id

        pids = self.bot.data.get_pets(target.id)
        active = []
        try:
            active = self.bot.data.get_active_pets(target.id)
        except Exception:
            active = []
        if not pids:
            await ctx.send(f"_Người dùng {target.display_name} chưa có pet nào._" if not is_self else "_Bạn chưa có pet nào._")
            return

        # Tính limit ô pet theo cấp của target
        try:
            lvl = self.bot.data.get_level(target.id)
        except Exception:
            lvl = 1
        slot_limit = 3 if lvl >= 10 else 2

        # Build unique list and counts
        seen = {}
        unique = []
        for pid in pids:
            if pid in seen:
                seen[pid] += 1
            else:
                seen[pid] = 1
                unique.append(pid)

        # Sort unique pets by rarity using RARITY_ORDER
        def sort_key(pid):
            base = pid.split('_', 1)[0] if '_' in pid else pid
            p = PETS.get(base, {})
            r = p.get('rarity', 'common')
            try:
                idx = RARITY_ORDER.index(r) if RARITY_ORDER else 0
            except Exception:
                idx = 0
            return (idx, p.get('name', ''))
        unique.sort(key=sort_key)

        # Format output lines
        lines = []
        for pid in unique:
            is_active = pid in active
            status = "Active" if is_active else "Inactive"

            base = pid.split('_', 1)[0] if '_' in pid else pid
            p = PETS.get(pid) or PETS.get(base)

            if not p:
                name = pid
                emoji = ''
                rarity = ''
                buff_str = ''
            else:
                name = p.get('name', base)
                emoji = p.get('emoji', '')
                rarity = p.get('rarity', '')
                buff_str = self._format_buffs(p.get('buffs', {}))

            r_letter = self._rarity_letter(rarity)
            count = seen.get(pid, 1)
            count_display = f"×{count}" if count > 1 else ""

            parts = [f"`{pid}`"]
            if r_letter:
                parts.append(f"[{r_letter}]")
            if emoji:
                parts.append(emoji)
            parts.append(f"**{name}**")
            if buff_str:
                parts.append(f"[{buff_str}]")

            line = " ".join(parts) + f" - [{status}]"
            lines.append(line)

        title = f"🐾 Pet của {target.display_name} — Ô dùng {len(active)}/{slot_limit}"
        embed = discord.Embed(title=title, description="\n".join(lines), color=0xB2FFDA)
        if is_self:
            embed.set_footer(text=f"Dùng /peton <id> / /petoff <id | all> để quản lý ô pet (Giới hạn: {slot_limit}).")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="peton", help="Kích hoạt pet đang sở hữu: /peton <pet_id> — giới hạn sử dụng 2 (3 khi Lv.10)")
    async def usepet(self, ctx: commands.Context, pet_id: str | None = None):
        if not hasattr(self.bot, "data"):
            await ctx.send("❌ Chưa cấu hình DataManager (bot.data).")
            return
        if not pet_id:
            await ctx.send("❗ Dùng: /peton <pet_id>")
            return
        owned = self.bot.data.get_pets(ctx.author.id)
        if pet_id not in owned:
            await ctx.send(f"❌ Bạn không sở hữu pet `{pet_id}`.")
            return
        # limit
        try:
            lvl = self.bot.data.get_level(ctx.author.id)
        except Exception:
            lvl = 1
        limit = 3 if lvl >= 10 else 2
        active = self.bot.data.get_active_pets(ctx.author.id)
        if pet_id in active:
            await ctx.send(f"ℹ️ Pet `{pet_id}` đã đang được sử dụng.")
            return
        if len(active) >= limit:
            await ctx.send(f"❌ Bạn chỉ có thể sử dụng tối đa **{limit}** pet (Lv.{lvl}). Hãy bỏ một pet trước khi thêm.")
            return
        await self.bot.data.add_active_pet(ctx.author.id, pet_id)
        p = PETS.get(pet_id, {})
        await ctx.send(f"✅ Đã active pet **{p.get('emoji','')} {p.get('name', pet_id)}** (`{pet_id}`).")

    @commands.hybrid_command(name="petoff", help="Bỏ pet: /petoff <pet_id | all>")
    async def unusepet(self, ctx: commands.Context, pet_id: str | None = None):
        if not hasattr(self.bot, "data"):
            await ctx.send("❌ Chưa cấu hình DataManager (bot.data).")
            return
        if not pet_id:
            await ctx.send("❗ Dùng: /petoff <pet_id|all>")
            return
        if pet_id.lower() == "all":
            await self.bot.data.set_active_pets(ctx.author.id, [])
            await ctx.send("✅ Đã bỏ tất cả pet.")
            return
        active = self.bot.data.get_active_pets(ctx.author.id)
        if pet_id not in active:
            await ctx.send(f"❌ Pet `{pet_id}` không đang được sử dụng.")
            return
        await self.bot.data.remove_active_pet(ctx.author.id, pet_id)
        p = PETS.get(pet_id, {})
        await ctx.send(f"✅ Đã bỏ pet **{p.get('emoji','')} {p.get('name', pet_id)}** (`{pet_id}`).")
    async def _choose_pet_for_tier(self, tier: int) -> str:
        choices = EGG_TIERS.get(tier, [])
        if not choices:
            return random.choice(list(PETS.keys())) if PETS else ""
        # Build weights by rarity
        weights = []
        for pid in choices:
            p = PETS.get(pid, {})
            r = p.get("rarity", "common")
            w = float(RARITY_WEIGHTS.get(r, 1))
            weights.append(w)
        total = sum(weights)
        if total <= 0:
            return random.choice(choices)
        pick = random.choices(choices, weights=weights, k=1)[0]
        return pick

    async def _process_hatch(self, user_id: str, egg: dict):
        # select pet, add to user, remove egg, notify
        tier = egg.get("tier")
        pet_id = await self._choose_pet_for_tier(tier)
        if not pet_id:
            return
        try:
            await self.bot.data.add_pet(int(user_id), pet_id)
            await self.bot.data.remove_egg(int(user_id), egg.get("id"))
        except Exception:
            # don't crash; leave egg for later
            return
        # notify user
        user = self.bot.get_user(int(user_id))
        try:
            p = PETS.get(pet_id, {})
            name = p.get("name", pet_id)
            emoji = p.get("emoji", "")
            msg = f"🥚 Trứng của bạn đã nở! Bạn nhận được **{emoji} {name}** (`{pet_id}`)."
            if user:
                await user.send(msg)
        except Exception:
            pass

    async def _egg_watcher(self):
        await self.bot.wait_until_ready()
        while True:
            try:
                # We intentionally do NOT auto-hatch eggs when hatch_at passes.
                # Eggs that have reached hatch_at are considered "ready" — users must run the `hatch` command to open them.
                # This loop remains to keep the cog alive for potential future notifications, but it will not change egg state.
                _ = self.bot.data.read_all_users()
            except asyncio.CancelledError:
                break
            except Exception:
                # ignore errors to keep loop running
                pass
            await asyncio.sleep(15)


async def setup(bot: commands.Bot):
    await bot.add_cog(EggCog(bot))