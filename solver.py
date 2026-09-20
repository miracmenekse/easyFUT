"""SBC çözücü (Google OR-Tools CP-SAT). Bütün SBC'ler tek modelde çözülür:
önce tamamlanan SBC sayısı en büyüklenir, sonra harcanan kart değeri + coin en küçüklenir.
Kimya ve reyting modeli Regista6/EA-FC-Automated-SBC-Solving (MIT) çalışmasına dayanır."""
import time

from ortools.sat.python import cp_model

# ---------- diziliş ----------

FORMATIONS = {
    "4-3-3": ["GK", "LB", "CB", "CB", "RB", "CM", "CM", "CM", "LW", "ST", "RW"],
    "4-3-3(2)": ["GK", "LB", "CB", "CB", "RB", "CM", "CDM", "CM", "LW", "ST", "RW"],
    "4-3-3(3)": ["GK", "LB", "CB", "CB", "RB", "CDM", "CDM", "CM", "LW", "ST", "RW"],
    "4-3-3(4)": ["GK", "LB", "CB", "CB", "RB", "CM", "CM", "CAM", "LW", "ST", "RW"],
    "4-4-2": ["GK", "LB", "CB", "CB", "RB", "LM", "CM", "CM", "RM", "ST", "ST"],
    "4-4-2(2)": ["GK", "LB", "CB", "CB", "RB", "LM", "CDM", "CDM", "RM", "ST", "ST"],
    "4-2-3-1": ["GK", "LB", "CB", "CB", "RB", "CDM", "CDM", "CAM", "CAM", "CAM", "ST"],
    "4-2-3-1(2)": ["GK", "LB", "CB", "CB", "RB", "CDM", "CDM", "LM", "CAM", "RM", "ST"],
    "4-1-2-1-2": ["GK", "LB", "CB", "CB", "RB", "CDM", "LM", "CAM", "RM", "ST", "ST"],
    "4-1-2-1-2(2)": ["GK", "LB", "CB", "CB", "RB", "CDM", "CM", "CAM", "CM", "ST", "ST"],
    "4-1-4-1": ["GK", "LB", "CB", "CB", "RB", "CDM", "LM", "CM", "CM", "RM", "ST"],
    "4-2-2-2": ["GK", "LB", "CB", "CB", "RB", "CDM", "CDM", "CAM", "CAM", "ST", "ST"],
    "4-2-1-3": ["GK", "LB", "CB", "CB", "RB", "CDM", "CDM", "CAM", "LW", "ST", "RW"],
    "4-2-4": ["GK", "LB", "CB", "CB", "RB", "CM", "CM", "LW", "ST", "ST", "RW"],
    "4-3-1-2": ["GK", "LB", "CB", "CB", "RB", "CM", "CM", "CM", "CAM", "ST", "ST"],
    "4-3-2-1": ["GK", "LB", "CB", "CB", "RB", "CM", "CM", "CM", "CF", "ST", "CF"],
    "4-4-1-1": ["GK", "LB", "CB", "CB", "RB", "LM", "CM", "CM", "RM", "CF", "ST"],
    "4-5-1": ["GK", "LB", "CB", "CB", "RB", "LM", "CM", "CAM", "CAM", "RM", "ST"],
    "4-5-1(2)": ["GK", "LB", "CB", "CB", "RB", "LM", "CM", "CM", "CM", "RM", "ST"],
    "3-4-1-2": ["GK", "CB", "CB", "CB", "LM", "CM", "CM", "RM", "CAM", "ST", "ST"],
    "3-4-2-1": ["GK", "CB", "CB", "CB", "LM", "CM", "CM", "RM", "CF", "ST", "CF"],
    "3-1-4-2": ["GK", "CB", "CB", "CB", "LM", "CM", "CDM", "CM", "RM", "ST", "ST"],
    "3-4-3": ["GK", "CB", "CB", "CB", "LM", "CM", "CM", "RM", "LW", "ST", "RW"],
    "3-5-2": ["GK", "CB", "CB", "CB", "CDM", "CDM", "LM", "CAM", "RM", "ST", "ST"],
    "5-2-1-2": ["GK", "LWB", "CB", "CB", "CB", "RWB", "CM", "CM", "CAM", "ST", "ST"],
    "5-2-2-1": ["GK", "LWB", "CB", "CB", "CB", "RWB", "CM", "CM", "LW", "ST", "RW"],
    "5-3-2": ["GK", "LWB", "CB", "CB", "CB", "RWB", "CM", "CDM", "CM", "ST", "ST"],
    "5-4-1": ["GK", "LWB", "CB", "CB", "CB", "RWB", "LM", "CM", "CM", "RM", "ST"],
}
DEFAULT_FORMATION = "4-3-3"
_ROW = {"GK": 0, "LB": 1, "CB": 1, "RB": 1, "LWB": 2, "RWB": 2, "CDM": 3, "LM": 4, "CM": 4, "RM": 4,
        "CAM": 5, "LW": 6, "RW": 6, "CF": 6, "ST": 7}


def layout(positions):
    """Slotların saha koordinatları (x, y %). Satır içinde soldan sağa: L*, orta, R*."""
    coords = [None] * len(positions)
    rows = {}
    for i, p in enumerate(positions):
        rows.setdefault(_ROW.get(p, 4), []).append(i)
    present = sorted(rows)  # sadece dizilişte olan satırlar, yukarıdan aşağı eşit aralıklı
    ys = {r: round(90 - 78 * k / max(1, len(present) - 1)) for k, r in enumerate(present)}
    for row, idx in rows.items():
        idx.sort(key=lambda i: (0 if positions[i].startswith("L") else 2 if positions[i].startswith("R") else 1, i))
        side = any(positions[i][0] in "LR" for i in idx)
        lo, hi = (12, 88) if side else (30, 70)
        n = len(idx)
        for k, i in enumerate(idx):
            coords[i] = (50 if n == 1 else round(lo + (hi - lo) * k / (n - 1)), ys[row])
    return coords


# ---------- kurallar ----------

CHEM_STEPS = {"club": (2, 4, 7), "league": (3, 5, 8), "nation": (2, 5, 8)}  # 1/2/3 kimya eşikleri
SPECIAL_CHEM = ("icon", "hero")  # pozisyonundaysa her zaman 3 kimya


def positions_of(card):
    alt = [p.strip() for p in str(card.get("positions") or "").replace(",", "|").split("|") if p.strip()]
    return [card.get("position", "")] + [p for p in alt if p != card.get("position")]


def squad_rating(ratings):
    """EA formülü: ortalamanın üstündeki farklar eklenir, toplam yuvarlanır, oyuncu sayısına tam bölünür."""
    n = len(ratings)
    avg = sum(ratings) / n
    return round(sum(ratings) + sum(max(0, r - avg) for r in ratings)) // n


def squad_chem(slots):
    """slots: [(slot_pos, card)] -> her oyuncunun kimyası (0-3)."""
    inpos = [c["source"] != "pazar" and pos in positions_of(c) for pos, c in slots]
    counts = {g: {} for g in CHEM_STEPS}
    for ok, (_, c) in zip(inpos, slots):
        if ok and c.get("rarity") not in SPECIAL_CHEM:
            for g in CHEM_STEPS:
                counts[g][c.get(g)] = counts[g].get(c.get(g), 0) + 1
    out = []
    for ok, (_, c) in zip(inpos, slots):
        if not ok:
            out.append(0)
        elif c.get("rarity") in SPECIAL_CHEM:
            out.append(3)
        else:
            out.append(min(3, sum(sum(counts[g].get(c.get(g), 0) >= t for t in CHEM_STEPS[g]) for g in CHEM_STEPS)))
    return out


def matches(card, req):
    if "all" in req:  # birleşik şart: hepsi birden (ör. reyting >= 75 VE nadirlik totw)
        return all(matches(card, r) for r in req["all"])
    v = card.get(req["field"], "")
    if "in" in req and v not in req["in"]:
        return False
    if "gte" in req and not (isinstance(v, int) and v >= req["gte"]):
        return False
    if "lte" in req and not (isinstance(v, int) and v <= req["lte"]):
        return False
    return True


# ---------- model ----------

COIN_WEIGHT = 2  # harcanan coin, kulüpteki kart değerinden 2 kat pahalı sayılır: önce kendi kartların


def _near(pos):
    """Kimya istemeyen SBC'de yerleşim için yakın pozisyonlar."""
    return {"GK": ["GK"], "CB": ["CB", "CDM"], "LB": ["LB", "LWB", "CB"], "RB": ["RB", "RWB", "CB"],
            "LWB": ["LWB", "LB", "LM"], "RWB": ["RWB", "RB", "RM"], "CDM": ["CDM", "CM", "CB"],
            "CM": ["CM", "CDM", "CAM"], "CAM": ["CAM", "CM", "CF"], "LM": ["LM", "LW", "LWB"],
            "RM": ["RM", "RW", "RWB"], "LW": ["LW", "LM", "ST"], "RW": ["RW", "RM", "ST"],
            "ST": ["ST", "CF"], "CF": ["CF", "ST", "CAM"]}.get(pos, [pos])


def place(cards, slots):
    """Seçilmiş kartları slotlara yerleştir: kendi pozisyonu > alternatif pozisyon > yakın > kalan yer."""
    out, left = [None] * len(slots), sorted(cards, key=lambda c: -c["rating"])
    tiers = [lambda c: [c.get("position")], lambda c: positions_of(c),
             lambda c: [q for p in positions_of(c) for q in _near(p)]]
    for tier in tiers:
        for s, pos in enumerate(slots):
            if out[s] is None:
                c = next((c for c in left if c["source"] != "pazar" and pos in tier(c)), None)
                if c:
                    out[s] = c
                    left.remove(c)
    for s in range(len(slots)):
        if out[s] is None:
            out[s] = left.pop(0)
    return list(zip(slots, out))


def _solve(jobs, cards, market, ccost, budget, time_limit, hint=None):
    """Tek CP-SAT modeli. Dönen: (sols, optimal_mi). sols[k]: None ya da {"cards": {i: slot}, "market": [(r, slot)]}"""
    m = cp_model.CpModel()
    n = len(cards)
    big = sum(ccost) + COIN_WEIGHT * sum(p for _, p in market) * 11 * max(1, len(jobs)) + 1

    use, done, spend_terms, cost_terms, info = {}, [], [], [], []
    for k, sbc in enumerate(jobs):
        size = sbc.get("size", 11)
        slots = FORMATIONS.get(sbc.get("formation"), FORMATIONS[DEFAULT_FORMATION]) if size == 11 else ["?"] * size
        d = m.NewBoolVar(f"done{k}")
        done.append(d)
        if k and jobs[k - 1].get("_file") == sbc.get("_file") and sbc.get("_file") and \
                jobs[k - 1]["name"] == sbc["name"]:
            m.Add(done[k - 1] >= d)  # aynı SBC'nin tekrarları sırayla: simetri kırma
        need_chem = size == 11 and (sbc.get("min_chem", 0) > 0 or sbc.get("min_player_chem", 0) > 0)
        no_market = sbc.get("min_player_chem", 0) > 0  # pazar kartının kimyası bilinmiyor

        u = [m.NewBoolVar(f"u{k}_{i}") for i in range(n)]
        units = []  # pazar kartları: (reyting, fiyat, bool, slot)
        x = {}
        if need_chem:  # kimya için oyuncu-slot eşleşmesi gerekir
            x = {(i, s): m.NewBoolVar(f"x{k}_{i}_{s}") for i in range(n) for s in range(size)}
            for i in range(n):
                m.Add(u[i] == sum(x[i, s] for s in range(size)))
            for s in range(size):
                ms = [] if no_market else [(r, p, m.NewBoolVar(f"m{k}_{r}_{s}"), s) for r, p in market]
                units += ms
                m.Add(sum(x[i, s] for i in range(n)) + sum(b for _, _, b, _ in ms) == d)
        else:  # sadece hangi kartlar: çok daha küçük model
            for r, p in market:
                cp = [m.NewBoolVar(f"m{k}_{r}_{j}") for j in range(size)]
                for a, b in zip(cp, cp[1:]):
                    m.Add(a >= b)  # kopyalar sırayla: simetri kırma
                units += [(r, p, b, None) for b in cp]
            m.Add(sum(u) + sum(b for _, _, b, _ in units) == size * d)
        for i in range(n):
            use[k, i] = u[i]
        names = {}
        for i, c in enumerate(cards):
            names.setdefault(c["name"], []).append(u[i])
        for vs in names.values():
            if len(vs) > 1:
                m.Add(sum(vs) <= 1)

        # reyting (EA formülünün tamsayı hali): n*S + Σ_r c_r*max(0, n*r - S) >= n²*T - n//2
        # c_r: r reytingli kaç kart seçildi. Reyting başına bir çarpım: kart başına olandan çok daha hızlı
        # (Regista6'nın squad_rating_constraint_3 fikri).
        T = sbc.get("min_rating", 0)
        if T:
            by_r = {}
            for i, c in enumerate(cards):
                by_r.setdefault(c["rating"], []).append(u[i])
            for r, _, b, _ in units:
                by_r.setdefault(r, []).append(b)
            S = m.NewIntVar(0, 99 * size, f"S{k}")
            m.Add(S == sum(r * sum(vs) for r, vs in by_r.items()))
            E = []
            for r, vs in by_r.items():
                c_r = m.NewIntVar(0, min(size, len(vs)), "")
                m.Add(c_r == sum(vs))
                g = m.NewIntVar(0, 99 * size, "")
                m.AddMaxEquality(g, [0, size * r - S])
                e = m.NewIntVar(0, 99 * size * size, "")
                m.AddMultiplicationEquality(e, [c_r, g])
                E.append(e)
            m.Add(size * S + sum(E) >= size * size * T - size // 2).OnlyEnforceIf(d)

        # oyuncu sayısı / aynı / farklı şartları
        for req in sbc.get("requirements", []):
            t = req.get("type", "count")
            if t == "count":
                expr = sum(u[i] for i, c in enumerate(cards) if matches(c, req)) + \
                    sum(b for r, _, b, _ in units if matches({"rating": r}, req))
                if "min" in req:
                    m.Add(expr >= req["min"]).OnlyEnforceIf(d)
                if "max" in req:
                    m.Add(expr <= req["max"])
            else:
                groups = {}
                for i, c in enumerate(cards):
                    groups.setdefault(c.get(req["field"], ""), []).append(u[i])
                if t == "same":
                    if "max" in req:
                        for vs in groups.values():
                            if len(vs) > req["max"]:
                                m.Add(sum(vs) <= req["max"])
                    if "min" in req:
                        hit = []
                        for vs in groups.values():
                            if len(vs) >= req["min"]:
                                b = m.NewBoolVar("")
                                m.Add(sum(vs) >= req["min"]).OnlyEnforceIf(b)
                                hit.append(b)
                        m.Add(sum(hit) >= 1).OnlyEnforceIf(d)
                elif t == "distinct":  # farklı lig/ülke/kulüp sayısı (pazar kartı sayılmaz)
                    has = []
                    for vs in groups.values():
                        h = m.NewBoolVar("")
                        m.AddMaxEquality(h, vs)
                        has.append(h)
                    if "min" in req:
                        m.Add(sum(has) >= req["min"]).OnlyEnforceIf(d)
                    if "max" in req:
                        m.Add(sum(has) <= req["max"])
                    if "exact" in req:
                        m.Add(sum(has) == req["exact"]).OnlyEnforceIf(d)

        # kimya: sadece pozisyonundaki oyuncular kimya alır ve verir
        if need_chem:
            inpos = []
            for i, c in enumerate(cards):
                ok = [s for s in range(size) if slots[s] in positions_of(c)]
                ip = m.NewBoolVar("")
                m.Add(ip == sum(x[i, s] for s in ok)) if ok else m.Add(ip == 0)
                inpos.append(ip)
            level = {}
            for g, steps in CHEM_STEPS.items():
                members = {}
                for i, c in enumerate(cards):
                    if c.get("rarity") not in SPECIAL_CHEM:
                        members.setdefault(c.get(g), []).append(i)
                for v, idx in members.items():
                    bs = []
                    for t in steps:
                        if len(idx) < t:
                            break
                        b = m.NewBoolVar("")
                        cnt = sum(inpos[i] for i in idx)
                        m.Add(cnt >= t).OnlyEnforceIf(b)
                        m.Add(cnt <= t - 1).OnlyEnforceIf(b.Not())
                        bs.append(b)
                    level[g, v] = sum(bs) if bs else 0
            pc = []
            for i, c in enumerate(cards):
                p = m.NewIntVar(0, 3, "")
                m.Add(p <= 3 * inpos[i])
                if c.get("rarity") not in SPECIAL_CHEM:
                    m.Add(p <= sum(level.get((g, c.get(g)), 0) for g in CHEM_STEPS))
                pc.append(p)
                if sbc.get("min_player_chem", 0) > 0:
                    m.Add(p >= sbc["min_player_chem"]).OnlyEnforceIf(u[i])
            if sbc.get("min_chem", 0) > 0:
                m.Add(sum(pc) >= sbc["min_chem"]).OnlyEnforceIf(d)
            cost_terms.append(size * d - sum(inpos))  # pozisyon dışı oyuncu başına 1 puan: eşitlikte kendi pozisyonu

        spend_terms += [p * b for _, p, b, _ in units]
        cost_terms += [ccost[i] * u[i] for i in range(n)]
        info.append((slots, x, units, u, size))

    for i in range(n):  # bir kart en fazla bir SBC'de
        m.Add(sum(use[k, i] for k in range(len(jobs))) <= 1)
    spent = sum(spend_terms)
    if market:
        m.Add(spent <= budget)
    m.Maximize(big * sum(done) - sum(cost_terms) - COIN_WEIGHT * spent)

    for k, sol in enumerate(hint or []):  # önceki (sıralı) çözümden başla
        slots, x, units, u, size = info[k]
        m.AddHint(done[k], sol is not None)
        sc, mk = (sol or {}).get("cards", {}), list((sol or {}).get("market", []))
        for i in range(n):
            m.AddHint(u[i], i in sc)
        for (i, s_), v in x.items():
            m.AddHint(v, sc.get(i) == s_)
        for r, _, b, s_ in units:
            hit = next((j for j, (r2, s2) in enumerate(mk) if r2 == r and (s_ is None or s2 == s_)), None)
            m.AddHint(b, hit is not None)
            if hit is not None:
                mk.pop(hit)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = 8
    status = solver.Solve(m)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return [None] * len(jobs), False
    sols = []
    for k in range(len(jobs)):
        slots, x, units, u, size = info[k]
        if not solver.Value(done[k]):
            sols.append(None)
            continue
        sc = {i: next((s_ for s_ in range(size) if solver.Value(x[i, s_])), None) if x else None
              for i in range(n) if solver.Value(u[i])}
        sols.append({"cards": sc, "market": [(r, s_) for r, _, b, s_ in units if solver.Value(b)]})
    return sols, status == cp_model.OPTIMAL


def _chosen(k, sbc, sol, cards, prices):
    """Çözümü [(slot_pos, kart)] listesine çevirir."""
    size = sbc.get("size", 11)
    slots = FORMATIONS.get(sbc.get("formation"), FORMATIONS[DEFAULT_FORMATION]) if size == 11 else ["?"] * size
    bought = [{"id": f"m{k}-{j}", "name": f"[SATIN AL] {r} genel kart", "rating": r, "price": prices[r],
               "source": "pazar", "tradeable": True, "_slot": s} for j, (r, s) in enumerate(sol["market"])]
    if any(s is not None for s in sol["cards"].values()) or any(c["_slot"] is not None for c in bought):
        by_slot = {s: cards[i] for i, s in sol["cards"].items()} | {c["_slot"]: c for c in bought}
        return [(slots[s], by_slot[s]) for s in range(size)]
    return place([cards[i] for i in sol["cards"]] + bought, slots)


def _score(sols, ccost, prices):
    done = [s for s in sols if s]
    return (len(done), -sum(ccost[i] for s in done for i in s["cards"])
            - COIN_WEIGHT * sum(prices[r] for s in done for r, _ in s["market"]))


def _sequential(jobs, cards, market, ccost, budget, time_budget):
    """Hızlı başlangıç: SBC'leri birkaç farklı sırayla tek tek çöz, en iyisini al."""
    prices = dict(market)
    J = len(jobs)
    hard = lambda k: (jobs[k].get("min_rating", 0), len(jobs[k].get("requirements", [])), jobs[k].get("min_chem", 0))
    tight = lambda k: (jobs[k].get("min_chem", 0) > 0 or jobs[k].get("min_player_chem", 0) > 0,
                       len(jobs[k].get("requirements", [])), jobs[k].get("min_rating", 0))
    # en kısıtlı SBC'ler önce: uygun kartları kolay SBC'ler kapmadan
    orders = [sorted(range(J), key=tight, reverse=True), sorted(range(J), key=hard, reverse=True),
              sorted(range(J), key=hard), list(range(J))]
    per_job = max(1.0, time_budget / (len(orders) * max(1, J)))  # tek SBC genelde <0,3 sn; alt sınır yük altında da çözsün
    best = None
    for order in orders:
        free, left, sols = list(range(len(cards))), budget, [None] * J
        for k in order:
            sub, _ = _solve([jobs[k]], [cards[i] for i in free], market if left > 0 else [],
                            [ccost[i] for i in free], left, per_job)
            if sub[0]:
                sol = {"cards": {free[j]: s for j, s in sub[0]["cards"].items()}, "market": sub[0]["market"]}
                sols[k] = sol
                free = [i for i in free if i not in sol["cards"]]
                left -= sum(prices[r] for r, _ in sol["market"])
        if best is None or _score(sols, ccost, prices) > _score(best, ccost, prices):
            best = sols
    return best


def plan(jobs, club, fodder, cost, budget=0, buy=True, time_limit=20):
    """Bütün SBC'ler: önce hızlı sıralı çözüm, sonra onu ipucu alan ortak model iyileştirir.
    Dönen: {"done": [(sbc, [(slot_pos, card)])], "skipped": [sbc], "spent": int, "status": str}"""
    t0 = time.time()
    cards = [c for c in club if not c.get("locked")]
    market = sorted(fodder.items()) if buy and budget > 0 else []
    prices = dict(market)
    ccost = [int(cost(c)) for c in cards]
    seq = _sequential(jobs, cards, market, ccost, budget, time_limit * 0.4)
    joint, optimal = _solve(jobs, cards, market, ccost, budget, max(2, time_limit - (time.time() - t0)), hint=seq)
    sols = joint if _score(joint, ccost, prices) >= _score(seq, ccost, prices) else seq
    out = [(sbc, _chosen(k, sbc, sol, cards, prices)) for k, (sbc, sol) in enumerate(zip(jobs, sols)) if sol]
    return {"done": out, "skipped": [sbc for sbc, sol in zip(jobs, sols) if not sol],
            "spent": sum(prices[r] for sol in sols if sol for r, _ in sol["market"]),
            "status": "kanıtlanmış en iyi" if optimal and sols is joint else "süre sınırında bulunan en iyi"}


def describe(slots):
    """Çözümü arayüz/CLI için zenginleştirir: koordinat, pozisyon uyumu, kimya."""
    pos = [p for p, _ in slots]
    xy = layout(pos) if len(pos) == 11 else [(None, None)] * len(pos)
    chem = squad_chem(slots)
    rows = []
    for (p, c), (x, y), ch in zip(slots, xy, chem):
        fit = "pazar" if c["source"] == "pazar" else "tam" if c.get("position") == p else \
            "alt" if p in positions_of(c) else "farklı"
        rows.append({"pos": p, "x": x, "y": y, "card": c, "fit": fit, "chem": ch})
    return rows, sum(chem)


FIELD_TR = {"league": "Lig", "nation": "Ülke", "club": "Kulüp", "rarity": "Nadirlik", "rating": "Reyting",
            "position": "Pozisyon"}


def check(sbc, slots):
    """Çözümü çözücüden bağımsız doğrular: [(şart metni, sağlandı mı)]."""
    cards = [c for _, c in slots]
    club = [c for c in cards if c["source"] != "pazar"]
    out = []
    if sbc.get("min_rating"):
        r = squad_rating([c["rating"] for c in cards])
        out.append((f"Takım reytingi en az {sbc['min_rating']} (şu an {r})", r >= sbc["min_rating"]))
    chem = squad_chem(slots)
    if sbc.get("min_chem"):
        out.append((f"Toplam kimya en az {sbc['min_chem']} (şu an {sum(chem)})", sum(chem) >= sbc["min_chem"]))
    if sbc.get("min_player_chem"):
        out.append((f"Oyuncu başı kimya en az {sbc['min_player_chem']}", min(chem) >= sbc["min_player_chem"]))
    for req in sbc.get("requirements", []):
        t, f = req.get("type", "count"), FIELD_TR.get(req.get("field"), req.get("field"))
        if t == "count":
            n = sum(matches(c, req) for c in cards)
            one = lambda q: f"{FIELD_TR.get(q.get('field'), q.get('field'))} " + (
                ", ".join(q["in"]) if "in" in q else f"≥ {q['gte']}" if "gte" in q else f"≤ {q.get('lte')}")
            f, what = ("", " ve ".join(one(q) for q in req["all"])) if "all" in req else (f, one(req).split(" ", 1)[1])
            ok = n >= req.get("min", 0) and n <= req.get("max", 99)
            out.append((f"{f} {what}: {n} oyuncu".strip() + (f" (en az {req['min']})" if "min" in req else "")
                        + (f" (en fazla {req['max']})" if "max" in req else ""), ok))
        elif t == "same":
            vals = [c.get(req["field"]) for c in club]
            top = max((vals.count(v) for v in set(vals)), default=0)
            ok = top <= req.get("max", 99) and top >= req.get("min", 0)
            out.append((f"Aynı {f.lower()} en çok {top} oyuncu"
                        + (f" (sınır {req['max']})" if "max" in req else f" (en az {req.get('min')})"), ok))
        elif t == "distinct":
            k = len({c.get(req["field"]) for c in club})
            ok = k >= req.get("min", 0) and k <= req.get("max", 99) and k == req.get("exact", k)
            lim = f"tam {req['exact']}" if "exact" in req else ", ".join(
                x for x in (f"en az {req['min']}" if "min" in req else "", f"en fazla {req['max']}" if "max" in req else "") if x)
            out.append((f"Farklı {f.lower()} sayısı {k} ({lim})", ok))
    return out
