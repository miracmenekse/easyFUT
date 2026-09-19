#!/usr/bin/env python3
"""Gerçek FC 26 oyuncu verisinden (sofifa tabanlı, GitHub) rastgele bir test kulübü üretir.
Kullanım: python3 ornek_kulup.py [oyuncu_sayısı] > data/club.csv"""
import csv, random, sys, urllib.request, io

URL = "https://raw.githubusercontent.com/ismailoksuz/EAFC26-DataHub/main/data/players.csv"
n = int(sys.argv[1]) if len(sys.argv) > 1 else 80

rows = list(csv.DictReader(io.StringIO(urllib.request.urlopen(URL).read().decode("utf-8"))))
gold = [r for r in rows if 75 <= int(r["overall"]) <= 88]
random.seed(27)
out = csv.writer(sys.stdout)
out.writerow(["name", "rating", "position", "positions", "nation", "league", "club", "rarity", "tradeable", "duplicate", "price"])
for r in random.sample(gold, n):
    # ponytail: veri kümesinde nadirlik ve coin fiyatı yok; rare rastgele, fiyat 0 (fodder_prices.csv kullanılır)
    pos = [p.strip() for p in r["player_positions"].split(",")]
    out.writerow([r["short_name"], r["overall"], pos[0], "|".join(pos), r["nationality_name"],
                  r["league_name"], r["club_name"], random.choice(["rare", "common"]),
                  "hayır", random.choice(["evet", "hayır", "hayır"]), 0])
