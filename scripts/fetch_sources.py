#!/usr/bin/env python3
"""Fetch pass 3 for Helene Dacosta pack. Runs on GitHub Actions runner."""
import glob
import json
import os
import re
import shutil
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

DBPF = b"DBPF"

def is_good(head, size):
    if size < 1000:
        return False
    if head[:1] == b"<":
        return False
    return True

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

def try_download(url, dest=None, headers=None, timeout=150):
    """Download to dest (extension auto-sniffed). Returns (ok, info, head, saved_path)."""
    try:
        r = SESSION.get(url, headers=headers, timeout=timeout, allow_redirects=True, stream=True)
        ct = r.headers.get("Content-Type", "")
        if r.status_code != 200:
            return False, f"HTTP {r.status_code} ct={ct} final={r.url}", b"", None
        base = dest if not os.path.splitext(dest)[1] else os.path.splitext(dest)[0]
        tmp = base + ".part"
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
        with open(tmp, "rb") as f:
            head = f.read(8)
        size = os.path.getsize(tmp)
        if not is_good(head, size):
            os.remove(tmp)
            return False, f"bad payload size={size} ct={ct} final={r.url}", head, None
        ext = sniff_ext(head, r.headers.get("Content-Disposition", ""))
        final_dest = base + ext
        os.replace(tmp, final_dest)
        return True, f"OK size={size} saved={os.path.basename(final_dest)} final={r.url}", head, final_dest
    except Exception as e:  # noqa
        return False, f"EXC {type(e).__name__}: {e}", b"", None

def clean_name(name):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")

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

def fetch_curseforge():
    log("\n===== CURSEFORGE =====")
    for idx, (prefix, name, fid, orig_name, slug) in enumerate(CF_ITEMS):
        dest = f"{OUT}/{prefix}_{name}"
        ok = False
        # A) direct media (tokenless, usually 403)
        a, b = fid // 1000, fid % 1000
        media_url = f"https://media.forgecdn.net/files/{a}/{b}/{urllib.parse.quote(orig_name)}"
        ok, info, _, saved = try_download(media_url, dest=dest,
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
        ok, info, _, saved = try_download(dl_url, dest=dest,
                                          headers={"Referer": f"https://www.curseforge.com/{slug}/"})
        log(f"-- CF {name}: endpoint {info}")
        if ok:
            continue
        # C) site API route: {base}/mods/{projectId}/files/{fileId}/download
        modid = get_modid(slug)
        if modid:
            api = f"https://www.curseforge.com/api/v1/mods/{modid}/files/{fid}/download"
            try:
                SESSION.get(f"https://www.curseforge.com/{slug}/download/{fid}", timeout=60)
                rr = SESSION.get(api, allow_redirects=False, timeout=60,
                                 headers={"Accept": "*/*",
                                          "Referer": f"https://www.curseforge.com/{slug}/download/{fid}"})
                log(f"-- CF {name}: api-download status={rr.status_code} ct={rr.headers.get('Content-Type')} loc={rr.headers.get('Location')}")
                if rr.status_code in (301, 302, 303, 307, 308) and rr.headers.get("Location"):
                    ok, info, _, saved = try_download(rr.headers["Location"], dest=dest,
                                                      headers={"Referer": api})
                    log(f"-- CF {name}: api redirect download {info}")
                elif rr.status_code == 200:
                    ct = rr.headers.get("Content-Type", "")
                    if "json" in ct:
                        try:
                            j = rr.json()
                            du = j.get("downloadUrl") or j.get("url") or (j.get("data") or {}).get("downloadUrl")
                            log(f"-- CF {name}: api json keys={list(j.keys()) if isinstance(j, dict) else type(j)} du={du}")
                            if du:
                                ok, info, _, saved = try_download(du, dest=dest)
                                log(f"-- CF {name}: api json download {info}")
                        except Exception as e:
                            log(f"-- CF {name}: api json parse err {e}")
                    elif not ct.startswith("text/html"):
                        # direct payload
                        tmp = dest + ".part"
                        with open(tmp, "wb") as f:
                            f.write(rr.content)
                        head = open(tmp, "rb").read(8)
                        if is_good(head, len(rr.content)):
                            ext = sniff_ext(head, rr.headers.get("Content-Disposition", ""))
                            os.replace(tmp, dest + ext)
                            log(f"-- CF {name}: api direct payload saved ({len(rr.content)} bytes)")
                            ok = True
                        else:
                            os.remove(tmp)
                            log(f"-- CF {name}: api direct payload bad")
            except Exception as e:
                log(f"-- CF {name}: api exc {type(e).__name__}: {e}")
        if ok:
            continue
        if idx == 0:
            cf_probe_deep(dl_url, fid)
    log("   (CF section done)")

def cf_probe_deep(dl_url, fid):
    """Collect intel to find the CurseForge signed download endpoint."""
    log("   === CF DEEP PROBE ===")
    try:
        SESSION.cookies.clear()
        r = SESSION.get(dl_url, timeout=60)
        body = r.text
        with open(f"{WORK}/cf_page.html", "w") as f:
            f.write(body)
        log(f"   page len={len(body)}")
        # build id
        m = re.search(r'"buildId"\s*:\s*"([^"]+)"', body)
        bid = m.group(1) if m else None
        log(f"   buildId={bid}")
        # Next.js data JSON
        if bid:
            data_url = dl_url.replace("https://www.curseforge.com", "") + ".json"
            full = f"https://www.curseforge.com/_next/data/{bid}{data_url}"
            try:
                rr = SESSION.get(full, timeout=60,
                                 headers={"Accept": "application/json"})
                log(f"   next-data {full[:120]} -> HTTP {rr.status_code} len={len(rr.content)}")
                if rr.status_code == 200:
                    try:
                        j = rr.json()
                        s = json.dumps(j)
                        with open(f"{WORK}/cf_nextdata.json", "w") as f:
                            f.write(s)
                        for kw in ("downloadUrl", "download_url", "signed", "expires"):
                            for mm in re.finditer(kw, s):
                                st = max(0, mm.start() - 60)
                                log(f"      [{kw}]: ...{s[st:mm.start()+160]}...")
                                break
                    except Exception as e:
                        log(f"   next-data parse err {e}")
            except Exception as e:
                log(f"   next-data exc {e}")
        # JS chunk scripts
        scripts = re.findall(r'<script src="([^"]+\.js)"', body)
        # filter app/main chunks
        cands = [s for s in scripts if "_next/static/chunks" in s][:14]
        log(f"   chunk scripts ({len(cands)} of {len(scripts)})")
        # keep the chunk that contains the DownloadFileContent logic for offline analysis
        for s in cands:
            try:
                c = SESSION.get(s, timeout=40).text
            except Exception:
                continue
            if "DownloadFileContent" in c or "buildFileDownloadUrl" in c:
                with open(f"{WORK}/cf_chunk_download.js", "w") as f:
                    f.write(f"// {s}\n" + c)
                log(f"   saved download chunk: {s} ({len(c)} bytes)")
                for kw in ("buildFileDownloadUrl", "DownloadFileContent"):
                    for mm in list(re.finditer(re.escape(kw), c))[:1]:
                        st = max(0, mm.start() - 200)
                        log(f"   js[{kw}] ctx: ...{c[st:mm.start()+900]}...".replace("\n", " "))
                break
    except Exception as e:
        log(f"   cf_probe_deep exc {e}")
    log("   === END CF DEEP PROBE ===")

# ================================================================ PATREON
PATREON_JOBS = [
    # (post id, prefixo, nome legivel, [(nome-arquivo regex, size esperado, idx candidatos)])
    ("64319245", "11", "NSW-LIPS-N35",
     [("LIPS N35", 3742201, [4, 3, 5, 2, 6])]),
    ("77031948", "07", "Belaloallure-phaedra-mini-skirt",
     [("phaedra_mini_skirt", 4170760, [2, 1, 3, 0, 4])]),
]

def fetch_patreon_public():
    log("\n===== PATREON PUBLIC ATTACHMENTS =====")
    # clean leftovers from previous runs
    for f in glob.glob(f"{WORK}/patreon_tmp_*"):
        os.remove(f)
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
            pairs = [(atts[i].get("file_name", ""), media_urls[i])
                     for i in range(min(len(atts), len(media_urls)))]
            for want_re, want_size, cands in wants:
                got = False
                order = cands or list(range(len(pairs)))
                tried = set()
                for i in order:
                    if i in tried or not (0 <= i < len(pairs)):
                        continue
                    tried.add(i)
                    fname, url = pairs[i]
                    if not re.search(want_re, fname, re.I):
                        continue
                    tmp = f"{WORK}/patreon_tmp_{pid}_{i}"
                    ok, info, _, saved = try_download(url, dest=tmp,
                                                      headers={"Referer": "https://www.patreon.com/"})
                    log(f"   [{label}] idx {i} ({fname}): {info}")
                    if not ok:
                        continue
                    size = os.path.getsize(saved)
                    if abs(size - want_size) > 50000:
                        log(f"   size mismatch (got {size}, want {want_size})")
                        os.remove(saved)
                        continue
                    final = f"{OUT}/{prefix}_{label}_{clean_name(fname)}"
                    os.replace(saved, final)
                    log(f"   => SAVED {final}")
                    got = True
                    break
                if not got:
                    log(f"   [{label}] FAILED (no candidate matched)")
        except Exception as e:
            log(f"-- PATREON {pid}: EXC {e}")

# ================================================================ SIMFILESHARE
def fetch_sfs(sfs_id, prefix, label):
    dest = f"{OUT}/{prefix}_{label}"
    try:
        SESSION.get(f"https://simfileshare.net/download/{sfs_id}/", timeout=60)
    except Exception:
        pass
    ok, info, _, saved = try_download(f"https://cdn.simfileshare.net/download/{sfs_id}/?dl",
                                      dest=dest,
                                      headers={"Referer": f"https://simfileshare.net/download/{sfs_id}/"})
    log(f"   SFS {sfs_id} ({label}): {info}")
    return ok

def fetch_sfs_folder():
    folder_id = "151649"
    want = re.compile(r"lips.*presets?\s*7f", re.I)
    log("\n===== SFS FOLDER obscurus 151649 =====")
    try:
        r = SESSION.get(f"https://simfileshare.net/folder/{folder_id}/", timeout=60)
        html = r.text
        entries = re.findall(r'href="(/download/\d+/)"[^>]*>(.*?)</a>', html, re.S)
        if not entries:
            for blk in re.split(r'<article|class="file', html):
                m1 = re.search(r'<a[^>]*href="(/download/\d+/)"', blk)
                m2 = re.search(r'<h[23][^>]*>.*?>\s*([^<]{3,80})', blk, re.S)
                if m1:
                    entries.append((m1.group(1), m2.group(1).strip() if m2 else "?"))
        log(f"   found {len(entries)} entries")
        for h, n in entries[:30]:
            log(f"     {h}  {n}")
        hits = [(h, n) for h, n in entries if want.search(n or "")]
        log(f"   name-matches: {len(hits)}")
        for h, n in hits:
            sid = re.search(r"/download/(\d+)/", h).group(1)
            log(f"   => match {h} {n}")
            fetch_sfs(sid, "12", f"obscurus-{clean_name(n)}")
        if not hits:
            log("   falling back to known id 2841763 (obscurus_lips_presets_7f.package)")
            fetch_sfs("2841763", "12", "obscurus-lips-presets-7f")
    except Exception as e:
        log(f"   SFS folder exc {e}")

# ================================================================ GOOGLE DRIVE
def gdrive_folder_list(folder_id):
    try:
        r = SESSION.get(f"https://drive.google.com/embeddedfolderview?id={folder_id}#list", timeout=60)
        html = r.text
        rows = re.findall(r'<a href="(https://drive\.google\.com/file/d/([^/"]+)/view[^"]*)"[^>]*>(.*?)</a>',
                          html, re.S)
        if not rows:
            log(f"   gdrive list failed; page len={len(html)} snippet={html[:300]}")
            return []
        out = []
        for url, fid, name in rows:
            name = re.sub(r"<[^>]+>", "", name).strip()
            out.append((fid, name))
        return out
    except Exception as e:
        log(f"   gdrive folder exc {e}")
        return []

def gdrive_download(fid, dest):
    url = f"https://drive.usercontent.google.com/download?id={fid}&export=download&confirm=t"
    ok, info, head, saved = try_download(url, dest=dest)
    if not ok:
        try:
            r = SESSION.get(f"https://drive.google.com/uc?id={fid}&export=download", timeout=60)
            m = re.search(r'name="confirm" value="([0-9A-Za-z_-]+)"', r.text)
            if m:
                ok, info, head, saved = try_download(
                    f"https://drive.google.com/uc?id={fid}&export=download&confirm={m.group(1)}", dest=dest)
        except Exception as e:
            log(f"   gdrive retry exc {e}")
    return ok, info, head, saved

def fetch_poyo_drive():
    log("\n===== GOOGLE DRIVE (poyo Heather Skin N7) =====")
    fid_folder = "1-gFVfhtikp1_OVZ96YuW9q8v2vIESD7l"
    items = gdrive_folder_list(fid_folder)
    log(f"   folder items ({len(items)}):")
    for fid, name in items:
        log(f"     {fid}  {name}")
    cand = [i for i in items if re.search(r"heather", i[1], re.I) and "overlay" not in i[1].lower()]
    chosen = cand[0] if cand else None
    if chosen:
        dest = f"{OUT}/06_poyo-{clean_name(chosen[1])}"
        ok, info, _, saved = gdrive_download(chosen[0], dest)
        log(f"   => downloading {chosen[1]} ok={ok} info={info} saved={saved}")
        if saved and os.path.exists(saved):
            log(f"   file size on disk: {os.path.getsize(saved)}")
        else:
            log("   WARNING: saved path missing on disk")
    else:
        log("   no heather skin candidate found (non-overlay)")

# ================================================================ EUNOSIMS
def fetch_eunosims():
    log("\n===== EUNOSIMS =====")
    try:
        r = SESSION.get("https://eunosims.tistory.com/entry/sims4cc-body-preset-1-5", timeout=60)
        m = re.search(r'(https://blog\.kakaocdn\.net/[^"\']+?knm=tfile\.package[^"\']*?)"', r.text)
        if not m:
            m = re.search(r'(https://blog\.kakaocdn\.net/[^"\']+?credential=[^"\']+?\.package[^"\']*?)"', r.text)
        if not m:
            log("   no .package kakaocdn link found")
            return
        link = m.group(1).replace("&amp;", "&")
        log(f"   link: {link[:150]}...")
        dest = f"{OUT}/15_eunosims-euno-Body-preset"
        ok, info, _, saved = try_download(link, dest=dest, timeout=200)
        log(f"   download: {info}")
    except Exception as e:
        log(f"   eunosims exc {e}")

# ================================================================ KIJIKO
def fetch_kijiko():
    if os.path.exists(f"{OUT}/14_Kijiko-Remove-EA-Lashes.zip"):
        log("\n===== KIJIKO: already present =====")
        return
    log("\n===== KIJIKO =====")
    try:
        SESSION.get("https://simfileshare.net/download/3247982/", timeout=60)
    except Exception:
        pass
    dest = f"{OUT}/14_Kijiko-Remove-EA-Lashes"
    ok, info, _, saved = try_download("https://cdn.simfileshare.net/download/3247982/?dl",
                                      dest=dest,
                                      headers={"Referer": "https://simfileshare.net/download/3247982/"})
    log(f"   {info}")

# ================================================================ main
SCRIPT_VERSION = "fetch-v4.1"
def main():
    try:
        import subprocess
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        head = "?"
    log(f"=== SCRIPT_VERSION={SCRIPT_VERSION} checkout_head={head[:12]} ===")
    fetch_kijiko()
    fetch_eunosims()
    fetch_curseforge()
    fetch_patreon_public()
    fetch_sfs(807916, "08", "GPME-Gold-C2-contour")
    fetch_sfs(472891, "09", "GPME-Gold-Eyes-G2")
    fetch_sfs(2759281, "13", "MagicBot-Default-Mouth")
    fetch_sfs_folder()
    if os.environ.get("FETCH_POYO") == "1":
        fetch_poyo_drive()
    else:
        log("\n===== GOOGLE DRIVE (poyo): SKIPPED (365MB file - needs decision) =====")
    with open(f"{WORK}/fetch_report.txt", "w") as f:
        f.write("\n".join(REPORT) + "\n")
    log("\n===== FINAL CCs DIR =====")
    for f in sorted(os.listdir(OUT)):
        log(f"   {f} ({os.path.getsize(os.path.join(OUT, f))} bytes)")
    log("\n===== FETCH 3 DONE =====")

if __name__ == "__main__":
    main()
