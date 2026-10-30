"""Web App "My Club Players" listesinin ekran görüntülerini alır (sadece fare tekerleği + Next tıklaması, sayfaya
kod enjekte etmez). Görüntüleri Claude okuyup data/webapp_kulup.csv'ye yazar; sonra: .venv/bin/python futgg.py kulup

Önce: Firefox'ta Web App > Club > Players açık, yakınlaştırma %60, 1920x1080 ekranda (sol üstteki) tam ekran.
Kesirli ölçeklendirme (2 kat X masaüstü) kendiliğinden hesaba katılır.
.venv/bin/python webapp_ekran.py ekran/        # görüntüler ekran/pSS_KK.png
Başka çözünürlükte KUTU / NEXT / PREV koordinatlarını bir ekran görüntüsüne bakarak güncelle.

Aktif kadro: Web App > Squads > aktif kadro açık, yakınlaştırma %100, Subs/Res kapalı:
.venv/bin/python webapp_ekran.py kadro ekran_kadro/   # saha.png, subs.png, res.png (Subs/Res panelini açıp kapatır)

SBC listesi (hangileri açık / ne kadar ilerlemiş): Web App > SBC > All, yakınlaştırma %60. Sadece tekerlek:
.venv/bin/python webapp_ekran.py sbc ekran_sbc/        # sbc_KK.png

Yarım set ("2/4 SBCs") içi: sbc taramasından hemen sonra, liste en üstteyken. Hedefi Claude sbc_KK.png'den verir:
.venv/bin/python webapp_ekran.py sbc-ic ekran_sbc/ 3:180:930 [5:600:520 ...]   # KK:x:y = o görüntüde set başlığı
Her hedef: aynı kaydırma tekrarlanır, ekran kayıttaki sbc_KK.png ile aynı mı bakılır (değilse durur), başlığa
tıklanır, içi set_KK_x_y.png olarak kaydedilir, sol üst geri okuyla listeye dönülür. Başka hiçbir yere tıklanmaz.
"""
import sys, time
from pathlib import Path

from PIL import Image, ImageChops
from Xlib import X, display
from Xlib.ext import xtest
from Xlib.protocol import event

KUTU = (665, 250, 1165, 985)  # oyuncu listesi paneli (Next satırı hariç), 1920x1080 %60 (LG)
NEXT, PREV = (1136, 997), (690, 997)
LISTE = (915, 600)  # tekerleğin çevrileceği nokta (liste üstü)
PENCERE = "FC Ultimate Team Web App"
KADRO = (233, 314, 1479, 1020)  # saha paneli, %100 yakınlık
SUBS, SUBS_ACIK, RES = (271, 992), (271, 836), (1434, 992)  # panel düğmeleri (açıkken Subs yukarı kayar)
SBC_KUTU, SBC_LISTE = (725, 250, 1310, 1075), (1015, 650)  # SBC listesi (iki sütun kart), %60 yakınlık
GERI = (102, 188)  # set içinde sol üst geri oku, %60 (tahmini; yanlışsa listeye dönüş kontrolü durdurur)
TAM = (0, 0, 1920, 1080)  # set içi: LG ekranın tamamı

d = display.Display()
root = d.screen().root
# Kesirli ölçeklendirme açıkken X masaüstü 2 kat çizilir (1920x1080 ekran -> 3840x2160); Web App sol üstteki ekranda
OLCEK = round(root.get_geometry().height / 1080) or 1
KUTU = tuple(v * OLCEK for v in KUTU)
KADRO, SBC_KUTU, TAM = (tuple(v * OLCEK for v in k) for k in (KADRO, SBC_KUTU, TAM))
NEXT, PREV, LISTE, SUBS, SUBS_ACIK, RES, SBC_LISTE, GERI = ((x * OLCEK, y * OLCEK) for x, y in
                                                     (NEXT, PREV, LISTE, SUBS, SUBS_ACIK, RES, SBC_LISTE, GERI))


def one_getir(title):
    net, name, utf = d.intern_atom("_NET_CLIENT_LIST"), d.intern_atom("_NET_WM_NAME"), d.intern_atom("UTF8_STRING")
    for w in root.get_full_property(net, X.AnyPropertyType).value:
        win = d.create_resource_object("window", w)
        p = win.get_full_property(name, utf)
        if p and title in p.value.decode():
            root.send_event(event.ClientMessage(window=win, client_type=d.intern_atom("_NET_ACTIVE_WINDOW"),
                                                data=(32, [2, X.CurrentTime, 0, 0, 0])),
                            event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
            d.flush()
            time.sleep(0.6)
            return
    sys.exit(f'"{title}" başlıklı pencere yok: Firefox\'ta Web App açık mı?')


def tik(x, y):
    xtest.fake_input(d, X.MotionNotify, x=x, y=y)
    xtest.fake_input(d, X.ButtonPress, 1)
    xtest.fake_input(d, X.ButtonRelease, 1)
    d.sync()
    time.sleep(0.3)


def teker(n, nokta=None):
    nokta = nokta or LISTE
    xtest.fake_input(d, X.MotionNotify, x=nokta[0], y=nokta[1])
    for _ in range(abs(n)):
        b = 5 if n > 0 else 4
        xtest.fake_input(d, X.ButtonPress, b)
        xtest.fake_input(d, X.ButtonRelease, b)
        d.sync()
        time.sleep(0.08)
    time.sleep(0.6)


def odakta():
    w = d.get_input_focus().focus
    for _ in range(6):
        if isinstance(w, int):
            return False
        n = w.get_full_property(d.intern_atom("_NET_WM_NAME"), d.intern_atom("UTF8_STRING"))
        if n:
            return PENCERE in n.value.decode()
        w = w.query_tree().parent
    return False


def goruntu(kutu=None, kucult=True):
    if not odakta():  # başka pencere öne geçtiyse yanlışlıkla "sayfa sonu" sanma
        sys.exit("Web App penceresi önde değil: yakalama durduruldu, eksik kalmasın diye baştan çalıştır")
    g = root.get_geometry()
    raw = root.get_image(0, 0, g.width, g.height, X.ZPixmap, 0xffffffff)
    im = Image.frombytes("RGB", (g.width, g.height), raw.data, "raw", "BGRX").crop(kutu or KUTU)
    return im.resize((im.width // OLCEK, im.height // OLCEK), Image.LANCZOS) if OLCEK > 1 and kucult else im


def ayni(a, b):
    """Sadece yazı sütunu (kart resmi ve ok hariç), küçük farklar yok sayılır: animasyonlu özel kartlar."""
    ta, tb = (im.crop((72, 0, 480, im.height)).convert("L") for im in (a, b))
    fark = ImageChops.difference(ta, tb).point(lambda v: 255 if v > 60 else 0)
    return fark.histogram()[255] < 0.003 * ta.width * ta.height


def kadro(out):
    """Aktif kadro: saha, Subs ve Res panelleri (kart yazıları küçük: tam çözünürlükte kaydedilir)."""
    out.mkdir(exist_ok=True)
    one_getir(PENCERE)
    goruntu(KADRO, False).save(out / "saha.png")
    tik(*SUBS)
    time.sleep(1.5)
    goruntu(KADRO, False).save(out / "subs.png")
    tik(*SUBS_ACIK)
    time.sleep(1)
    tik(*RES)
    time.sleep(1.5)
    goruntu(KADRO, False).save(out / "res.png")
    print(f"kadro görüntüleri: {out}/ (saha, subs, res)")


def sbc_listesi(out):
    """SBC listesini yukarıdan aşağı kaydırarak çeker (tıklama yok); ardışık görüntüler ~1 sıra çakışır."""
    out.mkdir(exist_ok=True)
    one_getir(PENCERE)
    teker(-80, SBC_LISTE)
    onceki, k = None, 0
    while k < 60:
        im = goruntu(SBC_KUTU, False)
        if onceki is not None and ayni(im, onceki):  # liste sonu
            break
        im.save(out / f"sbc_{k:02d}.png")
        onceki, k = im, k + 1
        teker(7, SBC_LISTE)
    print(f"{k} görüntü: {out}/")


def benzer(a, b):
    """Tüm görüntü karşılaştırması (ayni() yalnızca oyuncu listesinin yazı sütununa bakar)."""
    fark = ImageChops.difference(a.convert("L"), b.convert("L")).point(lambda v: 255 if v > 60 else 0)
    return fark.histogram()[255] < 0.02 * a.width * a.height


def sbc_ic(klasor, hedefler):
    one_getir(PENCERE)
    for h in hedefler:
        k, x, y = (int(v) for v in h.split(":"))
        kayit = Image.open(klasor / f"sbc_{k:02d}.png")
        if not (0 <= x < kayit.width and 0 <= y < kayit.height):
            sys.exit(f"{h}: nokta sbc_{k:02d}.png dışında")
        teker(-80, SBC_LISTE)
        for _ in range(k):
            teker(7, SBC_LISTE)
        if not benzer(goruntu(SBC_KUTU, False), kayit):
            sys.exit(f"{h}: ekran sbc_{k:02d}.png ile aynı değil (liste değişmiş ya da yanlış sayfa), durdu")
        tik(SBC_KUTU[0] + x, SBC_KUTU[1] + y)
        time.sleep(3)
        if benzer(goruntu(SBC_KUTU, False), kayit):
            sys.exit(f"{h}: tıklama seti açmadı, durdu")
        goruntu(TAM, False).save(klasor / f"set_{k:02d}_{x}_{y}.png")
        tik(*GERI)
        time.sleep(3)
        teker(-80, SBC_LISTE)
        for _ in range(k):
            teker(7, SBC_LISTE)
        if not benzer(goruntu(SBC_KUTU, False), kayit):
            sys.exit(f"{h}: içi kaydedildi ama listeye dönülemedi (GERI koordinatı?), durdu")
        print(f"{h}: {klasor}/set_{k:02d}_{x}_{y}.png")


def main():
    if sys.argv[1:2] == ["sbc-ic"]:
        return sbc_ic(Path(sys.argv[2]), sys.argv[3:])
    if sys.argv[1:2] == ["sbc"]:
        return sbc_listesi(Path(sys.argv[2] if len(sys.argv) > 2 else "ekran_sbc"))
    if sys.argv[1:2] == ["kadro"]:
        return kadro(Path(sys.argv[2] if len(sys.argv) > 2 else "ekran_kadro"))
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "ekran")
    out.mkdir(exist_ok=True)
    one_getir(PENCERE)
    for _ in range(20):  # ilk sayfaya dön
        teker(60)
        a = goruntu()
        tik(*PREV)
        time.sleep(2.5)
        if ayni(a, goruntu()):
            break
    teker(-80)
    sayfa, k, onceki = 1, 0, None
    while sayfa < 40:
        im = goruntu()
        if onceki is not None and ayni(im, onceki):  # sayfa sonu
            tik(*NEXT)
            time.sleep(3)
            im = goruntu()
            if ayni(im, onceki):
                break
            sayfa, k = sayfa + 1, 0
        im.resize((im.width * 3 // 2, im.height * 3 // 2), Image.LANCZOS).save(out / f"p{sayfa:02d}_{k:02d}.png")
        onceki, k = im, k + 1
        teker(9)  # 6 satır: her görüntü öncekiyle 2 satır çakışır, arada oyuncu kaçmaz
    print(f"{sayfa} sayfa, görüntüler: {out}/")


if __name__ == "__main__":
    main()
