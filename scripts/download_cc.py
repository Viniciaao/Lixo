#!/usr/bin/env python3
"""
Downloads the 'Lilith Cloud' household (CurseForge) + every CC listed on its
description page, one by one, into ./downloads/

Run on GitHub Actions (unrestricted internet). Best-effort: items that are
login-gated (TSR / Patreon attachments) are recorded in manifest.json as 'manual'.
"""
import json
import pathlib
import re
import sys
import time
import html
import traceback
from urllib.parse import urlparse, parse_qs, unquote

import requests

try:
    import cloudscraper
except ImportError:
    cloudscraper = None

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
HDRS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7"}

OUT = pathlib.Path("downloads")
OUT.mkdir(exist_ok=True)

MANIFEST = {"downloaded": [], "failed": [], "manual": []}
WB_DEBUG = []

# hosts that actually serve files without login
GOOD_HOSTS = [
    "simfileshare.net", "mediafire.com", "drive.google.com",
    "drive.usercontent.google.com", "dropbox.com", "dl.dropboxusercontent.com",
    "cdn.discordapp.com", "onedrive.live.com", "1drv.ms", "box.com",
    "app.box.com", "mega.nz", "mediafilez.forgecdn.net", "edge.forgecdn.net",
    "gofile.io", "pixeldrain.com", "wetransfer.com", "sendspace.com",
    "github.com", "raw.githubusercontent.com", "objects.githubusercontent.com",
    "tumblr.com",  # sometimes direct static media
]


def log(msg):
    print(f"[dl] {msg}", flush=True)


def record(kind, **kw):
    MANIFEST[kind].append(kw)


def ext_from_ct(ct, default=".bin"):
    m = {"application/zip": ".zip", "application/x-zip-compressed": ".zip",
         "application/octet-stream": ".package", "application/x-rar-compressed": ".rar",
         "application/vnd.rar": ".rar"}
    return m.get(ct, default)


def save_response(resp, folder: pathlib.Path, fallback_name: str):
    """Save a binary response. Returns filename or None if it looks like HTML."""
    data = resp.content
    if not data or len(data) < 512:
        return None
    ct = resp.headers.get("Content-Type", "").lower()
    if "text/html" in ct and "package" not in fallback_name:
        return None
    fname = fallback_name
    cd = resp.headers.get("Content-Disposition", "")
    m = re.search(r'filename\*?="?([^";]+)"?', cd)
    if m:
        fname = unquote(m.group(1))
    if not re.search(r"\.(zip|package|rar|7z)$", fname, re.I):
        fname += ext_from_ct(ct)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / fname).write_bytes(data)
    log(f"    saved {folder.name}/{fname} ({len(data)/1024:.0f} KB)")
    return fname


def fetch(url, **kw):
    s = kw.pop("session", S)
    method = kw.pop("method", "GET")
    kw.setdefault("timeout", 90)
    kw.setdefault("allow_redirects", True)
    if method == "HEAD":
        return s.head(url, **kw)
    return s.get(url, **kw)


S = requests.Session()
S.headers.update(HDRS)
SCRAPER = cloudscraper.create_scraper() if cloudscraper else S
if cloudscraper:
    SCRAPER.headers.update(HDRS)


# ----------------------------------------------------------------------------
# host-specific downloaders: page/direct url -> (ok, saved_name)
# ----------------------------------------------------------------------------
def dl_sfs(url, folder):
    r = fetch(url)
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}"
    name = save_response(r, folder, url.rstrip("/").split("/")[-1] + ".package")
    return (name is not None), "ok" if name else "html response"


def dl_mediafire(url, folder):
    r = fetch(url)
    m = re.search(r'href="(https://download\d+\.mediafire\.com/[^"]+)"', r.text)
    if not m:
        m = re.search(r'href="(https://[a-z0-9-]+\.mediafire\.com/[^"]+)"', r.text)
    if not m:
        return False, "no direct link on mediafire page"
    r2 = fetch(m.group(1))
    if r2.status_code != 200:
        return False, f"HTTP {r2.status_code}"
    name = save_response(r2, folder, unquote(m.group(1).rstrip("/").split("/")[-1]))
    return (name is not None), "ok" if name else "html response"


def dl_gdrive(url, folder):
    m = (re.search(r"/file/d/([a-zA-Z0-9_-]+)", url)
         or re.search(r"[?&]id=([a-zA-Z0-9_-]+)", url))
    if not m:
        return False, "no drive file id"
    fid = m.group(1)
    dl_url = f"https://drive.usercontent.google.com/download?id={fid}&export=download"
    r = fetch(dl_url)
    if "text/html" in r.headers.get("Content-Type", "").lower():
        # virus-scan confirm page
        mm = re.search(r'name="confirm" value="([^"]+)"', r.text)
        uuid = re.search(r'name="uuid" value="([^"]+)"', r.text)
        if mm:
            form = {"id": fid, "export": "download", "confirm": mm.group(1)}
            if uuid:
                form["uuid"] = uuid.group(1)
            r = fetch(dl_url + "&confirm=" + mm.group(1)
                      + (("&uuid=" + uuid.group(1)) if uuid else ""))
        else:
            return False, "drive confirm page unresolved (private/limit?)"
    name = save_response(r, folder, fid + ".zip")
    return (name is not None), "ok" if name else "html response"


def dl_dropbox(url, folder):
    u = re.sub(r"([?&])dl=0", r"\1dl=1", url)
    if "dl=1" not in u:
        u += ("&" if "?" in u else "?") + "dl=1"
    u = u.replace("://www.dropbox.com", "://dl.dropboxusercontent.com")
    r = fetch(u)
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}"
    name = save_response(r, folder, unquote(u.split("?")[0].rstrip("/").split("/")[-1]))
    return (name is not None), "ok" if name else "html response"


def dl_generic(url, folder, referer=None):
    h = {"Referer": referer} if referer else {}
    r = fetch(url, headers=h)
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}"
    name = save_response(r, folder, unquote(url.split("?")[0].rstrip("/").split("/")[-1]))
    return (name is not None), "ok" if name else "html response"


def try_url(url, folder, referer=None):
    """Dispatch by host. Returns (success_bool, detail)."""
    try:
        host = urlparse(url).netloc.lower()
        if "simfileshare" in host:
            return dl_sfs(url, folder)
        if "mediafire" in host:
            return dl_mediafire(url, folder)
        if "drive.google" in host or "docs.google" in host or "drive.usercontent" in host:
            return dl_gdrive(url, folder)
        if "dropbox" in host:
            return dl_dropbox(url, folder)
        return dl_generic(url, folder, referer)
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


# ----------------------------------------------------------------------------
# page scrapers -> candidate file urls
# ----------------------------------------------------------------------------
def extract_links(text):
    links = set()
    for m in re.findall(r'href="(https?://[^"#]+)"', text):
        links.add(html.unescape(m))
    for m in re.findall(r'data-[a-z-]*url="(https?://[^"]+)"', text):
        links.add(html.unescape(m))
    for m in re.findall(r'https?://(?:www\.)?(?:simfileshare\.net|mediafire\.com|drive\.google\.com|dropbox\.com)[^\s"\'<>\\)\]]+', text):
        links.add(html.unescape(m))
    return links


def pick_candidates(links):
    """Sort links: file hosts first (skip creator's own patreon/tumblr pages)."""
    cands, extra_posts = [], []
    for u in links:
        hu = u.lower()
        if any(g in hu for g in GOOD_HOSTS) and "tumblr.com" not in hu:
            if "dropbox.com" in hu and "dl.dropboxusercontent" not in hu:
                pass  # handled by dl_dropbox
            cands.append(u)
        elif re.search(r"patreon\.com/(?:posts/|(?:\w+/)*posts/[^/?#]*?)(\d+)", hu):
            extra_posts.append(u)
    # prefer sfs/mediafire/direct, cap to 4
    prio = {"simfileshare": 0, "mediafire": 0, "cdn.discordapp": 0,
            "dropboxusercontent": 0, "dropbox.com": 1, "drive.google": 1,
            "drive.usercontent": 1, "forgecdn": 0}
    cands.sort(key=lambda u: next((p for k, p in prio.items() if k in u.lower()), 5))
    seen, uniq = set(), []
    for u in cands:
        base = u.split("?")[0]
        if base not in seen:
            seen.add(base)
            uniq.append(u)
    return uniq[:4], extra_posts[:2]


def scrape_page(url, folder, label, session=None):
    """Fetch an html page, try to download file links found on it."""
    try:
        r = fetch(url, session=session or S)
        if r.status_code != 200:
            return False, f"page HTTP {r.status_code}"
        links = extract_links(r.text)
        cands, extra_posts = pick_candidates(links)
        log(f"  {label}: {len(links)} links, {len(cands)} candidates, "
            f"{len(extra_posts)} patreon refs")
        for pid_url in extra_posts:
            pid = re.search(r"(\d{6,})(?:[/?#]|$)", pid_url)
            if pid:
                patreon_post(int(pid.group(1)), folder, label + "-ref")
        for u in cands:
            ok, info = try_url(u, folder, referer=url)
            log(f"    try {u[:90]} -> {info}")
            if ok:
                return True, f"got {u}"
        return False, "no downloadable link on page"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


# ----------------------------------------------------------------------------
# source-specific
# ----------------------------------------------------------------------------
def curseforge_household():
    label = "lilith-cloud-household"
    folder = OUT / label
    fid = 8737710
    urls = [
        f"https://www.curseforge.com/sims4/sims-households/lilith-cloud/download/{fid}",
        f"https://www.curseforge.com/sims4/sims-households/lilith-cloud/download",
    ]
    for u in urls:
        for sess in (SCRAPER, S):
            try:
                r = fetch(u, session=sess)
                log(f"  cf page {u[-40:]} via {'cloudscraper' if sess is not S else 'requests'}: {r.status_code}")
                if r.status_code != 200:
                    continue
                m = re.search(r'(https://(?:mediafilez|edge)\.forgecdn\.net/files/\d+/\d+/[^"\'<> ]+)', r.text)
                if m:
                    cdn = html.unescape(m.group(1))
                    r2 = fetch(cdn)
                    name = save_response(r2, folder, cdn.split("/")[-1])
                    if name:
                        record("downloaded", item=label, source=u, file=name)
                        return True
            except Exception as e:
                log(f"    err {type(e).__name__}: {e}")
    # fallback: cfwidget to learn filename, then CDN
    try:
        r = fetch("https://api.cfwidget.com/sims4/sims-households/lilith-cloud")
        data = r.json()
        files = sorted(data.get("files", []), key=lambda f: f.get("uploaded_at", ""), reverse=True)
        for f in files:
            name = f.get("name", "")
            i = f["id"]
            for cand in (name, re.sub(r"[^\w.\- ]", "", name)):
                cdn = f"https://mediafilez.forgecdn.net/files/{i//1000}/{i%1000}/{cand}"
                ok, info = try_url(cdn, folder)
                log(f"  cfwidget cdn {cdn[-50:]} -> {info}")
                if ok:
                    record("downloaded", item=label, source="cfwidget", file=str(cand))
                    return True
    except Exception as e:
        log(f"  cfwidget err {e}")
    record("failed", item=label, reason="curseforge blocked")
    return False


def tsr_item(item_id, folder, label, page_url):
    """TSR needs a login; try the known endpoints anyway, else manual."""
    for u in (f"https://www.thesimsresource.com/downloads/download/itemId/{item_id}",
              f"https://www.thesimsresource.com/ajax.php?c=downloads&a=getdownload&itemId={item_id}"):
        try:
            r = fetch(u)
            ct = r.headers.get("Content-Type", "")
            if r.status_code == 200 and "html" not in ct.lower():
                name = save_response(r, folder, f"tsr-{item_id}.package")
                if name:
                    record("downloaded", item=label, source=u, file=name)
                    return True
        except Exception as e:
            log(f"    tsr err {e}")
    record("manual", item=label, site="The Sims Resource (login exigido)", url=page_url)
    return False


def patreon_post(pid, folder, label):
    url = f"https://www.patreon.com/posts/{pid}"
    try:
        r = fetch(url)
        if r.status_code != 200:
            record("manual", item=label, site="Patreon (post indisponível p/ bots)",
                   url=url, status=r.status_code)
            return False
        links = extract_links(r.text)
        cands, _ = pick_candidates(links)
        log(f"  patreon {pid}: {len(cands)} candidatos")
        for u in cands:
            ok, info = try_url(u, folder, referer=url)
            log(f"    try {u[:90]} -> {info}")
            if ok:
                record("downloaded", item=label, source=url, file=u)
                return True
        # attachment download urls require auth — detect them for the record
        att = re.findall(r'"url":"(https://www\.patreon\.com/file\?h=\d+[^"]+)"', r.text)
        if att:
            record("manual", item=label, site="Patreon (anexo exige login)",
                   url=url, note=f"{len(att)} attachment(s) behind login")
            return False
        record("manual", item=label, site="Patreon (sem link externo público no post)",
               url=url)
        return False
    except Exception as e:
        record("manual", item=label, site="Patreon", url=url, error=str(e))
        return False


def tumblr_post(url, folder, label):
    ok, info = scrape_page(url, folder, label)
    if ok:
        record("downloaded", item=label, source=url)
    else:
        # patreon refs found on the tumblr page were already followed inside scrape_page;
        # if that produced nothing, mark manual with the original url
        if not (folder.exists() and any(folder.iterdir())):
            record("manual", item=label, site="Tumblr/Patreon", url=url, reason=info)
        else:
            record("downloaded", item=label, source=url, note="via patreon ref")
    return ok


# ----------------------------------------------------------------------------
# the full CC list from the project description
# ----------------------------------------------------------------------------
CC = []  # (kind, slug, kind_of_source, args)


def add(label, fn, *args):
    CC.append((label, fn, args))


def main():
    log("== Lilith Cloud household ==")
    curseforge_household()

    log("== TSR items (login-gated, will be listed as manual) ==")
    tsr = [
        ("MoleFace / ddarkstonee Contour N4", 1500395,
         "https://www.thesimsresource.com/themes/halloween/downloads/details/category/sims4-makeup-female-skindetails/title/contour-n4/id/1500395/"),
        ("UpperBody / LMC's Ladida Top (Lisaminicatsims)", 1507735,
         "https://www.thesimsresource.com/downloads/details/category/sims4/title/lmcs-ladida-top/id/1507735/"),
        ("Shoes / Madlen Mia Boots Retexture (RemusSirion)", 1415870,
         "https://www.thesimsresource.com/downloads/details/category/sims4-shoes-female-teenadultelder/title/madlen-mia-boots-retexture-mesh-needed/id/1415870/"),
        ("SkinDetailMoleCheekLeft / RemusSirion Nose Mask 04", 1581487,
         "https://www.thesimsresource.com/members/RemusSirion/downloads/details/category/sims4-makeup-female-skindetails/title/nose-mask-04-full-coverage-update-for-sim-creators/id/1581487/"),
        ("Freckles / alf-si Soft Face Freckles HQ", 1355997,
         "https://www.thesimsresource.com/downloads/details/category/sims4-makeup-female-skindetails/title/soft-face-freckles-hq/id/1355997/"),
        ("Eyelashes / venerian Tea Time Lashes HQ", 1770164,
         "https://www.thesimsresource.com/downloads/details/category/sims4/title/venerian-tea-time-lashes-hq/id/1770164/"),
    ]
    for label, iid, url in tsr:
        log(f"  {label}")
        tsr_item(iid, OUT / f"tsr-{iid}", label, url)

    log("== Tumblr posts (usually link to SFS/Dropbox/Drive) ==")
    tumblr = [
        ("Bodycare Kit (Northern Siberia Winds) - stretchmarks + torso mask",
         "https://northernsiberiawinds.tumblr.com/post/734744726011576320/bodycare-kit"),
        ("BZIP Eyes Set (RemusSirion)",
         "https://remussirion.tumblr.com/post/766701696234684416/bzip-eyes-set-ts4"),
        ("Calluna skinblend (NESURII)",
         "https://nesurii.tumblr.com/post/623283055124217856/calluna-a-non-default-skinblend-a-face-only"),
        ("Saya eye reflections detail (SayaSims)",
         "https://sayasims.tumblr.com/post/183470649946/saya-eye-reflections-detail-22-swatches-female"),
        ("Arm & Hand Jewellery (Pralinesims)",
         "https://pralinesims.net/post/188285457999/arm-hand-jewellery-ultimate-collection"),
        ("MON makeup set (catplnt)",
         "https://catplnt.tumblr.com/post/164406141686/mon-makeup-set-bc-i-made-everyone-wait-9-years-and"),
        ("Eyebrows 33-41 (alf-si)",
         "https://alf-si.tumblr.com/post/614674051815849984/ts4-eyebrows-33-41-download-33-34-35-36-37-38-39"),
        ("Nosemask N10 (obscurus)",
         "https://obscurus-sims.tumblr.com/post/184629124468/nosemask-n10-70-colors-all-ages-all-genders"),
        ("Spotlight Tattoos (Simandy/SimMandy)",
         "https://simandy.tumblr.com/post/630272666330415104/because-every-time-i-look-at-photoshop-i-want-to"),
    ]
    for label, url in tumblr:
        log(f"  {label}")
        tumblr_post(url, OUT / re.sub(r"[^\w-]", "", label)[:60], label)

    log("== Patreon posts (public body may contain external links) ==")
    patreon = [
        ("Amaranth set lower body (148DAZED)", 117097930),
        ("Acne (miikocc)", 72457009),
        ("Misc face details (okruee)", 71370172),
        ("Lighting overlay (Jo_se_oh)", 94005453),
        ("3D eyelashes set (obscurus)", 93851178),
        ("Cleavage masks 3 (sims3melancholic)", 96600228),
        ("Because every time... tattoos (Simandy)", 42027501),
        ("Feet 1V remaster (magicbot/MB)", 92135508),
    ]
    for label, pid in patreon:
        log(f"  {label} [{pid}]")
        patreon_post(pid, OUT / f"patreon-{pid}", label)

    log("== Creator pages without direct post (manual) ==")
    for label, url in [
        ("Eyebrows (YUNSEOL) - poste especifico nao informado", "https://www.patreon.com/yunseol"),
        ("Moles (LutessaSims) - poste especifico nao informado", "https://www.patreon.com/lutessasims"),
        ("Realistic female body details (Mikooi Sims)", "https://www.patreon.com/MikooiSims"),
    ]:
        record("manual", item=label, site="Patreon (pagina da criadora)", url=url)

    # ------------------------------------------------------------------
    # RESCUE PHASE round 2: cloudscraper-patreon, wayback, boosty, NSW site
    # ------------------------------------------------------------------
    log("== RESCUE: patreon via cloudscraper ==")
    for pid, label, folder in PATREON_RETRY:
        patreon_cloudscraper(pid, folder, label)

    log("== RESCUE: wayback for patreon posts ==")
    for pid, label, folder in PATREON_RETRY:
        wayback_extract(f"https://www.patreon.com/posts/{pid}", folder, f"{label}-wayback")

    log("== RESCUE: wayback for tumblr posts ==")
    for url, label, folder in TUMBLR_RETRY:
        wayback_extract(url, folder, f"{label}-wayback")

    log("== RESCUE: boosty mirrors ==")
    for blog, keywords, label, folder in BOOSTY_HUNTS:
        boosty_hunt(blog, keywords, folder, label)

    log("== RESCUE: NSW official website ==")
    nsw_site("Bodycare Kit (NSW)", OUT / "rescue-nsw-bodycare")

    log("== RESCUE round 3 ==")
    rescue_round3()


def rescue_round3():
    dbg = OUT / "debug-rescue3.txt"
    lines = []

    def say(s):
        print(f"[r3] {s}", flush=True)
        lines.append(s)

    # ---- 1. explicit SFS link: Simandy Spotlight merged
    fold = OUT / "patreon-42027501"
    if not (fold.exists() and any(fold.iterdir())):
        ok, info = try_url("https://simfileshare.net/download/4346575/", fold)
        say(f"simandy spotlight sfs -> {info}")
        if ok:
            record("downloaded", item="Spotlight tattoos (Simandy)", source="sfs/4346575")

    # ---- 2. CurseForge projects via cfwidget + CDN
    def cf_project(slug, label, fold):
        if fold.exists() and any(fold.iterdir()):
            return
        try:
            r = fetch(f"https://api.cfwidget.com/sims4/{slug}", session=S)
            if r.status_code != 200:
                say(f"cf {slug}: widget HTTP {r.status_code}")
                return
            data = r.json()
            files = sorted(data.get("files", []),
                           key=lambda f: f.get("uploaded_at") or "", reverse=True)
            for f in files[:1]:
                i, name = f["id"], (f.get("name") or "").strip()
                variants = [name, name.replace(" ", "_"), name.replace(" ", "%20"),
                            re.sub(r"[^\w.\-]", "", name)]
                for cand in dict.fromkeys(v for v in variants if v):
                    cdn = f"https://mediafilez.forgecdn.net/files/{i//1000}/{i%1000}/{cand}"
                    ok, info = try_url(cdn, fold)
                    say(f"cf {slug} file {i} '{cand}' -> {info}")
                    if ok:
                        record("downloaded", item=label, source=f"curseforge:{slug}")
                        return
        except Exception as e:
            say(f"cf {slug} err {e}")

    cf_project("create-a-sim/amaranth-top", "Amaranth TOP (148DAZED)", OUT / "patreon-117097930-top")
    cf_project("create-a-sim/amaranth-skirt", "Amaranth SKIRT (148DAZED)", OUT / "patreon-117097930-skirt")
    cf_project("create-a-sim/amaranth-set", "Amaranth SET (148DAZED)", OUT / "patreon-117097930-set")
    cf_project("create-a-sim/lighting-overlay-2-0", "Lighting overlay (Jo_se_oh)", OUT / "patreon-94005453")
    cf_project("create-a-sim/moles-01", "Moles 01 (LutessaSims)", OUT / "rescue-lutessa-moles")

    # ---- 3. SFS folder crawler (creator archive folders), v2: navigate by name
    def sfs_fetch(folder_id, tries=3):
        for a in range(tries):
            try:
                r = fetch(f"https://simfileshare.net/folder/{folder_id}/", session=S)
                if r.status_code == 200:
                    return r
                say(f"sfs folder {folder_id}: HTTP {r.status_code} (tentativa {a+1})")
            except Exception as e:
                say(f"sfs folder {folder_id} err {e}")
            time.sleep(8)
        return None

    def sfs_folder(folder_id, out, keywords, seen=None, max_files=3, depth=0):
        seen = seen if seen is not None else set()
        if folder_id in seen or len(seen) > 25:
            return
        seen.add(folder_id)
        r = sfs_fetch(folder_id)
        if r is None:
            return
        items = re.findall(
            r'href="((?:https://simfileshare\.net)?/download/(\d+)/)"[^>]*>([^<]+)<',
            r.text)
        items = [(f"https://simfileshare.net/download/{i}/", n) for _, i, n in items]
        subs = re.findall(
            r'href="(?:https://simfileshare\.net)?/folder/(\d+)/">([^<]+)<', r.text)
        say(f"sfs folder {folder_id}: {len(items)} arquivos, {len(subs)} subpastas")
        hits = 0
        for u, fname in items:
            if hits >= max_files:
                break
            if any(k in fname.lower() for k in keywords):
                ok, info = try_url(u, out, referer="https://simfileshare.net/")
                say(f"  {fname} -> {info}")
                if ok:
                    hits += 1
        if hits:
            return
        # sub-pastas cujo nome combine com o alvo
        wanted = re.compile("|".join(keywords), re.I)
        named = [(fid, name) for fid, name in subs if wanted.search(name)]
        for fid, name in named[:4]:
            say(f"  entrando na subpasta '{name}'")
            sfs_folder(fid, out, keywords, seen, max_files, depth + 1)
            if out.exists() and any(out.iterdir()):
                return

    sfs_folder(60606, OUT / "rescue-okruee-miscface", ["okruee", "misc"])   # arquivo gigante por criador
    sfs_folder(60606, OUT / "rescue-obscurus-3dlash", ["obscurus"])
    sfs_folder(60606, OUT / "rescue-miikocc-acne", ["miikocc", "miiko"])
    sfs_folder(84952, OUT / "rescue-obscurus-3dlash", ["3d", "eyelash"])
    sfs_folder(190204, OUT / "rescue-miikocc-acne", ["acne"])
    sfs_folder(61005, OUT / "rescue-obscurus-3dlash", ["3d_eyelash", "eyelash"])

    # ---- 4. Madlen Mia Boots retexture: original tumblr post has SFS link
    fold = OUT / "rescue-madlen-boots"
    if not (fold.exists() and any(fold.iterdir())):
        ok, info = scrape_page(
            "https://remussirion.tumblr.com/post/174331197269/madlen-mia-boots-retexture-ts4-download-this",
            fold, "Madlen Mia Boots Retexture (RemusSirion)")
        say(f"madlen boots post -> {info}")
        if ok:
            record("downloaded", item="Madlen Mia Boots Retexture", source="remussirion tumblr")
        else:
            wayback_extract("https://remussirion.tumblr.com/post/174331197269/"
                            "madlen-mia-boots-retexture-ts4-download-this",
                            fold, "Madlen Mia Boots Retexture")

    # ---- 5. Wayback CDX: NSW website bodycare + remussirion patreon bzip
    def cdx_urls(pattern):
        try:
            r = fetch("http://web.archive.org/cdx/search/cdx?url=" + pattern
                      + "&matchType=prefix&output=text&fl=original&collapse=urlkey"
                      + "&limit=500", session=S)
            out = [u.strip() for u in r.text.splitlines() if u.strip()]
            say(f"cdx {pattern[:40]}: {len(out)} urls")
            return out
        except Exception as e:
            say(f"cdx {pattern} err {e}")
            return []

    fold = OUT / "rescue-nsw-bodycare"
    if not (fold.exists() and any(fold.iterdir())):
        urls = [u for u in cdx_urls("northernsiberiawinds.com*") if "bodycare" in u.lower()]
        say(f"nsw cdx bodycare pages: {urls[:5]}")
        for u in urls[:4]:
            wayback_extract(u, fold, "Bodycare Kit (NSW)")
            if fold.exists() and any(fold.iterdir()):
                break

    fold = OUT / "rescue-remussirion-bzip"
    if not (fold.exists() and any(fold.iterdir())):
        urls = [u for u in cdx_urls("patreon.com/remussirion*") if "bzip" in u.lower() or "eyes" in u.lower()]
        urls += [u for u in cdx_urls("remussirion.tumblr.com*") if "bzip" in u.lower()]
        say(f"remussirion bzip cdx: {urls[:5]}")
        for u in urls[:4]:
            wayback_extract(u, fold, "BZIP Eyes (RemusSirion)")
            if fold.exists() and any(fold.iterdir()):
                break

    # ---- 6. boosty debug dump + broader keyword hunt (429 backoff-aware)
    def boosty_posts(blog, attempts=3):
        for a in range(attempts):
            try:
                r = fetch(f"https://boosty.to/api/v1/blog/{blog}/posts?posts_count=300",
                          session=S)
                say(f"boosty {blog}: HTTP {r.status_code} (tentativa {a+1})")
                if r.status_code == 200:
                    return r.json().get("data", [])
                if r.status_code == 429:
                    time.sleep(50 * (a + 1))
                    continue
                return []
            except Exception as e:
                say(f"boosty {blog} err {e}")
                return []
        return []

    import time as _t
    for blog, kws, label, fold in [
        ("northernsiberiawinds", ["bodycare", "body care"], "Bodycare Kit (NSW)", OUT / "rescue-nsw-bodycare"),
        ("sims3melancholic", ["cleavage"], "Cleavage masks 3 (sims3melancholic)", OUT / "patreon-96600228"),
        ("okruee", ["misc"], "Misc face details (okruee)", OUT / "rescue-okruee-miscface"),
        ("miikocc", ["acne"], "Acne (miikocc)", OUT / "rescue-miikocc-acne"),
        ("obscurus_sims", ["eyelash", "lash"], "3D eyelashes (obscurus)", OUT / "rescue-obscurus-3dlash"),
        ("148dazed", ["amaranth"], "Amaranth (148DAZED)", OUT / "patreon-117097930"),
        ("jo_se_oh", ["light"], "Lighting overlay (Jo_se_oh)", OUT / "patreon-94005453"),
    ]:
        if fold.exists() and any(fold.iterdir()):
            continue
        posts = boosty_posts(blog)
        if posts:
            lines.append(f"boosty {blog} titles: " + " | ".join(
                (p.get("title") or "")[:40] for p in posts[:40]))
            boosty_hunt(blog, kws, fold, label)
        else:
            # fallback: pagina HTML do boosty (SSR embutida)
            try:
                r = fetch(f"https://boosty.to/{blog}", session=SCRAPER)
                say(f"boosty html {blog}: HTTP {r.status_code}")
                if r.status_code == 200:
                    urls = [u for u in _walk_urls(r.text)
                            if any(x in u for x in ("files.boosty", "simfileshare",
                                                    "mediafire", "drive.google", "dropbox"))]
                    say(f"boosty html {blog}: {len(urls)} urls de arquivo")
                    for u in urls[:8]:
                        ok, info = try_url(u, fold, referer=f"https://boosty.to/{blog}")
                        say(f"    try {u[:90]} -> {info}")
                        if ok:
                            record("downloaded", item=label, source=f"boosty.to/{blog}")
                            break
                    if not urls:
                        # tenta achar post urls do blog e visitar cada uma
                        purls = re.findall(
                            r'https://boosty\.to/' + re.escape(blog) +
                            r'/posts/([a-z0-9\-]+)', r.text)
                        say(f"boosty html {blog}: {len(purls)} posts")
                        for slug in purls[:30]:
                            t = slug.lower()
                            if any(k in t for k in kws):
                                r2 = fetch(f"https://boosty.to/{blog}/posts/{slug}",
                                           session=SCRAPER)
                                u2 = [u for u in _walk_urls(r2.text)
                                      if any(x in u for x in ("files.boosty", "simfileshare",
                                                              "mediafire", "drive.google",
                                                              "dropbox"))]
                                for u in u2[:6]:
                                    ok, info = try_url(u, fold, referer=r2.url)
                                    say(f"    {slug} try {u[:80]} -> {info}")
                                    if ok:
                                        record("downloaded", item=label,
                                               source=f"boosty.to/{blog}/posts/{slug}")
                                        break
                                if fold.exists() and any(fold.iterdir()):
                                    break
            except Exception as e:
                say(f"boosty html {blog} err {e}")
        _t.sleep(10)

    if WB_DEBUG:
        lines.append("--- wayback debug ---")
        lines.extend(WB_DEBUG)

    # ---- 7. anexos do patreon: wayback revela os ids (file?h=..&i=..) e o
    # endpoint patreon.com/file serve o arquivo SEM login p/ posts publicos
    for pid in ("93373994", "72457009", "71370172", "96600228", "93851178",
                "94005453", "92135508", "117097930", "42027501", "26574490"):
        fold = OUT / f"rescue-pat-{pid}"
        got = set()
        if fold.exists():
            got = {p.name for p in fold.iterdir() if p.is_file()}
        ids = set()
        for mode in ("", "id_"):
            try:
                r = fetch(f"https://web.archive.org/web/2{mode}/"
                          f"https://www.patreon.com/posts/{pid}", session=S)
                if r.status_code != 200:
                    continue
                ids |= set(re.findall(r'patreon\.com/file\?h=' + pid + r'&(?:amp;)?i=(\d+)', r.text))
                ids |= {("m" + m) for m in
                        re.findall(r'patreon\.com/file\?h=' + pid + r'&(?:amp;)?m=(\d+)', r.text)}
            except Exception as e:
                say(f"wb-pat {pid} err {e}")
        ids = sorted(ids)[:16]
        say(f"patreon {pid}: {len(ids)} attachment ids do wayback")
        for a in ids:
            u = (f"https://www.patreon.com/file?h={pid}&i={a}"
                 if not a.startswith("m") else
                 f"https://www.patreon.com/file?h={pid}&m={a[1:]}")
            try:
                r = fetch(u, session=SCRAPER, allow_redirects=True)
                ct = r.headers.get("Content-Type", "").lower()
                say(f"  {u[-45:]} -> {r.status_code} {ct[:30]}")
                if r.status_code == 200 and "html" not in ct and len(r.content) > 512:
                    if save_response(r, fold, f"patreon-{pid}-{a}.package"):
                        record("downloaded", item=f"patreon attachment {pid}/{a}", source=u)
            except Exception as e:
                say(f"  patreon file err {e}")

    # ---- 8. ModCo (modcollective.gg) - bzip eyes da RemusSirion
    fold = OUT / "rescue-remussirion-bzip"
    if not (fold.exists() and any(fold.iterdir())):
        try:
            r = fetch("https://www.modcollective.gg/sims4/artist/remussirion", session=SCRAPER)
            say(f"modco artist page: {r.status_code}")
            if r.status_code == 200:
                creates = re.findall(r'href="(/sims4/details/creation/[^"]+)"', r.text)
                bz = [c for c in creates if "bzip" in c.lower() or "zip" in c.lower()]
                say(f"modco criacoes: {creates[:10]} bzip: {bz}")
                for c in (bz or creates)[:6]:
                    r2 = fetch("https://www.modcollective.gg" + c, session=SCRAPER)
                    if r2.status_code != 200:
                        continue
                    for m in re.findall(r'href="([^"]*(?:download|api)[^"]*)"', r2.text)[:5]:
                        u = m if m.startswith("http") else "https://www.modcollective.gg" + m
                        ok, info = try_url(u, fold, referer=r2.url)
                        say(f"    modco {u[:80]} -> {info}")
                        if ok:
                            record("downloaded", item="BZIP Eyes (RemusSirion)", source=u)
                            break
                    if fold.exists() and any(fold.iterdir()):
                        break
        except Exception as e:
            say(f"modco err {e}")

    dbg.write_text("\n".join(lines), encoding="utf-8")

    (OUT / "manifest.json").write_text(
        json.dumps(MANIFEST, indent=2, ensure_ascii=False))
    log(f"DONE. downloaded={len(MANIFEST['downloaded'])} "
        f"failed={len(MANIFEST['failed'])} manual={len(MANIFEST['manual'])}")


# ----------------------------------------------------------------------------
# RESCUE: alternate routes
# ----------------------------------------------------------------------------
def patreon_cloudscraper(pid, folder, label):
    url = f"https://www.patreon.com/posts/{pid}"
    if folder.exists() and any(folder.iterdir()):
        return
    try:
        r = fetch(url, session=SCRAPER)
        if r.status_code != 200:
            log(f"  cloudscraper {pid}: {r.status_code}")
            return
        cands, _ = pick_candidates(extract_links(r.text))
        for u in cands:
            ok, info = try_url(u, folder, referer=url)
            log(f"    try {u[:90]} -> {info}")
            if ok:
                record("downloaded", item=label, source=url + " (cloudscraper)")
                return
        record("manual", item=label, site="Patreon (cloudscraper sem link)", url=url)
    except Exception as e:
        log(f"  cloudscraper {pid} err {e}")


def wayback_extract(url, folder, label):
    """Fetch a wayback snapshot of a page and try its file links."""
    if folder.exists() and any(folder.iterdir()):
        return
    from urllib.parse import unquote
    for ts in ("2", "2024", "2023"):
        for mode in ("", "id_"):
            try:
                r = fetch(f"https://web.archive.org/web/{ts}{mode}/{url}", session=S)
                if r.status_code != 200 or "has not archived that URL" in r.text:
                    continue
                text = r.text
                # unwrap wayback-prefixed hrefs
                text = re.sub(r'(https?://web\.archive\.org/web/\d+[a-z_]*/)(https?://)',
                              r'\2', text)
                # decode tumblr t.umblr.com redirect wrappers
                for enc in re.findall(r't\.umblr\.com/redirect\?z=([^&"\']+)', text):
                    text += " " + unquote(enc)
                cands, extra_posts = pick_candidates(extract_links(text))
                log(f"  wayback[{ts}{mode}] {url[-50:]}: {len(cands)} candidatos")
                if not cands:
                    hostish = [h for h in extract_links(text)
                               if any(d in h for d in ("fileshare", "mediafire",
                                                       "drive.", "dropbox", "patreon.com/file",
                                                       "forgecdn", "discord", "box.", "1drv"))]
                    WB_DEBUG.append(f"wayback[{ts}{mode}] {url}: filehost hrefs="
                                    + " | ".join(hostish[:40]))
                for u in cands:
                    ok, info = try_url(u, folder, referer=url)
                    log(f"    try {u[:90]} -> {info}")
                    if ok:
                        record("downloaded", item=label, source=f"wayback:{url}")
                        return
                for pid_url in extra_posts:
                    pid = re.search(r"(\d{6,})(?:[/?#]|$)", pid_url)
                    if pid:
                        patreon_cloudscraper(int(pid.group(1)), folder, label)
                if folder.exists() and any(folder.iterdir()):
                    return
                # sem candidatos nesta modalidade; tenta a proxima (raw id_)
            except Exception as e:
                log(f"  wayback {url[-40:]} err {e}")


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


def boosty_hunt(blog, keywords, folder, label):
    """Boosty (RU patreon clone) public posts often carry the same files."""
    if folder.exists() and any(folder.iterdir()):
        return
    try:
        r = fetch(f"https://boosty.to/api/v1/blog/{blog}/posts?posts_count=300", session=S)
        if r.status_code != 200:
            log(f"  boosty {blog}: HTTP {r.status_code}")
            return
        posts = r.json().get("data", [])
        for p in posts:
            title = (p.get("title") or "").lower()
            if p.get("blocked"):
                continue
            if not any(k in title for k in keywords):
                continue
            log(f"  boosty {blog}: match '{p.get('title')}'")
            urls = [u for u in _walk_urls(p) if "boosty.to" not in u
                    or "files.boosty" in u]
            for u in urls[:8]:
                ok, info = try_url(u, folder, referer=f"https://boosty.to/{blog}")
                log(f"    try {u[:90]} -> {info}")
                if ok:
                    record("downloaded", item=label,
                           source=f"boosty.to/{blog} post '{p.get('title')}'")
                    return
    except Exception as e:
        log(f"  boosty {blog} err {e}")


def nsw_site(label, folder):
    """NSW official website posts carry the public download links."""
    try:
        r = fetch("https://northernsiberiawinds.com/", session=SCRAPER)
        if r.status_code != 200:
            log(f"  nsw site: HTTP {r.status_code}")
            return
        pages = [html.unescape(m) for m in
                 re.findall(r'href="([^"]*bodycare[^"]*)"', r.text, re.I)]
        base = "https://northernsiberiawinds.com"
        for p in pages[:3]:
            u = p if p.startswith("http") else base + (p if p.startswith("/") else "/" + p)
            ok, info = scrape_page(u, folder, label, session=SCRAPER)
            log(f"    nsw page {u} -> {info}")
            if ok:
                record("downloaded", item=label, source=u)
                return
    except Exception as e:
        log(f"  nsw site err {e}")


PATREON_RETRY = [
    (93373994, "Bodycare Kit (NSW)", OUT / "patreon-93373994"),
    (117097930, "Amaranth set (148DAZED)", OUT / "patreon-117097930"),
    (72457009, "Acne (miikocc)", OUT / "patreon-72457009"),
    (71370172, "Misc face details (okruee)", OUT / "patreon-71370172"),
    (94005453, "Lighting overlay (Jo_se_oh)", OUT / "patreon-94005453"),
    (93851178, "3D eyelashes (obscurus)", OUT / "patreon-93851178"),
    (96600228, "Cleavage masks 3 (sims3melancholic)", OUT / "patreon-96600228"),
    (42027501, "Spotlight tattoos (Simandy)", OUT / "patreon-42027501"),
    (92135508, "Feet 1V remaster (magicbot)", OUT / "patreon-92135508"),
    (26574490, "Nosemask N10 (obscurus)", OUT / "rescue-obscurus-n10"),
]

TUMBLR_RETRY = [
    ("https://northernsiberiawinds.tumblr.com/post/734744726011576320/bodycare-kit",
     "Bodycare Kit (NSW)", OUT / "rescue-nsw-bodycare"),
    ("https://remussirion.tumblr.com/post/766701696234684416/bzip-eyes-set-ts4",
     "BZIP Eyes (RemusSirion)", OUT / "rescue-remussirion-bzip"),
    ("https://sayasims.tumblr.com/post/183470649946/saya-eye-reflections-detail-22-swatches-female",
     "Saya eye reflections (SayaSims)", OUT / "rescue-sayasims"),
    ("https://pralinesims.net/post/188285457999/arm-hand-jewellery-ultimate-collection",
     "Arm&Hand Jewellery (Pralinesims)", OUT / "rescue-pralinesims"),
    ("https://obscurus-sims.tumblr.com/post/184629124468/nosemask-n10-70-colors-all-ages-all-genders",
     "Nosemask N10 (obscurus)", OUT / "rescue-obscurus-n10"),
    ("https://simandy.tumblr.com/post/630272666330415104/because-every-time-i-look-at-photoshop-i-want-to",
     "Spotlight Tattoos (Simandy)", OUT / "patreon-42027501"),
]

BOOSTY_HUNTS = [
    ("northernsiberiawinds", ["bodycare"], "Bodycare Kit (NSW)", OUT / "patreon-93373994"),
    ("148dazed", ["amaranth"], "Amaranth set (148DAZED)", OUT / "patreon-117097930"),
    ("miikocc", ["acne"], "Acne (miikocc)", OUT / "patreon-72457009"),
    ("okruee", ["misc face", "miscface"], "Misc face details (okruee)", OUT / "patreon-71370172"),
    ("jo_se_oh", ["lighting"], "Lighting overlay (Jo_se_oh)", OUT / "patreon-94005453"),
    ("obscurus_sims", ["3d lash", "3d eyelash", "lashes", "eyelash"], "3D eyelashes (obscurus)", OUT / "patreon-93851178"),
    ("obscurus", ["3d lash", "eyelash", "lashes"], "3D eyelashes (obscurus)", OUT / "patreon-93851178"),
    ("sims3melancholic", ["cleavage"], "Cleavage masks 3 (sims3melancholic)", OUT / "patreon-96600228"),
    ("simandy", ["spotlight"], "Spotlight tattoos (Simandy)", OUT / "patreon-42027501"),
    ("magicbot", ["feet"], "Feet 1V remaster (magicbot)", OUT / "patreon-92135508"),
    ("lutessasims", ["moles"], "Moles (LutessaSims)", OUT / "rescue-lutessa-moles"),
    ("yunseol", ["eyebrow", "brow"], "Eyebrows (YUNSEOL)", OUT / "rescue-yunseol-brows"),
    ("mikooi", ["body detail", "realistic"], "Body details (Mikooi)", OUT / "rescue-mikooi-body"),
]


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        (OUT / "manifest.json").write_text(
            json.dumps(MANIFEST, indent=2, ensure_ascii=False))
        sys.exit(1)
