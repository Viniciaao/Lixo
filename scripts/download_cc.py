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

    (OUT / "manifest.json").write_text(
        json.dumps(MANIFEST, indent=2, ensure_ascii=False))
    log(f"DONE. downloaded={len(MANIFEST['downloaded'])} "
        f"failed={len(MANIFEST['failed'])} manual={len(MANIFEST['manual'])}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        (OUT / "manifest.json").write_text(
            json.dumps(MANIFEST, indent=2, ensure_ascii=False))
        sys.exit(1)
