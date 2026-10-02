"""SBC şartlarını FUT.GG'den (EA'nın kendi şart metinleri) çekip data/sbcs/*.json üretir.

Hangi SBC'lerin açık olduğu ve dizilişler data/sbc_liste.json'dan gelir (FC Companion / Web App'ten):
  [{"set": "League & Nation Advanced", "challenge": "4 Leagues & 5 Nations", "formation": "4-1-4-1",
    "file": "4_lig_5_ulke.json"}, ...]
.venv/bin/python sbc_cek.py            # çek, çevir, yaz (tanınmayan şart metni varsa hiçbir şey yazmadan durur)
.venv/bin/python sbc_cek.py kontrol    # sadece çevir ve göster, dosya yazma
Dosyada zaten olan passive / completed / reward_value / notes / fixed alanları korunur.
"""
import json, re, sys, time, urllib.request
from pathlib import Path

import solver

API = "https://www.fut.gg/api/fut/sbc/27/"
DATA = Path(__file__).parent / "data"
QUALITY = {"bronze": {"lte": 64}, "silver": {"gte": 65, "lte": 74}, "gold": {"gte": 75}}
QMIN = {"bronze": None, "silver": {"gte": 65}, "gold": {"gte": 75}}  # "Min. X": X ve üstü
SAME = {"league": "league", "nation": "nation", "club": "club"}
DISTINCT = {"leagues": "league", "nationalities": "nation", "nations": "nation", "clubs": "club"}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.load(urllib.request.urlopen(req, timeout=30))


def known_values():
    """"X OR Y" hangi alan? Kulüpteki kartların ülke/lig/kulüp adlarından bakılır."""
    import csv
    vals = {f: set() for f in ("nation", "league", "club")}
    for r in csv.DictReader(open(DATA / "club.csv", encoding="utf-8")):
        for f in vals:
            vals[f].add(r[f])
    return vals


def parse(texts, known):
    """EA şart metinleri -> SBC alanları. Tanınmayan metin: ValueError (tahmin yok)."""
    out, reqs, size = {}, [], 11
    lim = lambda w: {"min.": "min", "max.": "max", "exact": "exact", "min": "min", "max": "max", "exactly": "exact"}[w.lower()]
    for t in texts:
        s = t.strip()
        if m := re.fullmatch(r"(Min\.|Max\.) (\d+) Players from the same (League|Nation|Club)", s):
            reqs.append({"type": "same", "field": SAME[m[3].lower()], lim(m[1]): int(m[2])})
        elif m := re.fullmatch(r"(Min\.|Max\.|Exact) (Leagues|Nationalities|Clubs) in Squad: (\d+)", s):
            reqs.append({"type": "distinct", "field": DISTINCT[m[2].lower()], lim(m[1]): int(m[3])})
        elif m := re.fullmatch(r"(Leagues|Nationalities|Nations|Clubs): (Min\.?|Max\.?|Exactly) (\d+)", s):
            reqs.append({"type": "distinct", "field": DISTINCT[m[1].lower()], lim(m[2]): int(m[3])})
        elif m := re.fullmatch(r"(Min\.|Max\.) (\d+) Players from: (.+)", s):
            names = [x.strip() for x in m[3].split(" OR ")]
            fields = [f for f in ("nation", "league", "club") if all(n in known[f] for n in names)]
            if len(fields) != 1:
                raise ValueError(f"'{s}': {names} ülke mi, lig mi, kulüp mü anlaşılamadı")
            reqs.append({"field": fields[0], "in": names, lim(m[1]): int(m[2])})
        elif m := re.fullmatch(r"Player quality: Min\. (Bronze|Silver|Gold)", s, re.I):
            if QMIN[m[1].lower()]:
                reqs.append({"field": "rating", **QMIN[m[1].lower()], "min": "SIZE"})
        elif m := re.fullmatch(r"Exactly (Bronze|Silver|Gold) Players", s):
            reqs.append({"field": "rating", **QUALITY[m[1].lower()], "min": "SIZE"})
        elif m := re.fullmatch(r"(Min\.|Max\.) (\d+) Players: (Bronze|Silver|Gold)", s):
            reqs.append({"field": "rating", **QUALITY[m[3].lower()], lim(m[1]): int(m[2])})
        elif m := re.fullmatch(r"(Min\.|Max\.) (\d+) players? with minimum OVR of (\d+)", s, re.I):
            reqs.append({"field": "rating", "gte": int(m[3]), lim(m[1]): int(m[2])})
        elif m := re.fullmatch(r"(Min\.|Max\.) Team Rating: (\d+)", s):
            out["min_rating" if m[1] == "Min." else "max_rating"] = int(m[2])
        elif m := re.fullmatch(r"Min\. Squad Total Chemistry Points: (\d+)", s):
            out["min_chem"] = int(m[1])
        elif m := re.fullmatch(r"Min\. (\d+) Chemistry Points Per Player", s, re.I):
            out["min_player_chem"] = int(m[1])
        # FUT.GG'nin 2026-10 biçimi ("Same league: Max. 4 players", "Quality: Gold only" ...)
        elif m := re.fullmatch(r"Same (league|nation|club): (Min\.|Max\.) (\d+) players", s):
            reqs.append({"type": "same", "field": SAME[m[1]], lim(m[2]): int(m[3])})
        elif m := re.fullmatch(r"Quality: (Bronze|Silver|Gold) only", s):
            reqs.append({"field": "rating", **QUALITY[m[1].lower()], "min": "SIZE"})
        elif m := re.fullmatch(r"Quality: (Min\.|Max\.) (\d+) (Bronze|Silver|Gold) players", s):
            reqs.append({"field": "rating", **QUALITY[m[3].lower()], lim(m[1]): int(m[2])})
        elif m := re.fullmatch(r"Quality: Min\. (Bronze|Silver|Gold)", s):
            if QMIN[m[1].lower()]:
                reqs.append({"field": "rating", **QMIN[m[1].lower()], "min": "SIZE"})
        elif m := re.fullmatch(r"Team rating: (Min\.|Max\.) (\d+)", s):
            out["min_rating" if m[1] == "Min." else "max_rating"] = int(m[2])
        elif m := re.fullmatch(r"Chemistry: Min\. (\d+)", s):
            out["min_chem"] = int(m[1])
        elif m := re.fullmatch(r"(Nation|League|Club): (Min\.|Max\.) (\d+) players? from (.+)", s):
            reqs.append({"field": m[1].lower(), "in": m[4].split(" or "), lim(m[2]): int(m[3])})
        elif m := re.fullmatch(r"Players: (\d+)", s):
            size = int(m[1])
        elif m := re.fullmatch(r"Number of players: (\d+)", s, re.I):
            size = int(m[1])
        else:
            raise ValueError(f"tanınmayan şart metni: '{s}'")
    for r in reqs:
        for k in ("min", "max"):
            if r.get(k) == "SIZE":
                r[k] = size
    return out | {"size": size, "requirements": reqs}


def parse_filter(texts):
    """Streamlined SBC'de her karta uyan şart ("Rating: Min. 45"). Tanınmayan metin: ValueError."""
    out = []
    for t in texts:
        if m := re.fullmatch(r"Rating: Min\. (\d+)", t.strip()):
            out.append({"field": "rating", "gte": int(m[1])})
        elif m := re.fullmatch(r"Quality: (Bronze|Silver|Gold) only", t.strip()):
            out.append({"field": "rating", **QUALITY[m[1].lower()]})
        else:
            raise ValueError(f"tanınmayan streamlined şartı: '{t}'")
    return out


def main():
    liste = json.load(open(DATA / "sbc_liste.json", encoding="utf-8"))
    known = known_values()
    sets, page = [], 1
    while page:
        d = get(f"{API}?page={page}")
        sets += d["data"]
        page = d.get("next")
        time.sleep(0.3)
    detay, yaz = {}, []
    for e in liste:
        s = next((s for s in sets if s["name"] == e["set"]), None)
        if not s:
            sys.exit(f"FUT.GG'de set yok: {e['set']}")
        if s["slug"] not in detay:
            detay[s["slug"]] = get(f"{API}{s['slug']}/")["data"]
            time.sleep(0.3)
        c = next((c for c in detay[s["slug"]]["challenges"] if c["name"] == e["challenge"]), None)
        if not c:
            sys.exit(f"{e['set']} içinde görev yok: {e['challenge']}")
        if e["formation"] and e["formation"] not in solver.FORMATIONS:  # streamlined: diziliş yok
            sys.exit(f"{e['challenge']}: diziliş {e['formation']} solver.FORMATIONS'ta yok")
        try:
            if c.get("scoreRequirement"):  # streamlined: kart sayısı serbest (en çok 30), toplam item score eşiği
                p = {"size": 0, "min_score": c["scoreRequirement"], "requirements": [],
                     "card_filter": parse_filter(c["requirementsText"])}
            else:
                p = parse(c["requirementsText"], known)
        except ValueError as err:
            sys.exit(f"{e['challenge']}: {err}")
        rep = s["numberOfRepeats"] if s["repeatabilityMode"] == "REFRESH" else 1
        sbc = {"name": e["challenge"], "formation": e["formation"], **p, "repeat": rep,
               "expires": s["endTime"][:10], "source": f"fut.gg {s['slug']} / {c['eaId']}",
               "requirements_text": c["requirementsText"]}
        if s["repeatabilityMode"] == "UNLIMITED":
            sbc["notes_repeat"] = "sınırsız tekrarlanabilir: planda bir kez"
        path = DATA / "sbcs" / e["file"]
        old = json.load(open(path, encoding="utf-8")) if path.exists() else {}
        for k in ("reward_value", "notes", "fixed"):  # açık SBC listesi: pasif/tamamlandı işareti sıfırlanır
            if k in old:
                sbc[k] = old[k]
        yaz.append((path, sbc, old))
        print(f"{e['challenge']:28s} {e['formation']:11s} tekrar {rep} | " +
              " | ".join(c["requirementsText"]))
    if sys.argv[1:] == ["kontrol"]:
        for path, sbc, old in yaz:
            print(path.name, json.dumps({k: v for k, v in sbc.items() if k != "requirements_text"}, ensure_ascii=False))
        return
    for path, sbc, old in yaz:
        path.write_text(json.dumps(sbc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(yaz)} SBC yazıldı.")


if __name__ == "__main__":
    main()
