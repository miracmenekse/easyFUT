#!/usr/bin/env python3
"""FUT asistanı: veriyi data/ klasöründen okur, EA'ya hiç bağlanmaz.
Çıktılar sadece öneridir; oyundaki tıklamaları kullanıcı yapar."""
import argparse, csv, json, math, sys
from pathlib import Path

import solver
from solver import matches, squad_rating, FORMATIONS, DEFAULT_FORMATION  # noqa: F401 (ui.py kullanır)

DATA = Path(__file__).parent / "data"
TAX = 0.05
YES = ("evet", "yes", "1", "true")


# ---------- veri okuma (tek giriş noktası; veri kaynağı değişirse sadece burası değişir) ----------

def load_club(path=None):
    rows = list(csv.DictReader(open(path or DATA / "club.csv", encoding="utf-8")))
    for i, r in enumerate(rows):
        r["id"] = i
        r["rating"] = int(r["rating"])
        r["price"] = int(r.get("price") or 0)
        r["value"] = int(r.get("value") or 0)  # FUT.GG kart değeri (gradingScore), futgg.py deger
        for k in ("tradeable", "duplicate", "locked"):
            r[k] = str(r.get(k) or "").strip().lower() in YES
        r["source"] = "kulüp"
    return rows


def load_fodder_prices(path=None):
    p = Path(path or DATA / "fodder_prices.csv")
    if not p.exists():
        return {}
    return {int(r["rating"]): int(r["price"]) for r in csv.DictReader(open(p, encoding="utf-8"))}


def load_json_dir(name):
    return [json.load(open(p, encoding="utf-8")) | {"_file": p.name}
            for p in sorted((DATA / name).glob("*.json"))]


# ---------- ortak kurallar ----------

def card_cost(card, fodder):
    """Kartı kullanmanın bedeli: kulüp kartı için fırsat maliyeti (kopyalar yarı fiyat).
    Fiyat tablosunda olmayan yüksek reyting tablodaki en yüksek fiyattan sayılır,
    yoksa 90'lık kart bedava görünür ve SBC'de harcanır."""
    r = card["rating"]
    tablo = fodder.get(r, max(fodder.values()) if fodder and r > max(fodder) else 0)
    base = max(card["price"], tablo)
    return base * 0.5 if card.get("duplicate") else base


def price_step(p):
    return 50 if p < 1000 else 100 if p < 10000 else 250 if p < 50000 else 500 if p < 100000 else 1000


# ---------- SBC ----------

def expand_repeats(sbcs):
    """"repeat": 3 olan SBC üç ayrı iş sayılır."""
    return [s | {"_copy": k + 1} for s in sbcs for k in range(s.get("repeat", 1))]


WILD_FIELDS = ("club", "league", "nation", "rarity")
FIELD_TR = {"club": "Kulüp", "league": "Lig", "nation": "Ülke", "rarity": "Nadirlik"}


def wild_profiles(sbc, club):
    """Eksik oyuncunun alabileceği özellikler (None = herhangi): kulüpteki gerçek kartların kulüp/lig/ülke
    birleşimleri (gerçekte var olanlar) ve SBC şartlarında geçen değerler. SBC'nin hiç bakmadığı alan hep
    herhangi (model küçük kalsın). Gereksiz belirtilen alanları çözücü sonradan "herhangi" yapar."""
    reqs = [q for r in sbc.get("requirements", []) for q in r.get("all", [r])]
    chem = solver._needs_chem(sbc)
    used = {f for f in WILD_FIELDS if any(q.get("field") == f for q in reqs) or chem and f != "rarity"}
    kv = lambda f, v: v if f in used and v and not str(v).startswith(("Bilinmiyor", "?")) else None
    prof = {tuple(kv(f, c.get(f)) for f in WILD_FIELDS) for c in club + sbc.get("fixed", [])
            if c.get("rarity") not in solver.SPECIAL_CHEM}  # Icon/Hero alınacak oyuncu olarak önerilmez
    for q in reqs:
        if q.get("field") in used:
            prof |= {tuple(v if f == q["field"] else None for f in WILD_FIELDS) for v in q.get("in", [])}
    prof.add((None,) * len(WILD_FIELDS))
    return [dict(zip(WILD_FIELDS, p)) for p in sorted(prof, key=lambda p: [str(x) for x in p])]


def needs(sbc, slots):
    """Eksik oyuncuların alınma özellikleri: belirtilen alanlar (None olmayanlar) şart, diğerleri herhangi.
    Reyting aralığı: SBC'nin reyting şartlarında üyeliği değişmeyen ve takım reytingi üst sınırını birlikte
    yükselseler de aşmayan en geniş [r, üst]. Dönen: [{"pos", "rating", "min", "max", "needs", "chem"}]"""
    wild = [c for _, c in slots if c["source"] == "eksik"]
    rq = [r for r in sbc.get("requirements", []) if r.get("type", "count") == "count" and solver._parts(r)[0]]
    same = lambda c, r2: all(matches(c | {"rating": r2}, q, u) == matches(c, q, u) for q in rq for u in (False, True))
    hi = {}
    for c in wild:
        h = c["rating"]
        while h < 99 and same(c, h + 1):
            h += 1
        hi[c["id"]] = h
    if sbc.get("max_rating") and wild:  # takım reytingi her oyuncunun reytingiyle artar: hepsi birden yükselsin
        r0 = {c["id"]: c["rating"] for c in wild}
        best = 0
        for delta in range(1, 55):
            for c in wild:
                c["rating"] = min(r0[c["id"]] + delta, hi[c["id"]])
            if not all(ok for _, ok in solver.check(sbc, slots)):
                break
            best = delta
        for c in wild:
            c["rating"] = r0[c["id"]]
            hi[c["id"]] = min(hi[c["id"]], r0[c["id"]] + best)
    return [{"pos": pos, "rating": c["rating"], "min": c["rating"], "max": hi[c["id"]], "chem": solver._needs_chem(sbc),
             "needs": {f: c[f] for f in WILD_FIELDS if solver.known(c.get(f))}}
            for pos, c in slots if c["source"] == "eksik"]


def plan_max(sbcs, club, fodder, budget=0, time_limit=20, partial_time=60):
    """Bütün SBC'leri birlikte çözer: en fazla SBC, sonra en az coin + kart değeri.
    budget=0: sadece kulüpteki kartlar, hiçbir şey satın alınmaz. Sonra yapılamayan her SBC, kalan kartlarla
    en az eksik oyuncuyla doldurulur (partial; partial_time=0 ise yapılmaz)."""
    jobs = expand_repeats([s for s in sbcs if not s.get("passive") and not s.get("completed")])  # pasif/bitmiş girmez
    r = solver.plan(jobs, club, fodder, lambda c: card_cost(c, fodder), budget, True, time_limit)
    done = []
    for sbc, chosen in r["done"]:
        rows, chem = solver.describe(chosen)
        squad = [c for _, c in chosen]
        spend = sum(c["price"] for c in squad if c["source"] == "pazar")
        used = sum(card_cost(c, fodder) for c in squad if c["source"] == "kulüp")
        done.append((sbc, {"slots": rows, "squad": squad, "chem": chem, "spend": spend, "used": used,
                           "checks": solver.check(sbc, chosen),
                           "rating": squad_rating([c["rating"] for c in squad]),
                           "net": sbc.get("reward_value", 0) - spend - used}))
    # yapılamayanlar: kalan kartlarla elden geldiğince doldur, eksik yerler pazardan alınacak
    used = {c["id"] for _, chosen in r["done"] for _, c in chosen if c["source"] == "kulüp"}
    left = [c for c in club if not c.get("locked") and c["id"] not in used]
    tablo = lambda r: fodder.get(r, max(fodder.values()) if fodder and r > max(fodder) else 0)
    ratings = [(r, tablo(r)) for r in range(45, 100)]
    partial, seen = [], set()
    for sbc in r["skipped"] if partial_time > 0 else []:
        if (sbc.get("_file"), sbc["name"]) in seen:  # tekrarlı SBC'nin bir kopyası yeter
            continue
        seen.add((sbc.get("_file"), sbc["name"]))
        chosen, proven = solver.partial(sbc, left, [int(card_cost(c, fodder)) for c in left], ratings,
                                        wild_profiles(sbc, club), partial_time)
        if not chosen:  # eksik oyuncuyla bile olmuyor (ör. "en fazla" şartları)
            continue
        rows, chem = solver.describe(chosen)
        partial.append((sbc, {"slots": rows, "chem": chem, "checks": solver.check(sbc, chosen),
                              "missing": needs(sbc, chosen), "proven": proven,
                              "rating": squad_rating([c["rating"] for _, c in chosen])}))
    partial.sort(key=lambda t: len(t[1]["missing"]))
    return {"done": done, "skipped": r["skipped"], "spent": r["spent"], "total": len(jobs), "status": r["status"],
            "proven": r["proven"], "partial": partial}


def need_text(m):
    """{"pos": "ST", "min": 78, "max": 99, "needs": {"league": "Premier League"}} -> 'ST · reyting 78+ · Lig: ...'"""
    n = dict(m["needs"])
    what = []
    if "club" in n:  # kulüp ligi de belirler
        what.append(f"Kulüp: {n.pop('club')}" + (f" ({n.pop('league')})" if "league" in n else ""))
    what += [f"{FIELD_TR[f]}: {v}" for f, v in n.items()]
    r = f"{m['min']}+" if m["max"] == 99 else str(m["min"]) if m["min"] == m["max"] else f"{m['min']}-{m['max']}"
    return f"{m['pos'] if m.get('chem', True) else 'Herhangi pozisyon'} · reyting {r} · " + \
        (" + ".join(what) or "herhangi bir oyuncu")


def complete_sbc(file, cards, today=None):
    """SBC oyunda yapıldı: kullanılan kulüp kartları club.csv'den çıkar (kopyası varsa satır kalır, kopya işareti
    kalkar); SBC tekrarlıysa tekrar sayısı bir azalır, değilse "completed" (tarih) olur ve plana girmez.
    cards: [{"name", "rating", "club"}]. Önce club.csv.bak yedeği alınır.
    Dönen: {"silinen": [...], "kopyasi_kalan": [...], "bulunamayan": [...], "kalan_tekrar": int}"""
    import datetime
    path = DATA / "sbcs" / Path(file).name
    if path.suffix != ".json" or not path.exists():
        raise ValueError(f"SBC dosyası yok: {file}")
    club = DATA / "club.csv"
    with open(club, encoding="utf-8") as f:
        r = csv.DictReader(f)
        fields, rows = r.fieldnames, list(r)
    out = {"silinen": [], "kopyasi_kalan": [], "bulunamayan": []}
    for c in cards:
        i = next((i for i, row in enumerate(rows) if row["name"] == c["name"] and str(row["rating"]) == str(c["rating"])
                  and row.get("club", "") == (c.get("club") or row.get("club", ""))), None)
        if i is None:
            out["bulunamayan"].append(c["name"])
        elif rows[i].get("duplicate", "").strip().lower() in YES:
            rows[i]["duplicate"] = "hayır"
            out["kopyasi_kalan"].append(c["name"])
        else:
            out["silinen"].append(rows.pop(i)["name"])
    club.with_suffix(".csv.bak").write_text(club.read_text(encoding="utf-8"), encoding="utf-8")
    with open(club, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fields)
        w.writeheader()
        w.writerows(rows)
    sbc = json.load(open(path, encoding="utf-8"))
    if sbc.get("repeat", 1) > 1:
        sbc["repeat"] -= 1
    else:
        sbc["completed"] = str(today or datetime.date.today())
    path.write_text(json.dumps(sbc, ensure_ascii=False, indent=2), encoding="utf-8")
    out["kalan_tekrar"] = 0 if sbc.get("completed") else sbc.get("repeat", 1)
    return out


def need_lines(missing):
    """Aynı özellikli eksikleri birleştir: [(adet, metin)]"""
    out = {}
    for m in missing:
        t = need_text(m)
        out[t] = out.get(t, 0) + 1
    return [(n, t) for t, n in out.items()]


def solve_sbc(sbc, club, fodder, buy=True):
    """Tek SBC'nin en ucuz çözümü (kadro listesi) ya da None."""
    p = plan_max([sbc], club, fodder, budget=10**9 if buy else 0, time_limit=10, partial_time=0)
    return p["done"][0][1]["squad"] if p["done"] else None


def print_squad(s):
    for r in s["slots"]:
        c = r["card"]
        who = f"Pazardan al: {c['rating']} (~{c['price']} coin)" if c["source"] == "pazar" else \
            f"{c['rating']} {c['name']}  ({c.get('league', '')} / {c.get('nation', '')})" + (" kopya" if c.get("duplicate") else "")
        print(f"   {r['pos']:>4}  {who}  [kimya {r['chem']}, {r['fit']}]")
    print(f"   Takım {s['rating']} | Kimya {s['chem']}/33 | Coin {s['spend']} | Kart değeri {s['used']:.0f}")


# ---------- komutlar ----------

def cmd_sbc(a):
    club, fodder = load_club(), load_fodder_prices()
    sbcs = [json.load(open(a.file, encoding="utf-8"))] if a.file else load_json_dir("sbcs")
    for sbc in sbcs:  # her SBC tek başına, en ucuz haliyle
        print(f"\n=== {sbc['name']} (takım ≥ {sbc.get('min_rating', '-')}) ===")
        p = plan_max([sbc | {"repeat": 1}], club, fodder, budget=10**9, time_limit=10, partial_time=0)
        if not p["done"]:
            print("   Çözüm yok (kulüp + fodder_prices.csv yetmiyor).")
        else:
            print_squad(p["done"][0][1])


def cmd_kulup(a):
    club, fodder = load_club(), load_fodder_prices()
    print(f"Toplam kart: {len(club)} | Takaslanabilir: {sum(c['tradeable'] for c in club)} | "
          f"Kopya: {sum(c['duplicate'] for c in club)}")
    by = {}
    for c in club:
        by[c["rating"]] = by.get(c["rating"], 0) + 1
    print("Reyting dağılımı: " + ", ".join(f"{r}:{n}" for r, n in sorted(by.items(), reverse=True)))
    dups = [c for c in club if c["duplicate"]]
    if dups:
        print("\nÖnce SBC'de kullanılacak kopyalar:")
        for c in sorted(dups, key=lambda c: -c["rating"]):
            print(f"  {c['rating']} {c['name']}")
    sell = [c for c in club if c["tradeable"] and c["price"] >= a.min_sat]
    if sell:
        print(f"\nSatılabilir takaslanabilir kartlar (>= {a.min_sat}):")
        for c in sorted(sell, key=lambda c: -c["price"]):
            print(f"  {c['rating']} {c['name']}  piyasa ~{c['price']}  -> vergi sonrası {int(c['price'] * (1 - TAX))}")


def cmd_evo(a):
    club = load_club()
    evos = [json.load(open(a.file, encoding="utf-8"))] if a.file else load_json_dir("evos")
    for e in evos:
        ok = [c for c in club if all(matches(c, r) for r in e.get("requirements", []))]
        print(f"\n=== {e['name']}: {len(ok)} uygun oyuncu ===")
        for c in sorted(ok, key=lambda c: -c["rating"]):
            print(f"  {c['rating']} {c['name']} ({c.get('position', '')})")


def cmd_kar(a):
    net = int(a.satis * (1 - TAX))
    print(f"Vergi sonrası eline geçen: {net} | Kâr: {net - a.alis}")


def cmd_fiyat(a):
    p = math.ceil((a.alis + a.kar) / (1 - TAX))
    step = price_step(p)
    p = math.ceil(p / step) * step
    print(f"En az {p} coin'e listele (vergi sonrası kâr: {int(p * (1 - TAX)) - a.alis})")


def cmd_plan(a):
    club, fodder = load_club(), load_fodder_prices()
    print("BUGÜNÜN LİSTESİ (tıklamaları oyunda sen yap)\n")
    p = plan_max(load_json_dir("sbcs"), club, fodder, a.butce)
    print(f"SBC: {len(p['done'])}/{p['total']} yapılabilir ({p['status']}), harcama {p['spent']} coin (bütçe {a.butce})\n")
    n = 1
    for sbc, s in p["done"]:
        print(f"{n}. {sbc['name']}" + (f" #{sbc['_copy']}" if sbc.get("repeat", 1) > 1 else ""))
        print_squad(s)
        n += 1
    for sbc in p["skipped"]:
        print(f"-  {sbc['name']}: kartlar/bütçe yetmiyor")
    options = [(sbc, s) for sbc, s in p["partial"] if len(s["missing"]) <= a.eksik]
    if options:
        print(f"\nYARIM KALANLAR (en fazla {a.eksik} eksik). Kalan kartları paylaşırlar, BİRİNİ seç:")
        for j, (sbc, s) in enumerate(options):
            print(f"{'   veya ' if j else '   '}{sbc['name']}: {len(s['missing'])} oyuncu eksik"
                  f"{' (daha azı olmaz, kanıtlı)' if s['proven'] else ' (süre sınırında)'}, pazardan al:")
            for n, text in need_lines(s["missing"]):
                print(f"      - {n} × {text}" if n > 1 else f"      - {text}")
    for e in load_json_dir("evos"):
        ok = [c for c in club if all(matches(c, r) for r in e.get("requirements", []))]
        if ok:
            best = max(ok, key=lambda c: c["rating"])
            print(f"{n}. Evolution: {e['name']} -> {best['name']} ({best['rating']})")
            n += 1


def main(argv=None):
    p = argparse.ArgumentParser(description="FUT asistanı (EA'ya bağlanmaz)")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sbc", help="SBC çöz"); s.add_argument("file", nargs="?"); s.set_defaults(f=cmd_sbc)
    s = sub.add_parser("kulup", help="kulüp analizi"); s.add_argument("--min-sat", type=int, default=5000)
    s.set_defaults(f=cmd_kulup)
    s = sub.add_parser("evo", help="Evolution uygunluğu"); s.add_argument("file", nargs="?"); s.set_defaults(f=cmd_evo)
    s = sub.add_parser("kar", help="alış/satış kârı"); s.add_argument("alis", type=int); s.add_argument("satis", type=int)
    s.set_defaults(f=cmd_kar)
    s = sub.add_parser("fiyat", help="hedef kâr için satış fiyatı"); s.add_argument("alis", type=int)
    s.add_argument("kar", type=int); s.set_defaults(f=cmd_fiyat)
    s = sub.add_parser("plan", help="günlük yapılacaklar (en fazla SBC)")
    s.add_argument("--butce", type=int, default=0, help="SBC için harcanabilecek coin (0: sadece kulüp)")
    s.add_argument("--eksik", type=int, default=3, help="yarım SBC önerisi için en fazla eksik oyuncu")
    s.set_defaults(f=cmd_plan)
    a = p.parse_args(argv)
    a.f(a)


if __name__ == "__main__":
    sys.exit(main())
