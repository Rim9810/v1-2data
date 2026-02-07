# data_manager.py
from __future__ import annotations
import asyncio
import random
import string
import re
import os
from pathlib import Path
from typing import Dict, Any
try:
    from motor.motor_asyncio import AsyncIOMotorClient
except ImportError:
    AsyncIOMotorClient = None


class DataManager:
    """Quản lý dữ liệu MongoDB với Write-Through Cache.
    Phù hợp cho Render/Heroku vì dữ liệu lưu trên Cloud.
    """
    def __init__(self, data_file: Path):
        # MongoDB Connection
        # Lấy URI từ biến môi trường hoặc dùng localhost nếu test máy nhà
        if AsyncIOMotorClient is None:
            raise ImportError("❌ Thư viện 'motor' chưa được cài đặt. Hãy chạy lệnh: pip install motor dnspython")

        self.mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.client = AsyncIOMotorClient(self.mongo_uri)
        self.db = self.client["fishing_bot"]
        self.users_col = self.db["users"]
        self.guilds_col = self.db["guilds"]

        # Cache (RAM) - Lưu toàn bộ user vào đây để đọc nhanh (Sync Getters)
        self._users_cache: Dict[str, Any] = {}
        self._guilds_cache: Dict[str, Any] = {}
        self._initialized = False

    async def initialize(self):
        """Load dữ liệu từ Mongo vào RAM khi bot khởi động."""
        if self._initialized:
            return
            
        print("⏳ Đang tải dữ liệu từ MongoDB...")
        async for user in self.users_col.find():
            self._users_cache[user["_id"]] = user
        
        async for guild in self.guilds_col.find():
            self._guilds_cache[guild["_id"]] = guild
        print(f"✅ Đã tải {len(self._users_cache)} users và {len(self._guilds_cache)} guilds.")
        self._initialized = True

    def _ensure_user(self, user_id: str):
        """Tạo user mới trong cache nếu chưa có."""
        if user_id not in self._users_cache:
            self._users_cache[user_id] = self._empty_user()
            self._users_cache[user_id]["_id"] = user_id

    # ---------- Model ----------
    @staticmethod
    def _empty_user() -> Dict[str, Any]:
        # THÊM ví tiền (wallet), XP và Level, rod info vào hồ sơ user
        return {
            "wallet": 0,
            "gems": 0,
            "xp": 0,
            "level": 1,
            "rod_level": 1,
            "max_rod_level": 1,
            "inventory": {
                "common": {},
                "uncommon": {},
                "rare": {},
                "epic": {},
                "legendary": {},
                "mythical": {},
                "unreal": {},
            },
            # shiny_inventory: lưu số lượng cá shiny theo bậc -> tên
            "shiny_inventory": {
                "common": {},
                "uncommon": {},
                "rare": {},
                "epic": {},
                "legendary": {},
                "mythical": {},
                "unreal": {},
            },
            # items: mapping item_id -> count (vật phẩm có thể bán; keys là IDs từ game_items.ITEMS)
            "items": {},
            # equipped_items: list of item IDs currently equipped
            "equipped_items": [],
            # eggs: danh sách trứng đang ấp/chờ nở; mỗi egg là dict với các khóa: id, tier, hatch_at (epoch)
            "eggs": [],
            # pets: danh sách pet_id mà user sở hữu (pet passive buffs)
            "pets": [],
            # active_pets: danh sách pet_id đang được kích hoạt (áp dụng buffs)
            "active_pets": [],
            # last_daily: epoch timestamp của lần nhận daily cuối
            "last_daily": 0,
            # fishes: list of caught fish objects. Each fish is a dict with keys like:
            # id, name, rarity, weight (kg), weight_class, caught_at, variation (optional), price_per_kg (optional)
            "fishes": [],
            # aquarium: dict of fish_id -> {added_at: timestamp}
            "aquarium": {},
        }

    def _generate_unique_fish_id(self, user_id: int) -> str:
        """Generate a unique 4-char alphanumeric fish id for the given user."""
        chars = string.ascii_letters + string.digits
        uid = str(user_id)
        existing = {f.get("id") for f in self._users_cache.get(uid, self._empty_user()).get("fishes", [])}
        for _ in range(500):
            cand = ''.join(random.choices(chars, k=4))
            if cand not in existing:
                return cand
        # fallback (extremely unlikely)
        return ''.join(random.choices(chars, k=4))

    # ---------- Inventory ----------
    def get_inventory(self, user_id: int) -> Dict[str, Dict[str, int]]:
        """Lấy kho đồ dạng {rarity: {fish_name: count}}."""
        return self._users_cache.get(str(user_id), self._empty_user()).get("inventory", {})

    async def set_inventory(self, user_id: int, new_inventory: Dict[str, Dict[str, int]]) -> None:
        """Ghi đè kho đồ (dùng sau các thao tác như bán).
        new_inventory nên có đủ các bậc: common/uncommon/rare/epic (sẽ được chuẩn hóa).
        """
        uid = str(user_id)
        self._ensure_user(uid)

        # Chuẩn hóa dữ liệu để luôn có đủ các bậc
        normalized = {
            "common": dict(new_inventory.get("common", {})),
            "uncommon": dict(new_inventory.get("uncommon", {})),
            "rare": dict(new_inventory.get("rare", {})),
            "epic": dict(new_inventory.get("epic", {})),
            "legendary": dict(new_inventory.get("legendary", {})),
            "mythical": dict(new_inventory.get("mythical", {})),
            "unreal": dict(new_inventory.get("unreal", {})),
        }
        self._users_cache[uid]["inventory"] = normalized
        await self.users_col.update_one({"_id": uid}, {"$set": {"inventory": normalized}}, upsert=True)

    # ---------- Items (vật phẩm) ----------
    def get_items(self, user_id: int) -> Dict[str, int]:
        """Trả về dict item_name -> count."""
        return self._users_cache.get(str(user_id), self._empty_user()).get("items", {})

    async def add_item(self, user_id: int, item_id: str, count: int = 1) -> None:
        uid = str(user_id)
        self._ensure_user(uid)
        
        items = self._users_cache[uid].setdefault("items", {})
        items[item_id] = items.get(item_id, 0) + int(count)
        
        await self.users_col.update_one({"_id": uid}, {"$set": {"items": items}}, upsert=True)

    async def remove_item(self, user_id: int, item_id: str, count: int = 1) -> bool:
        """Giảm số lượng item; trả về True nếu thành công, False nếu không đủ."""
        uid = str(user_id)
        self._ensure_user(uid)
        
        items = self._users_cache[uid].setdefault("items", {})
        cur = int(items.get(item_id, 0))
        if cur < count:
            return False
        if cur == count:
            items.pop(item_id, None)
        else:
            items[item_id] = cur - count
            
        await self.users_col.update_one({"_id": uid}, {"$set": {"items": items}}, upsert=True)
        return True

    def get_equipped_items(self, user_id: int) -> list[str]:
        return list(self._users_cache.get(str(user_id), self._empty_user()).get("equipped_items", []))

    async def set_equipped_items(self, user_id: int, equipped: list[str]) -> None:
        uid = str(user_id)
        self._ensure_user(uid)
        
        self._users_cache[uid]["equipped_items"] = list(equipped)
        await self.users_col.update_one({"_id": uid}, {"$set": {"equipped_items": list(equipped)}}, upsert=True)

    # ---------- Eggs & Pets ----------
    def get_eggs(self, user_id: int) -> list[dict]:
        return list(self._users_cache.get(str(user_id), self._empty_user()).get("eggs", []))

    async def add_egg(self, user_id: int, egg: dict) -> str:
        """egg should be dict with keys at least: id, tier, hatch_at."""
        uid = str(user_id)
        self._ensure_user(uid)
        
        self._users_cache[uid].setdefault("eggs", []).append(dict(egg))
        await self.users_col.update_one({"_id": uid}, {"$push": {"eggs": dict(egg)}}, upsert=True)
        return egg.get("id")

    async def remove_egg(self, user_id: int, egg_id: str) -> bool:
        uid = str(user_id)
        self._ensure_user(uid)
        
        eggs = self._users_cache[uid].setdefault("eggs", [])
        new = [e for e in eggs if e.get("id") != egg_id]
        if len(new) == len(eggs):
            return False
        self._users_cache[uid]["eggs"] = new
        await self.users_col.update_one({"_id": uid}, {"$set": {"eggs": new}}, upsert=True)
        return True

    def get_pets(self, user_id: int) -> list[str]:
        return list(self._users_cache.get(str(user_id), self._empty_user()).get("pets", []))

    async def add_pet(self, user_id: int, pet_id: str) -> None:
        uid = str(user_id)
        self._ensure_user(uid)
        
        self._users_cache[uid].setdefault("pets", []).append(pet_id)
        await self.users_col.update_one({"_id": uid}, {"$push": {"pets": pet_id}}, upsert=True)

    async def remove_pet(self, user_id: int, pet_id: str) -> bool:
        uid = str(user_id)
        self._ensure_user(uid)
        
        pets = self._users_cache[uid].setdefault("pets", [])
        if pet_id not in pets:
            return False
        pets.remove(pet_id)
        await self.users_col.update_one({"_id": uid}, {"$set": {"pets": pets}}, upsert=True)
        return True

    # ---------- Active pets (đang sử dụng) ----------
    def get_active_pets(self, user_id: int) -> list[str]:
        return list(self._users_cache.get(str(user_id), self._empty_user()).get("active_pets", []))

    async def set_active_pets(self, user_id: int, active: list[str]) -> None:
        uid = str(user_id)
        self._ensure_user(uid)
        
        self._users_cache[uid]["active_pets"] = list(active)
        await self.users_col.update_one({"_id": uid}, {"$set": {"active_pets": list(active)}}, upsert=True)

    async def add_active_pet(self, user_id: int, pet_id: str) -> bool:
        """Add pet to active list; return True if added, False if already active."""
        uid = str(user_id)
        self._ensure_user(uid)
        
        act = self._users_cache[uid].setdefault("active_pets", [])
        if pet_id in act:
            return False
        act.append(pet_id)
        await self.users_col.update_one({"_id": uid}, {"$set": {"active_pets": act}}, upsert=True)
        return True

    async def remove_active_pet(self, user_id: int, pet_id: str) -> bool:
        uid = str(user_id)
        self._ensure_user(uid)
        
        act = self._users_cache[uid].setdefault("active_pets", [])
        if pet_id not in act:
            return False
        act.remove(pet_id)
        await self.users_col.update_one({"_id": uid}, {"$set": {"active_pets": act}}, upsert=True)
        return True

    async def add_fish(self, user_id: int, rarity: str, fish_name: str) -> None:
        """Tăng 1 con cá vào kho."""
        uid = str(user_id)
        self._ensure_user(uid)

        rarity = rarity.lower()
        inv = self._users_cache[uid]["inventory"]
        inv.setdefault(rarity, {})
        inv[rarity][fish_name] = inv[rarity].get(fish_name, 0) + 1
        
        await self.users_col.update_one({"_id": uid}, {"$set": {f"inventory.{rarity}.{fish_name}": inv[rarity][fish_name]}}, upsert=True)

    async def reset_inventory(self, user_id: int) -> None:
        """Xóa sạch kho đồ (không ảnh hưởng ví)."""
        uid = str(user_id)
        self._ensure_user(uid)
        
        empty_inv = {"common": {}, "uncommon": {}, "rare": {}, "epic": {}}
        self._users_cache[uid]["inventory"] = empty_inv
        self._users_cache[uid]["shiny_inventory"] = empty_inv
        
        await self.users_col.update_one({"_id": uid}, {"$set": {"inventory": empty_inv, "shiny_inventory": empty_inv}}, upsert=True)

    # ---------- Fish objects (new model) ----------
    def get_fish_objects(self, user_id: int) -> list:
        """Return list of fish objects the user owns."""
        return list(self._users_cache.get(str(user_id), self._empty_user()).get("fishes", []))

    async def add_caught_fish(self, user_id: int, fish: dict) -> str:
        """Add a fish object to user's 'fishes' list. Returns fish id."""
        uid = str(user_id)
        self._ensure_user(uid)
        
        lst = self._users_cache[uid].setdefault("fishes", [])
        fish_copy = dict(fish)
        fid = fish_copy.get("id")
        # Ensure id follows 4-char alnum format and is unique per-user
        if not isinstance(fid, str) or not re.fullmatch(r'[A-Za-z0-9]{4}', fid):
            fid = self._generate_unique_fish_id(user_id)
        else:
            existing = {f.get("id") for f in lst}
            if fid in existing:
                fid = self._generate_unique_fish_id(user_id)
        fish_copy["id"] = fid
        lst.append(fish_copy)
        
        await self.users_col.update_one({"_id": uid}, {"$push": {"fishes": fish_copy}}, upsert=True)
        return fid

    async def remove_fish_by_id(self, user_id: int, fish_id: str) -> bool:
        """Remove a fish by its id; return True if removed, False if not found."""
        uid = str(user_id)
        self._ensure_user(uid)
        
        lst = self._users_cache[uid].setdefault("fishes", [])
        new = [f for f in lst if f.get("id") != fish_id]
        if len(new) == len(lst):
            return False
        self._users_cache[uid]["fishes"] = new
        await self.users_col.update_one({"_id": uid}, {"$set": {"fishes": new}}, upsert=True)
        return True

    async def migrate_inventory_to_objects(self, user_id: int, game_config_defaults: dict | None = None) -> int:
        """Helper to migrate legacy inventory counts to fish objects."""
        uid = str(user_id)
        if uid not in self._users_cache:
            return 0
        u = self._users_cache[uid]
        inv = u.get('inventory', {})
        migr_count = 0
        # fallbacks
        price_map = (game_config_defaults or {}).get('PRICE_PER_KG_BY_RARITY', {})
        weight_map = (game_config_defaults or {}).get('WEIGHT_BY_RARITY', {})
        
        # Import config once outside loop
        try:
            from game_config import PRICE_PER_KG_BY_RARITY as CFG_PRICE, WEIGHT_CLASS_PCT_RANGES as CFG_PCT_RANGES, FISH_POOLS as CFG_POOLS
        except Exception:
            CFG_PRICE, CFG_PCT_RANGES, CFG_POOLS = {}, {"normal": (0.9, 1.1)}, {}
            
        import random
        import time

        for rarity, bucket in inv.items():
            for name, cnt in list(bucket.items()):
                for _ in range(int(cnt)):
                    # generate fish object using per-fish base_weight and price if available
                    # look up fish definition in FISH_POOLS by rarity and name
                    fish_def = None
                    try:
                        pool = CFG_POOLS.get(rarity, [])
                        for ent in pool:
                            if ent.get('name') == name:
                                fish_def = ent
                                break
                    except Exception:
                        fish_def = None
                    # determine base weight
                    if fish_def and fish_def.get('base_weight') is not None:
                        base_w = float(fish_def.get('base_weight'))
                    else:
                        wmin, wmax = weight_map.get(rarity, (0.5, 2.0))
                        base_w = (float(wmin) + float(wmax)) / 2.0
                    # sample weight using normal class pct (migrate to normal class)
                    try:
                        pmin, pmax = CFG_PCT_RANGES.get('normal', (0.9, 1.1))
                        weight = round(base_w * random.uniform(float(pmin), float(pmax)), 2)
                    except Exception:
                        weight = round(base_w, 2)
                    # determine price_per_kg (per-fish override > provided map > rarity map)
                    if fish_def and fish_def.get('price_per_kg') is not None:
                        price_per_kg = int(fish_def.get('price_per_kg'))
                    else:
                        price_per_kg = int(price_map.get(rarity, CFG_PRICE.get(rarity, 10)))
                    fish_obj = {
                        'id': self._generate_unique_fish_id(user_id),
                        'name': name,
                        'rarity': rarity,
                        'weight': weight,
                        'weight_class': 'normal',
                        'price_per_kg': price_per_kg,
                        'sell_price': int(price_per_kg * weight),
                        'caught_at': int(time.time()),
                        'shiny': False,
                    }
                    self._users_cache[uid].setdefault('fishes', []).append(fish_obj)
                    migr_count += 1
        # Clear legacy inventory
        empty_inv = {"common": {}, "uncommon": {}, "rare": {}, "epic": {}}
        self._users_cache[uid]['inventory'] = empty_inv
        
        # Update Mongo with both changes
        await self.users_col.update_one(
            {"_id": uid}, 
            {"$set": {"fishes": self._users_cache[uid]['fishes'], "inventory": empty_inv}}, 
            upsert=True
        )
        return migr_count

    # ---------- Shiny fish support ----------
    def get_shiny_inventory(self, user_id: int) -> Dict[str, Dict[str, int]]:
        """Lấy kho cá shiny: {rarity: {fish_name: count}}."""
        return self._users_cache.get(str(user_id), self._empty_user()).get("shiny_inventory", {"common": {}, "uncommon": {}, "rare": {}, "epic": {}, "legendary": {}, "mythical": {}, "unreal": {}})

    async def set_shiny_inventory(self, user_id: int, new_shiny_inventory: Dict[str, Dict[str, int]]) -> None:
        uid = str(user_id)
        self._ensure_user(uid)
        
        normalized = {
            "common": dict(new_shiny_inventory.get("common", {})),
            "uncommon": dict(new_shiny_inventory.get("uncommon", {})),
            "rare": dict(new_shiny_inventory.get("rare", {})),
            "epic": dict(new_shiny_inventory.get("epic", {})),
            "legendary": dict(new_shiny_inventory.get("legendary", {})),
            "mythical": dict(new_shiny_inventory.get("mythical", {})),
            "unreal": dict(new_shiny_inventory.get("unreal", {})),
        }
        self._users_cache[uid]["shiny_inventory"] = normalized
        await self.users_col.update_one({"_id": uid}, {"$set": {"shiny_inventory": normalized}}, upsert=True)

    async def add_shiny_fish(self, user_id: int, rarity: str, fish_name: str, count: int = 1) -> None:
        """Tăng số lượng cá shiny."""
        uid = str(user_id)
        self._ensure_user(uid)
        
        rarity = rarity.lower()
        shin = self._users_cache[uid].setdefault("shiny_inventory", {})
        shin.setdefault(rarity, {})
        shin[rarity][fish_name] = shin[rarity].get(fish_name, 0) + int(count)
        
        await self.users_col.update_one({"_id": uid}, {"$set": {f"shiny_inventory.{rarity}.{fish_name}": shin[rarity][fish_name]}}, upsert=True)

    async def remove_shiny_fish(self, user_id: int, rarity: str, fish_name: str, count: int = 1) -> bool:
        """Giảm số lượng cá shiny; trả về True nếu thành công, False nếu không đủ."""
        uid = str(user_id)
        self._ensure_user(uid)
        
        shin = self._users_cache[uid].setdefault("shiny_inventory", {})
        bucket = shin.setdefault(rarity.lower(), {})
        cur = int(bucket.get(fish_name, 0))
        if cur < count:
            return False
        if cur == count:
            bucket.pop(fish_name, None)
        else:
            bucket[fish_name] = cur - count
            
        await self.users_col.update_one({"_id": uid}, {"$set": {"shiny_inventory": shin}}, upsert=True)
        return True

    # ---------- Aquarium (new) ----------
    def get_aquarium(self, user_id: int) -> dict:
        """Lấy dữ liệu bể cá của người chơi."""
        return self._users_cache.get(str(user_id), self._empty_user()).get("aquarium", {})

    async def set_aquarium(self, user_id: int, aquarium_data: dict) -> None:
        """Ghi đè toàn bộ dữ liệu bể cá."""
        uid = str(user_id)
        self._ensure_user(uid)
        
        self._users_cache[uid]["aquarium"] = dict(aquarium_data)
        await self.users_col.update_one({"_id": uid}, {"$set": {"aquarium": dict(aquarium_data)}}, upsert=True)

    # ---------- Wallet ----------
    def get_balance(self, user_id: int) -> int:
        """Lấy số dư ví (coins)."""
        return int(self._users_cache.get(str(user_id), self._empty_user()).get("wallet", 0))

    async def add_money(self, user_id: int, amount: int) -> int:
        """Cộng (hoặc trừ nếu âm) tiền vào ví. Trả về số dư mới (>= 0)."""
        uid = str(user_id)
        self._ensure_user(uid)
        
        cur = int(self._users_cache[uid].get("wallet", 0))
        new_val = max(0, cur + int(amount))
        self._users_cache[uid]["wallet"] = new_val
        
        await self.users_col.update_one({"_id": uid}, {"$set": {"wallet": new_val}}, upsert=True)
        return new_val

    async def set_money(self, user_id: int, amount: int) -> int:
        """Đặt số dư ví về một giá trị cụ thể (>= 0)."""
        uid = str(user_id)
        self._ensure_user(uid)
        
        val = max(0, int(amount))
        self._users_cache[uid]["wallet"] = val
        await self.users_col.update_one({"_id": uid}, {"$set": {"wallet": val}}, upsert=True)
        return val

    # ---------- Gems (mới) ----------
    def get_gems(self, user_id: int) -> int:
        """Lấy số lượng gem hiện tại."""
        return int(self._users_cache.get(str(user_id), self._empty_user()).get("gems", 0))

    async def add_gems(self, user_id: int, amount: int) -> int:
        """Cộng (hoặc trừ) gem vào tài khoản. Trả về số gem mới (>=0)."""
        uid = str(user_id)
        self._ensure_user(uid)
        
        cur = int(self._users_cache[uid].get("gems", 0))
        new_val = max(0, cur + int(amount))
        self._users_cache[uid]["gems"] = new_val
        
        await self.users_col.update_one({"_id": uid}, {"$set": {"gems": new_val}}, upsert=True)
        return new_val

    async def set_gems(self, user_id: int, amount: int) -> int:
        """Đặt gem về một giá trị cụ thể (>=0)."""
        uid = str(user_id)
        self._ensure_user(uid)
        
        val = max(0, int(amount))
        self._users_cache[uid]["gems"] = val
        await self.users_col.update_one({"_id": uid}, {"$set": {"gems": val}}, upsert=True)
        return val

    # ---------- Daily timestamp (mới) ----------
    def get_last_daily(self, user_id: int) -> int:
        return int(self._users_cache.get(str(user_id), self._empty_user()).get("last_daily", 0))

    async def set_last_daily(self, user_id: int, timestamp: int) -> None:
        uid = str(user_id)
        self._ensure_user(uid)
        
        self._users_cache[uid]["last_daily"] = int(timestamp)
        await self.users_col.update_one({"_id": uid}, {"$set": {"last_daily": int(timestamp)}}, upsert=True)

    # ---------- XP & Level ----------
    def get_xp(self, user_id: int) -> int:
        """Lấy XP hiện thời của user."""
        return int(self._users_cache.get(str(user_id), self._empty_user()).get("xp", 0))

    async def add_xp(self, user_id: int, amount: int) -> int:
        """Cộng XP (dương hoặc âm). Trả về XP mới."""
        uid = str(user_id)
        self._ensure_user(uid)
        
        cur = int(self._users_cache[uid].get("xp", 0))
        new_val = max(0, cur + int(amount))
        self._users_cache[uid]["xp"] = new_val
        
        await self.users_col.update_one({"_id": uid}, {"$set": {"xp": new_val}}, upsert=True)
        return new_val

    async def set_xp(self, user_id: int, amount: int) -> int:
        """Đặt XP về giá trị cụ thể (>=0)."""
        uid = str(user_id)
        self._ensure_user(uid)
        
        val = max(0, int(amount))
        self._users_cache[uid]["xp"] = val
        await self.users_col.update_one({"_id": uid}, {"$set": {"xp": val}}, upsert=True)
        return val

    def get_level(self, user_id: int) -> int:
        """Lấy cấp hiện thời của user."""
        return int(self._users_cache.get(str(user_id), self._empty_user()).get("level", 1))

    async def set_level(self, user_id: int, level: int) -> int:
        """Đặt cấp cho user (>=1)."""
        uid = str(user_id)
        self._ensure_user(uid)
        
        level = max(1, int(level))
        self._users_cache[uid]["level"] = level
        await self.users_col.update_one({"_id": uid}, {"$set": {"level": level}}, upsert=True)
        return level


    # ---------- Rod (cần câu) ----------
    def get_rod_level(self, user_id: int) -> int:
        return int(self._users_cache.get(str(user_id), self._empty_user()).get("rod_level", 1))

    async def set_rod_level(self, user_id: int, level: int) -> int:
        uid = str(user_id)
        self._ensure_user(uid)
        
        level = max(1, int(level))
        self._users_cache[uid]["rod_level"] = level
        await self.users_col.update_one({"_id": uid}, {"$set": {"rod_level": level}}, upsert=True)
        return level

    def get_max_rod_level(self, user_id: int) -> int:
        """Lấy cấp cần cao nhất mà user từng mua/so hữu."""
        return int(self._users_cache.get(str(user_id), self._empty_user()).get("max_rod_level", 1))

    async def set_max_rod_level(self, user_id: int, level: int) -> int:
        """Cập nhật max_rod_level (không giảm)."""
        uid = str(user_id)
        self._ensure_user(uid)
        
        level = max(1, int(level))
        current = int(self._users_cache[uid].get("max_rod_level", 1))
        if level > current:
            self._users_cache[uid]["max_rod_level"] = level
            await self.users_col.update_one({"_id": uid}, {"$set": {"max_rod_level": level}}, upsert=True)
            return level
        return current


    # ---------- Public getter phục vụ leaderboard/khác ----------
    def read_all_users(self) -> Dict[str, dict]:
        """Trả về toàn bộ USERS (chỉ đọc) để làm leaderboard, thống kê, v.v."""
        return self._users_cache

    # ---------- Guild Config (Prefix & Channels) ----------
    def get_guild_prefix(self, guild_id: int) -> str | None:
        """Lấy prefix riêng của guild, trả về None nếu chưa set."""
        return self._guilds_cache.get(str(guild_id), {}).get("prefix")

    async def set_guild_prefix(self, guild_id: int, prefix: str) -> None:
        gid = str(guild_id)
        g = self._guilds_cache.setdefault(gid, {})
        g["prefix"] = prefix
        await self.guilds_col.update_one({"_id": gid}, {"$set": {"prefix": prefix}}, upsert=True)

    def get_allowed_channels(self, guild_id: int) -> list[int]:
        """Trả về danh sách ID kênh cho phép. Nếu rỗng -> cho phép tất cả."""
        return list(self._guilds_cache.get(str(guild_id), {}).get("allowed_channels", []))

    async def add_allowed_channel(self, guild_id: int, channel_id: int) -> None:
        gid = str(guild_id)
        g = self._guilds_cache.setdefault(gid, {})
        channels = g.setdefault("allowed_channels", [])
        if channel_id not in channels:
            channels.append(channel_id)
            await self.guilds_col.update_one({"_id": gid}, {"$set": {"allowed_channels": channels}}, upsert=True)

    async def remove_allowed_channel(self, guild_id: int, channel_id: int) -> bool:
        gid = str(guild_id)
        g = self._guilds_cache.setdefault(gid, {})
        channels = g.setdefault("allowed_channels", [])
        if channel_id in channels:
            channels.remove(channel_id)
            await self.guilds_col.update_one({"_id": gid}, {"$set": {"allowed_channels": channels}}, upsert=True)
            return True
        return False

    async def clear_allowed_channels(self, guild_id: int) -> None:
        gid = str(guild_id)
        if gid in self._guilds_cache:
            self._guilds_cache[gid]["allowed_channels"] = []
            await self.guilds_col.update_one({"_id": gid}, {"$set": {"allowed_channels": []}}, upsert=True)