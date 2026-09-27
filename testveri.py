"""Uydurma test verisi: gerçekçi bir kulüp ve SBC listesi üretir (tohum -> hep aynı veri).

.venv/bin/python testveri.py 7                 # 7 numaralı örneği özetle
from testveri import ornek; club, sbcs, fodder = ornek(7)
"""
import random, sys

# lig -> (ev sahibi ülke, ev sahibi oranı, kulüp sayısı)
LEAGUES = {"Premier League": ("England", .4, 12), "LALIGA EA SPORTS": ("Spain", .5, 10),
           "Bundesliga": ("Germany", .45, 10), "Serie A Enilive": ("Italy", .45, 10),
           "Ligue 1 McDonald's": ("France", .5, 9), "Eredivisie": ("Netherlands", .55, 6),
           "Liga Portugal": ("Portugal", .55, 6), "Trendyol Süper Lig": ("Türkiye", .5, 8),
           "MLS": ("United States", .4, 8), "ROSHN Saudi League": ("Saudi Arabia", .4, 6),
           "Barclays WSL": ("England", .45, 8), "NWSL": ("United States", .5, 8),
           "Liga F": ("Spain", .55, 6), "EFL Championship": ("England", .6, 8), "Icons": (None, 0, 0)}
LEAGUE_W = [18, 12, 11, 10, 8, 4, 4, 5, 3, 4, 7, 5, 3, 5, 0]
NATIONS = ["England", "Spain", "Germany", "Italy", "France", "Netherlands", "Portugal", "Brazil", "Argentina",
           "Belgium", "Türkiye", "United States", "Saudi Arabia", "Croatia", "Norway", "Denmark", "Morocco",
           "Senegal", "Nigeria", "Japan", "Korea Republic", "Uruguay", "Colombia", "Poland", "Austria",
           "Switzerland", "Canada", "Scotland", "Wales", "Sweden", "Mexico", "Ghana", "Algeria", "Serbia"]
NATION_W = [10, 8, 8, 7, 9, 5, 5, 8, 6, 4, 3, 3, 2, 3, 2, 2, 3, 2, 2, 2, 1, 2, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1]
POS = {"GK": 8, "CB": 18, "LB": 6, "RB": 6, "CDM": 9, "CM": 11, "CAM": 9, "LM": 4, "RM": 4, "LW": 5, "RW": 5,
       "ST": 14, "CF": 1}
ALT = {"GK": [], "CB": ["CDM", "RB", "LB"], "LB": ["LM", "LWB", "CB"], "RB": ["RM", "RWB", "CB"],
       "CDM": ["CM", "CB"], "CM": ["CDM", "CAM"], "CAM": ["CM", "ST", "CF"], "LM": ["LW", "LB", "CAM"],
       "RM": ["RW", "RB", "CAM"], "LW": ["LM", "ST", "CAM"], "RW": ["RM", "ST", "CAM"], "ST": ["CF", "LW", "RW"],
       "CF": ["ST", "CAM"]}
FORMS = ["4-3-3", "4-4-2", "4-2-3-1", "3-4-3", "3-5-2", "4-1-4-1", "4-1-2-1-2", "5-3-2", "4-2-2-2"]


def kulup(rng, n):
    cards = []
    for i in range(n):
        lg = rng.choices(list(LEAGUES), LEAGUE_W)[0]
        home, share, nclub = LEAGUES[lg]
        na = home if rng.random() < share else rng.choices(NATIONS, NATION_W)[0]
        cl = f"{lg.split()[0]} Kulüp {rng.randint(1, nclub)}"
        pos = rng.choices(list(POS), list(POS.values()))[0]
        alts = rng.sample(ALT[pos], k=min(len(ALT[pos]), rng.choice([0, 0, 1, 1, 2, 3])))
        tier = rng.random()
        rating = rng.randint(75, 91) if tier < .62 else rng.randint(65, 74) if tier < .82 else rng.randint(50, 64)
        special = rating >= 78 and rng.random() < .1
        rarity = rng.choice(["totw", "ones to watch", "squad foundations"]) if special else \
            "rare" if rng.random() < .75 else "common"
        tradeable = rng.random() < .25
        cards.append({"name": f"O{i}", "rating": rating, "position": pos, "positions": "|".join([pos] + alts),
                      "nation": na, "league": lg, "club": cl, "rarity": rarity, "tradeable": tradeable,
                      "duplicate": rng.random() < .05, "locked": False,
                      "price": rng.choice([0, 500, 900, 1500, 4000]) if tradeable else 0})
    for j in range(rng.randint(0, 2)):  # Icon / Hero
        icon = rng.random() < .5
        cards.append({"name": f"Y{j}", "rating": rng.randint(84, 90), "position": rng.choice(["ST", "CM", "CB"]),
                      "positions": "", "nation": rng.choices(NATIONS, NATION_W)[0],
                      "league": "Icons" if icon else rng.choice(list(LEAGUES)[:5]), "club": "",
                      "rarity": "icon" if icon else "hero", "tradeable": False, "duplicate": False, "locked": False,
                      "price": 0})
    for c in sorted(cards, key=lambda c: -c["rating"])[:rng.randint(0, 23)]:  # aktif kadro
        c["locked"] = rng.random() < .8
    for i, c in enumerate(cards):
        c.update(id=i, source="kulüp")
    return cards


def sbc_listesi(rng, cards, n):
    leagues = [lg for lg in LEAGUES if lg != "Icons"]
    nats = sorted({c["nation"] for c in cards})
    out = []
    for k in range(n):
        t = rng.choice(["yukseltme", "yukseltme", "reyting", "lig_ulke", "lig_ulke", "hibrit", "ust", "hazir",
                        "kimya1", "nadir"])
        s = {"name": f"S{k} {t}", "size": 11, "formation": rng.choice(FORMS), "_file": f"s{k}.json"}
        if t == "yukseltme":
            lo, hi = rng.choice([(None, 64), (65, 74), (75, None)])
            s["requirements"] = [{"field": "rating", **({"gte": lo} if lo else {}), **({"lte": hi} if hi else {}),
                                  "min": 11}]
            s["repeat"] = rng.choice([1, 1, 2, 3])
        elif t == "reyting":
            s["min_rating"] = rng.randint(78, 86)
            s["min_chem"] = rng.choice([0, 0, 15, 20])
            s["requirements"] = [rng.choice([{"field": "league", "in": [rng.choice(leagues)], "min": rng.randint(1, 3)},
                                             {"field": "nation", "in": [rng.choice(nats)], "min": 1},
                                             {"field": "rarity", "in": ["rare"], "min": rng.randint(2, 6)}])]
        elif t == "lig_ulke":
            a, b = rng.randint(2, 5), rng.randint(2, 6)
            s["min_chem"] = rng.randint(18, 30)
            s["min_rating"] = rng.choice([0, 0, 75, 78, 81])
            s["requirements"] = [{"type": "distinct", "field": "league", "exact": a},
                                 {"type": "distinct", "field": "nation", "exact": b},
                                 {"type": "same", "field": rng.choice(["league", "nation", "club"]),
                                  "max": rng.randint(3, 6)}]
        elif t == "hibrit":
            s["min_chem"] = rng.randint(8, 20)
            s["requirements"] = [{"type": "same", "field": "league", "min": rng.randint(3, 5)},
                                 {"type": "distinct", "field": "nation", "min": rng.randint(2, 5)},
                                 {"type": "distinct", "field": "club", "max": rng.randint(3, 6)}]
        elif t == "ust":
            s["max_rating"] = rng.randint(80, 86)
            s["min_chem"] = rng.choice([0, 10])
            s["requirements"] = [{"field": "rating", "gte": 75, "min": 11}]
        elif t == "hazir":
            c = rng.choice(cards)
            s["fixed"] = [{"name": "Hazır oyuncu", "rating": 82, "position": "ST", "positions": "ST",
                           "nation": c["nation"], "league": c["league"], "club": c["club"], "rarity": "rare",
                           "price": 0}]
            s["formation"] = "4-3-3"
            s["min_chem"] = rng.randint(5, 15)
            s["requirements"] = [{"type": "same", "field": "league", "min": 4},
                                 {"type": "distinct", "field": "club", "max": 4}]
        elif t == "kimya1":
            s["min_player_chem"] = 1
            s["min_chem"] = rng.randint(15, 25)
            s["min_rating"] = rng.choice([0, 76, 80])
        else:
            s["min_rating"] = rng.randint(75, 82)
            s["requirements"] = [{"all": [{"field": "rating", "gte": 80}, {"field": "rarity", "in": ["rare"]}],
                                  "min": rng.randint(2, 5)},
                                 {"field": "league", "in": [rng.choice(leagues)], "max": 3}]
        out.append(s)
    return out


def ornek(seed, n_cards=None, n_sbc=None):
    """seed -> (kulüp kartları, SBC listesi, pazar fiyatları)"""
    rng = random.Random(seed)
    cards = kulup(rng, n_cards or rng.randint(80, 260))
    sbcs = sbc_listesi(rng, cards, n_sbc or rng.randint(4, 10))
    fodder = {r: p for r, p in zip(range(75, 92), [200, 250, 300, 350, 450, 600, 800, 1100, 1600, 2500, 4000,
                                                    6500, 10000, 15000, 22000, 32000, 45000])}
    return cards, sbcs, fodder


if __name__ == "__main__":
    cards, sbcs, fodder = ornek(int(sys.argv[1]) if len(sys.argv) > 1 else 0)
    print(len(cards), "kart,", sum(c["locked"] for c in cards), "kilitli")
    for s in sbcs:
        print(" ", s["name"], s.get("formation"), {k: v for k, v in s.items() if k not in ("name", "formation", "_file")})
