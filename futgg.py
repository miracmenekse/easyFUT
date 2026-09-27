"""club.csv'yi FUT.GG'den (oyuncu başına bir istek) tamamlar.

.venv/bin/python futgg.py           # yalnızca positions'ı tek pozisyon olanlar
.venv/bin/python futgg.py hepsi     # bütün oyuncular
.venv/bin/python futgg.py kulup     # data/webapp_kulup.csv'den (Web App ekran görüntülerinden okunan liste)
                                    # club.csv'yi baştan kurar; eski dosya club.csv.bak olur
.venv/bin/python futgg.py ekle yeni.csv   # yeni gelen oyuncuları (aynı biçim) club.csv'ye ekler
.venv/bin/python futgg.py deger     # club.csv'nin value sütununu (FUT.GG kart değeri, gradingScore) doldurur
"""
import csv, json, sys, time, unicodedata, urllib.parse, urllib.request
from pathlib import Path

API = "https://www.fut.gg/api/fut/players/v2/27/?name="
CLUB = Path(__file__).parent / "data" / "club.csv"


def norm(s):
    return "".join(c for c in unicodedata.normalize("NFKD", str(s or "")) if not unicodedata.combining(c)).lower().strip()


def ara(c):
    """En uygun kartı döndür: ad eşleşmeli; sonra ülke, pozisyon, reyting yakınlığına göre."""
    ad = c["name"].split(". ")[-1].split("-")[-1]  # "L. Martínez" -> "Martínez", "Lewis-Potter" -> "Potter", baş harf aşağıda kontrol edilir
    bas = c["name"].split(". ")[0].lower() if ". " in c["name"] else ""
    req = urllib.request.Request(API + urllib.parse.quote(ad), headers={"User-Agent": "Mozilla/5.0"})
    kartlar = json.load(urllib.request.urlopen(req, timeout=30))["data"]
    n = norm(c["name"])
    m = [p for p in kartlar
         if (n in (norm(p["commonName"]), norm(p["lastName"]), norm(f'{p["firstName"]} {p["lastName"]}'))
             or bas and norm(p["lastName"]) == norm(ad) and norm(p["firstName"]).startswith(bas))
         and norm((p["nation"] or {}).get("name")) == norm(c["nation"])]
    m.sort(key=lambda p: (p["position"] != c["position"], abs(p["overall"] - int(c["rating"]))))
    return m[0] if m else None


RARITY = {"rare": "rare", "common": "common", "team of the week": "totw", "base icon": "icon", "icon": "icon",
          "hero": "hero"}
STATS = ("facePace", "faceShooting", "facePassing", "faceDribbling", "faceDefending", "facePhysicality")
GK_STATS = ("gkFaceDiving", "gkFaceHandling", "gkFaceKicking", "gkFaceReflexes", "gkFaceSpeed", "gkFacePositioning")


def kart(name, rating, stats):
    """Web App satırındaki kartın FUT.GG karşılığı: aynı reyting ve aynı 6 yüz istatistiği (özel kartlar da ayrılır)."""
    ad = name.replace("'", " ").replace("-", " ").split()[-1]
    uzak = lambda p: min(sum(abs(p["faceStatsV2"][k] - v) for k, v in zip(ks, stats)) for ks in (STATS, GK_STATS))
    for filtre in (f"&overall__gte={rating}&overall__lte={rating}", ""):  # yoksa Evolution kartı: en yakın temel kart
        kartlar, sayfa = [], 1
        while sayfa and sayfa <= 10:  # kısa isimler ("Ba") çok sonuç verir: tam eşleşme bulunana kadar sonraki sayfa
            req = urllib.request.Request(API + urllib.parse.quote(ad) + filtre + f"&page={sayfa}",
                                         headers={"User-Agent": "Mozilla/5.0"})
            d = json.load(urllib.request.urlopen(req, timeout=30))
            kartlar += [p for p in d["data"] if filtre or
                        norm(name) in (norm(p["commonName"]), norm(p["lastName"]), norm(f'{p["firstName"]} {p["lastName"]}'))]
            sayfa = None if any(p["overall"] == rating and uzak(p) == 0 for p in kartlar) else d.get("next")
        m = sorted(kartlar, key=lambda p: (p["overall"] != rating, uzak(p) + 3 * abs(p["overall"] - rating)))
        if m:
            return m[0], uzak(m[0]) if m[0]["overall"] == rating else f"Evolution? FUT.GG'de {m[0]['overall']}"
    return None, None


def kulup():
    """Web App listesini (isim, reyting, istatistik, takas, aktif kadro) FUT.GG ile tamamlayıp club.csv yazar."""
    eski = {}
    with open(CLUB) as f:
        r = csv.DictReader(f)
        fields = cols(r.fieldnames)
        for c in r:
            eski[(norm(c["name"]), c["rating"])] = c
    CLUB.with_suffix(".csv.bak").write_text(CLUB.read_text())
    rows, sorun = [], []
    liste = list(csv.DictReader(open(CLUB.parent / "webapp_kulup.csv")))
    for i, w in enumerate(liste, 1):
        print(f"\r{i}/{len(liste)}", end="", flush=True)
        stats = [int(v) for v in w["stats"].split()]
        p, fark = kart(w["name"], int(w["rating"]), stats)
        time.sleep(0.3)  # siteye yük bindirme
        if not p:
            sorun.append(f'{w["name"]} {w["rating"]}: FUT.GG\'de yok')
            continue
        if fark:
            sorun.append(f'{w["name"]} {w["rating"]}: istatistik tam tutmadı ({fark}), en yakın kart alındı: '
                         f'{p["commonName"] or p["lastName"]} {p["overall"]} {p["rarityName"]}')
        rows.append(satir(w, p, eski.get((norm(w["name"]), w["rating"]), {})))
    print()
    with open(CLUB, "w", newline="") as f:
        wr = csv.DictWriter(f, fields)
        wr.writeheader()
        wr.writerows(rows)
    print(f"{len(rows)}/{len(liste)} oyuncu club.csv'ye yazıldı (eskisi club.csv.bak).")
    for s_ in sorun:
        print("  " + s_)


def cols(fields):
    return fields + ["value"] * ("value" not in fields)


def deger():
    """club.csv'yi baştan kurmadan (kilitler, elle düzeltmeler kalır) her kartın FUT.GG değerini value'ya yazar.
    Kart, webapp_kulup.csv'deki 6 istatistikle bulunur; orada yoksa isim/ülke/pozisyonla (ara)."""
    with open(CLUB) as f:
        r = csv.DictReader(f)
        fields, club = cols(r.fieldnames), list(r)
    stats = {(norm(w["name"]), w["rating"]): [int(v) for v in w["stats"].split()]
             for w in csv.DictReader(open(CLUB.parent / "webapp_kulup.csv"))}
    CLUB.with_suffix(".csv.bak").write_text(CLUB.read_text())
    sorun = []
    for i, c in enumerate(club, 1):
        print(f"\r{i}/{len(club)}", end="", flush=True)
        st = stats.get((norm(c["name"]), c["rating"]))
        p, fark = kart(c["name"], int(c["rating"]), st) if st else (ara(c), "istatistik yok, isimle bulundu")
        time.sleep(0.3)  # siteye yük bindirme
        c["value"] = (p or {}).get("gradingScore") or 0
        if not p or fark:
            sorun.append(f'{c["name"]} {c["rating"]}: ' + (f"{fark} -> {c['value']}" if p else "FUT.GG'de yok, value=0"))
    print()
    with open(CLUB, "w", newline="") as f:
        w = csv.DictWriter(f, fields)
        w.writeheader()
        w.writerows(club)
    print(f"{len(club)} kartın değeri yazıldı (eskisi club.csv.bak). Toplam: {sum(int(c['value']) for c in club):,}")
    for s_ in sorun:
        print("  " + s_)


def satir(w, p, o):
    """Web App satırı (w) + FUT.GG kartı (p) + eski club.csv satırı (o: kopya/fiyat) -> club.csv satırı"""
    return {"name": w["name"], "rating": w["rating"], "position": p["position"],
            "positions": "|".join([p["position"]] + p["alternativePositions"]),
            "nation": (p["nation"] or {}).get("name", ""), "league": (p["league"] or {}).get("name", ""),
            "club": (p["club"] or {}).get("name", ""),
            "rarity": "icon" if p["isIcon"] else "hero" if p["isHero"] else  # kimya: her zaman 3
                      RARITY.get(p["rarityName"].lower(), p["rarityName"].lower()),
            "tradeable": w["tradeable"], "duplicate": o.get("duplicate", "hayır"), "locked": w["active"],
            "price": o.get("price", 0) if w["tradeable"] == "evet" else 0, "value": p.get("gradingScore") or 0}


def ekle(path):
    """Yeni gelen oyuncular (webapp_kulup.csv biçiminde bir dosya) FUT.GG ile tamamlanıp club.csv'ye eklenir.
    Aynı isim + reyting zaten varsa yeni satır eklenmez, var olanın kopya işareti açılır."""
    with open(CLUB) as f:
        r = csv.DictReader(f)
        fields, club = cols(r.fieldnames), list(r)
    CLUB.with_suffix(".csv.bak").write_text(CLUB.read_text())
    for w in csv.DictReader(open(path)):
        var = next((c for c in club if c["name"] == w["name"] and c["rating"] == w["rating"]), None)
        if var:
            var["duplicate"] = "evet"
            print(f'{w["name"]} {w["rating"]}: zaten var, kopya olarak işaretlendi')
            continue
        p, fark = kart(w["name"], int(w["rating"]), [int(v) for v in w["stats"].split()])
        time.sleep(0.3)
        if not p:
            print(f'{w["name"]} {w["rating"]}: FUT.GG\'de yok, eklenmedi (elle ekle)')
            continue
        club.append(satir(w, p, {}))
        print(f'{w["name"]} {w["rating"]}: eklendi ({p["position"]}, {(p["nation"] or {}).get("name")}, '
              f'{(p["league"] or {}).get("name")}, {(p["club"] or {}).get("name")})' + (f" [dikkat: {fark}]" if fark else ""))
    with open(CLUB, "w", newline="") as f:
        wr = csv.DictWriter(f, fields)
        wr.writeheader()
        wr.writerows(club)


def main():
    with open(CLUB) as f:
        r = csv.DictReader(f)
        fields, club = r.fieldnames, list(r)
    eksik = []
    for i, c in enumerate(club, 1):
        print(f"\r{i}/{len(club)}", end="", flush=True)
        if "hepsi" not in sys.argv and "|" in c["positions"]:
            continue
        p = ara(c)
        time.sleep(0.3)  # siteye yük bindirme
        if not p:
            eksik.append(c["name"])
            continue
        c["position"] = c["position"] or p["position"]
        c["positions"] = "|".join(dict.fromkeys([c["position"], p["position"]] + p["alternativePositions"]))
    print()
    with open(CLUB, "w", newline="") as f:
        w = csv.DictWriter(f, fields)
        w.writeheader()
        w.writerows(club)
    print(f"{len(club) - len(eksik)}/{len(club)} oyuncu tamam.")
    if eksik:
        print("Bulunamadı, elle bak: " + ", ".join(eksik))


if __name__ == "__main__":
    if sys.argv[1:2] == ["ekle"]:
        ekle(sys.argv[2])
    elif sys.argv[1:] == ["deger"]:
        deger()
    else:
        kulup() if sys.argv[1:] == ["kulup"] else main()
