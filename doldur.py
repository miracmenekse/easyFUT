#!/usr/bin/env python3
"""İsim (ve varsa reyting) listesinden kart bilgilerini doldurur.

Kaynak: easySBC'nin açık arama servisi (api.easysbc.io). EA hesabına bağlanmaz.
Ülke/lig/kulüp isimleri data/ea_ids.json içindeki eşlemeden gelir; eşleme
data/club.csv'deki bilinen kartlardan öğrenilir (bkz. "ogren" komutu).

Kullanım:
  python3 doldur.py ogren                 # mevcut club.csv'den numara->isim eşlemesini öğren
  python3 doldur.py isimler.txt           # satır başına "İsim" ya da "İsim, reyting"
  python3 doldur.py isimler.txt >> data/club.csv
"""
import csv, json, sys, time, unicodedata, urllib.parse, urllib.request
from pathlib import Path

import fut

API = "https://api.easysbc.io/players?page=1&search="
IDS = fut.DATA / "ea_ids.json"
FIELDS = ["nation", "league", "club"]
KEYS = {"nation": "countryId", "league": "leagueId", "club": "clubId"}


def sade(s):
    """Aksanları at, küçük harfe indir: 'Šeško' -> 'sesko'."""
    return "".join(c for c in unicodedata.normalize("NFD", str(s).lower()) if not unicodedata.combining(c)).strip()


def ara(isim):
    url = API + urllib.parse.quote(isim)
    req = urllib.request.Request(url, headers={"User-Agent": "fut-asistan (personal use)"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r).get("players", [])


def esleme():
    return json.loads(IDS.read_text(encoding="utf-8")) if IDS.exists() else {f: {} for f in FIELDS}


def cmd_ogren():
    """club.csv'de ismi ve lig/kulüp/ülkesi bilinen kartlardan numara->isim eşlemesi çıkar."""
    m = esleme()
    club = fut.load_club()
    yeni = 0
    for c in club:
        kartlar = ara(c["name"])
        time.sleep(0.3)  # servisi yormayalım
        # isim de tutmalı: sadece reytinge bakmak "Gabriel 89" -> "Gabriel Batistuta 89" gibi
        # yanlış eşleşme yapıp eşlemeyi bozuyor
        soyad = sade(c["name"]).split()[-1]
        uyan = [p for p in kartlar if soyad in sade(p["name"]).split()]
        tam = [p for p in uyan if p["rating"] == c["rating"]] or uyan
        kimlik = {(p["countryId"], p["leagueId"], p["clubId"]) for p in tam}
        k = tam[0] if len(kimlik) == 1 else None  # aynı isimden birden fazla oyuncu varsa öğrenme
        if not k:
            print(f"  bulunamadı: {c['name']} {c['rating']}", file=sys.stderr)
            continue
        for f in FIELDS:
            ad = str(c.get(f) or "")
            if ad and not ad.startswith("Bilinmiyor") and ad != "?":
                anahtar = str(k[KEYS[f]])
                if m[f].get(anahtar) != ad:
                    m[f][anahtar] = ad
                    yeni += 1
    IDS.write_text(json.dumps(m, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    print(f"{yeni} yeni eşleme öğrenildi -> {IDS}", file=sys.stderr)
    for f in FIELDS:
        print(f"  {f}: {len(m[f])} kayıt", file=sys.stderr)


def cmd_doldur(path):
    m = esleme()
    out = csv.writer(sys.stdout)
    out.writerow(["name", "rating", "position", "positions", "nation", "league", "club",
                  "rarity", "tradeable", "duplicate", "locked", "price"])
    for satir in Path(path).read_text(encoding="utf-8").splitlines():
        satir = satir.strip()
        if not satir or satir.startswith("#"):
            continue
        parca = [x.strip() for x in satir.split(",")]
        isim = parca[0]
        rey = int(parca[1]) if len(parca) > 1 and parca[1].isdigit() else None
        kulup = parca[2] if len(parca) > 2 else None  # aynı isim+reytingden birden fazlaysa ayırt eder
        kartlar = ara(isim)
        time.sleep(0.3)
        if not kartlar:
            print(f"  BULUNAMADI: {satir}", file=sys.stderr)
            continue
        soyad = sade(isim).split()[-1]
        uyan = [p for p in kartlar if soyad in sade(p["name"]).split()]
        tam = [p for p in uyan if rey and p["rating"] == rey]
        if kulup:
            tam = [p for p in tam if sade(m["club"].get(str(p["clubId"]), "")) == sade(kulup)] or tam
        if len(tam) > 1 and len({(p["countryId"], p["leagueId"], p["clubId"]) for p in tam}) > 1:
            print(f"  ! {isim} {rey}: birden fazla oyuncuya uyuyor -> "
                  + " | ".join(f"{p['name']} ({m['club'].get(str(p['clubId']), p['clubId'])})" for p in tam[:4])
                  + "  (satıra kulüp adı ekle: 'İsim, reyting, Kulüp')", file=sys.stderr)
        k = tam[0] if tam else None
        if not k:
            aday = uyan or kartlar
            k = max(aday, key=lambda p: p["rating"])
            print(f"  ! {isim}: {rey} reytingli kart bulunamadı, {k['name']} {k['rating']} alındı "
                  f"(seçenekler: {sorted({p['rating'] for p in aday}, reverse=True)[:6]})", file=sys.stderr)
        pos = k.get("positions") or [k.get("preferredPosition")]
        eksik = [f for f in FIELDS if str(k[KEYS[f]]) not in m[f]]
        if eksik:
            print(f"  ! {isim}: {', '.join(eksik)} bilinmiyor "
                  f"({', '.join(f'{f}#{k[KEYS[f]]}' for f in eksik)})", file=sys.stderr)
        out.writerow([k["name"], k["rating"], k.get("preferredPosition") or pos[0], "|".join(pos)]
                     + [m[f].get(str(k[KEYS[f]]), f"?{KEYS[f]}{k[KEYS[f]]}") for f in FIELDS]
                     + ["", "hayır", "hayır", "hayır",  # takas/kopya/kilit bilgisi karttan gelmez, sen işaretlersin
                        (k.get("priceInfo") or {}).get("displayPrice") or 0])


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd_ogren() if sys.argv[1] == "ogren" else cmd_doldur(sys.argv[1])
