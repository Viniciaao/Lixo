#!/usr/bin/env python3
"""Probe downloadability of every CC source used by the Helene Dacosta sim.

Runs on a GitHub Actions runner (full internet). Prints one line per source:
status | content-type | size | final URL | markers
"""
import json
import re
import sys
import urllib.request
import urllib.error

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

# (id, nome legivel, url)
SOURCES = [
    # --- CurseForge (arquivo direto) ---
    ("household",      "Helene Dacosta - SIM (household)",       "https://www.curseforge.com/sims4/sims-households/helene-dacosta/download/8763744"),
    ("eggsims19",      "[EGGSIMS] earrings 19",                  "https://www.curseforge.com/sims4/create-a-sim/eggsims-earrings-19/download/6496196"),
    ("sparklynails",   "Sparkly French Nails (4w25)",            "https://www.curseforge.com/sims4/create-a-sim/sparkly-french-nails/download/8649348"),
    ("maryjane",       "Shiny Patent Mary Jane Heels (PolySphere)","https://www.curseforge.com/sims4/create-a-sim/shiny-patent-mary-jane-heels/download/7751173"),
    ("maryjane_ah",    "Shiny Patent Mary Jane Heels AutoHeight", "https://www.curseforge.com/sims4/create-a-sim/shiny-patent-mary-jane-heels/download/7751168"),
    ("avasweatshirt",  "Ava Sweatshirt (MissValentinee)",        "https://www.curseforge.com/sims4/create-a-sim/ava-sweatshirt/download/8177818"),
    # --- Patreon posts ---
    ("gpme_c2",        "GPME Gold C2 (goppolsme)",               "https://www.patreon.com/posts/gpme-gold-c2-22436855"),
    ("nsw_n6",         "3D Eyelashes N6 (NorthernSiberiaWinds)", "https://www.patreon.com/posts/3d-eyelashes-123193524"),
    ("gpme_eyes",      "GPME Gold Eyes (goppolsme)",             "https://www.patreon.com/posts/gpme-gold-eyes-17490207"),
    ("heather_skin",   "Heather Skin N7 (poyopoyosim)",          "https://www.patreon.com/posts/heather-skin-n7-85159474"),
    ("phaedra_skirt",  "_phaedra_mini_skirt (Belaloallure)",     "https://www.patreon.com/posts/belaloallure-day-77031948"),
    ("lips_n35",       "Wild Cat Make-up / LIPS N35 (NSW)",      "https://www.patreon.com/posts/wild-cat-make-up-64319245"),
    ("lips_presets",   "_lips_presets_7f / helgatisha (obscurus)","https://www.patreon.com/posts/helgatisha-sims-59616486"),
    ("default_mouth",  "Default Mouth (MagicBot)",               "https://www.patreon.com/posts/default-mouth-56990147"),
    # --- TSR (The Sims Resource) ---
    ("tsr_blush",      "Holiday Snow Blush (VELYSEA) TSR",       "https://www.thesimsresource.com/members/VELYSEA/downloads/details/category/sims4-makeup-female-blush/title/holiday-snow-blush/id/1632502/"),
    ("tsr_eyeshadow",  "Eyeshadow N42 TSR",                      "https://www.thesimsresource.com/downloads/details/category/sims4-makeup-female-eyeshadow/title/eyeshadow-n42/id/1458745/"),
    ("tsr_hair",       "Elegante Long Hairstyle 071124 S-CLUB TSR","https://www.thesimsresource.com/downloads/details/category/sims4-hair-hairstyles/title/elegante-long-hairstyle-071124-by-s-club/id/1721513/"),
    ("tsr_brows",      "Eyebrows 28 v2 TSR",                     "https://www.thesimsresource.com/downloads/details/category/sims4-hair-facial-eyebrows/title/eyebrows-28-v2/id/1485348/"),
    ("tsr_lashes",     "S-CLUB WM TS4 Eyelashes 201801 TSR",     "https://www.thesimsresource.com/downloads/details/category/sims4-makeup-female-eyeliner/title/s-club-wm-ts4-eyelashes-201801/id/1400406/"),
    ("tsr_freckles",   "Freckles Z53 TSR",                       "https://www.thesimsresource.com/downloads/details/category/sims4-makeup-female-skindetails/title/freckles-z53/id/1658934/"),
    # --- Kijiko (hosts externos) ---
    ("kijiko_sfs",     "[Kijiko] EA Eyelashes Remover (SimFileShare)","https://simfileshare.net/download/3247982/"),
    ("kijiko_mf",      "[Kijiko] EA Eyelashes Remover (MediaFire)","https://www.mediafire.com/file/tgp3kcs4iy2mnft/%255BKijiko%255DRemove-EA-Lashes.zip/file"),
    # --- eunosims (tistory) ---
    ("euno_page",      "eunosims body preset page",              "https://eunosims.tistory.com/entry/sims4cc-body-preset-1-5"),
]


def probe(url, timeout=40):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "*/*",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            final = r.geturl()
            ctype = r.headers.get("Content-Type", "")
            clen = r.headers.get("Content-Length", "")
            # pega so um pedaco para analisar marcadores em paginas pequenas
            data = r.read(200_000) if not (clen and int(clen) > 400_000) else b""
            return r.status, ctype, clen, final, data
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", ""), "", url, b""
    except Exception as e:  # noqa
        return "ERR", "", "", url, f"{type(e).__name__}: {e}".encode()


def markers(url, text):
    out = []
    host = urllib.parse.urlparse(url).netloc
    if "patreon" in host:
        low = text[:120_000]
        if "attachment" in low or 'file?h=' in low:
            out.append("HAS_ATTACH")
        if re.search(r'var.*post.*\{', low):
            out.append("PAGE_OK")
        if "checkout" in low or "Unlock" in low or "join as a patron" in low.lower():
            out.append("LOCKED_MARK")
    if "thesimsresource" in host:
        if "login" in text[:60_000].lower() and "download" in text[:60_000].lower():
            out.append("LOGIN_MARK")
    return out


def main():
    print(f"== probe start {len(SOURCES)} sources ==", flush=True)
    for sid, name, url in SOURCES:
        status, ctype, clen, final, data = probe(url)
        m = markers(final, data.decode("utf-8", "replace"))
        try:
            txt = data.decode("utf-8", "replace")
        except Exception:
            txt = ""
        # marcadores extras
        extra = []
        if "curseforge" in final and status == 200:
            extra.append("CF_200")
        if "patreon" in final:
            if txt.count("attachment") or ("/file?h=" in txt):
                extra.append("PUBLIC_ATTACH?")
        clen_s = clen or ("~" + str(len(data)))
        print(f"[{sid}] {name}\n   status={status} type={ctype} len={clen_s}\n   final={final}\n   markers={m} {extra}", flush=True)
    print("== probe done ==", flush=True)


if __name__ == "__main__":
    import urllib.parse
    main()
