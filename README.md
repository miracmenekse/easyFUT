# FUT Asistanı

EA hesabına **hiç bağlanmaz**. Veriyi sen `data/` klasörüne koyarsın, program hesaplar ve önerir, tıklamaları Web App'te sen yaparsın. Bu yüzden ban riski yok.

Python 3.10+ ve Google OR-Tools gerekir. OR-Tools proje içindeki `.venv` ortamında kurulu (sistem Python'una dokunulmaz). Sıfırdan kurulum:

```bash
python3 -m venv --without-pip .venv && curl -sS https://bootstrap.pypa.io/get-pip.py | .venv/bin/python && .venv/bin/python -m pip install ortools
```

## Arayüz

Uygulama menüsünden **FUT Asistanı**'na tıkla ya da `./start.sh` çalıştır. Tarayıcıda http://127.0.0.1:8765 açılır.
Ana Sayfa, bütçene göre **en fazla sayıda SBC'yi** tamamlayacak kart dağıtımını ve her SBC'nin sahadaki dizilişini gösterir. "Şu an oyunda hangi SBC'desin?" seçimiyle sadece o kadro büyük görünür.

SBC ve kulüp ekran görüntülerini Claude Code oturumuna atarsan veri dosyalarını Claude yazar (kurallar `CLAUDE.md`'de). Arayüz değişikliği 3 saniye içinde kendisi görür, yeniden başlatma gerekmez.

## Komutlar

```bash
.venv/bin/python fut.py plan --butce 20000 # en fazla SBC planı (0: sadece kulüp kartları)
.venv/bin/python fut.py sbc                # data/sbcs/ içindeki bütün SBC'leri çöz
.venv/bin/python fut.py sbc data/sbcs/x.json
.venv/bin/python fut.py kulup              # kopyalar, reyting dağılımı, satılabilir kartlar
.venv/bin/python fut.py evo                # hangi oyuncu hangi Evolution'a uygun
.venv/bin/python fut.py kar 10000 12500    # 10.000'e alıp 12.500'e satarsam kârım (%5 vergi dahil)
.venv/bin/python fut.py fiyat 10000 1000   # 1.000 kâr için en az kaça listelemeliyim
.venv/bin/python test_fut.py               # hızlı kontrol
```

## Veriyi nasıl atarsın

Veri almanın tek yolu `data/` klasörü. İleride veriyi başka bir yoldan alırsan (ekran görüntüsünden okuma gibi) sadece `fut.py` içindeki `load_*` fonksiyonları değişir.

### 1. `data/club.csv`: kulübün (zorunlu)

Web App'te Kulüp > Oyuncular ekranından elle girebilir ya da ekran görüntüsünü bir yapay zekaya verip bu formatta yazdırabilirsin. İlk satır başlık satırıdır:

```csv
name,rating,position,nation,league,club,rarity,tradeable,duplicate,price
Mauro Icardi,83,ST,Argentina,Süper Lig,Galatasaray,rare,hayır,hayır,0
Declan Rice,87,CDM,England,Premier League,Arsenal,rare,evet,hayır,14000
```

| Sütun | Ne yazılır |
|---|---|
| name | Oyuncu adı. Aynı oyuncu bir kadroda iki kez kullanılamaz, bu ad ile kontrol edilir. |
| rating | Reyting (sayı) |
| position | Ana pozisyon (ST, CM, CB, GK…) |
| nation / league / club | Ülke, lig, kulüp. **SBC dosyasında da aynen böyle yazılmalı** ("Süper Lig", "La Liga", "Premier League"). |
| rarity | `rare` / `common`. Özel kartlar için `totw`, `special` gibi istediğin bir etiket. |
| tradeable | Takaslanabilir mi: `evet` / `hayır` |
| duplicate | Yedekte kopyası var mı: `evet` / `hayır`. Kopyalar SBC'de önce kullanılır. |
| price | Takaslanabilirse piyasa fiyatı (FUTBIN veya FUT.GG'den), değilse `0` |

### 2. `data/fodder_prices.csv`: pazardaki en ucuz kart fiyatları (önerilir)

Her reyting için pazardaki en ucuz fiyat. FUTBIN'de "Cheapest by rating" sayfasından günde bir kez güncellemen yeterli. Bu dosya varsa çözücü eksik kartlar için "[SATIN AL] 84 genel kart" önerebilir.

```csv
rating,price
83,700
84,1000
```

### 3. `data/sbcs/*.json`: SBC'ler (her SBC ayrı dosya)

```json
{
  "name": "Süper Lig Meydan Okuması",
  "size": 11,
  "min_rating": 82,
  "reward_value": 8000,
  "requirements": [
    {"field": "league", "in": ["Süper Lig"], "min": 3},
    {"field": "nation", "in": ["Türkiye"], "min": 2},
    {"field": "rarity", "in": ["rare"], "min": 1},
    {"field": "rating", "gte": 85, "max": 1}
  ]
}
```

- `repeat`: Bu SBC kaç kez yapılabilir (varsayılan 1). Planlayıcı her tekrarı ayrı sayar.
- `reward_value`: Ödülün yaklaşık coin değeri. Ödül-maliyet hesabında kullanılır, bilmiyorsan dosyaya yazma.
- Şartlar: `field` herhangi bir sütun adı olabilir. Eşleşme için `in` (listeden biri), `gte` (en az) ve `lte` (en fazla) kullanılır. Sayı için `min` (en az kaç kart) ve `max` (en fazla kaç kart) kullanılır.

### 4. `data/evos/*.json`: Evolution'lar

```json
{"name": "Genç Forvet Evo",
 "requirements": [{"field": "rating", "lte": 83}, {"field": "position", "in": ["ST", "CAM"]}]}
```

## Gerçek verilerle deneme

`python3 ornek_kulup.py 80 > data/ornek/club_fc26.csv` komutu gerçek FC 26 oyuncu verisinden ([EAFC26-DataHub](https://github.com/ismailoksuz/EAFC26-DataHub), 18 bin oyuncu) rastgele bir kulüp üretir. Bu veride coin fiyatı ve nadirlik bilgisi yok, nadirlik rastgele atanır. FC 27 verisi çıkınca aynı yöntem kullanılabilir. Kaggle'da da benzer veri kümeleri var: [FC 26 Player Ratings](https://www.kaggle.com/datasets/justdhia/ea-sports-fc-26-player-ratings), [EAFC26 Player Database](https://www.kaggle.com/datasets/flynn28/eafc26-player-database).

## SBC çözücü nasıl çalışır

`solver.py`, Google OR-Tools CP-SAT ile bütün SBC'leri tek modelde çözer (fikirler [Regista6/EA-FC-Automated-SBC-Solving](https://github.com/Regista6/EA-FC-Automated-SBC-Solving) çalışmasından):
1. Önce SBC'ler birkaç farklı sırayla tek tek çözülür, en iyisi başlangıç noktası olur.
2. Sonra ortak model bu noktadan başlayıp iyileştirir: önce **en fazla SBC**, sonra en az coin (2 kat ağırlıklı) + en az kart değeri.
3. Her çözüm `solver.check` ile çözücüden bağımsız yeniden doğrulanır; arayüzde şart listesi ✓/✗ olarak görünür.

Desteklenen şartlar: takım reytingi (EA formülü), toplam kimya, oyuncu başı kimya, lig/ülke/kulüp/nadirlik/reyting/isim oyuncu sayısı, birleşik şartlar (`"all"`: iki alan birden, ör. 84+ VE rare), aynı lig/ülke/kulüp en çok/en az, farklı lig/ülke/kulüp sayısı (en az/en çok/tam), tekrar sayısı, kilitli kartlar.

## Bilinen sınırlar

- **Pazardan alınacak kartlar "genel" sayılır:** lig/ülke/kulüp şartına ve kimyaya katkı vermez (güvenli taraf). Oyuncu başı kimya isteyen SBC'de hiç önerilmez.
- **İkon/Hero kimyası basitleştirildi:** pozisyonundaysa 3 kimya alır, başkalarına lig/ülke katkısı hesaplanmaz.
- **Süre sınırı:** arayüzde 20 sn. Sonuç "kanıtlanmış en iyi" değilse süre sınırında bulunan en iyidir.
- **Reyting formülü topluluk (EasySBC) formülüdür.** Sınırdaki bir sonucu (tam 84 gibi) göndermeden önce oyunda kontrol et.
- SBC grupları (hepsi bitince ödül veren çok kadrolu SBC'ler) ayrı ayrı girilir; grup ödülü hesaba katılmaz.
