#!/usr/bin/env python3
"""Hratelny original v prohlizeci a ukladani stavu pro harness.

Bezobsluzna jizda harnessu se v RIVERu zablokuje (zavadeci originalu dojde
pamet, docs/GAPS.md), takze zony ICE, SCIFI a FINAL overit neumi. Tenhle
skript spusti original ve STEJNEM jadru vAmiga jako harness (web/hrat.html),
hrac dohraje, kam je potreba, a tlacitkem U ulozi stav. Snapshot jadra
harness nacte beze zmeny (`vacmp.nacti_stav`).

    python3 tools/hrat.py        # otevre prohlizec, stavy do build/vacmp/stavy/

Kickstart 1.3 a SWIVFIX.ADF bere stejne jako harness (tools/survey/vacmp.py).
Po uvodu se zapne MEGA TRAINER (nekonecne zivoty, zbrane) a zacne hra;
stranka navic umi drzet zivoty primo v pameti (slot +68).
"""
import datetime
import functools
import http.server
import json
import os
import socketserver
import sys
import webbrowser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools", "survey"))
import vacmp                                        # noqa: E402

STAVY = os.path.join(ROOT, "build", "vacmp", "stavy")


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def posli(self, data, typ="application/octet-stream"):
        self.send_response(200)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/rom":
            return self.posli(open(vacmp.ROM, "rb").read())
        if self.path == "/adf":
            return self.posli(open(vacmp.ADF, "rb").read())
        if self.path == "/prologue.js":
            return self.posli(("(" + vacmp.PLAY_PROLOGUE + ")").encode(),
                              "text/javascript")
        if self.path == "/info":
            return self.posli(json.dumps({"a6": vacmp.A6_BASE,
                                          "lives": vacmp.LIVES}).encode(),
                              "application/json")
        return super().do_GET()

    def do_POST(self):
        if not self.path.startswith("/ulozit"):
            self.send_error(404); return
        q = dict(kv.split("=", 1) for kv in self.path.split("?", 1)[1].split("&"))
        data = self.rfile.read(int(self.headers["Content-Length"]))
        os.makedirs(STAVY, exist_ok=True)
        cas = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        jmeno = f"{q.get('zona', 'X')}_{q.get('pos', '0')}_{cas}.vamiga"
        open(os.path.join(STAVY, jmeno), "wb").write(data)
        print(f"  ulozeno {jmeno} ({len(data) // 1024} kB)", flush=True)
        self.posli(jmeno.encode(), "text/plain")


def main():
    handler = functools.partial(Handler, directory=os.path.join(ROOT, "web"))
    srv = socketserver.TCPServer(("127.0.0.1", 0), handler)
    url = f"http://127.0.0.1:{srv.server_address[1]}/hrat.html"
    print(f"SWIV original: {url}\nstavy se ukladaji do {STAVY}\nkonec: Ctrl+C",
          flush=True)
    webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
