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
    """Kartı kullanmanın bedeli: kulüp kartı için fırsat maliyeti (kopyalar yarı fiyat)."""
    base = max(card["price"], fodder.get(card["rating"], 0))
    return base * 0.5 if card.get("duplicate") else base


def price_step(p):
    return 50 if p < 1000 else 100 if p < 10000 else 250 if p < 50000 else 500 if p < 100000 else 1000


# ---------- SBC ----------

def expand_repeats(sbcs):
    """"repeat": 3 olan SBC üç ayrı iş sayılır."""
    return [s | {"_copy": k + 1} for s in sbcs for k in range(s.get("repeat", 1))]


def plan_max(sbcs, club, fodder, budget=0, time_limit=20):
    """Bütün SBC'leri birlikte çözer: en fazla SBC, sonra en az coin + kart değeri.
    budget=0: sadece kulüpteki kartlar, hiçbir şey satın alınmaz."""
    jobs = expand_repeats(sbcs)
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
    return {"done": done, "skipped": r["skipped"], "spent": r["spent"], "total": len(jobs), "status": r["status"]}


def solve_sbc(sbc, club, fodder, buy=True):
    """Tek SBC'nin en ucuz çözümü (kadro listesi) ya da None."""
    p = plan_max([sbc], club, fodder, budget=10**9 if buy else 0, time_limit=10)
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
        p = plan_max([sbc | {"repeat": 1}], club, fodder, budget=10**9, time_limit=10)
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
    s.set_defaults(f=cmd_plan)
    a = p.parse_args(argv)
    a.f(a)


if __name__ == "__main__":
    sys.exit(main())
