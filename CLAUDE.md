# FUT Asistanı: Claude için çalışma notları

Kullanıcı (Mirac, Türkçe konuşur) FC 27 ekran görüntülerini bu oturuma atar. Senin işin görüntüyü `data/` altındaki dosyalara çevirmek. EA'ya hiçbir şekilde bağlanma, otomasyon kurma.
Tek istisna (kullanıcı istedi): Web App kulüp listesini `webapp_ekran.py` ile salt okuma olarak kaydırıp ekran
görüntüsü almak. Satın alma, satma, SBC gönderme gibi hiçbir işlem yapma; sayfaya kod enjekte etme.

## Yeniden başlatma gerekmez
- Arayüz (`ui.py`, http://127.0.0.1:8765) veri dosyalarını her istekte diskten okur. Sayfa 3 saniyede bir değişiklik yoklar, yeni veri gelince planı kendisi yeniden hesaplar.
- `fut.py` / `solver.py` değişirse sunucu onları kendisi yeniden yükler. Sadece `ui.py` değişirse ya da sunucu kapalıysa: `./start.sh`
  (`pkill -f ui.py` kullanma: komut satırı kendi kabuğunla eşleşir ve oturumu öldürür.)
- Python her zaman `.venv/bin/python` (OR-Tools orada). Test: `.venv/bin/python test_fut.py`. Plan: `.venv/bin/python fut.py plan --butce 0`.
- Planlayıcıyı değiştirirsen `.venv/bin/python bench.py 0-11` ile önce/sonra ölç (uydurma veri `testveri.py`):
  kanıtlı örnek sayısı düşmemeli, "hatalı örnek" 0 kalmalı.

## SBC ekran görüntüsü → `data/sbcs/<kısa_ad>.json`
Her SBC (ya da SBC grubundaki her kadro) ayrı dosyadır. Dosya adı küçük harf, ASCII ve `_` kullanır: `premier_league_hybrid.json`.

```json
{
  "name": "Premier League Hybrid",
  "size": 11,
  "min_rating": 83,
  "formation": "4-3-3",
  "repeat": 1,
  "reward_value": 10000,
  "min_chem": 20,
  "min_player_chem": 0,
  "expires": "2026-09-25",
  "requirements": [
    {"field": "league", "in": ["Premier League"], "min": 3},
    {"field": "rarity", "in": ["rare"], "min": 2},
    {"field": "rating", "gte": 85, "max": 1},
    {"type": "same", "field": "league", "max": 5},
    {"type": "distinct", "field": "nation", "min": 3}
  ]
}
```

Görüntüdeki şartların karşılığı:

| Oyundaki şart | JSON |
|---|---|
| Min. Team Rating 83 | `"min_rating": 83` |
| Premier League players: Min 3 | `{"field":"league","in":["Premier League"],"min":3}` |
| Same League Count: Max 5 | `{"type":"same","field":"league","max":5}` |
| Same Nation Count: Min 4 | `{"type":"same","field":"nation","min":4}` |
| Leagues: Min 3 / Max 3 / Exactly 3 | `{"type":"distinct","field":"league","min":3}` / `"max":3` / `"exact":3` |
| Nations / Clubs: Max 5 | `{"type":"distinct","field":"nation","max":5}` (club için `"field":"club"`) |
| Nationality: Türkiye Min 2 | `{"field":"nation","in":["Türkiye"],"min":2}` |
| Clubs: Galatasaray Min 1 | `{"field":"club","in":["Galatasaray"],"min":1}` |
| Rare players: Min 2 | `{"field":"rarity","in":["rare"],"min":2}` |
| Player OVR: Min 80 (her oyuncu) | `{"field":"rating","gte":80,"min":11}` (`min` = size) |
| # of players in the Squad: 11 | `"size": 11` |
| Team of the Week: Min 1 | `{"field":"rarity","in":["totw"],"min":1}` |
| Squad Total Chemistry Points: Min 20 | `"min_chem": 20` |
| Team Rating: Max 64 | `"max_rating": 64` |
| Player Quality: Min Gold | `{"field":"rating","gte":75,"min":11}` (min = size) |
| Player Quality: Exactly Silver | `{"field":"rating","gte":65,"lte":74,"min":11}` |
| Player Quality: Exactly Bronze | `{"field":"rating","lte":64,"min":11}` |
| Clubs in Squad: Max 3 (farklı kulüp) | `{"type":"distinct","field":"club","max":3}` |
| SBC'nin hazır verdiği oyuncu | `"fixed": [{"name":..., "rating":..., "position":..., "nation":..., "league":..., "club":...}]` |
| Chemistry Points Per Player: Min 1 | `"min_player_chem": 1` |
| Gold TOTW: Min 1 (iki şart birden) | `{"all":[{"field":"rating","gte":75},{"field":"rarity","in":["totw"]}],"min":1}` |
| Real Madrid + Arsenal toplam Min 3 | `{"field":"club","in":["Real Madrid","Arsenal"],"min":3}` (liste = "veya") |
| Belirli oyuncu: Mauro Icardi | `{"field":"name","in":["Mauro Icardi"],"min":1}` |
| Repeatable x5 | `"repeat": 5` |

- **Diziliş:** `solver.FORMATIONS` anahtarlarından biri olmalı (`.venv/bin/python -c "import solver;print(list(solver.FORMATIONS))"`). Aynı adlı varyantlar `4-3-3(2)` gibi yazılır; slot pozisyonlarını görüntüdekiyle karşılaştırıp doğru varyantı seç. Listede yoksa `solver.FORMATIONS`'a ekle. Kimya şartı varsa diziliş doğru olmalı: kimya sadece pozisyonundaki oyuncuya gelir.
- **Ödül değeri:** `reward_value` paket ya da oyuncunun yaklaşık coin karşılığıdır. Görüntüde yoksa bilinen paket değerini tahmin et ve `"notes"` alanında bunun tahmin olduğunu belirt.
- **Ad yazımı:** Lig, ülke ve kulüp adları `data/club.csv` ile birebir aynı olmalı (oyundaki İngilizce ad: "Premier League", "LALIGA EA SPORTS" değil, club.csv'de ne yazıyorsa o). Emin değilsen `cut -d, -f5 data/club.csv | sort -u` ile kontrol et.
- **Süresi dolanlar:** `expires` bilgi amaçlıdır. Süresi dolmuş SBC dosyalarını kullanıcıya sorarak sil.
- **Kontrol:** Her dosyayı yazdıktan sonra `python3 -m json.tool dosya.json >/dev/null` ile doğrula. En sonda `.venv/bin/python fut.py plan` ile sonucu kontrol et ve kullanıcıya kısa bir özet ver: kaç SBC eklendi, kaçı yapılabilir.

## Kulübü Web App'ten okuma → `data/club.csv`
Kullanıcı "kulübü güncelle" derse (Firefox'ta Web App > Club > Players açık, %67 yakınlaştırma):
1. `.venv/bin/python webapp_ekran.py ekran/` görüntüleri alır (sadece tekerlek + Next; sayfaya kod enjekte etme,
   konsol kullanma: kullanıcı "güvenlik protokolleri" nedeniyle istemiyor). Başka çözünürlükte önce bir ekran
   görüntüsüne bakıp betikteki KUTU / NEXT / PREV koordinatlarını düzelt.
2. Görüntüleri oku, her oyuncu için `data/webapp_kulup.csv` satırı yaz: `name,rating,stats,tradeable,active`.
   `stats` kart altındaki 6 sayı (kaleci: DIV HAN KIC REF SPD POS). İsmin yanında ⊘ işareti = takaslanamaz
   (`tradeable=hayır`). `active` (club.csv'de kilitli olur): listedeki yeşil rozet aktif kadro DEĞİL (başka bir
   kadroda olmak gibi bir şey); aktif kadroyu kullanıcının Squads ekranı görüntüsünden (ilk 11 + yedek + rezerv)
   al, eski kilitleri koru ya da kullanıcıya sor. Görüntüler 2 satır çakışır: aynı satırı iki kez yazma.
3. `.venv/bin/python futgg.py kulup`: FUT.GG'de aynı reyting + aynı 6 istatistik = aynı kart (özel kartlar dahil);
   ülke/lig/kulüp/alternatif pozisyon/nadirlik oradan gelir. Eşleşmeyenler (Evolution kartları) en yakın temel
   karttan alınır ve listelenir. Kopya (`duplicate`) ve fiyat eski club.csv'den taşınır. Eski dosya club.csv.bak.
4. `.venv/bin/python futgg.py deger`: club.csv'yi bozmadan `value` sütununu (FUT.GG kart değeri = `gradingScore`,
   sitedeki elmas ikonlu sayı) doldurur. `value` pazar fiyatı (`price`) değildir.

## Kulüp ekran görüntüsü → `data/club.csv`
- Sütunlar: `name,rating,position,positions,nation,league,club,rarity,tradeable,duplicate,locked,price,value`
- `positions`: oyuncunun oynayabildiği bütün pozisyonlar `ST|CF|LW` biçiminde (kart üstündeki alternatif pozisyonlar). Kimya hesabı için önemli.
- `locked`: kullanıcı bu kartı SBC'de kullanmak istemiyorsa `evet`.
- `rarity`: `rare`, `common`, özel kartlar için `totw`, `icon`, `hero` vb. (icon/hero pozisyonundayken her zaman 3 kimya).
- Görüntüdeki her kartı bir satır olarak **ekle**. Aynı isim zaten varsa kopya demektir: mevcut satırın `duplicate` alanını `evet` yap.
- Görüntüde lig veya ülke görünmüyorsa oyuncunun gerçek bilgisini kullan. Emin değilsen boş bırakma, kullanıcıya sor.
- `tradeable` bilgisini görüntüden anlayamıyorsan `hayır` yaz. `price` alanına sadece takaslanabilir kartlar için değer gir.
- Değiştirmeden önce yedek al: `cp data/club.csv data/club.csv.bak`

## Pazar fiyatları → `data/fodder_prices.csv`
Kullanıcı FUTBIN veya FUT.GG'deki "cheapest by rating" ekranının görüntüsünü atarsa `rating,price` satırlarını güncelle.

## İsimden doldurma (doldur.py) — sınırlı güvenilirlik
`python3 doldur.py ogren` club.csv'deki bilinen kartlardan EA numara→isim eşlemesini öğrenir (`data/ea_ids.json`).
`python3 doldur.py isimler.txt` satır başına "İsim", "İsim, reyting" ya da "İsim, reyting, Kulüp" okuyup CSV üretir.
Kaynak: api.easysbc.io (açık arama servisi, EA hesabına bağlanmaz).
**Dikkat:** Bu serviste FC 27 verisi eksik; bazı kartların reytingi/kulübü FC 26'dan geliyor. Üretilen satırları
kullanıcının ekran görüntüsüyle karşılaştırmadan club.csv'ye ekleme. Eşleşmeyenleri kullanıcıya sor.

## Aktif kadro (SBC'ye girmesin)
Kullanıcının oyunda kullandığı ilk 11 + yedekler SBC'de harcanmamalı. Bunlar `data/club.csv`'de
`locked=evet` ile işaretlenir; `solver.py` kilitli kartları havuza hiç almaz.
- Kullanıcı kadro ekran görüntüsü atarsa: görüntüdeki her kartı reyting+pozisyon+ülke ile club.csv'de
  bul ve `locked=evet` yap. Önce eski kilitleri temizle (kadro değişmiş olabilir).
- Emin olamadığın kartı kilitleme, kullanıcıya sor — yanlış kilit iyi bir kartı plandan çıkarır.
- Kulüp PDF'lerinde aktif kadro ayrı işaretli değildir; kadro görüntüsü ayrıca gerekir.
