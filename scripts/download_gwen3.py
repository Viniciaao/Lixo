#!/usr/bin/env python3
"""Gwen round 3: CDX blog-prefix hunting, modco API guesses, goppolsme cc48 SFS."""
import json
import pathlib
import re
import sys
import time
import traceback

import requests

try:
    import cloudscraper
except ImportError:
    cloudscraper = None

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
HDRS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
OUT = pathlib.Path("downloads-gwen")
DEBUG = []

S = requests.Session()
S.headers.update(HDRS)
SCRAPER = cloudscraper.create_scraper() if cloudscraper else S
if cloudscraper:
    SCRAPER.headers.update(HDRS)


def say(m):
    print(f"[gwen3] {m}", flush=True)
    DEBUG.append(m)


def save_bytes(resp, folder, fallback):
    data = resp.content
    if not data or len(data) < 512:
        return None
    head = data[:4096].lstrip()
    if head.startswith(b"<") or b"<html" in head.lower():
        return None
    if "text/html" in resp.headers.get("Content-Type", "").lower():
        return None
    name = fallback
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?',
                  resp.headers.get("Content-Disposition", ""))
    if m:
        name = requests.utils.unquote(m.group(1))
    if not re.search(r"\.(zip|package|rar|7z)$", name, re.I):
        name += ".package"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(data)
    say(f"    saved {folder.name}/{name} ({len(data)/1024:.0f} KB)")
    return name


def cdx_prefix(prefix):
    try:
        r = S.get("http://web.archive.org/cdx/search/cdx?url=" + prefix
                  + "&matchType=prefix&output=text&fl=timestamp,original"
                  + "&collapse=urlkey&limit=800", timeout=120)
        rows = [x.split(" ", 1) for x in r.text.splitlines() if " " in x]
        say(f"cdx {prefix}: {len(rows)} urls")
        return rows
    except Exception as e:
        say(f"cdx {prefix} err {e}")
        return []


def harvest_patreon_snapshot(ts, orig, pid, folder, label):
    """Download snapshot; harvest attachment ids; fetch files."""
    try:
        r = S.get(f"https://web.archive.org/web/{ts}id_/{orig}", timeout=120)
        if r.status_code != 200:
            return False
        ids = set(re.findall(r'patreon\.com/file\?h=(\d+)&(?:amp;)?i=(\d+)', r.text))
        ext = [h for h in re.findall(r'href="(https?://[^"]+)"', r.text)
               if any(d in h for d in ("simfileshare", "mediafire", "drive.google",
                                       "dropbox", "boosty", "1drv", "box."))]
        say(f"  {ts} {orig[-45:]}: {len(ids)} ids, {len(ext)} ext links {ext[:3]}")
        got = False
        for h, i in sorted(ids)[:10]:
            try:
                rr = SCRAPER.get(f"https://www.patreon.com/file?h={h}&i={i}",
                                 allow_redirects=True, timeout=180)
                ct = rr.headers.get("Content-Type", "").lower()
                if rr.status_code == 200 and "html" not in ct and len(rr.content) > 512:
                    if save_bytes(rr, folder, f"patreon-{h}-{i}.package"):
                        got = True
            except Exception as e:
                say(f"    file err {e}")
        if got:
            return True
        for u in ext[:4]:
            try:
                rr = SCRAPER.get(u, timeout=180)
                if save_bytes(rr, folder, u.split("?")[0].split("/")[-1] or "ext.package"):
                    got = True
                    break
                # mediafire/sfs pages: resolve inner link
                m = re.search(r'href="(https://download\d+\.mediafire\.com/[^"]+)"', rr.text)
                m2 = re.search(r'href="((?:https://simfileshare\.net)?/download/\d+/)"', rr.text)
                target = m.group(1) if m else (
                    ("https://simfileshare.net" + m2.group(1)) if m2 and m2.group(1).startswith("/") else (m2.group(1) if m2 else None))
                if target:
                    rr2 = SCRAPER.get(target, timeout=300)
                    if save_bytes(rr2, folder, target.split("?")[0].split("/")[-1]):
                        got = True
                        break
            except Exception as e:
                say(f"    ext {u[:50]} err {e}")
        return got
    except Exception as e:
        say(f"  harvest {orig[-40:]} err {e}")
        return False


def hunt_blog(blog, pid, folder, label):
    if folder.exists() and any(folder.iterdir()):
        return
    for pat in (f"patreon.com/{blog}*", f"www.patreon.com/{blog}*"):
        rows = cdx_prefix(pat)
        cand = [(t, o) for t, o in rows if pid in o]
        say(f"  {blog} posts com {pid}: {len(cand)}")
        for t, o in cand[:5]:
            if harvest_patreon_snapshot(t, o, pid, folder, label):
                record_ok(label, o)
                return
        # sem post especifico: procurar paginas do blog com o pid em file ids
        for t, o in rows[:60]:
            if re.search(r'/posts/[a-z0-9-]+\d{6,}$', o):
                if harvest_patreon_snapshot(t, o, pid, folder, label):
                    record_ok(label, o)
                    return
        if folder.exists() and any(folder.iterdir()):
            return


def record_ok(label, src):
    pass


def goppolsme_cc48():
    folder = OUT / "patreon-31627231"
    if folder.exists() and any(folder.iterdir()):
        return
    # cc48 tem SFS/mediafire no post publico
    for variant in ("https://www.patreon.com/posts/gpme-gold-liner-63398471",
                    "https://www.patreon.com/posts/63398471"):
        rows = cdx_prefix("patreon.com/posts/gpme-gold-liner-63398471")
        if not rows:
            try:
                r = S.get("http://web.archive.org/web/2/" + variant, timeout=90)
                if r.status_code == 200:
                    ext = [h for h in re.findall(r'href="(https?://[^"]+)"', r.text)
                           if any(d in h for d in ("simfileshare", "mediafire", "dropbox"))]
                    say(f"cc48: {len(ext)} ext links {ext[:4]}")
                    for u in ext[:3]:
                        rr = SCRAPER.get(u, timeout=180)
                        if save_bytes(rr, folder, u.split("?")[0].split("/")[-1]):
                            return
                        m2 = re.search(r'href="((?:https://simfileshare\.net)?/download/\d+/)"', rr.text)
                        if m2:
                            t = m2.group(1)
                            t = t if t.startswith("http") else "https://simfileshare.net" + t
                            rr2 = SCRAPER.get(t, timeout=300)
                            if save_bytes(rr2, folder, t.split("?")[0].split("/")[-1]):
                                return
            except Exception as e:
                say(f"cc48 {variant[-30:]} err {e}")
        for t, o in rows[:4]:
            if harvest_patreon_snapshot(t, o, "63398471", folder, "GPME Gold Liner cc48"):
                return


def modco_api():
    folder = OUT / "rescue-bzip-eyes"
    # remove junk anterior
    for junk in folder.glob("sdk-loader*"):
        junk.unlink()
    if folder.exists() and any(folder.iterdir()):
        return
    guesses = [
        "https://www.modcollective.gg/api/creations/4695",
        "https://www.modcollective.gg/api/sims4/creations/4695",
        "https://api.modcollective.gg/creations/4695",
        "https://www.modcollective.gg/api/download/creation/4695",
        "https://www.modcollective.gg/api/files/creation/4695",
    ]
    for u in guesses:
        try:
            r = SCRAPER.get(u, timeout=60)
            say(f"modco api {u[-45:]}: {r.status_code} {r.headers.get('Content-Type','')[:24]}")
            if r.status_code != 200:
                continue
            if "json" in r.headers.get("Content-Type", ""):
                say("    json: " + r.text[:600])
                for m in re.findall(r'https?://[^"\s]+\.(?:zip|package|rar)', r.text)[:6]:
                    rr = SCRAPER.get(m, timeout=300)
                    if save_bytes(rr, folder, m.split("?")[0].split("/")[-1]):
                        return
        except Exception as e:
            say(f"  err {e}")


def main():
    say("== magicbot convert shoes ==")
    hunt_blog("magicbot", "23286338", OUT / "patreon-23286338", "Convert Shoes")

    say("== ddarkstonee lips-eyelids ==")
    hunt_blog("ddarkstonee", "31835588", OUT / "patreon-31835588", "Eyeshadow set")

    say("== SMSims peach friend ==")
    hunt_blog("SMSims", "141401392", OUT / "patreon-141401392", "Fullbody Peach Friend")

    say("== goppolsme cc48 (SFS publico) ==")
    goppolsme_cc48()

    say("== modco api guesses ==")
    modco_api()

    (OUT / "debug-gwen3.txt").write_text("\n".join(DEBUG), encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        (OUT / "debug-gwen3.txt").write_text("\n".join(DEBUG), encoding="utf-8")
        sys.exit(1)
