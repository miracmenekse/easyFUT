#!/usr/bin/env python3
"""Tarayıcı arayüzü: .venv/bin/python ui.py -> http://127.0.0.1:8765 açılır. Sadece bu bilgisayardan erişilir."""
import csv, importlib, io, json, math, sys, threading, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
import fut

PORT = 8765
ROOT = fut.DATA.parent
CLUB_COLS = ["name", "rating", "position", "positions", "nation", "league", "club", "rarity", "tradeable", "duplicate",
             "locked", "price"]


_fut_mtime = [0]


def fresh():
    """fut.py / solver.py değiştiyse yeniden yükle: kod güncellemesi için sunucuyu yeniden başlatmak gerekmez."""
    m = max((ROOT / f).stat().st_mtime for f in ("fut.py", "solver.py"))
    if m != _fut_mtime[0]:
        if _fut_mtime[0]:
            importlib.reload(fut.solver)
            importlib.reload(fut)
        _fut_mtime[0] = m


def version():
    """Veri ya da arayüz değişince artar; sayfa bunu yoklayıp kendini yeniler."""
    files = [p for p in fut.DATA.rglob("*") if p.is_file()] + [ROOT / f for f in ("ui.html", "fut.py", "solver.py")]
    return max(p.stat().st_mtime for p in files)


def data_path(name):
    p = (fut.DATA / name).resolve()
    if fut.DATA.resolve() not in p.parents or p.suffix not in (".csv", ".json"):
        raise ValueError("geçersiz dosya")
    return p


def card_json(c):
    return {k: c.get(k) for k in CLUB_COLS + ["id", "source"]}


def state():
    return {"v": version(),  # sayfa bu sürümü geri gönderir: eski sayfanın üzerine yazmasını önler
            "club": [card_json(c) for c in fut.load_club()],
            "fodder": fut.load_fodder_prices(),
            "sbcs": fut.load_json_dir("sbcs"),
            "evos": fut.load_json_dir("evos"),
            "formations": list(fut.FORMATIONS)}


_plan_lock, _plan_cache = threading.Lock(), {}


def plan(budget, time_limit=20):
    """Aynı anda tek plan hesaplanır (paralel hesaplar işlemciyi bölüp sonucu kötüleştirir);
    veri ve bütçe değişmediyse önceki sonuç döner."""
    with _plan_lock:
        v = version()
        if _plan_cache.get("v") != v:  # veri değişti: bütün eski sonuçlar geçersiz
            _plan_cache.clear()
            _plan_cache["v"] = v
        key = (budget, time_limit)
        if key not in _plan_cache:
            _plan_cache[key] = _plan(budget, time_limit)
        return _plan_cache[key]


def _plan(budget, time_limit):
    p = fut.plan_max(fut.load_json_dir("sbcs"), fut.load_club(), fut.load_fodder_prices(), budget, time_limit)
    return {"total": p["total"], "spent": p["spent"], "status": p["status"],
            "done": [{"sbc": s, "spend": r["spend"], "used": r["used"], "net": r["net"], "rating": r["rating"],
                      "chem": r["chem"], "checks": r["checks"],
                      "formation": s.get("formation") or fut.DEFAULT_FORMATION,
                      "slots": [sl | {"card": card_json(sl["card"])} for sl in r["slots"]]}
                     for s, r in p["done"]],
            "skipped": p["skipped"]}


def evos():
    club = fut.load_club()
    return [{"evo": e, "players": [card_json(c) for c in sorted(club, key=lambda c: -c["rating"])
                                   if all(fut.matches(c, r) for r in e.get("requirements", []))]}
            for e in fut.load_json_dir("evos")]


def calc(buy, sell, profit):
    target = math.ceil((buy + profit) / (1 - fut.TAX))
    step = fut.price_step(target)
    target = math.ceil(target / step) * step
    return {"net": int(sell * (1 - fut.TAX)), "profit": int(sell * (1 - fut.TAX)) - buy,
            "list_at": target, "list_profit": int(target * (1 - fut.TAX)) - buy}


def save_club(rows):
    out = io.StringIO()
    w = csv.DictWriter(out, CLUB_COLS, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        if not str(r.get("name", "")).strip() or not str(r.get("rating", "")).strip().isdigit():
            raise ValueError(f"eksik isim veya reyting: {r}")
        w.writerow({**r, **{k: "evet" if r.get(k) in (True, "evet") else "hayır" for k in ("tradeable", "duplicate", "locked")},
                    "price": int(r.get("price") or 0)})
    (fut.DATA / "club.csv").write_text(out.getvalue(), encoding="utf-8")


class H(BaseHTTPRequestHandler):
    def send(self, body, ctype="application/json", code=200):
        b = (body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def route(self, method):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode("utf-8")
        try:
            fresh()
            if method == "GET" and u.path == "/api/version":
                return self.send({"v": version()})
            if method == "GET" and u.path == "/":
                return self.send((ROOT / "ui.html").read_text(encoding="utf-8"), "text/html")
            if method == "GET" and u.path == "/api/state":
                return self.send(state())
            if method == "GET" and u.path == "/api/plan":
                return self.send(plan(int(q.get("budget") or 0), int(q.get("time") or 20)))
            if method == "GET" and u.path == "/api/evos":
                return self.send(evos())
            if method == "GET" and u.path == "/api/calc":
                return self.send(calc(int(q["buy"]), int(q["sell"]), int(q["profit"])))
            if method == "POST" and u.path == "/api/club":
                if q.get("v") and abs(float(q["v"]) - version()) > 1e-6:
                    raise ValueError("veri bu sayfa açıldıktan sonra değişti, sayfa yenilendi")
                save_club(json.loads(body))
                return self.send({"ok": True})
            if u.path == "/api/file":
                p = data_path(q["name"])
                if method == "GET":
                    return self.send(p.read_text(encoding="utf-8"), "text/plain")
                if method == "DELETE":
                    p.unlink()
                    return self.send({"ok": True})
                if p.suffix == ".json":
                    json.loads(body)  # bozuk JSON kaydedilmesin
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(body, encoding="utf-8")
                return self.send({"ok": True})
            self.send({"error": "yok"}, code=404)
        except Exception as e:  # bozuk veri dosyası vb.: hatayı arayüzde göster
            self.send({"error": f"{type(e).__name__}: {e}"}, code=400)

    def do_GET(self): self.route("GET")
    def do_POST(self): self.route("POST")
    def do_DELETE(self): self.route("DELETE")
    def log_message(self, *a): pass


if __name__ == "__main__":
    url = f"http://127.0.0.1:{PORT}"
    webbrowser.open(url) if "--no-browser" not in sys.argv else None
    print(f"FUT Asistanı açık: {url}  (kapatmak için Ctrl+C)")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
