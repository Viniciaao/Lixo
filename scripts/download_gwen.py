#!/usr/bin/env python3
"""
Downloads the 'Gwen' household (CurseForge, by MizuTS4) + the required CC list.
Uses the tactics that worked for Lilith Cloud:
  - CurseForge CDN via cfwidget
  - Patreon public attachments via wayback-snapshots (file?h=..&i=..)
  - Boosty HTML fallback, ModCo search
Only NEW items (shared items with Lilith are already in the other zips).
"""
import json
import pathlib
import re
import sys
import time
import html
import traceback
from urllib.parse import urlparse, unquote

import requests

try:
    import cloudscraper
except ImportError:
    cloudscraper = None

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
HDRS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7"}

OUT = pathlib.Path("downloads-gwen")
OUT.mkdir(exist_ok=True)
MANIFEST = {"downloaded": [], "failed": [], "manual": []}
DEBUG = []

S = requests.Session()
S.headers.update(HDRS)
SCRAPER = cloudscraper.create_scraper() if cloudscraper else S
if cloudscraper:
    SCRAPER.headers.update(HDRS)


def log(m):
    print(f"[gwen] {m}", flush=True)


def say(m):
    print(f"[gwen] {m}", flush=True)
    DEBUG.append(m)


def record(kind, **kw):
    MANIFEST[kind].append(kw)


def ext_from_ct(ct, default=".bin"):
    return {"application/zip": ".zip", "application/x-zip-compressed": ".zip",
            "application/vnd.rar": ".rar", "application/x-rar-compressed": ".rar",
            "application/octet-stream": ".package"}.get(ct, default)


def save_response(resp, folder: pathlib.Path, fallback_name: str):
    data = resp.content
    if not data or len(data) < 512:
        return None
    head = data[:4096].lstrip()
    if head.startswith(b"<") or b"<html" in head.lower():
        return None
    if "text/html" in resp.headers.get("Content-Type", "").lower():
        return None
    fname = fallback_name
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?',
                  resp.headers.get("Content-Disposition", ""))
    if m:
        fname = unquote(m.group(1))
    if not re.search(r"\.(zip|package|rar|7z)$", fname, re.I):
        fname += ext_from_ct(resp.headers.get("Content-Type", ""))
    folder.mkdir(parents=True, exist_ok=True)
    (folder / fname).write_bytes(data)
    log(f"    saved {folder.name}/{fname} ({len(data)/1024:.0f} KB)")
    return fname


def fetch(url, session=None, **kw):
    kw.setdefault("timeout", 90)
    kw.setdefault("allow_redirects", True)
    return (session or S).get(url, **kw)


def _walk_urls(obj):
    if isinstance(obj, str):
        if obj.startswith("http"):
            yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_urls(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_urls(v)


# ---------------------------------------------------------------- household
def cf_household():
    label, folder = "gwen-household", OUT / "gwen-household"
    fid = 8625877  # from the install link
    names = ["Gwen.zip", "Gwen.zip.zip", "gwen.zip"]
    for cand in names:
        cdn = f"https://mediafilez.forgecdn.net/files/{fid//1000}/{fid%1000}/{cand}"
        try:
            r = fetch(cdn)
            if save_response(r, folder, cand):
                record("downloaded", item=label, source=cdn)
                return
        except Exception as e:
            log(f"  {cdn} err {e}")
    # cfwidget fallback (pega o nome real do arquivo)
    try:
        r = fetch("https://api.cfwidget.com/sims4/sims-households/gwen")
        files = sorted(r.json().get("files", []),
                       key=lambda f: f.get("uploaded_at") or "", reverse=True)
        for f in files:
            i, name = f["id"], (f.get("name") or "").strip()
            for cand in dict.fromkeys([name, name.replace(" ", "_"),
                                       re.sub(r"[^\w.\-]", "", name)]):
                if not cand:
                    continue
                cdn = f"https://mediafilez.forgecdn.net/files/{i//1000}/{i%1000}/{cand}"
                r2 = fetch(cdn)
                if save_response(r2, folder, cand):
                    record("downloaded", item=label, source=cdn)
                    return
    except Exception as e:
        log(f"  cfwidget err {e}")
    record("failed", item=label, reason="curseforge cdn")


# ----------------------------------------------- patreon via wayback attachments
def patreon_wayback(pid, label, folder):
    if folder.exists() and any(folder.iterdir()):
        return
    ids = set()
    for mode in ("", "id_"):
        for ts in ("2", "2024", "2023", "2022"):
            try:
                r = fetch(f"https://web.archive.org/web/{ts}{mode}/"
                          f"https://www.patreon.com/posts/{pid}", session=S)
                if r.status_code != 200:
                    continue
                ids |= set(re.findall(
                    r'patreon\.com/file\?h=' + str(pid) + r'&(?:amp;)?i=(\d+)', r.text))
                ids |= {("m" + m) for m in re.findall(
                    r'patreon\.com/file\?h=' + str(pid) + r'&(?:amp;)?m=(\d+)', r.text)}
                if ids:
                    break
            except Exception as e:
                say(f"wb {pid} err {e}")
        if ids:
            break
    say(f"patreon {pid} ({label}): {len(ids)} attachment ids")
    for a in sorted(ids)[:24]:
        u = (f"https://www.patreon.com/file?h={pid}&i={a}" if not a.startswith("m")
             else f"https://www.patreon.com/file?h={pid}&m={a[1:]}")
        try:
            r = fetch(u, session=SCRAPER, allow_redirects=True)
            ct = r.headers.get("Content-Type", "").lower()
            if r.status_code == 200 and "html" not in ct and len(r.content) > 512:
                if save_response(r, folder, f"patreon-{pid}-{a}.package"):
                    record("downloaded", item=f"{label} [{a}]", source=u)
        except Exception as e:
            say(f"  file {a} err {e}")


def patreon_cdx(pid, label, folder):
    if folder.exists() and any(folder.iterdir()):
        return
    try:
        r = fetch(f"http://web.archive.org/cdx/search/cdx?url=patreon.com/posts/{pid}"
                  "&output=text&fl=timestamp,original&limit=20", session=S)
        rows = [x.split() for x in r.text.splitlines() if x.strip()]
        say(f"cdx {pid}: {len(rows)} snapshots")
        for ts, orig in rows[:6]:
            rr = fetch(f"https://web.archive.org/web/{ts}id_/{orig}", session=S)
            if rr.status_code != 200:
                continue
            ids = set(re.findall(r'patreon\.com/file\?h=' + str(pid)
                                 + r'&(?:amp;)?i=(\d+)', rr.text))
            ids |= {("m" + m) for m in re.findall(
                r'patreon\.com/file\?h=' + str(pid) + r'&(?:amp;)?m=(\d+)', rr.text)}
            for a in sorted(ids)[:16]:
                u = (f"https://www.patreon.com/file?h={pid}&i={a}"
                     if not a.startswith("m")
                     else f"https://www.patreon.com/file?h={pid}&m={a[1:]}")
                try:
                    r3 = fetch(u, session=SCRAPER, allow_redirects=True)
                    ct = r3.headers.get("Content-Type", "").lower()
                    if r3.status_code == 200 and "html" not in ct and len(r3.content) > 512:
                        if save_response(r3, folder, f"patreon-{pid}-{a}.package"):
                            record("downloaded", item=f"{label} [{a}]", source=u)
                except Exception as e:
                    say(f"  err {e}")
    except Exception as e:
        say(f"cdx {pid} err {e}")


# ---------------------------------------------------------------- boosty html
def boosty_html(blog, kws, folder, label):
    if folder.exists() and any(folder.iterdir()):
        return
    try:
        r = fetch(f"https://boosty.to/{blog}", session=SCRAPER)
        say(f"boosty html {blog}: HTTP {r.status_code}")
        if r.status_code != 200:
            return
        urls = [u for u in _walk_urls(r.text)
                if any(x in u for x in ("files.boosty", "simfileshare",
                                        "mediafire", "drive.google", "dropbox"))]
        for u in urls[:8]:
            ok_file = save_response(fetch(u), folder, u.split("?")[0].split("/")[-1])
            if ok_file:
                record("downloaded", item=label, source=f"boosty.to/{blog}")
                return
        purls = re.findall(r'https://boosty\.to/' + re.escape(blog) + r'/posts/([a-z0-9\-]+)',
                           r.text)
        say(f"boosty {blog}: {len(purls)} posts")
        for slug in purls[:40]:
            if not any(k in slug.lower() for k in kws):
                continue
            r2 = fetch(f"https://boosty.to/{blog}/posts/{slug}", session=SCRAPER)
            u2 = [u for u in _walk_urls(r2.text)
                  if any(x in u for x in ("files.boosty", "simfileshare",
                                          "mediafire", "drive.google", "dropbox"))]
            for u in u2[:6]:
                ok_file = save_response(fetch(u, session=SCRAPER), folder,
                                        u.split("?")[0].split("/")[-1])
                if ok_file:
                    record("downloaded", item=label, source=f"boosty.to/{blog}/{slug}")
                    return
    except Exception as e:
        say(f"boosty {blog} err {e}")


# ---------------------------------------------------------------- modco (bzip)
def modco_bzip():
    folder = OUT / "rescue-bzip-eyes"
    if folder.exists() and any(folder.iterdir()):
        return
    for u in ("https://www.modcollective.gg/sims4/browse?search=bzip",
              "https://www.modcollective.gg/sims4/browse?search=eyes",
              "https://www.modcollective.gg/sims4/free-mods"):
        try:
            r = fetch(u, session=SCRAPER)
            say(f"modco {u[-40:]}: {r.status_code}")
            if r.status_code != 200:
                continue
            creates = [c for c in re.findall(r'href="(/sims4/details/[^"]+)"', r.text)
                       if "bzip" in c.lower() or "zip-eyes" in c.lower()
                       or "remus" in c.lower()]
            say(f"  criacoes: {creates[:6]}")
            for c in creates[:3]:
                r2 = fetch("https://www.modcollective.gg" + c, session=SCRAPER)
                if r2.status_code != 200:
                    continue
                for m in re.findall(r'"(https?://[^"]*(?:download|file)[^"]*)"', r2.text)[:8]:
                    f = save_response(fetch(m, session=SCRAPER), folder,
                                      m.split("?")[0].split("/")[-1])
                    if f:
                        record("downloaded", item="BZIP Eyes (RemusSirion)", source=m)
                        return
        except Exception as e:
            say(f"modco {u[-30:]} err {e}")


# ---------------------------------------------------------------- main
def main():
    log("== household ==")
    cf_household()

    posts = [
        (108144816, "Hair F-Hair No.9 (Hazeh)", OUT / "patreon-108144816"),
        (141401392, "Fullbody Peach Friend (SMSims)", OUT / "patreon-141401392"),
        (23286338, "Convert Shoes (MadMan/magicbot)", OUT / "patreon-23286338"),
        (61905018, "Lipstick n33 Gloss Collection (NSW)", OUT / "patreon-61905018"),
        (31835588, "Eyeshadow Lips+Eyelids set (ddarkstonee)", OUT / "patreon-31835588"),
        (31627231, "Eyeliner GPME Gold (goppolsme)", OUT / "patreon-31627231"),
        (64319245, "Blush Wild Cat (NSW)", OUT / "patreon-64319245"),
        (117517959, "Teeth Default Alpha (MADMAN)", OUT / "patreon-117517959"),
        (30029164, "Teeth alpha update 2020 (MADMAN)", OUT / "patreon-30029164"),
    ]
    log("== patreon posts ==")
    for pid, label, fold in posts:
        patreon_wayback(pid, label, fold)
        patreon_cdx(pid, label, fold)

    log("== boosty fallbacks ==")
    for blog, kws, label, fold in [
        ("northernsiberiawinds", ["gloss", "wild-cat", "wildcat"], "NSW lipstick/blush", OUT / "patreon-61905018"),
        ("ddarkstonee", ["eyelid", "lips", "set"], "ddarkstonee set", OUT / "patreon-31835588"),
        ("goppolsme", ["gold", "liner"], "goppolsme liner", OUT / "patreon-31627231"),
        ("hazeh", ["hair"], "Hazeh hair", OUT / "patreon-108144816"),
        ("smsims", ["peach"], "SMSims fullbody", OUT / "patreon-141401392"),
        ("magicbot", ["teeth", "shoes"], "MADMAN teeth/shoes", OUT / "patreon-117517959"),
    ]:
        boosty_html(blog, kws, fold, label)

    log("== modco bzip ==")
    modco_bzip()

    (OUT / "manifest.json").write_text(
        json.dumps(MANIFEST, indent=2, ensure_ascii=False))
    (OUT / "debug-gwen.txt").write_text("\n".join(DEBUG), encoding="utf-8")
    log(f"DONE dl={len(MANIFEST['downloaded'])} fail={len(MANIFEST['failed'])}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        (OUT / "manifest.json").write_text(
            json.dumps(MANIFEST, indent=2, ensure_ascii=False))
        sys.exit(1)
