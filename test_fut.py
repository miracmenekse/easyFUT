"""Hızlı kontrol (gerçek kulüp verisinden bağımsız, uydurma kartlarla): .venv/bin/python test_fut.py"""
import random, time

import bench, fut, solver, testveri
from fut import plan_max, squad_rating, matches
from solver import squad_chem

t0 = time.time()
assert squad_rating([84] * 11) == 84
assert squad_rating([90] + [80] * 10) == 81  # ortalamanın üstü fark eklenir

# kimya: 11 kişi aynı kulüp/lig/ülke, hepsi pozisyonunda -> 33
same = {"club": "A", "league": "L", "nation": "N", "source": "kulüp", "rarity": "rare"}
assert sum(squad_chem([(p, same | {"position": p}) for p in ["GK"] + ["CB"] * 10])) == 33
assert squad_chem([("ST", same | {"position": "GK"})])[0] == 0  # pozisyon dışı oyuncu kimya almaz
eksik = {"club": None, "league": "L", "nation": None, "source": "eksik", "rarity": None, "position": "CB"}
assert squad_chem([("CB", eksik)] + [("CB", same | {"position": "CB"})] * 2)[0] == 1  # bilinmeyen alan kimya vermez


def kart(i, rating, **k):
    return {"id": i, "name": f"O{i}", "rating": rating, "position": "CM", "positions": "CM", "nation": "N%d" % (i % 3),
            "league": "L%d" % (i % 2), "club": "K%d" % (i % 4), "rarity": "rare", "tradeable": False,
            "duplicate": False, "locked": False, "price": 0, "source": "kulüp"} | k


# takım reytingi kısıtı EA formülüyle birebir: rastgele 11'lilerde model "olur" dediği kadroyu formül de onaylar,
# formül "olur" dediği kadroyu model de bulur (en az / en fazla sınırında)
rng = random.Random(1)
for _ in range(12):
    rs = [rng.randint(70, 90) for _ in range(11)]
    T = squad_rating(rs)
    cards = [kart(i, r) for i, r in enumerate(rs)]
    for sbc, ok in (({"name": "a", "min_rating": T}, True), ({"name": "b", "min_rating": T + 1}, False),
                    ({"name": "c", "max_rating": T}, True), ({"name": "d", "max_rating": T - 1}, False)):
        got = bool(plan_max([sbc], cards, {}, 0, 5, 3)["done"])
        assert got == ok, (rs, T, sbc, got)
print("takım reytingi formülü ok")

# pazar kartının (alanları bilinmiyor) en kötü durum hesabı
pz = {"source": "pazar", "rating": 80, "league": None, "nation": None, "club": None, "rarity": None}
assert not matches(pz, {"field": "league", "in": ["L0"]}) and matches(pz, {"field": "league", "in": ["L0"]}, True)
sq = [("CM", kart(i, 80, league="L0")) for i in range(5)] + [("CM", pz)] + [("CM", kart(9 + i, 80, league="L5")) for i in range(5)]
assert not all(ok for _, ok in solver.check({"requirements": [{"type": "same", "field": "league", "max": 5}]}, sq))
assert all(ok for _, ok in solver.check({"requirements": [{"type": "same", "field": "league", "max": 6}]}, sq))

# uydurma kulüp + SBC listesi: her kadro şartları sağlar, bir kart iki SBC'de yok, yarım SBC gerekenleri doğru
club, sbcs, fodder = testveri.ornek(3)
p = plan_max(sbcs, club, fodder, 0, 30, 20)
used = [c["id"] for _, s in p["done"] for c in s["squad"] if c["source"] == "kulüp"]
assert len(used) == len(set(used))
assert all(ok for _, s in p["done"] for _, ok in s["checks"])
for sbc, r in p["partial"]:
    assert not bench.adversarial(sbc, [(sl["pos"], sl["card"]) for sl in r["slots"]], r["missing"], rng), sbc["name"]
print("plan ok", len(p["done"]), "/", p["total"], "| yarım", len(p["partial"]), "|", p["status"])

sahte = [kart(i, 84 if i < 4 else 80, rarity="rare" if i < 3 else "common") for i in range(22)]
# birleşik şart: iki alan birden
sbc = {"name": "birleşik", "size": 11,
       "requirements": [{"all": [{"field": "rating", "gte": 84}, {"field": "rarity", "in": ["rare"]}], "min": 3}]}
s = plan_max([sbc], sahte, {}, 0, 10, 5)["done"][0][1]
assert sum(c["rating"] >= 84 and c["rarity"] == "rare" for c in s["squad"]) >= 3
assert all(ok for _, ok in s["checks"])

# SBC'nin hazır verdiği oyuncu kadroda zorunlu ve şartlara sayılır
sbc = {"name": "hazır oyuncu", "size": 11, "min_chem": 3, "formation": "4-3-3",
       "fixed": [{"name": "Hazır", "rating": 99, "position": "LW", "positions": "LW",
                  "nation": "N0", "league": "L0", "club": "K0", "rarity": "", "price": 0}],
       "requirements": [{"field": "club", "in": ["K0"], "min": 2}]}
s = plan_max([sbc], sahte, {}, 0, 15, 5)["done"][0][1]
assert "Hazır" in [c["name"] for c in s["squad"]] and len(s["squad"]) == 11
assert sum(c.get("club") == "K0" for c in s["squad"]) >= 2
assert next(sl for sl in s["slots"] if sl["card"]["name"] == "Hazır")["pos"] == "LW"
assert all(ok for _, ok in s["checks"])

# pasife alınan SBC plana girmez
p = plan_max([{"name": "aktif", "size": 11}, {"name": "pasif", "size": 11, "passive": True}], sahte, {}, 0, 10)
assert p["total"] == 1 and [s["name"] for s, _ in p["done"]] == ["aktif"]

# yarım SBC: 3 L9 oyuncusu isteniyor, kulüpte 1 tane var -> 2 eksik, ikisi de "Lig: L9"
sbc = {"name": "yarım", "size": 11, "requirements": [{"field": "league", "in": ["L9"], "min": 3}]}
p = plan_max([sbc], sahte[:10] + [kart(50, 80, league="L9")], {}, 0, 10, 10)
(_, r), = p["partial"]
assert len(r["missing"]) == 2 and r["proven"], r["missing"]
assert all(m["needs"] == {"league": "L9"} for m in r["missing"]), r["missing"]
print("birleşik şart, hazır oyuncu, pasif SBC, yarım SBC ok")

# "Bunu yaptım": kartlar kulüpten çıkar (kopyası olanın satırı kalır), tekrar azalır / SBC tamamlanır
import json, tempfile
from pathlib import Path
eski_data = fut.DATA
with tempfile.TemporaryDirectory() as tmp:
    fut.DATA = Path(tmp)
    (fut.DATA / "sbcs").mkdir()
    (fut.DATA / "club.csv").write_text("name,rating,club,duplicate\nA,80,K,hayır\nB,81,K,evet\nC,82,K,hayır\n")
    (fut.DATA / "sbcs" / "t.json").write_text(json.dumps({"name": "t", "repeat": 2}))
    r = fut.complete_sbc("t.json", [{"name": "A", "rating": 80, "club": "K"}, {"name": "B", "rating": 81},
                                    {"name": "Z", "rating": 70}])
    assert r == {"silinen": ["A"], "kopyasi_kalan": ["B"], "bulunamayan": ["Z"], "kalan_tekrar": 1}, r
    assert (fut.DATA / "club.csv").read_text().split() == ["name,rating,club,duplicate", "B,81,K,hayır", "C,82,K,hayır"]
    fut.complete_sbc("t.json", [])
    assert json.load(open(fut.DATA / "sbcs" / "t.json")).get("completed")
    assert plan_max(fut.load_json_dir("sbcs"), [], {}, 0, 5, 0)["total"] == 0  # tamamlanan plana girmez
fut.DATA = eski_data
print("SBC tamamlama ok")
print(f"geçti ({time.time() - t0:.0f} sn)")
