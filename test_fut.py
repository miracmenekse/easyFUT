import time
from fut import load_club, load_fodder_prices, plan_max, squad_rating, matches
from solver import squad_chem

assert squad_rating([84] * 11) == 84
assert squad_rating([90] + [80] * 10) == 81  # ortalamanın üstü fark eklenir

# kimya: 11 kişi aynı kulüp/lig/ülke, hepsi pozisyonunda -> 33
same = {"club": "A", "league": "L", "nation": "N", "source": "kulüp", "rarity": "rare"}
assert sum(squad_chem([(p, same | {"position": p}) for p in ["GK"] + ["CB"] * 10])) == 33
# pozisyon dışı oyuncu kimya almaz
assert squad_chem([("ST", same | {"position": "GK"})])[0] == 0

club, fodder = load_club(), load_fodder_prices()
t = time.time()
sbc = {"name": "t", "size": 11, "min_rating": 82, "formation": "4-4-2", "min_chem": 15,
       "requirements": [{"field": "league", "in": ["Süper Lig"], "min": 2},
                        {"type": "same", "field": "league", "max": 5},
                        {"type": "distinct", "field": "nation", "min": 4}]}
p = plan_max([sbc], club, fodder, budget=10**9, time_limit=10)
assert p["done"], p
s = p["done"][0][1]
cards = [c for c in s["squad"] if c["source"] == "kulüp"]
assert s["rating"] >= 82 and s["chem"] >= 15, (s["rating"], s["chem"])
assert sum(matches(c, {"field": "league", "in": ["Süper Lig"]}) for c in cards) >= 2
assert max([c["league"] for c in cards].count(l) for l in {c["league"] for c in cards}) <= 5
assert len({c["nation"] for c in cards}) >= 4
print("tek SBC ok", round(time.time() - t, 1), "sn")

p = plan_max([{"name": "a", "min_rating": 80, "repeat": 2}, {"name": "b", "min_rating": 83}], club, fodder, 0, 10)
used = [c["id"] for _, s in p["done"] for c in s["squad"] if c["source"] == "kulüp"]
assert len(used) == len(set(used))  # bir kart iki SBC'de yok
assert p["spent"] == 0 and p["total"] == 3
assert not plan_max([{"name": "imkansız", "min_rating": 99}], club, fodder, 0, 5)["done"]
print("plan ok", len(p["done"]), "/", p["total"])
assert all(ok for _, s in p["done"] for _, ok in s["checks"])
print("bağımsız doğrulama ok")

# birleşik şart: iki alan birden (veriden bağımsız, kendi kartlarıyla)
sahte = [{"id": i, "name": f"O{i}", "rating": 84 if i < 4 else 80, "position": "CM", "positions": "CM",
          "nation": "N%d" % (i % 3), "league": "L%d" % (i % 2), "club": "K%d" % (i % 4),
          "rarity": "rare" if i < 3 else "common", "tradeable": False, "duplicate": False,
          "locked": False, "price": 0, "source": "kulüp"} for i in range(22)]
sbc = {"name": "birleşik", "size": 11,
       "requirements": [{"all": [{"field": "rating", "gte": 84}, {"field": "rarity", "in": ["rare"]}], "min": 3}]}
s = plan_max([sbc], sahte, {}, 0, 10)["done"][0][1]
kc = [c for c in s["squad"] if c["source"] == "kulüp"]
assert sum(c["rating"] >= 84 and c["rarity"] == "rare" for c in kc) >= 3
assert all(ok for _, ok in s["checks"])
print("birleşik şart ok")

# SBC'nin hazır verdiği oyuncu kadroda zorunlu ve şartlara sayılır
sbc = {"name": "hazır oyuncu", "size": 11, "min_chem": 3, "formation": "4-3-3",
       "fixed": [{"name": "Hazır", "rating": 99, "position": "LW", "positions": "LW",
                  "nation": "N0", "league": "L0", "club": "K0", "rarity": "", "price": 0}],
       "requirements": [{"field": "club", "in": ["K0"], "min": 2}]}
s = plan_max([sbc], sahte, {}, 0, 15)["done"][0][1]
isim = [c["name"] for c in s["squad"]]
assert "Hazır" in isim and len(s["squad"]) == 11
assert sum(c.get("club") == "K0" for c in s["squad"]) >= 2  # hazır oyuncu da sayılıyor
assert next(sl for sl in s["slots"] if sl["card"]["name"] == "Hazır")["pos"] == "LW"
assert all(ok for _, ok in s["checks"])
print("hazır oyuncu ok")

# pasife alınan SBC plana girmez
akt = {"name": "aktif", "size": 11}
pas = {"name": "pasif", "size": 11, "passive": True}
p = plan_max([akt, pas], sahte, {}, 0, 10)
assert p["total"] == 1 and [s["name"] for s, _ in p["done"]] == ["aktif"]
print("pasif SBC ok")
