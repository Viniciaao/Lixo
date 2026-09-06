#!/usr/bin/env python3
"""Fetch pass 2 for Helene Dacosta pack. Runs on GitHub Actions runner."""
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

DBPF = b"\x05\x73\x47\x50"  # TS4 .package magic (little endian DBPF 0x50534705)

def sniff_ext(head, cdisp=""):
    if head[:2] == b"PK":
        return ".zip"
    if head[:4] == DBPF:
        return ".package"
    m = re.search(r"filename=\"?([^\";]+)", cdisp or "")
    if m:
        ext = os.path.splitext(m.group(1))[1][:10]
        if ext:
            return ext
    return ".bin"

def is_good(head, size):
    if size < 1000:
        return False
    if head[:1] == b"<":
        return False
    return True

def try_download(url, dest=None, headers=None, timeout=120):
    """returns (ok, info, head_bytes)"""
    try:
        r = SESSION.get(url, headers=headers, timeout=timeout, allow_redirects=True, stream=True)
        ct = r.headers.get("Content-Type", "")
        if r.status_code != 200:
            return False, f"HTTP {r.status_code} ct={ct} final={r.url}", b""
        tmp = dest + ".part"
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
        with open(tmp, "rb") as f:
            head = f.read(8)
        size = os.path.getsize(tmp)
        if not is_good(head, size):
            os.remove(tmp)
            return False, f"bad payload size={size} ct={ct} final={r.url}", head
        ext = sniff_ext(head, r.headers.get("Content-Disposition", ""))
        if dest.endswith(".bin") or not os.path.splitext(dest)[1]:
            final_dest = dest + ext
        else:
            final_dest = dest
        os.replace(tmp, final_dest)
        return True, f"OK size={size} saved={os.path.basename(final_dest)} final={r.url}", head
    except Exception as e:  # noqa
        return False, f"EXC {type(e).__name__}: {e}", b""

# ================================================================ CURSEFORGE
CF_ITEMS = [
    ("01", "SIM-Helene-Dacosta", 8763744,
     "Anyulinela_Household_Dacosta_0x0026170a56100035.zip",
     "sims4/sims-households/helene-dacosta"),
    ("02", "EGGSIMS-earrings-19", 6496196,
     "[EGGSIMS] earrings 19_TS4.zip",
     "sims4/create-a-sim/eggsims-earrings-19"),
    ("03", "Sparkly-French-Nails", 8649348,
     "4w25_SparklyFrenchNails.zip",
     "sims4/create-a-sim/sparkly-french-nails"),
    ("04", "Shiny-Patent-Mary-Jane-Heels", 7751173,
     "[PolySphere]ShinyPatentMaryJaneHeels_NonAutoHeight.package.zip",
     "sims4/create-a-sim/shiny-patent-mary-jane-heels"),
    ("05", "Ava-Sweatshirt", 8177818,
     "Valentine_Top_Ava.zip",
     "sims4/create-a-sim/ava-sweatshirt"),
]

def fetch_curseforge(debug_only_first=True):
    log("\n===== CURSEFORGE =====")
    for idx, (prefix, name, fid, orig_name, slug) in enumerate(CF_ITEMS):
        dest = f"{OUT}/{prefix}_{name}.bin"
        ok = False
        # A) direct media (tokenless) - usually 403 but cheap to try
        a, b = fid // 1000, fid % 1000
        media_url = f"https://media.forgecdn.net/files/{a}/{b}/{urllib.parse.quote(orig_name)}"
        ok, info, _ = try_download(media_url, dest=dest,
                                   headers={"Referer": "https://www.curseforge.com/"})
        log(f"-- CF {name}: media {info if ok else info}")
        if ok:
            continue
        # B) download endpoint, two-pass
        dl_url = f"https://www.curseforge.com/{slug}/download/{fid}"
        try:
            SESSION.get(dl_url, timeout=60)
            time.sleep(2)
        except Exception:
            pass
        ok, info, _ = try_download(dl_url, dest=dest,
                                   headers={"Referer": f"https://www.curseforge.com/{slug}/"})
        log(f"-- CF {name}: endpoint {info}")
        if ok:
            continue
        # C) internal API download-url (needs modId)
        modid = get_modid(slug)
        if modid:
            api = f"https://www.curseforge.com/api/v1/mods/{modid}/files/{fid}/download-url"
            try:
                r = SESSION.get(api, timeout=40,
                                headers={"Accept": "application/json",
                                         "Referer": f"https://www.curseforge.com/{slug}/"})
                log(f"-- CF {name}: api-v1 status={r.status_code} body={r.text[:300]}")
                if r.status_code == 200:
                    try:
                        j = r.json()
                        data = j.get("data", [])
                        for d in (data if isinstance(data, list) else [data]):
                            du = (d or {}).get("downloadUrl")
                            if du:
                                ok, info, _ = try_download(du, dest=dest)
                                log(f"-- CF {name}: api download {info}")
                                break
                    except Exception as e:
                        log(f"-- CF {name}: api parse err {e}")
            except Exception as e:
                log(f"-- CF {name}: api exc {e}")
        if ok:
            continue
        # D) debug the interstitial (only first item)
        if debug_only_first and idx == 0:
            cf_debug(dl_url, slug, fid)

MODID_CACHE = {}
def get_modid(slug):
    if slug in MODID_CACHE:
        return MODID_CACHE[slug]
    mid = None
    try:
        r = SESSION.get(f"https://www.curseforge.com/{slug}", timeout=40)
        m = re.search(r'"projectId"\s*:\s*"?(\d+)"?', r.text)
        if not m:
            m = re.search(r'data-project-id="(\d+)"', r.text)
        if not m:
            m = re.search(r'"id":\s*(\d{4,8})', r.text[:5000])
        mid = m.group(1) if m else None
        if mid:
            log(f"   modid({slug}) = {mid}")
    except Exception as e:
        log(f"   get_modid exc {e}")
    # fallback: cfwidget
    if not mid:
        try:
            r = SESSION.get(f"https://api.cfwidget.com/{slug}", timeout=40)
            j = r.json()
            mid = str(j.get("id", "")) or None
            if mid:
                log(f"   modid via cfwidget({slug}) = {mid}")
        except Exception as e:
            log(f"   cfwidget exc {e}")
    MODID_CACHE[slug] = mid
    return mid

def cf_debug(dl_url, slug, fid):
    log("   === CF DEBUG ===")
    try:
        SESSION.cookies.clear()
        r1 = SESSION.get(dl_url, timeout=60)
        log(f"   pass1: status={r1.status_code} final={r1.url} len={len(r1.content)}")
        log(f"   pass1 cookies: {[c.name for c in SESSION.cookies]}")
        time.sleep(2)
        r2 = SESSION.get(dl_url, timeout=60)
        log(f"   pass2: status={r2.status_code} final={r2.url} ct={r2.headers.get('Content-Type')} len={len(r2.content)}")
        if r2.status_code == 200 and r2.headers.get("Content-Type", "").startswith("text/html"):
            body = r2.text
            for kw in ("8763744", "media.forgecdn", "edge.forgecdn", "downloadUrl",
                       "window.location", "token", "Seconds", "api/v1", "cf-chl"):
                for m in re.finditer(re.escape(kw), body):
                    s = max(0, m.start() - 120)
                    seg = body[s:m.start() + 220].replace("\n", " ")
                    log(f"   ...{kw}...: {seg[:330]}")
                    break  # only first occurrence each
    except Exception as e:
        log(f"   cf_debug exc {e}")
    log("   === END CF DEBUG ===")

# ================================================================ PATREON
PATREON_JOBS = [
    # (post id, prefixo, nome legivel, [(nome-alvo regex, size esperado, idx candidatos)])
    ("64319245", "11", "NSW-LIPS-N35",
     [("LIPS N35", 3742201, [3, 4, 5, 2, 6])]),
    ("77031948", "07", "Belaloallure-phaedra-mini-skirt",
     [("phaedra_mini_skirt", 4170760, [1, 2, 3, 0, 4])]),
]

def fetch_patreon_public():
    log("\n===== PATREON PUBLIC ATTACHMENTS =====")
    for pid, prefix, label, wants in PATREON_JOBS:
        try:
            r = SESSION.get(f"https://www.patreon.com/api/posts/{pid}",
                            headers={"Accept": "application/json, text/plain, */*"}, timeout=60)
            log(f"-- PATREON {pid} ({label}): HTTP {r.status_code}")
            if r.status_code != 200:
                continue
            d = r.json()
            with open(f"{WORK}/patreon/{pid}.json", "w") as f:
                json.dump(d, f)
            atts = d["data"]["attributes"].get("attachments_preview_metadata") or []
            media_urls = []
            for obj in d.get("included") or []:
                if obj.get("type") == "media":
                    u = obj.get("attributes", {}).get("download_url")
                    if u:
                        media_urls.append(u)
            # build idx->(name,url)
            pairs = [(atts[i].get("file_name", ""), media_urls[i])
                     for i in range(min(len(atts), len(media_urls)))]
            for want_re, want_size, cands in wants:
                chosen = None
                for i in cands:
                    if 0 <= i < len(pairs):
                        name, url = pairs[i]
                        chosen = (i, name, url)
                        break
                if not chosen:
                    log(f"   [{label}] no candidate idx available")
                    continue
                i, fname, url = chosen
                # match name regex first, then verify size after download
                tmp_dest = f"{WORK}/patreon_tmp_{pid}_{i}.bin"
                ok, info, _ = try_download(url, dest=tmp_dest,
                                           headers={"Referer": "https://www.patreon.com/"})
                log(f"   [{label}] try idx {i} ({fname}): {info}")
                size = os.path.getsize(tmp_dest) if os.path.exists(tmp_dest) else -1
                if not ok or abs(size - want_size) > 50000:
                    ok = False
                    log(f"   [{label}] size mismatch (got {size}, want {want_size}); trying more indices")
                    for j in [c for c in cands if c != i]:
                        if 0 <= j < len(pairs):
                            nm, u2 = pairs[j]
                            tmp2 = f"{WORK}/patreon_tmp_{pid}_{j}.bin"
                            ok2, info2, _ = try_download(u2, dest=tmp2,
                                                         headers={"Referer": "https://www.patreon.com/"})
                            log(f"      try idx {j} ({nm}): {info2}")
                            sz2 = os.path.getsize(tmp2) if os.path.exists(tmp2) else -1
                            if ok2 and abs(sz2 - want_size) <= 50000:
                                ok, tmp_dest, fname = ok2, tmp2, nm
                                break
                if ok:
                    base = re.sub(r'[^A-Za-z0-9._-]+', '_', fname).strip("_")
                    final = f"{OUT}/{prefix}_{label}_{base}.bin"
                    os.replace(tmp_dest, final)
                    log(f"   => SAVED {final}")
                else:
                    log(f"   [{label}] FAILED")
        except Exception as e:
            log(f"-- PATREON {pid}: EXC {e}")

# ================================================================ SIMFILESHARE
def fetch_sfs(sfs_id, prefix, label, name_filter=None):
    """Download a single file from SimFileShare."""
    dest = f"{OUT}/{prefix}_{label}.bin"
    try:
        SESSION.get(f"https://simfileshare.net/download/{sfs_id}/", timeout=60)
    except Exception:
        pass
    ok, info, _ = try_download(f"https://cdn.simfileshare.net/download/{sfs_id}/?dl",
                               dest=dest,
                               headers={"Referer": f"https://simfileshare.net/download/{sfs_id}/"})
    log(f"   SFS {sfs_id} ({label}): {info}")
    return ok

def fetch_sfs_folder():
    """List files of an SFS folder, download ones matching filter."""
    folder_id = "151649"
    want = re.compile(r"lips.{0,4}presets?\s*7f|7f|helga", re.I)
    log("\n===== SFS FOLDER obscurus 151649 =====")
    try:
        r = SESSION.get(f"https://simfileshare.net/folder/{folder_id}/", timeout=60)
        html = r.text
        # entries: look for download links with nearby names
        entries = re.findall(r'href="(/download/\d+/)"[^>]*>(.*?)</a>', html, re.S)
        # fallback pattern: blocks containing file name and a link
        if not entries:
            blocks = re.split(r'<article|class="file', html)
            for blk in blocks:
                m1 = re.search(r'<a[^>]*href="(/download/\d+/)"', blk)
                m2 = re.search(r'<h[23][^>]*>.*?>\s*([^<]{3,80})', blk, re.S)
                if m1:
                    name = m2.group(1).strip() if m2 else "?"
                    entries.append((m1.group(1), name))
        log(f"   found {len(entries)} entries")
        for href, name in entries[:80]:
            name = re.sub(r"\s+", " ", name).strip()
            log(f"     {href}  {name}")
        hits = [(h, n) for h, n in entries if want.search(n or "")]
        for href, name in hits:
            sid = re.search(r"/download/(\d+)/", href).group(1)
            label = re.sub(r"[^A-Za-z0-9._-]+", "_", name or sid).strip("_")[:60]
            log(f"   => downloading match: {href} {name}")
            fetch_sfs(sid, "12", f"obscurus-{label}")
    except Exception as e:
        log(f"   SFS folder exc {e}")

# ================================================================ GOOGLE DRIVE
def gdrive_folder_list(folder_id):
    """List public gdrive folder via embeddedfolderview."""
    try:
        r = SESSION.get(f"https://drive.google.com/embeddedfolderview?id={folder_id}#list",
                        timeout=60)
        html = r.text
        rows = re.findall(r'<a href="(https://drive\.google\.com/file/d/([^/"]+)/view[^"]*)"[^>]*>(.*?)</a>',
                          html, re.S)
        if not rows:
            log(f"   gdrive list failed; page len={len(html)}")
            log("   page snippet: " + html[:500].replace("\n", " "))
            return []
        out = []
        for url, fid, name in rows:
            name = re.sub(r"<[^>]+>", "", name)
            name = name.strip()
            out.append((fid, name))
        return out
    except Exception as e:
        log(f"   gdrive folder exc {e}")
        return []

def gdrive_download(fid, dest):
    """Download a public gdrive file by id (handles virus-scan confirm)."""
    url = f"https://drive.usercontent.google.com/download?id={fid}&export=download&confirm=t"
    ok, info, _ = try_download(url, dest=dest)
    if not ok:
        # second chance: classic drive host with confirm token
        try:
            r = SESSION.get(f"https://drive.google.com/uc?id={fid}&export=download", timeout=60)
            m = re.search(r'name="confirm" value="([0-9A-Za-z_-]+)"', r.text)
            if m:
                url2 = f"https://drive.google.com/uc?id={fid}&export=download&confirm={m.group(1)}"
                ok, info, _ = try_download(url2, dest=dest)
        except Exception as e:
            log(f"   gdrive retry exc {e}")
    return ok

def fetch_poyo_drive():
    log("\n===== GOOGLE DRIVE (poyo Heather Skin N7) =====")
    fid_folder = "1-gFVfhtikp1_OVZ96YuW9q8v2vIESD7l"
    items = gdrive_folder_list(fid_folder)
    log(f"   folder items ({len(items)}):")
    for fid, name in items:
        log(f"     {fid}  {name}")
    # choose: name mentioning heather (any skin file the sim needs is N7);
    # if several heather, prefer ones containing N7 / 7 / skin
    cand = [i for i in items if re.search(r"heather", i[1], re.I)]
    log(f"   heather candidates: {[n for _, n in cand]}")
    chosen = None
    if len(cand) == 1:
        chosen = cand[0]
    elif len(cand) > 1:
        for c in cand:
            if re.search(r"\bN7\b|\b7\b|skin.?7", c[1], re.I):
                chosen = c
                break
        if not chosen:
            chosen = cand[0]
    if chosen:
        base = re.sub(r"[^A-Za-z0-9._-]+", "_", chosen[1]).strip("_")
        dest = f"{OUT}/06_poyo-{base}.bin"
        ok = gdrive_download(chosen[0], dest)
        log(f"   => downloading {chosen[1]} -> {ok}")
    else:
        log("   no heather candidate found")

# ================================================================ EUNOSIMS
def fetch_eunosims():
    log("\n===== EUNOSIMS =====")
    try:
        r = SESSION.get("https://eunosims.tistory.com/entry/sims4cc-body-preset-1-5", timeout=60)
        # the .package download link on the entry page
        m = re.search(r'(https://blog\.kakaocdn\.net/[^"\']+?(?:preset|Body)[^"\']*?\.package[^"\']*?)"',
                      r.text, re.I)
        if not m:
            m = re.search(r'(https://blog\.kakaocdn\.net/[^"\']+?credential=[^"\']+?\.package[^"\']*?)"', r.text)
        if not m:
            log("   no .package kakaocdn link found")
            log("   candidates: " + "; ".join(re.findall(r'https://blog\.kakaocdn\.net/[^"\']{40,160}', r.text)[:5]))
            return
        link = m.group(1).replace("&amp;", "&")
        log(f"   link: {link[:150]}...")
        dest = f"{OUT}/15_eunosims-euno-Body-preset.bin"
        ok, info, _ = try_download(link, dest=dest, timeout=180)
        log(f"   download: {info}")
    except Exception as e:
        log(f"   eunosims exc {e}")

# ================================================================ KIJIKO
def fetch_kijiko():
    dest = f"{OUT}/14_Kijiko-Remove-EA-Lashes.bin"
    if os.path.exists("helene-dacosta-tudo-junto/CCs/14_Kijiko-Remove-EA-Lashes.zip"):
        log("\n===== KIJIKO: already present =====")
        return
    log("\n===== KIJIKO =====")
    try:
        SESSION.get("https://simfileshare.net/download/3247982/", timeout=60)
    except Exception:
        pass
    ok, info, _ = try_download("https://cdn.simfileshare.net/download/3247982/?dl",
                               dest=dest,
                               headers={"Referer": "https://simfileshare.net/download/3247982/"})
    log(f"   {info}")

# ================================================================ main
def main():
    fetch_kijiko()
    fetch_eunosims()
    fetch_curseforge()
    fetch_patreon_public()
    fetch_sfs(807916, "08", "GPME-Gold-C2-contour")
    fetch_sfs(472891, "09", "GPME-Gold-Eyes-G2")
    fetch_sfs(2759281, "13", "MagicBot-Default-Mouth")
    fetch_sfs_folder()
    fetch_poyo_drive()
    with open(f"{WORK}/fetch_report.txt", "w") as f:
        f.write("\n".join(REPORT) + "\n")
    log("\n===== FETCH 2 DONE =====")

if __name__ == "__main__":
    main()
