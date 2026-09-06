#!/usr/bin/env python3
"""Fetch all obtainable CC sources for the Helene Dacosta sim pack.

Runs on a GitHub Actions runner (full internet). Saves files under
helene-dacosta-tudo-junto/ and writes a report to work/fetch_report.txt
"""
import json
import os
import re
import sys
import time
import urllib.parse

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

H = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

OUT = "helene-dacosta-tudo-junto/CCs"
WORK = "work"
os.makedirs(OUT, exist_ok=True)
os.makedirs(f"{WORK}/patreon", exist_ok=True)

REPORT = []
def log(msg):
    print(msg, flush=True)
    REPORT.append(msg)

SESSION = requests.Session()
SESSION.headers.update(H)

def looks_html(data, ct=""):
    return (data[:1] == b"<") or ("html" in ct)

def save_file(path, data):
    if not data:
        return False
    with open(path, "wb") as f:
        f.write(data)
    return True

def try_download(url, headers=None, timeout=90, stream_to=None, extra_notes=""):
    """Download url to stream_to (or return bytes). Returns (ok, info)."""
    try:
        r = SESSION.get(url, headers=headers, timeout=timeout, allow_redirects=True,
                        stream=True)
        ct = r.headers.get("Content-Type", "")
        if r.status_code != 200:
            return False, f"HTTP {r.status_code} ct={ct} final={r.url} {extra_notes}"
        if stream_to:
            with open(stream_to, "wb") as f:
                for chunk in r.iter_content(1 << 16):
                    f.write(chunk)
            size = os.path.getsize(stream_to)
            with open(stream_to, "rb") as f:
                head = f.read(4)
            if size < 100 or looks_html(head, ct):
                os.remove(stream_to)
                return False, f"bad payload size={size} ct={ct} final={r.url} {extra_notes}"
            return True, f"OK size={size} final={r.url} {extra_notes}"
        data = r.content
        if len(data) < 100 or looks_html(data[:4], ct):
            return False, f"bad payload size={len(data)} ct={ct} final={r.url} {extra_notes}"
        return data, f"OK size={len(data)} final={r.url} {extra_notes}"
    except Exception as e:  # noqa
        return False, f"EXC {type(e).__name__}: {e} {extra_notes}"

# ---------------------------------------------------------------- CurseForge
CF_ITEMS = [
    # (prefixo, nome arquivo, file id, filename original, classe)
    ("01", "SIM-Helene-Dacosta",
     8763744, "Anyulinela_Household_Dacosta_0x0026170a56100035.zip",
     "sims-households/helene-dacosta"),
    ("02", "EGGSIMS-earrings-19",
     6496196, "[EGGSIMS] earrings 19_TS4.zip",
     "create-a-sim/eggsims-earrings-19"),
    ("03", "Sparkly-French-Nails",
     8649348, "4w25_SparklyFrenchNails.zip",
     "create-a-sim/sparkly-french-nails"),
    ("04", "Shiny-Patent-Mary-Jane-Heels",
     7751173, "[PolySphere]ShinyPatentMaryJaneHeels_NonAutoHeight.package.zip",
     "create-a-sim/shiny-patent-mary-jane-heels"),
    ("05", "Ava-Sweatshirt",
     8177818, "Valentine_Top_Ava.zip",
     "create-a-sim/ava-sweatshirt"),
]

def fetch_curseforge():
    log("\n===== CURSEFORGE =====")
    for prefix, name, fid, orig_name, slug in CF_ITEMS:
        dest = f"{OUT}/{prefix}_{name}.zip"
        ok = False
        # Strategy 1: tokenless media.forgecdn.net URL
        a, b = fid // 1000, fid % 1000
        enc = urllib.parse.quote(orig_name)
        media_url = f"https://media.forgecdn.net/files/{a}/{b}/{enc}"
        log(f"-- CF {name}: trying media URL {media_url}")
        ok, info = try_download(media_url, stream_to=dest,
                                headers={"Referer": "https://www.curseforge.com/"})
        log(f"   media: {info}")
        if not ok:
            # Strategy 2: download endpoint, two passes with cookies
            dl_url = f"https://www.curseforge.com/{slug}/download/{fid}"
            try:
                SESSION.get(dl_url, timeout=60)  # warm up / get cookies
                time.sleep(2)
            except Exception:
                pass
            ok, info = try_download(dl_url, stream_to=dest,
                                    headers={"Referer": "https://www.curseforge.com/"})
            log(f"   endpoint: {info}")
        if ok:
            log(f"   => SAVED {dest}")

# ---------------------------------------------------------------- Patreon
PATREON_POSTS = [
    # (post id, label, arquivo alvo esperado)
    ("22436855", "GPME-Gold-C2-contour", "GPME Gold C2 (goppolsme)"),
    ("123193524", "NSW-3D-Eyelashes-N6", "3D Eyelashes N6 (NSW)"),
    ("17490207", "GPME-Gold-Eyes-G2", "GPME Gold Eyes (goppolsme)"),
    ("85159474", "Heather-Skin-N7", "Heather Skin N7 (poyopoyosim)"),
    ("77031948", "Belaloallure-phaedra-mini-skirt", "_phaedra_mini_skirt (Belaloallure)"),
    ("64319245", "NSW-LIPS-N35", "Wild Cat Make-up / LIPS N35 (NSW)"),
    ("59616486", "obscurus-helgatisha-lips-presets", "_lips_presets_7f (obscurus/helgatisha)"),
    ("56990147", "MagicBot-default-mouth", "Default Mouth (MagicBot)"),
]

def fetch_patreon_analysis():
    log("\n===== PATREON ANALYSIS =====")
    for pid, key, label in PATREON_POSTS:
        api = f"https://www.patreon.com/api/posts/{pid}"
        try:
            r = SESSION.get(api, headers={"Accept": "application/json, text/plain, */*"}, timeout=60)
            log(f"-- PATREON {key} ({label}): HTTP {r.status_code}")
            if r.status_code != 200:
                log(f"   body: {r.text[:200]}")
                continue
            data = r.json()
            with open(f"{WORK}/patreon/{pid}.json", "w") as f:
                json.dump(data, f, indent=1)
            attrs = data.get("data", {}).get("attributes", {})
            # content links
            content = attrs.get("content_json_string") or "{}"
            try:
                cj = json.loads(content)
                text = json.dumps(cj)
            except Exception:
                text = content or ""
            hrefs = re.findall(r'https?://[^\s"\\]+', text)
            hrefs = [h.rstrip('\\').rstrip('"') for h in hrefs]
            hrefs = [h for h in hrefs if "patreon.com" not in h or "/posts/" not in h or "patreonusercontent" in h]
            log(f"   hrefs[{len(hrefs)}]: {hrefs[:25]}")
            # attachment metadata
            atts = attrs.get("attachments_preview_metadata", []) or []
            log(f"   attachments[{len(atts)}]:")
            for a in atts:
                log(f"     - {a.get('file_name')} ({a.get('size_bytes')} bytes)")
            # included (public attachment urls etc.)
            inc = data.get("included", []) or []
            urls = []
            for obj in inc:
                at = obj.get("attributes", {})
                for k in ("url", "download_url", "display_url"):
                    v = at.get(k)
                    if v and isinstance(v, str) and v.startswith("http"):
                        urls.append((obj.get("type"), at.get("name", ""), k, v))
            log(f"   included[{len(inc)}] url-fields[{len(urls)}]:")
            for u in urls[:20]:
                log(f"     - {u}")
        except Exception as e:  # noqa
            log(f"-- PATREON {key}: EXC {type(e).__name__}: {e}")

# ---------------------------------------------------------------- Kijiko
def fetch_kijiko():
    log("\n===== KIJIKO (EA eyelashes remover) =====")
    dest = f"{OUT}/14_Kijiko-Remove-EA-Lashes.zip"
    # 1) SimFileShare direct
    try:
        SESSION.get("https://simfileshare.net/download/3247982/", timeout=60)
    except Exception:
        pass
    ok, info = try_download("https://cdn.simfileshare.net/download/3247982/?dl",
                            headers={"Referer": "https://simfileshare.net/download/3247982/"},
                            stream_to=dest)
    log(f"   SFS direct: {info}")
    if not ok:
        # 2) MediaFire v1.5 API
        try:
            r = SESSION.get("https://www.mediafire.com/api/1.5/file/get.php"
                            "?quick_key=tgp3kcs4iy2mnft&response_format=json", timeout=60)
            log(f"   MF api: HTTP {r.status_code} {r.text[:400]}")
            try:
                j = r.json()
                fi = j.get("response", {}).get("file_info", {})
                lnk = fi.get("links", {}).get("normal_download", "")
                log(f"   MF link: {lnk}")
                if lnk:
                    ok, info = try_download(lnk, stream_to=dest)
                    log(f"   MF download: {info}")
            except Exception as e:
                log(f"   MF parse exc {e}")
        except Exception as e:
            log(f"   MF api exc {e}")
    if ok:
        log(f"   => SAVED {dest}")

# ---------------------------------------------------------------- eunosims
def fetch_eunosims():
    log("\n===== EUNOSIMS (tistory body preset) =====")
    try:
        r = SESSION.get("https://eunosims.tistory.com/entry/sims4cc-body-preset-1-5", timeout=60)
        m = re.search(r'(https://blog\.kakaocdn\.net/[^"\']+?credential=[^"\']+)', r.text)
        if not m:
            log(f"   no kakaocdn link found; page size={len(r.text)}")
            return
        link = m.group(1).replace("&amp;", "&")
        log(f"   link: {link[:160]}...")
        dest = f"{OUT}/15_eunosims-euno-Body-preset.package"
        ok, info = try_download(link, stream_to=dest, timeout=120)
        log(f"   download: {info}")
        if ok:
            log(f"   => SAVED {dest}")
    except Exception as e:
        log(f"   EXC {type(e).__name__}: {e}")

# ---------------------------------------------------------------- main
def main():
    fetch_curseforge()
    fetch_patreon_analysis()
    fetch_kijiko()
    fetch_eunosims()
    with open(f"{WORK}/fetch_report.txt", "w") as f:
        f.write("\n".join(REPORT) + "\n")
    log("\n===== FETCH DONE =====")

if __name__ == "__main__":
    main()
