"""SBC çözücü (Google OR-Tools CP-SAT). Bütün SBC'ler tek modelde çözülür:
önce tamamlanan SBC sayısı en büyüklenir, sonra harcanan kart değeri + coin en küçüklenir.
Kimya ve reyting modeli Regista6/EA-FC-Automated-SBC-Solving (MIT) çalışmasına dayanır."""
import itertools, os, time

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
    "5-2-1-2(2)": ["GK", "LB", "CB", "CB", "CB", "RB", "CM", "CM", "CAM", "ST", "ST"],
    "5-2-2-1": ["GK", "LWB", "CB", "CB", "CB", "RWB", "CM", "CM", "LW", "ST", "RW"],
    "5-3-2": ["GK", "LWB", "CB", "CB", "CB", "RWB", "CM", "CDM", "CM", "ST", "ST"],
    "5-3-2(2)": ["GK", "LB", "CB", "CB", "CB", "RB", "CM", "CDM", "CM", "ST", "ST"],
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
GROUPS = tuple(CHEM_STEPS)
SPECIAL_CHEM = ("icon", "hero")  # pozisyonundaysa her zaman 3 kimya; kulüp/lig/ülke sayımına girmez
# Alınacak oyuncu (source "pazar" ya da "eksik"): belirtilmemiş alanı None, yani "herhangi". Şartlar bunlar için
# en kötü durumla değerlendirilir: hangi değer gelirse gelsin SBC tamamlanır. Kulüp kartında boş alan "" = değer yok.
BUY = ("pazar", "eksik")


def known(v):
    return v is not None and v != ""


def _val(card, f):
    v = card.get(f)
    return v if v is not None or card.get("source") in BUY else ""


def positions_of(card):
    alt = [p.strip() for p in str(card.get("positions") or "").replace(",", "|").split("|") if p.strip()]
    return [card.get("position", "")] + [p for p in alt if p != card.get("position")]


def squad_rating(ratings):
    """EA formülü: ortalamanın üstündeki farklar eklenir, toplam yuvarlanır, oyuncu sayısına tam bölünür."""
    n = len(ratings)
    avg = sum(ratings) / n
    return round(sum(ratings) + sum(max(0, r - avg) for r in ratings)) // n


def squad_chem(slots):
    """slots: [(slot_pos, card)] -> her oyuncunun kimyası (0-3). Bilinmeyen alan (None) kimya vermez, almaz."""
    inpos = [c["source"] != "pazar" and pos in positions_of(c) for pos, c in slots]
    counts = {g: {} for g in GROUPS}
    for ok, (_, c) in zip(inpos, slots):
        if ok and c.get("rarity") not in SPECIAL_CHEM:
            for g in GROUPS:
                if known(c.get(g)):
                    counts[g][c[g]] = counts[g].get(c[g], 0) + 1
    out = []
    for ok, (_, c) in zip(inpos, slots):
        if not ok:
            out.append(0)
        elif c.get("rarity") in SPECIAL_CHEM:
            out.append(3)
        else:
            out.append(min(3, sum(sum(counts[g][c[g]] >= t for t in CHEM_STEPS[g])
                                  for g in GROUPS if known(c.get(g)))))
    return out


def matches(card, req, unknown=False):
    """Kart şartı sağlıyor mu. Alanı bilinmiyorsa (None) sonuç `unknown`: "en az" şartında False (sayılmaz),
    "en fazla" şartında True (sayılır) verilerek en kötü durum alınır."""
    if "all" in req:  # birleşik şart: hepsi birden (ör. reyting >= 75 VE nadirlik totw)
        return all(matches(card, r, unknown) for r in req["all"])
    v = _val(card, req["field"])
    if v is None:
        return unknown
    if "in" in req and v not in req["in"]:
        return False
    if "gte" in req and not (isinstance(v, int) and v >= req["gte"]):
        return False
    if "lte" in req and not (isinstance(v, int) and v <= req["lte"]):
        return False
    return True


# ---------- model ----------

COIN_WEIGHT = 2  # harcanan coin, kulüpteki kart değerinden 2 kat pahalı sayılır: önce kendi kartların
OOP = 1  # pozisyon dışı oyuncu başına ceza (eşitlik bozucu): eşit maliyette oyuncu kendi pozisyonunda


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
                c = next((c for c in left if c["source"] not in BUY and pos in tier(c)), None)
                if c:
                    out[s] = c
                    left.remove(c)
    for s in range(len(slots)):
        if out[s] is None:
            out[s] = left.pop(0)
    return list(zip(slots, out))


def _slots(sbc):
    size = sbc.get("size", 11)
    return FORMATIONS.get(sbc.get("formation"), FORMATIONS[DEFAULT_FORMATION]) if size == 11 else ["?"] * size


def _needs_chem(sbc):
    return sbc.get("size", 11) == 11 and (sbc.get("min_chem", 0) > 0 or sbc.get("min_player_chem", 0) > 0)


def _every(sbc):
    """Kadrodaki herkesin sağlaması gereken şartlar (min = kadro sayısı)."""
    return [r for r in sbc.get("requirements", []) if r.get("type", "count") == "count"
            and r.get("min", 0) >= sbc.get("size", 11)]


def candidates(sbc, cards):
    """SBC'de kullanılabilecek kartlar: herkesin sağlaması gereken şartı sağlamayan ya da "en fazla 0" şartına
    takılan kart baştan elenir (model küçülür)."""
    every = _every(sbc)
    zero = [r for r in sbc.get("requirements", []) if r.get("type", "count") == "count" and r.get("max") == 0]
    return [i for i, c in enumerate(cards)
            if all(matches(c, r) for r in every) and not any(matches(c, r) for r in zero)]


def _parts(req):
    ps = req.get("all", [req])
    return [q for q in ps if q["field"] == "rating"], [q for q in ps if q["field"] != "rating"]


def _add_sbc(m, k, sbc, cards, cand, market, wild):
    """Tek SBC'nin kısıtları. Dönen sözlük: değişkenler + maliyet terimleri (çözüm okumak için)."""
    size = sbc.get("size", 11)
    slots = _slots(sbc)
    d = m.NewBoolVar(f"d{k}")
    fixed = sbc.get("fixed", [])
    chem = _needs_chem(sbc)
    pchem = sbc.get("min_player_chem", 0) if chem else 0
    real = [(cards[i], m.NewBoolVar(f"u{k}_{i}")) for i in cand] + [(f, d) for f in fixed]
    mk = {} if pchem else {r: (p, m.NewIntVar(0, size, f"m{k}_{r}")) for r, p in market}
    # yarım SBC: s. slotta eksik oyuncu; profil j (alan değerleri, None = herhangi) ve reyting r seçilir
    W = size if wild else 0
    profs = wild["profiles"] if wild else []
    wr = [(r, p) for r, p in (wild["ratings"] if wild else [])
          if all(matches({"source": "eksik", "rating": r}, q, True) for q in _every(sbc))]
    if wild and not (sbc.get("min_rating") or sbc.get("max_rating")):
        # takım reytingi şartı yoksa reyting sadece reyting şartlarındaki üyelik için önemli: her üyelik desenine
        # en ucuz reyting yeter (model küçülür)
        rq = [_parts(r)[0] for r in sbc.get("requirements", []) if r.get("type", "count") == "count" and _parts(r)[0]]
        best = {}
        for r, p in wr:
            key = tuple(all(matches({"rating": r}, q) for q in qs) for qs in rq)
            if key not in best or p + r < sum(best[key]):
                best[key] = (r, p)
        wr = sorted(best.values())
    z = [[m.NewBoolVar("") for _ in profs] for _ in range(W)]
    rb = [{r: m.NewBoolVar("") for r, _ in wr} for _ in range(W)]
    a = [m.NewBoolVar("") for _ in range(W)]  # s. slotta eksik oyuncu var mı
    for s in range(W):
        m.Add(sum(z[s]) == a[s])
        m.Add(sum(rb[s].values()) == a[s])
    m.Add(sum(v for _, v in real) + sum(v for _, v in mk.values()) + sum(a) == size * d)
    if wild:
        m.Add(d == 1)
    names = {}
    for c, v in real:
        names.setdefault(c["name"], []).append(v)
    for vs in names.values():
        if len(vs) > 1:
            m.Add(sum(vs) <= 1)

    # pozisyon: kart i, P pozisyonunda oynuyorsa y=1 (aynı pozisyonlu slotlar birbirinin yerine geçer: simetri yok)
    ys = [[] for _ in real]  # [(P, y)]
    inpos = [0] * len(real)
    oop = 0
    if chem:
        cnt = {}
        for p in slots:
            cnt[p] = cnt.get(p, 0) + 1
        for idx, (c, v) in enumerate(real):
            ys[idx] = [(P, m.NewBoolVar("")) for P in dict.fromkeys(positions_of(c)) if P in cnt]
            if ys[idx]:
                inpos[idx] = sum(y for _, y in ys[idx])
                m.Add(inpos[idx] <= v)
            elif pchem:
                m.Add(v == 0)
        for P, n_ in cnt.items():
            m.Add(sum(y for yl in ys for Q, y in yl if Q == P) + sum(a[s] for s in range(W) if slots[s] == P) <= n_)
        for s in range(W):  # aynı pozisyondaki eksik slotları sırayla doldur: simetri kırma
            nxt = next((t for t in range(s + 1, W) if slots[t] == slots[s]), None)
            if nxt is not None:
                m.Add(a[s] >= a[nxt])
                m.Add(sum(j * zz for j, zz in enumerate(z[s])) >= sum(j * zz for j, zz in enumerate(z[nxt])))
        oop = sum(v for c, v in real[:len(cand)]) - sum(inpos[:len(cand)])
    else:
        for s in range(W - 1):
            m.Add(a[s] >= a[s + 1])
            m.Add(sum(j * zz for j, zz in enumerate(z[s])) >= sum(j * zz for j, zz in enumerate(z[s + 1])))

    # eksik oyuncunun alan değerleri: wv[s][g][değer] = o değerde mi (0/1 ifade)
    wv = [{g: {} for g in GROUPS + ("rarity",)} for _ in range(W)]
    for s in range(W):
        for j, p in enumerate(profs):
            for g in wv[s]:
                if known(p.get(g)):
                    wv[s][g].setdefault(p[g], []).append(z[s][j])

    # kimya: sadece pozisyonundaki oyuncular kimya alır ve verir
    if chem:
        lvl = {}
        for g, steps in CHEM_STEPS.items():
            members = {}
            for idx, (c, v) in enumerate(real):
                if ys[idx] and c.get("rarity") not in SPECIAL_CHEM and known(c.get(g)):
                    members.setdefault(c[g], []).append(inpos[idx])
            for s in range(W):
                for val, zs in wv[s][g].items():
                    members.setdefault(val, []).append(sum(zs))
            for val, ex in members.items():
                prev, bs = None, []
                for t in steps:
                    if len(ex) < t:
                        break
                    b = m.NewBoolVar("")
                    m.Add(sum(ex) >= t).OnlyEnforceIf(b)
                    if prev is not None:
                        m.AddImplication(b, prev)
                    prev = b
                    bs.append(b)
                lvl[g, val] = sum(bs)
        pcs = []
        for idx, (c, v) in enumerate(real):
            if not ys[idx]:
                continue
            p = m.NewIntVar(0, 3, "")
            m.Add(p <= 3 * inpos[idx])
            if c.get("rarity") not in SPECIAL_CHEM:
                m.Add(p <= sum(lvl.get((g, c[g]), 0) for g in GROUPS if known(c.get(g))))
            if pchem:
                m.Add(p >= pchem).OnlyEnforceIf(v)
            pcs.append(p)
        for s in range(W):
            p = m.NewIntVar(0, 3, "")
            m.Add(p <= 3 * a[s])
            terms = []
            for g in GROUPS:
                if not wv[s][g]:
                    continue
                lg = m.NewIntVar(0, 3, "")
                m.Add(lg <= 3 * sum(sum(zs) for zs in wv[s][g].values()))
                for val, zs in wv[s][g].items():
                    m.Add(lg <= lvl.get((g, val), 0) + 3 - 3 * sum(zs))
                terms.append(lg)
            m.Add(p <= sum(terms))
            if pchem:
                m.Add(p >= pchem * a[s])
            pcs.append(p)
        if sbc.get("min_chem", 0) > 0:
            m.Add(sum(pcs) >= sbc["min_chem"]).OnlyEnforceIf(d)

    # takım reytingi (EA formülünün tamsayı hali): n*S + Σ_r c_r*max(0, n*r - S) >= n²*T - (n-1)//2
    # c_r: r reytingli kaç oyuncu. Reyting başına bir çarpım (Regista6'nın squad_rating_constraint_3 fikri).
    T, T2 = sbc.get("min_rating", 0), sbc.get("max_rating", 0)
    if T or T2:
        n = size
        by_r = {}
        for c, v in real:
            by_r.setdefault(c["rating"], []).append(v)
        for r, (_, v) in mk.items():
            by_r.setdefault(r, []).append(v)
        for s in range(W):
            for r, b in rb[s].items():
                by_r.setdefault(r, []).append(b)
        S = m.NewIntVar(0, 99 * n, f"S{k}")
        m.Add(S == sum(r * sum(vs) for r, vs in by_r.items()))
        E = []
        for r, vs in by_r.items():
            c_r = m.NewIntVar(0, n, "")
            m.Add(c_r == sum(vs))
            g_ = m.NewIntVar(0, 99 * n, "")
            m.AddMaxEquality(g_, [0, n * r - S])
            e = m.NewIntVar(0, 99 * n * n, "")
            m.AddMultiplicationEquality(e, [c_r, g_])
            E.append(e)
        half = (n - 1) // 2  # yuvarlama: kesirli kısım tam 0,5 olabiliyorsa (çift n) güvenli taraf
        if T:
            m.Add(n * S + sum(E) >= n * n * T - half).OnlyEnforceIf(d)
        if T2:  # "Team Rating: Max X"
            m.Add(n * S + sum(E) <= n * n * T2 + n * n - n + half)

    # oyuncu sayısı / aynı / farklı şartları (alınacak oyuncuda bilinmeyen alan: en kötü durum)
    for req in sbc.get("requirements", []):
        t = req.get("type", "count")
        if t == "count":
            rp, fp = _parts(req)
            must = [v for c, v in real if matches(c, req)]
            could = list(must)
            for r, (_, v) in mk.items():
                buy = {"source": "pazar", "rating": r}
                must += [v] if matches(buy, req) else []
                could += [v] if matches(buy, req, True) else []
            for s in range(W):
                for unknown, lst in ((False, must), (True, could)):
                    if unknown and "max" not in req or not unknown and "min" not in req:
                        continue
                    zj = [z[s][j] for j, p in enumerate(profs)
                          if all(matches(p | {"source": "eksik"}, q, unknown) for q in fp)]
                    rr = [b for r, b in rb[s].items() if all(matches({"rating": r}, q) for q in rp)]
                    if not fp:
                        lst.append(sum(rr))
                    elif not rp:
                        lst.append(sum(zj))
                    else:  # iki alan birden: ikisinin VE'si
                        w = m.NewBoolVar("")
                        if unknown:
                            m.Add(w >= sum(zj) + sum(rr) - 1)
                        else:
                            m.Add(w <= sum(zj))
                            m.Add(w <= sum(rr))
                        lst.append(w)
            if "min" in req:
                m.Add(sum(must) >= req["min"]).OnlyEnforceIf(d)
            if "max" in req:
                m.Add(sum(could) <= req["max"])
            continue
        f = req["field"]
        groups, unk = {}, [v for _, v in mk.values()]  # unk: alanı bilinmeyen oyuncular
        for c, v in real:
            if known(c.get(f)):
                groups.setdefault(c[f], []).append(v)
        for s in range(W):
            for j, p in enumerate(profs):
                (groups.setdefault(p[f], []) if known(p.get(f)) else unk).append(z[s][j])
        if t == "same":
            if "max" in req:  # bilinmeyenlerin hepsi en kalabalık gruba girebilir
                for vs in list(groups.values()) + [[]]:
                    m.Add(sum(vs) + sum(unk) <= req["max"])
            if "min" in req:
                hit = []
                for vs in groups.values():
                    if len(vs) >= req["min"]:
                        b = m.NewBoolVar("")
                        m.Add(sum(vs) >= req["min"]).OnlyEnforceIf(b)
                        hit.append(b)
                m.Add(sum(hit) >= 1).OnlyEnforceIf(d)
        elif t == "distinct":  # farklı lig/ülke/kulüp sayısı; bilinmeyen: en az'da yok, en fazla'da yeni değer
            lo, hi = req.get("exact", req.get("min")), req.get("exact", req.get("max"))
            has = []
            for vs in groups.values():
                h = m.NewBoolVar("")
                if lo is not None:
                    m.Add(h <= sum(vs))
                if hi is not None:
                    for x in vs:
                        m.Add(h >= x)
                has.append(h)
            if lo is not None:
                m.Add(sum(has) >= lo).OnlyEnforceIf(d)
            if hi is not None:
                m.Add(sum(has) + sum(unk) <= hi)

    price = dict(wr)
    return {"d": d, "real": real, "ys": ys, "mk": mk, "z": z, "rb": rb, "a": a, "cand": cand,
            "missing": sum(a),
            "specs": sum(z[s][j] * sum(known(v) for v in p.values()) for s in range(W) for j, p in enumerate(profs)),
            "cost": OOP * oop + sum(COIN_WEIGHT * p_ * v for p_, v in mk.values())
            + sum((price[r] + r) * b for s in range(W) for r, b in rb[s].items()),
            "spend": sum(p_ * v for p_, v in mk.values())}




OK = (cp_model.OPTIMAL, cp_model.FEASIBLE)
WORKERS = min(8, os.cpu_count() or 4)


def _lex(m, goals, time_limit):
    """Hedefleri sırayla çöz, her biri bir öncekinin en iyi değeri sabitken.
    Dönen: (değişken değerleri ya da None, her hedef için kanıtlandı mı)."""
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = WORKERS
    end = time.time() + time_limit
    vals, proven = None, []
    for i, (sense, var) in enumerate(goals):
        (m.Maximize if sense == "max" else m.Minimize)(var)
        left = end - time.time()
        # ilk hedef en önemlisi: sürenin çoğu onun; sonrakilere de biraz kalsın
        solver.parameters.max_time_in_seconds = max(1.0, left * (0.75 if i < len(goals) - 1 else 1.0))
        st = solver.Solve(m)
        if st not in OK:
            return vals, proven + [vals is None and st == cp_model.INFEASIBLE] + [False] * (len(goals) - i - 1)
        proven.append(st == cp_model.OPTIMAL)
        vals = [solver.Value(m.GetIntVarFromProtoIndex(j)) for j in range(len(m.Proto().variables))]
        m.Add(var >= vals[var.Index()]) if sense == "max" else m.Add(var <= vals[var.Index()])
        m.ClearHints()  # sonraki hedef bu çözümden başlasın
        for j, x in enumerate(vals):
            m.AddHint(m.GetIntVarFromProtoIndex(j), x)
    return vals, proven


def _extract(inf, V, sbc):
    """Model değerlerinden bir SBC'nin çözümü (yapılmadıysa None)."""
    if not V(inf["d"]):
        return None
    pos = lambda idx: next((P for P, y in inf["ys"][idx] if V(y)), None)
    nc = len(inf["cand"])
    return {"cards": {i: pos(idx) for idx, (i, (_, v)) in enumerate(zip(inf["cand"], inf["real"])) if V(v)},
            "fixed": [pos(nc + j) for j in range(len(sbc.get("fixed", [])))],
            "market": [r for r, (_, v) in inf["mk"].items() for _ in range(V(v))],
            "wild": [(s, next(j for j, zz in enumerate(inf["z"][s]) if V(zz)),
                      next(r for r, b in inf["rb"][s].items() if V(b)))
                     for s in range(len(inf["a"])) if V(inf["a"][s])]}


def _hint(m, inf, sol):
    """Bir SBC çözümünü modele başlangıç noktası olarak ver (kartlar ve oynadıkları pozisyon)."""
    m.AddHint(inf["d"], sol is not None)
    used, cnt = (sol or {}).get("cards", {}), {}
    for r in (sol or {}).get("market", []):
        cnt[r] = cnt.get(r, 0) + 1
    for idx, (i, (_, v)) in enumerate(zip(inf["cand"], inf["real"])):
        m.AddHint(v, i in used)
        for P, y in inf["ys"][idx]:
            m.AddHint(y, i in used and used[i] == P)
    for r, (_, v) in inf["mk"].items():
        m.AddHint(v, cnt.get(r, 0))


def _solve_wild(sbc, cards, ccost, time_limit, wild):
    """Yarım SBC modeli: SBC mutlaka tamamlanır, kartı olmayan yerler eksik oyuncu. Önce eksik sayısı, sonra maliyet
    en küçük. Dönen: (çözüm ya da None, [eksik sayısı kanıtlandı mı, maliyet kanıtlandı mı])"""
    m = cp_model.CpModel()
    inf = _add_sbc(m, 0, sbc, cards, candidates(sbc, cards), [], wild)

    def var(expr, hi):
        v = m.NewIntVar(0, hi, "")
        m.Add(v == expr)
        return v
    cost = var(sum(ccost[i] * v for i, (_, v) in zip(inf["cand"], inf["real"])) + inf["cost"], sum(ccost) + 10 ** 7)
    vals, proven = _lex(m, [("min", var(inf["missing"], 99)), ("min", cost)], time_limit)
    return (_extract(inf, lambda x: vals[x.Index()], sbc) if vals else None), proven


def _chosen(k, sbc, sol, cards, prices, profiles=()):
    """Çözümü [(slot_pos, kart)] listesine çevirir."""
    slots = _slots(sbc)
    unknown = {g: None for g in GROUPS + ("rarity",)}
    bought = [unknown | {"id": f"m{k}-{j}", "name": f"[SATIN AL] {r} genel kart", "rating": r,
                         "price": prices.get(r, 0), "source": "pazar", "tradeable": True, "position": None}
              for j, r in enumerate(sol["market"])]
    fixed = [f | {"source": "hazır", "id": f"f{k}-{j}"} for j, f in enumerate(sbc.get("fixed", []))]
    missing = {s: unknown | {g: profiles[j].get(g) for g in unknown} |
               {"name": "Eksik oyuncu", "rating": r, "source": "eksik", "id": f"w{k}-{s}", "price": 0}
               for s, j, r in sol.get("wild", [])}
    real = [(cards[i], P) for i, P in sol["cards"].items()] + list(zip(fixed, sol.get("fixed") or [None] * len(fixed)))
    out = [None] * len(slots)
    rest = [c for c, _ in real] + bought
    if _needs_chem(sbc):  # çözücünün pozisyonları: eksik oyuncu kendi slotunda, kartlar oynadığı pozisyonda
        out = [missing.get(s) for s in range(len(slots))]
        rest = bought[:]
        for c, P in real:
            s = next((s for s in range(len(slots)) if out[s] is None and slots[s] == P), None) if P else None
            if s is None:
                rest.append(c)
            else:
                out[s] = c
    else:
        rest += list(missing.values())
    free = [s for s in range(len(slots)) if out[s] is None]
    for s, (_, c) in zip(free, place(rest, [slots[s] for s in free])):
        out[s] = c
    for pos, c in zip(slots, out):
        if c["source"] == "eksik":
            c["position"] = c["positions"] = pos  # bu pozisyonda alınacak
    return list(zip(slots, out))


def _negotiate(jobs, cards, ccost, time_budget):
    """Hızlı başlangıç çözümü (PathFinder benzeri pazarlık): her SBC tek başına, bütün kartlarla çözülür; başka
    SBC'nin de kullandığı kartın bedeli her turda artar, SBC'ler başka kart bulmaya zorlanır. Çakışma kalmayınca
    biter. Dönen: (sols, hepsi çakışmasız mı, son çözümler); çakışma kaldıysa en çok çakışan SBC'ler çıkarılır
    (None); son çözümler çakışanları da içerir (ortak modele ipucu)."""
    end = time.time() + time_budget
    models = []
    for sbc in jobs:
        m = cp_model.CpModel()
        inf = _add_sbc(m, 0, sbc, cards, candidates(sbc, cards), [], None)
        m.Add(inf["d"] == 1)
        models.append((m, inf))
    unit = max(500, sum(ccost) // max(1, len(cards)))  # ceza birimi: ortalama kart değeri
    hist, owner, sols = [0] * len(cards), {}, [None] * len(jobs)
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = WORKERS
    for it in range(1, 200):
        for k, (m, inf) in enumerate(models):
            left = end - time.time()
            if left <= 0:
                break
            others = lambda i: len(owner.get(i, set()) - {k})
            m.Minimize(sum((ccost[i] + unit * (hist[i] + it * others(i))) * v
                           for i, (_, v) in zip(inf["cand"], inf["real"])) + inf["cost"])
            m.ClearHints()
            if sols[k]:
                _hint(m, inf, sols[k])
            solver.parameters.max_time_in_seconds = min(3.0, left)  # zor SBC tek başına birkaç sn
            if solver.Solve(m) not in OK:
                continue
            for i in (sols[k] or {}).get("cards", {}):
                owner[i].discard(k)
            sols[k] = _extract(inf, solver.Value, jobs[k])
            for i in sols[k]["cards"]:
                owner.setdefault(i, set()).add(k)
        clash = [i for i, ks in owner.items() if len(ks) > 1]
        if not clash and all(sols):
            return sols, True, sols
        if time.time() >= end:
            break
        for i in clash:
            hist[i] += 1
    alive = {k for k in range(len(jobs)) if sols[k]}
    while True:  # çakışma kaldı: en çok çakışan SBC'yi çıkar
        cnt = {}
        for ks in owner.values():
            if len(ks & alive) > 1:
                for k in ks & alive:
                    cnt[k] = cnt.get(k, 0) + 1
        if not cnt:
            break
        alive.discard(max(cnt, key=cnt.get))
    return [sols[k] if k in alive else None for k in range(len(jobs))], False, sols


def _feasible(jobs, sel, cards, market, ccost, budget, time_limit, hints=None, minimize=False, soft=False, bans=()):
    """sel'deki SBC'lerin hepsi birden yapılabilir mi? Saf uygunluk sorusu (SBC'ler "yapılacak" diye sabit): aynı
    sorunun "en çok kaç SBC" biçiminden çok daha hızlı çözülüyor. minimize: olursa en düşük maliyetliyi ara.
    soft: "bir kart bir SBC'de" kuralı yumuşak (aşım en aza): çakışan ipucu bile geçerli başlangıç olur.
    bans: [(iş, kart)] bu kart bu SBC'de kullanılmasın.
    Dönen: ("evet", {k: çözüm}, maliyet kanıtlı mı) | ("hayır", sel, True) | ("bilinmiyor", ara çözüm ya da None, False)
    Ara çözüm (soft): {"sols": {k: çözüm}, "clash": [(kart, [iş])]}"""
    m = cp_model.CpModel()
    info = {k: _add_sbc(m, k, jobs[k], cards, candidates(jobs[k], cards), market, None) for k in sel}
    use, over = {}, []
    for k, inf in info.items():
        for i, (_, v) in zip(inf["cand"], inf["real"]):
            use.setdefault(i, []).append((k, v))
            if (k, i) in bans:
                m.Add(v == 0)
    for i, kv in use.items():
        if len(kv) > 1:
            if soft:
                o = m.NewIntVar(0, len(kv) - 1, "")
                m.Add(sum(v for _, v in kv) <= 1 + o)
                over.append(o)
            else:
                m.Add(sum(v for _, v in kv) <= 1)
    if market:
        m.Add(sum(inf["spend"] for inf in info.values()) <= budget)
    for inf in info.values():  # varsayım (AddAssumptions) değil sabit: ön işleme d'yi silip kısıtları güçlendirir
        m.Add(inf["d"] == 1)
    for k, inf in info.items():
        if (hints or {}).get(k):
            _hint(m, inf, hints[k])
    if soft:
        m.Minimize(sum(over))
    elif minimize:
        m.Minimize(sum(ccost[i] * v for inf in info.values() for i, (_, v) in zip(inf["cand"], inf["real"]))
                   + sum(inf["cost"] for inf in info.values()))
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = WORKERS
    solver.parameters.max_time_in_seconds = max(0.5, time_limit)
    st = solver.Solve(m)
    sols = {k: _extract(inf, solver.Value, jobs[k]) for k, inf in info.items()} if st in OK else None
    if st in OK and (not soft or solver.ObjectiveValue() == 0):
        return "evet", sols, st == cp_model.OPTIMAL
    if st == cp_model.INFEASIBLE or soft and st == cp_model.OPTIMAL:
        return "hayır", list(sel), True
    if not sols:
        return "bilinmiyor", None, False
    clash = [(i, [k for k, v in kv if solver.Value(v)]) for i, kv in use.items()]
    return "bilinmiyor", {"sols": sols, "clash": [(i, ks) for i, ks in clash if len(ks) > 1]}, False


def _repair(jobs, S, cards, market, ccost, budget, hints, end, bans=(), depth=0):
    """Yumuşak modelle çakışmaları sök; aşım sıfıra inmezse çakışan kartı SBC'lerden birine yasaklayıp dallan
    (en çok 3 kat). "hayır" sadece yasaksız ilk çağrıda kanıttır. Dönen: (cevap, çözüm ya da None)"""
    ans, res, _ = _feasible(jobs, S, cards, market, ccost, budget, min(4.0, end - time.time()), hints,
                            soft=True, bans=bans)
    if ans == "evet" or ans == "hayır" and not bans:
        return ans, res
    if ans == "hayır" or res is None or depth >= 3 or time.time() >= end:
        return "bilinmiyor", None
    hints = {**hints, **res["sols"]}
    i, users = res["clash"][0]
    for k in users:
        a2, r2 = _repair(jobs, S, cards, market, ccost, budget, hints, end, bans + ((k, i),), depth + 1)
        if a2 == "evet":
            return a2, r2
    return "bilinmiyor", None


def _hitting_set(groups, cores):
    """Her çekirdekten en az bir SBC'yi bırakan en küçük küme. Aynı SBC'nin tekrarları birbirinin aynısı: hep
    son kopyalar bırakılır. groups: {anahtar: [iş no, kopya sırasıyla]}"""
    keys = list(groups)
    for size in range(sum(map(len, groups.values())) + 1):
        for combo in itertools.combinations_with_replacement(keys, size):
            drop = {k: combo.count(k) for k in keys}
            if any(drop[k] > len(groups[k]) for k in keys):
                continue
            H = {j for k in keys for j in groups[k][len(groups[k]) - drop[k]:]}
            if all(H & set(c) for c in cores):
                return H
    return {j for js in groups.values() for j in js}


def plan(jobs, club, fodder, cost, budget=0, buy=True, time_limit=20):
    """Bütün SBC'ler, kesin yöntem (MaxSAT'teki "implicit hitting set"):
    1. tek başına bile yapılamayanlar ayıklanır;
    2. pazarlık (PathFinder benzeri) hızlı bir çözüm arar; hepsi çakışmasızsa o en iyidir;
    3. değilse "şunların hepsi birden olur mu?" diye sorulur; olmuyorsa çözücü birlikte olmayan grubu (çekirdek)
       verir, küçültülür; bütün çekirdeklerden birer SBC bırakan en küçük küme çıkarılıp tekrar sorulur. İlk "olur"
       cevabı kanıtlı en fazla SBC'dir;
    4. seçilen SBC'ler için en düşük kart maliyeti aranır.
    Dönen: {"done": [(sbc, [(slot_pos, card)])], "skipped": [sbc], "spent": int, "status": str, "proven": bool}"""
    t0 = time.time()
    left = lambda: time_limit - (time.time() - t0)
    cards = [c for c in club if not c.get("locked")]
    market = sorted(fodder.items()) if buy and budget > 0 else []
    prices = dict(market)
    ccost = [int(cost(c)) for c in cards]
    key = lambda sbc: (sbc.get("_file"), sbc["name"])
    alone, hard = {}, {}  # tek başına yapılabilir mi ("hayır" kanıtlıysa hiç denenmez); çözme süresi = zorluk
    for k, sbc in enumerate(jobs):
        if key(sbc) not in alone:
            t1 = time.time()
            alone[key(sbc)] = _feasible(jobs, [k], cards, market, ccost, budget, max(1.0, time_limit * 0.05))[0]
            hard[key(sbc)] = time.time() - t1
    # en zor SBC'ler önce: boş kart çokken yerleşsinler
    live = sorted((k for k, sbc in enumerate(jobs) if alone[key(sbc)] != "hayır"), key=lambda k: -hard[key(jobs[k])])
    dbg = (lambda *a: print(f"[{time.time() - t0:5.1f}]", *a, flush=True)) if os.environ.get("FUT_DEBUG") else \
        (lambda *a: None)
    dbg("tek başına:", alone)
    groups = {}
    for k in live:
        groups.setdefault(key(jobs[k]), []).append(k)
    sub = [jobs[k] for k in live]
    neg, all_ok, raw = _negotiate(sub, cards, ccost, time_limit * 0.3) if sub else ([], True, [])
    best = {live[j]: sol for j, sol in enumerate(neg) if sol}  # bilinen en iyi (alt sınır)
    hints = {live[j]: sol for j, sol in enumerate(raw) if sol}
    proven, cores = all_ok, []
    dbg("pazarlık:", len(best), "/", len(live), all_ok)
    ub = lambda: len(live) - len(_hitting_set(groups, cores))  # kanıtlı üst sınır

    reserve = max(3.0, time_limit * 0.15)  # en sonda maliyet aşamasına

    def ask(S, limit, grow=False):
        """Hepsi birden olur mu? Önce kesin model (kısa: imkânsızlık çoğu zaman hemen kanıtlanır), olmazsa
        yumuşak model + dallanma (çakışan ipuçlarından çözüm onarır)."""
        end = time.time() + limit
        ans, res, _ = _feasible(jobs, S, cards, market, ccost, budget, min(limit, 2.0 if grow else limit / 3), hints)
        if ans == "bilinmiyor" and time.time() < end:
            ans, res = _repair(jobs, S, cards, market, ccost, budget, hints, end)
        dbg("soru:", len(S), "SBC ->", ans)
        if ans == "evet":
            hints.update(res)
        elif ans == "hayır":
            cores.append(res)
        return ans, res
    # aşağıdan: bilinen en iyiye bir SBC daha (ipucu neredeyse tam: hızlı); tekrarlarda sıradaki kopya
    grow = True
    while grow and not proven and left() > reserve + time_limit * 0.15:
        grow = False
        for js in groups.values():
            k = next((j for j in js if j not in best), None)
            if k is None or left() <= reserve + time_limit * 0.15:
                continue
            ans, res = ask(sorted(set(best) | {k}), min(15.0, left() - reserve - time_limit * 0.15), grow=True)
            if ans == "evet":
                best, grow = res, True
            proven = len(best) >= ub()
            if proven:
                break
    # yukarıdan: bütün çekirdeklerden birer SBC bırakan en küçük kümeyi çıkar, kalanları sor
    while not proven and left() > reserve:
        H = _hitting_set(groups, cores)
        if len(live) - len(H) <= len(best):
            proven = True
            break
        ans, res = ask([k for k in live if k not in H], left() - reserve)
        if ans == "evet":
            best, proven = res, True
        elif ans == "hayır":  # çekirdeği küçült (kısa sürede cevap gelmezse bırak)
            core = res
            for k in list(core):
                if len(core) > 1 and left() > reserve + 3:
                    a2, r2, _ = _feasible(jobs, [x for x in core if x != k], cards, market, ccost, budget, 3.0, hints)
                    if a2 == "hayır":
                        core = r2
                    elif a2 == "evet":
                        hints.update(r2)
                    else:
                        break
            cores[-1] = core
            dbg("çekirdek:", [jobs[k]["name"] for k in core])
        else:
            break
    dbg("sonuç:", len(best), "üst sınır:", ub(), "kanıtlı" if proven else "")
    sel = sorted(best)
    cost_ok = False
    if sel and left() > 1:  # seçilen SBC'ler sabit: en düşük maliyet
        ans, res, cost_ok = _feasible(jobs, sel, cards, market, ccost, budget, min(left(), reserve), best,
                                      minimize=True)
        if ans == "evet":
            best = res
    sols = [best.get(k) for k in range(len(jobs))]
    status = ("kanıtlanmış en iyi" if proven and cost_ok else
              "SBC sayısı kanıtlanmış en iyi (kart maliyeti süre sınırında)" if proven else
              "süre sınırında bulunan en iyi")
    return {"done": [(sbc, _chosen(k, sbc, sol, cards, prices)) for k, (sbc, sol) in enumerate(zip(jobs, sols)) if sol],
            "skipped": [sbc for sbc, sol in zip(jobs, sols) if not sol],
            "spent": sum(prices[r] for sol in sols if sol for r in sol["market"]),
            "status": status, "proven": proven}


def _maximal(profiles):
    """Belirtilen alan hiçbir şartı kötüleştirmez (en kötü durum hesabında "herhangi" hep daha kötü), bu yüzden
    en az eksik için başka bir profilin genellemesi olan profiller gereksiz."""
    ps = [p for p in {tuple(sorted(p.items())): p for p in profiles}.values()]
    spec = lambda p: {f: v for f, v in p.items() if v is not None}
    return [p for p in ps if not any(q is not p and spec(p).items() < spec(q).items() for q in ps)]


def _generalize(sbc, slots):
    """Eksik oyuncunun gereksiz belirtilmiş alanlarını "herhangi" yapar; check() en kötü durumla doğrular."""
    ok = lambda: all(v for _, v in check(sbc, slots))
    for _, c in slots:
        if c["source"] != "eksik":
            continue
        for f in ("club", "rarity", "nation", "league"):
            if c.get(f) is None or f == "league" and c.get("club") is not None:
                continue  # kulüp belli ise lig de belli
            old, c[f] = c[f], None
            if not ok():
                c[f] = old


def partial(sbc, cards, ccost, ratings, profiles, time_limit=30):
    """Kartlar yetmeyen SBC'yi en az eksikle doldurur; kalan yerler "eksik oyuncu" (source="eksik"): belirtilen
    alanlar gerekli, None alanlar herhangi. ratings: [(r, pazar fiyatı)], profiles: [{alan: değer ya da None}].
    Dönen: (slots ya da None, eksik sayısı kanıtlandı mı)"""
    full = _maximal(profiles)
    sol, proven = _solve_wild(sbc, cards, ccost, time_limit, {"profiles": full, "ratings": ratings})
    if not sol:
        return None, proven[0]
    slots = _chosen(0, sbc, sol, cards, {}, full)
    _generalize(sbc, slots)
    return slots, proven[0]


def describe(slots):
    """Çözümü arayüz/CLI için zenginleştirir: koordinat, pozisyon uyumu, kimya."""
    pos = [p for p, _ in slots]
    xy = layout(pos) if len(pos) == 11 else [(None, None)] * len(pos)
    chem = squad_chem(slots)
    rows = []
    for (p, c), (x, y), ch in zip(slots, xy, chem):
        fit = c["source"] if c["source"] in BUY else "tam" if c.get("position") == p else \
            "alt" if p in positions_of(c) else "farklı"
        rows.append({"pos": p, "x": x, "y": y, "card": c, "fit": fit, "chem": ch})
    return rows, sum(chem)


FIELD_TR = {"league": "Lig", "nation": "Ülke", "club": "Kulüp", "rarity": "Nadirlik", "rating": "Reyting",
            "position": "Pozisyon"}


def check(sbc, slots):
    """Çözümü çözücüden bağımsız doğrular: [(şart metni, sağlandı mı)]. Alınacak oyuncunun bilinmeyen alanı için
    en kötü durum: hangi değer gelirse gelsin sağlanıyorsa ✓."""
    cards = [c for _, c in slots]
    out = []
    if sbc.get("min_rating") or sbc.get("max_rating"):
        r = squad_rating([c["rating"] for c in cards])
        if sbc.get("min_rating"):
            out.append((f"Takım reytingi en az {sbc['min_rating']} (şu an {r})", r >= sbc["min_rating"]))
        if sbc.get("max_rating"):
            out.append((f"Takım reytingi en fazla {sbc['max_rating']} (şu an {r})", r <= sbc["max_rating"]))
    chem = squad_chem(slots)
    if sbc.get("min_chem"):
        out.append((f"Toplam kimya en az {sbc['min_chem']} (şu an {sum(chem)})", sum(chem) >= sbc["min_chem"]))
    if sbc.get("min_player_chem"):
        out.append((f"Oyuncu başı kimya en az {sbc['min_player_chem']}", min(chem) >= sbc["min_player_chem"]))
    for req in sbc.get("requirements", []):
        t, f = req.get("type", "count"), FIELD_TR.get(req.get("field"), req.get("field"))
        if t == "count":
            n = sum(matches(c, req) for c in cards)
            n2 = sum(matches(c, req, True) for c in cards)  # bilinmeyenler dahil en fazla
            one = lambda q: f"{FIELD_TR.get(q.get('field'), q.get('field'))} " + (
                ", ".join(q["in"]) if "in" in q else f"≥ {q['gte']}" if "gte" in q else f"≤ {q.get('lte')}")
            f, what = ("", " ve ".join(one(q) for q in req["all"])) if "all" in req else (f, one(req).split(" ", 1)[1])
            ok = n >= req.get("min", 0) and n2 <= req.get("max", 99)
            out.append((f"{f} {what}: {n} oyuncu".strip() + (f" (+{n2 - n} belirsiz)" if n2 > n else "")
                        + (f" (en az {req['min']})" if "min" in req else "")
                        + (f" (en fazla {req['max']})" if "max" in req else ""), ok))
            continue
        vals = [_val(c, req["field"]) for c in cards]
        unk = sum(v is None for v in vals)
        vals = [v for v in vals if known(v)]
        more = f" (+{unk} belirsiz)" if unk else ""
        if t == "same":
            top = max((vals.count(v) for v in set(vals)), default=0)
            ok = top + unk <= req.get("max", 99) and top >= req.get("min", 0)
            out.append((f"Aynı {f.lower()} en çok {top} oyuncu{more}"
                        + (f" (sınır {req['max']})" if "max" in req else f" (en az {req.get('min')})"), ok))
        elif t == "distinct":
            k = len(set(vals))
            lo, hi = req.get("exact", req.get("min", 0)), req.get("exact", req.get("max", 99))
            ok = k >= lo and k + unk <= hi
            lim = f"tam {req['exact']}" if "exact" in req else ", ".join(
                x for x in (f"en az {req['min']}" if "min" in req else "", f"en fazla {req['max']}" if "max" in req else "") if x)
            out.append((f"Farklı {f.lower()} sayısı {k}{more} ({lim})", ok))
    return out
