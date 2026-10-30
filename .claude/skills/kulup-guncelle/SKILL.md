---
name: kulup-guncelle
description: easyFUT kulübünü Web App'ten güncelleme akışı (oyuncu listesi + aktif kadro kilidi). Kullanıcı "kulübü güncelle", "oyuncuları çek", Web App "Players" listesi ekran görüntüleri ya da Squads (kadro) ekran görüntüsü attığında yükle.
---

# Kulübü güncelle

Kurallar `CLAUDE.md`'de ("Kulübü Web App'ten okuma"); bu beceri sırayı ve bu makineye özgü durumu tutar.
VM'de masaüstü yok: ekran görüntülerini kullanıcı **ana makinede** alır (`vm-guvenlik` becerisi).

## 1. Oyuncu listesi (ana makinede, kullanıcı yapar)

Firefox'ta Web App > Club > Players, yakınlaştırma %60, Firefox LG ekranında (sol, 1920x1080) tam ekran.
Ana makinede kesirli ölçeklendirme açık (X masaüstü 6912x2160); `webapp_ekran.py` bunu `OLCEK` ile hesaplar.
`webapp_ekran.py` değiştiyse kullanıcı VS Code Explorer → sağ tık → **Download** ile ana makineye alır.

```bash
rm -rf ~/ekran && cd ~ && ~/fut-ekran/bin/python webapp_ekran.py ekran/
```

Görüntüleri sohbete yapıştırır ya da Explorer'da `easyFUT/ekran_web/`'e sürükler.

## 2. Aktif kadro (her güncellemede İSTE, listeyle birlikte)

Kullanıcı ana makinede Web App > Squads > aktif kadroyu %100 yakınlıkta açar (Subs/Res kapalı) ve çalıştırır:
`cd ~ && ~/fut-ekran/bin/python webapp_ekran.py kadro ekran_kadro/` → `saha.png`, `subs.png`, `res.png`
(**saha (ilk 11)**, **Subs** paneli, **Res** (rezerv) paneli); `ekran_web/`'e sürükler. Menajer kartı oyuncu değil, sayma. Kadrodaki her kartı ad + reyting ile eşle;
bunlar `webapp_kulup.csv` `active=evet` ve `club.csv` `locked=evet`. Arayüzde elle konan kilitler
(eski club.csv `locked=evet`) `futgg.py kulup` tarafından korunur; kadro kilidini uygularken onları SİLME.
Kadro görüntüsü yoksa eski `active` değerlerini ad+reyting+istatistikle taşı ve listede olmayan eski
aktifleri kullanıcıya bildir.

## 2b. SBC Storage (depo)

Web App'te depo sayfası oyuncu listesiyle aynı düzende; %60 yakınlıkta aynı mod çalışır:
`rm -rf ~/ekran_depo && cd ~ && ~/fut-ekran/bin/python webapp_ekran.py ekran_depo/` → dosya adlarını
karıştırmamak için kullanıcı `ekran_web/depo/`'ya sürükler.
Depodaki her kart `webapp_kulup.csv`'ye AYRI satır olarak eklenir, `depo=evet` sütunuyla (diğer satırlarda boş).
`futgg.py kulup` bunları `duplicate=evet` (SBC'de önce harcanır) ve kilitsiz yazar: kulüpteki kopya kadroda
kilitliyken depodaki kopya SBC'ye gidebilir. Aynı oyuncunun iki kartı aynı SBC'ye girmez (çözücü ada göre).

## 3. Dosyalar

1. `cp data/webapp_kulup.csv data/webapp_kulup.csv.bak`, sonra listeyi yaz (`name,rating,stats,tradeable,active`).
   Sayfa başına 20 oyuncu; ardışık görüntüler 2 satır çakışır, sayfa sayısıyla kontrol et.
2. `.venv/bin/python futgg.py kulup` **bir kez** çalıştır (~1-2 dk). Her çalıştırma `club.csv.bak`'ın üzerine
   yazar: ikinci çalıştırma eski kulübün yedeğini siler.
3. Kadro kilidini uygula (adım 2), `.venv/bin/python test_fut.py` ve `fut.py plan --butce 0` ile kontrol et.
4. Kullanıcıya: kaç oyuncu, kaç yeni/giden, kaç kilitli, FUT.GG'de eşleşmeyen ya da şüpheli kartlar.

## Bilinen durumlar (2026-10-10)

- Heath 86 RW: FUT.GG'de `Icons` ligi, kulüp boş; kartta da kulüp yok, doğru.
- Rezerv (Res) paneli henüz alınmadı; kilitli 18 kart = ilk 11 + 7 yedek.
