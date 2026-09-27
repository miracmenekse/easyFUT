"""Web App "My Club Players" listesinin ekran görüntülerini alır (sadece fare tekerleği + Next tıklaması, sayfaya
kod enjekte etmez). Görüntüleri Claude okuyup data/webapp_kulup.csv'ye yazar; sonra: .venv/bin/python futgg.py kulup

Önce: Firefox'ta Web App > Club > Players açık, yakınlaştırma %67 (Ctrl+- üç kez), ekran 1920x1200.
.venv/bin/python webapp_ekran.py ekran/        # görüntüler ekran/pSS_KK.png
Başka çözünürlükte KUTU / NEXT / PREV koordinatlarını bir ekran görüntüsüne bakarak güncelle.
"""
import sys, time
from pathlib import Path

from PIL import Image, ImageChops
from Xlib import X, display
from Xlib.ext import xtest
from Xlib.protocol import event

KUTU = (630, 300, 1190, 1095)  # oyuncu listesi paneli (Next satırı hariç)
NEXT, PREV = (1148, 1107), (666, 1107)
LISTE = (900, 700)  # tekerleğin çevrileceği nokta (liste üstü)
PENCERE = "FC Ultimate Team Web App"

d = display.Display()
root = d.screen().root


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


def teker(n):
    xtest.fake_input(d, X.MotionNotify, x=LISTE[0], y=LISTE[1])
    for _ in range(abs(n)):
        b = 5 if n > 0 else 4
        xtest.fake_input(d, X.ButtonPress, b)
        xtest.fake_input(d, X.ButtonRelease, b)
        d.sync()
        time.sleep(0.08)
    time.sleep(0.6)


def goruntu():
    g = root.get_geometry()
    raw = root.get_image(0, 0, g.width, g.height, X.ZPixmap, 0xffffffff)
    return Image.frombytes("RGB", (g.width, g.height), raw.data, "raw", "BGRX").crop(KUTU)


def ayni(a, b):
    """Sadece yazı sütunu (kart resmi ve ok hariç), küçük farklar yok sayılır: animasyonlu özel kartlar."""
    ta, tb = (im.crop((72, 0, 480, im.height)).convert("L") for im in (a, b))
    fark = ImageChops.difference(ta, tb).point(lambda v: 255 if v > 60 else 0)
    return fark.histogram()[255] < 0.003 * ta.width * ta.height


def main():
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
