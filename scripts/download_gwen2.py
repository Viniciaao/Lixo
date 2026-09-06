#!/usr/bin/env python3
"""Gwen round 2: CDX-by-slug, ModCo direct pages, CurseForge official sets."""
import json
import pathlib
import re
import sys
import time
import traceback
import zipfile
from urllib.parse import quote

import requests

try:
    import cloudscraper
except ImportError:
    cloudscraper = None

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
HDRS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
OUT = pathlib.Path("downloads-gwen")
OUT.mkdir(exist_ok=True)
DEBUG = []

S = requests.Session()
S.headers.update(HDRS)
SCRAPER = cloudscraper.create_scraper() if cloudscraper else S
if cloudscraper:
    SCRAPER.headers.update(HDRS)


def say(m):
    print(f"[gwen2] {m}", flush=True)
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


def patreon_by_slug(slug_url, label, folder):
    """Wayback snapshot of a patreon post URL WITH slug; harvest attachment ids."""
    if folder.exists() and any(folder.iterdir()):
        return
    ids = set()
    for mode in ("", "id_"):
        try:
            r = S.get(f"https://web.archive.org/web/2{mode}/{slug_url}", timeout=90)
            if r.status_code != 200:
                say(f"wb {slug_url[-50:]}: {r.status_code}")
                continue
            pid_m = re.search(r"/posts/([a-z0-9-]*?)(\d{6,})(?:[/?#]|$)", slug_url)
            pid = pid_m.group(2) if pid_m else r"\d+"
            ids |= set(re.findall(r'patreon\.com/file\?h=(\d+)&(?:amp;)?i=(\d+)', r.text))
            say(f"wb {slug_url[-45:]}: {len(ids)} ids")
            break
        except Exception as e:
            say(f"wb {slug_url[-40:]} err {e}")
    for h, i in sorted(ids)[:16]:
        try:
            r = SCRAPER.get(f"https://www.patreon.com/file?h={h}&i={i}",
                            allow_redirects=True, timeout=120)
            ct = r.headers.get("Content-Type", "").lower()
            say(f"  file?h={h}&i={i} -> {r.status_code} {ct[:28]}")
            if r.status_code == 200 and "html" not in ct and len(r.content) > 512:
                save_bytes(r, folder, f"patreon-{h}-{i}.package")
        except Exception as e:
            say(f"  err {e}")


def modco_creation(url, folder, label):
    """ModCo creation page: find its file download link."""
    if folder.exists() and any(folder.iterdir()):
        return
    try:
        r = SCRAPER.get(url, timeout=90)
        say(f"modco {url}: {r.status_code}")
        if r.status_code != 200:
            return
        text = r.text
        # 1. any direct file host links
        for m in re.findall(r'https?://[^\s"\'<>]+\.(?:zip|package|rar)', text)[:5]:
            f = save_bytes(SCRAPER.get(m, timeout=180), folder, m.split("/")[-1])
            if f:
                return
        # 2. api/download-ish urls
        cands = set()
        cands |= set(re.findall(r'"(https?://[^"]*(?:api|download|files?|cdn)[^"]*)"', text))
        cands |= set(re.findall(r'href="(/[^"]*(?:download|api)[^"]*)"', text))
        say(f"  candidatos: {len(cands)}")
        for c in sorted(cands)[:12]:
            if any(x in c for x in ("logo", "icon", "favicon", "svg", "png", "css", "js?")):
                continue
            full = c if c.startswith("http") else "https://www.modcollective.gg" + c
            try:
                rr = SCRAPER.get(full, timeout=180)
                f = save_bytes(rr, folder, full.split("?")[0].split("/")[-1] or "modco.package")
                if f:
                    return
            except Exception as e:
                say(f"    {full[:70]} err {e}")
        # dump um pouco do html pra debug
        DEBUG.append("modco html sample: " + re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text))[:800])
    except Exception as e:
        say(f"modco {url} err {e}")


def cf_extract(slug, wanted_regex, dest, label):
    """Download a CurseForge project zip and extract matching .package files."""
    try:
        r = S.get(f"https://api.cfwidget.com/sims4/{slug}", timeout=60)
        if r.status_code != 200:
            say(f"cf {slug}: HTTP {r.status_code}")
            return
        files = sorted(r.json().get("files", []),
                       key=lambda f: f.get("uploaded_at") or "", reverse=True)
        if not files:
            return
        i = files[0]["id"]
        name = (files[0].get("name") or "").strip()
        tmp = pathlib.Path("/tmp/cf.zip")
        for cand in dict.fromkeys([name, name.replace(" ", "_")]):
            cdn = f"https://mediafilez.forgecdn.net/files/{i//1000}/{i%1000}/{cand}"
            rr = S.get(cdn, timeout=300)
            if rr.status_code == 200 and len(rr.content) > 10000 and \
                    rr.content[:2] == b"PK":
                tmp.write_bytes(rr.content)
                say(f"cf {slug}: baixou {cand} ({len(rr.content)/1e6:.0f} MB)")
                with zipfile.ZipFile(tmp) as z:
                    for n in z.namelist():
                        if re.search(wanted_regex, n, re.I):
                            data = z.read(n)
                            dest.mkdir(parents=True, exist_ok=True)
                            (dest / pathlib.Path(n).name).write_bytes(data)
                            say(f"    extraido {pathlib.Path(n).name} "
                                f"({len(data)/1024:.0f} KB)")
                tmp.unlink(missing_ok=True)
                return
        say(f"cf {slug}: nenhum cand baixou")
    except Exception as e:
        say(f"cf {slug} err {e}")


def main():
    say("== CDX/wayback por slug ==")
    for slug, label, fold in [
        ("https://www.patreon.com/posts/peach-friend-end-141401392",
         "Fullbody Peach Friend (SMSims)", OUT / "patreon-141401392"),
        ("https://www.patreon.com/posts/convert-shoes-23286338",
         "Convert Shoes (MadMan)", OUT / "patreon-23286338"),
        ("https://www.patreon.com/posts/lips-eyelids-set-31835588",
         "Eyeshadow set (ddarkstonee)", OUT / "patreon-31835588"),
        ("https://www.patreon.com/posts/gpme-gold-liner-31627231",
         "Eyeliner GPME Gold (goppolsme)", OUT / "patreon-31627231"),
    ]:
        patreon_by_slug(slug, label, fold)

    say("== ModCo bzip direto ==")
    for u, fold in [
        ("https://www.modcollective.gg/sims4/details/creation/4695",
         OUT / "rescue-bzip-eyes"),
        ("https://modcollective.gg/bg3/details/creation/4695",
         OUT / "rescue-bzip-eyes"),
        ("https://www.modcollective.gg/sims4/details/collection/627",
         OUT / "rescue-bzip-eyes"),
    ]:
        modco_creation(u, fold, "BZIP Eyes (RemusSirion)")
        if (OUT / "rescue-bzip-eyes").exists() and any((OUT / "rescue-bzip-eyes").iterdir()):
            break

    say("== CurseForge oficiais: extrair item exato ==")
    # Wild Cat: blush N7
    cf_extract("create-a-sim/wild-cat-make-up-and-genetics-collection",
               r"N7\.package|blush.*n7|wildcat.*blush",
               OUT / "cf-wildcat-blush", "Blush N7 Wild Cat (NSW)")
    # Gloss: lipstick n33
    cf_extract("create-a-sim/gloss-collection",
               r"N33\.package",
               OUT / "cf-gloss-lipstick", "Lipstick n33 (NSW)")

    (OUT / "debug-gwen2.txt").write_text("\n".join(DEBUG), encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        (OUT / "debug-gwen2.txt").write_text("\n".join(DEBUG), encoding="utf-8")
        sys.exit(1)
