"""Planlayıcı ölçümü: testveri.py örnekleriyle hız, kanıt ve doğruluk.

.venv/bin/python bench.py 0-9                  # tohum 0..9, ana plan 60 sn, yarım SBC 60 sn
.venv/bin/python bench.py 0-9 --time 30 --budget 20000
Her örnekte: tamamlanan SBC sayısı, kanıtlı mı, süreler; her kadro check()'ten geçmeli; yarım SBC'deki
"gerekenler" en kötü durum denemesiyle (rastgele + kasıtlı kötü değerlerle 200 alım) doğrulanır.
"""
import argparse, json, random, sys, time

import fut, solver, testveri


def adversarial(sbc, slots, missing, rng, trials=200):
    """Gerekenleri sağlayan her alım SBC'yi tamamlamalı: belirtilmemiş alanlara kadroda olan ya da yeni değerler,
    reytinge aralıktan değer verilir. Dönen: None (hep tamam) ya da ilk bozulan şartlar."""
    cards = [c for _, c in slots]
    pool = {f: sorted({c[f] for c in cards if solver.known(c.get(f))} |
                      {v for r in sbc.get("requirements", []) for q in r.get("all", [r])
                       if q.get("field") == f for v in q.get("in", [])}) for f in fut.WILD_FIELDS}
    wild = [i for i, (_, c) in enumerate(slots) if c["source"] in solver.BUY]
    for t in range(trials):
        real = list(slots)
        for n, i in enumerate(wild):
            pos, c = slots[i]
            m = missing[n] if c["source"] == "eksik" else {"min": c["rating"], "max": c["rating"], "needs": {}}
            card = {"name": f"X{t}_{i}", "position": pos, "positions": pos, "source": "kulüp",
                    "rating": rng.choice([m["min"], m["max"], rng.randint(m["min"], m["max"])])}
            for f in fut.WILD_FIELDS:
                card[f] = m["needs"][f] if f in m["needs"] else rng.choice(pool[f] + [f"yeni{t}_{i}"] * 2)
            if c["source"] == "pazar":
                card["position"] = card["positions"] = "?"  # pazar kartına kimya sayılmıyor
            real[i] = (pos, card)
        bad = [txt for txt, ok in solver.check(sbc, real) if not ok]
        if bad:
            return bad
    return None


def run(seed, time_limit, partial_time, budget):
    club, sbcs, fodder = testveri.ornek(seed)
    t = time.time()
    p = fut.plan_max(sbcs, club, fodder, budget, time_limit, partial_time)
    total = time.time() - t
    rng = random.Random(seed)
    errors = []
    for sbc, r in p["done"]:
        bad = [txt for txt, ok in r["checks"] if not ok]
        chosen = [(sl["pos"], sl["card"]) for sl in r["slots"]]
        bad = bad or adversarial(sbc, chosen, [], rng) if any(c["source"] == "pazar" for _, c in chosen) else bad
        if bad:
            errors.append(f"{sbc['name']}: {bad}")
    for sbc, r in p["partial"]:
        chosen = [(sl["pos"], sl["card"]) for sl in r["slots"]]
        bad = [txt for txt, ok in r["checks"] if not ok] or adversarial(sbc, chosen, r["missing"], rng)
        if bad:
            errors.append(f"yarım {sbc['name']}: {bad}")
    return {"seed": seed, "cards": len(club), "jobs": p["total"], "done": len(p["done"]), "proven": p["proven"],
            "status": p["status"], "time": round(total, 1),
            "partial": [(s["name"], len(r["missing"]), r["proven"]) for s, r in p["partial"]], "errors": errors}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("seeds", help="ör. 0-9 ya da 3,5,8")
    ap.add_argument("--time", type=float, default=60)
    ap.add_argument("--partial-time", type=float, default=60)
    ap.add_argument("--budget", type=int, default=0)
    ap.add_argument("--json")
    a = ap.parse_args()
    seeds = [s for part in a.seeds.split(",") for s in
             (range(int(part.split("-")[0]), int(part.split("-")[1]) + 1) if "-" in part else [int(part)])]
    rows = []
    for seed in seeds:
        r = run(seed, a.time, a.partial_time, a.budget)
        rows.append(r)
        pk = sum(p[2] for p in r["partial"])
        print(f"tohum {seed:3d} | {r['cards']:3d} kart {r['jobs']:2d} iş | tam {r['done']:2d} "
              f"{'KANITLI ' if r['proven'] else 'kanıtsız'} | yarım {len(r['partial'])} ({pk} kanıtlı) | "
              f"{r['time']:6.1f} sn | {'HATA ' + str(r['errors']) if r['errors'] else 'doğru'}", flush=True)
    n = len(rows)
    print(f"\nÖZET: ana plan kanıtlı {sum(r['proven'] for r in rows)}/{n} | yarım kanıtlı "
          f"{sum(p[2] for r in rows for p in r['partial'])}/{sum(len(r['partial']) for r in rows)} | "
          f"hatalı örnek {sum(bool(r['errors']) for r in rows)} | ort. {sum(r['time'] for r in rows) / n:.1f} sn "
          f"| en uzun {max(r['time'] for r in rows):.1f} sn")
    if a.json:
        json.dump(rows, open(a.json, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    sys.exit(main())
