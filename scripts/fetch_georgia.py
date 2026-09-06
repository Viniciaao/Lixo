#!/usr/bin/env python3
"""Fetch Georgia's public CC only; record manual/failed sources explicitly.

Restored from the user's previous-session script; the old commits were not
available in this checkout. No accounts, paid attachments or unofficial mirrors.
Binary payloads go to ignored CCs/ and Actions artifacts, not ordinary Git blobs.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from georgia_validation import MAX_FILE_BYTES, sniff_extension, validate_file

PACK = Path("georgia-tudo-junto")
WORK = Path("work")
CF_PAGE = "https://www.curseforge.com/sims4/sims-households/georgia"
DRIVE_FOLDER = "1p4W_kdF7oPJ4aRVQQ-alkEDZAJdrkm5B"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def source(number, name, creator, urls, mode="auto", note=""):
    return {"id": f"{number:02}", "name": name, "creator": creator, "urls": urls,
            "mode": mode, "note": note}


def patreon(post):
    return f"https://www.patreon.com/posts/{post}"


def tsr(post):
    # Exact URLs from Georgia/Georgia CC.txt inside the verified household ZIP.
    routes = {
        1766849: "sims4-hair-hairstyles/title/s-club-031226-double-ponytail",
        1486209: "sims4-clothing-female-teenadultelder-everyday/title/belaloallure-rina-sweatpants",
        1459200: "sims4-eyecolors/title/cytosine-eyes",
        1355997: "sims4-makeup-female-skindetails/title/soft-face-freckles-hq",
        1770164: "sims4/title/venerian-tea-time-lashes-hq",
    }
    return f"https://www.thesimsresource.com/downloads/details/category/{routes.get(post, 'sims4')}/id/{post}/"


SOURCES = [
    source(1, "Sim Georgia", "MizuTS4", [CF_PAGE, CF_PAGE + "/files/8674144"],
           note="Georgia.zip; file id 8674144. Somente household/Tray, sem CC."),
    source(2, "Hair S-Club 031226 Double Ponytail", "S-Club", [tsr(1766849)], "manual", "TSR: download manual conforme acesso da sua conta."),
    source(3, 'Teeth "Normal" — alpha teeth', "MagicBot", ["https://simfileshare.net/folder/235489/", patreon(117517959)],
           note="Variantes DEFAULT e NON-DEFAULT: não instalar todos os defaults juntos."),
    source(4, "Rina Sweatpants (Fullbody na lista do sim)", "Belaloallure; lista cita [tabae]clothes01", [tsr(1486209)], "manual",
           "A lista original chama o item Fullbody e cita [tabae]clothes01, mas fornece este link de Rina Sweatpants. Confirmar a correspondência/variante com o criador do sim; download manual TSR."),
    source(5, "Leo levis shoes conversion", "MadMan / MagicBot", [patreon(23286338)], note="Preferir o arquivo FIX F+M publicado pelo criador."),
    source(6, "GPME-GOLD MAKEUP SET CC31", "goppolsme", [patreon(44511936), "https://simfileshare.net/download/2172979/"]),
    source(7, "Basics Please — eyeshadows", "TwistedCat", [patreon(63321024)], note="EyeLid / Full / OuterEdge: alternativas do mesmo conjunto."),
    source(8, "GPME-GOLD Liner cc10", "goppolsme", [patreon(19279776), "https://simfileshare.net/download/568017/"]),
    source(9, "WILD CAT — BLUSH N7", "Northern Siberia Winds", [patreon(64319245)], note="Selecionar BLUSH N7, não as peles/maquiagens restantes do post."),
    source(10, "Cytosine Eyes — facepaint", "RemusSirion", [tsr(1459200)], "manual", "TSR: download manual conforme acesso da sua conta."),
    source(11, "Realistic Female Body Details (16154)", "Mikooi Sims (conforme lista do sim)",
           ["https://bestsimsmods.com/sims-4-mikkoi-female-body-details-6-0/"], "manual",
           "A lista original cita Mikooi Sims e 16154-realistic-female-body-details, sem link. O guia recebido não foi validado: conteúdo adulto, ~273 MB e possível Get Famous são informações a confirmar na fonte original. Não confundir automaticamente com Miiko; mirror não usado."),
    source(12, "misc. face details", "okruee", [patreon(71370172)], note="TATTOO / OCCULT / SKINDETAIL: escolher a categoria desejada."),
    source(13, "Lighting Overlay 2.0", "jo_se_oh", [patreon(94005453)], note="TRUE BLACK e COLOR: variantes; conferir instruções do criador."),
    source(14, "In game shadow — face shadow", "Simandy", ["https://simandy.tumblr.com/post/630272666330415104/because-every-time-i-look-at-photoshop-i-want-to", patreon(42027501)], note="O post oferece opções em 3 arquivos/categorias; não são 16 dependências independentes."),
    source(15, "Soft Face Freckles HQ", "alf-si", [tsr(1355997)], "manual", "TSR: download manual conforme acesso da sua conta."),
    source(16, "Bodycare Kit — seleção feminina", "Northern Siberia Winds", [patreon(93373994)],
           note="Seleção de nomes FEMALE / CLEAVAGE / BODY PRESET, excluindo MALE quando não FEMALE. Escolher variantes/presets no CAS."),
    source(17, "Tea Time Lashes HQ", "venerian", [tsr(1770164)], "manual", "TSR: download manual conforme acesso da sua conta."),
    source(18, "3D Eyelashes Set", "obscurus", [patreon(93848968), patreon(93851178), patreon(115736891)], "manual",
           "O post original foi atualizado em 31/05/2026 e remete ao post 115736891: exige entrar/participar como membro gratuito. Baixar manualmente as variantes N6 straight/curly/extra conforme o criador; não é indicação de assinatura paga."),
    source(19, "Eyebrows 33–41", "alf-si / ANGISSI", ["https://alf-si.tumblr.com/post/614674051815849984", tsr(1561164), tsr(1561412), tsr(1561566)],
           "manual", "Mapeamento recebido confirma somente links candidatos n33/n34/n35. n36–41 e a variante usada pelo sim ainda precisam de confirmação manual; não substituí-las silenciosamente."),
    source(20, "Cleavage Masks Collection", "sims3melancholic", [patreon(96600228), f"https://drive.google.com/drive/folders/{DRIVE_FOLDER}"],
           note="A pasta pública atual contém CLEAVAGE MASKS #1-6, com subpastas OVERLAYS/SKIN COLORS e categorias SCARS/TATTOO. São alternativas; não sobrepor todas."),
    source(21, "Nosemask N10 + overlay + presets", "obscurus", ["https://obscurus-sims.tumblr.com/post/184629124468/nosemask-n10-70-colors-all-ages-all-genders", patreon(26574490), "https://simfileshare.net/folder/66108/"],
           note="O post público aponta ao SFS: nosemask N10 LRLE, overlay e um .package com os quatro presets. 70 cores / HQ compatível conforme o criador; escolher no CAS."),
]

# Post, item id, output label, optional attachment-name regex.
PATREON_JOBS = [
    ("23286338", "05", "MagicBot-leo-levis-shoes", r"FIX.*F\+M"),
    ("63321024", "07", "TwistedCat-BasicsPlease", None),
    ("64319245", "09", "NSW-BLUSH-N7", r"\bBLUSH[\s_]*N7\b"),
    ("71370172", "12", "okruee-misc-face-details", None),
    ("94005453", "13", "Jo_se_oh-Lighting-Overlay", None),
    ("42027501", "14", "Simandy-face-shadow", None),
    ("93373994", "16", "NSW-Bodycare-Kit", r"FEMALE|CLEAVAGE|BODY[\s_]*PRESET"),
    ("26574490", "21", "obscurus-Nosemask-N10", None),
]


class PublicUnavailable(Exception):
    """The author has not made the attachment available to anonymous visitors."""


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.current = [dict(attrs).get("href", ""), ""]

    def handle_data(self, data):
        if self.current is not None:
            self.current[1] += data

    def handle_endtag(self, tag):
        if tag == "a" and self.current is not None:
            self.links.append(tuple(self.current))
            self.current = None


def clean_name(name):
    result = re.sub(r"[^A-Za-z0-9._-]+", "_", html.unescape(name)).strip("._")
    if not result:
        raise ValueError("empty sanitized filename")
    return result


def attachment_selected(number, name, pattern):
    if Path(name).suffix.lower() not in {".package", ".zip", ".rar", ".7z"}:
        return False
    if pattern and not re.search(pattern, name, re.I):
        return False
    return not (number == "16" and re.search(r"(?<![A-Za-z])MALE(?![A-Za-z])", name, re.I))


def sanitized_error(error):
    # Do not store expiring/signed download query strings in Git or logs.
    def redact(match):
        parsed = urlsplit(match.group(0))
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    return re.sub(r"https?://[^\s\"']+", redact, str(error))[:700]


def post_link_urls(attributes):
    """Patreon now returns some public bodies as ProseMirror JSON, not HTML."""
    parser = Links()
    parser.feed(attributes.get("content") or "")
    urls = [href for href, _ in parser.links]
    rich_text = attributes.get("content_json_string")
    if rich_text:
        pending = [json.loads(rich_text)]
        while pending:
            node = pending.pop()
            if isinstance(node, list):
                pending.extend(node)
            elif isinstance(node, dict):
                if node.get("type") == "link":
                    href = node.get("attrs", {}).get("href")
                    if isinstance(href, str):
                        urls.append(href)
                pending.extend(value for value in node.values() if isinstance(value, (dict, list)))
    return list(dict.fromkeys(urls))


def public_attachments(document):
    """Join by media id/owner, never zip two independently ordered API arrays."""
    post = document["data"]
    if post["attributes"].get("current_user_can_view") is not True:
        raise PublicUnavailable("Post/anexos não disponíveis anonimamente; abrir a página do criador.")
    refs = post.get("relationships", {}).get("attachments_media", {}).get("data")
    ids = {str(r["id"]) for r in refs} if refs is not None else None
    output = []
    for obj in document.get("included") or []:
        attr = obj.get("attributes", {})
        if obj.get("type") != "media":
            continue
        if ids is not None:
            if str(obj["id"]) not in ids:
                continue
        elif (attr.get("owner_relationship") != "attachment"
              or str(attr.get("owner_id")) != str(post["id"])):
            continue
        name = attr.get("file_name")
        if not name:
            raise ValueError("attachment media is missing its own file_name")
        output.append({"id": str(obj["id"]), "name": name,
                       "bytes": attr.get("size_bytes"), "url": attr.get("download_url")})
    return output


class Fetcher:
    def __init__(self, pack=PACK, work=WORK):
        self.pack, self.work = Path(pack), Path(work)
        self.out = self.pack / "CCs"
        self.out.mkdir(parents=True, exist_ok=True)
        self.work.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
        retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504],
                      allowed_methods=["GET"])
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.items = {s["id"]: {**s, "status": "manual" if s["mode"] == "manual" else "pending",
                                "files": [], "errors": []} for s in SOURCES}
        self.lines = []

    def log(self, text):
        text = sanitized_error(text)
        print(text, flush=True)
        self.lines.append(text)

    def get(self, url, **kwargs):
        response = self.session.get(url, timeout=(20, 90), **kwargs)
        response.raise_for_status()
        return response

    def download(self, number, url, stem, source_url, expected_size=None):
        filename = clean_name(stem)
        for suffix in (".package", ".zip", ".rar", ".7z"):
            if filename.lower().endswith(suffix):
                filename = filename[:-len(suffix)]
                break
        tmp = self.out / (filename + ".part")
        try:
            with self.get(url, headers={"Referer": source_url}, stream=True) as response:
                total = 0
                with tmp.open("wb") as stream:
                    for chunk in response.iter_content(1024 * 1024):
                        total += len(chunk)
                        if total > MAX_FILE_BYTES:
                            raise ValueError("download exceeds 512 MiB limit")
                        stream.write(chunk)
                if expected_size is not None and total != int(expected_size):
                    raise ValueError(f"size mismatch: got {total}, metadata says {expected_size}")
            with tmp.open("rb") as stream:
                extension = sniff_extension(stream.read(96))
            result = validate_file(tmp, household=number == "01")
            final = self.out / (filename + extension)
            if final.exists():
                raise ValueError(f"refusing to overwrite/collide with {final.name}")
            tmp.replace(final)
            result.update(path=f"CCs/{final.name}", source_url=source_url)
            self.items[number]["files"].append(result)
            self.log(f"[{number}] VALIDATED {final.name} bytes={total} sha256={result['sha256']}")
        finally:
            tmp.unlink(missing_ok=True)

    def attempt(self, number, callback):
        item = self.items[number]
        self.log(f"\n=== [{number}] {item['name']} ===")
        try:
            callback()
            if not item["files"]:
                raise ValueError("no matching attachment was downloaded")
            item["status"] = "downloaded"
        except PublicUnavailable as error:
            item["status"] = "manual"
            item["errors"].append(str(error))
            self.log(f"[{number}] MANUAL: {error}")
        except Exception as error:
            item["status"] = "failed"
            item["errors"].append(sanitized_error(error))
            self.log(f"[{number}] FAILED: {type(error).__name__}: {error}")

    def fetch_cf_sim(self):
        page = self.get(CF_PAGE).text.replace('\\"', '"')
        match = re.search(r'"projectId"\s*:\s*"?(\d+)', page) or re.search(r'data-project-id="(\d+)"', page)
        modid = match.group(1) if match else None
        if not modid:
            modid = self.get("https://api.cfwidget.com/sims4/sims-households/georgia").json().get("id")
        if not modid:
            raise ValueError("CurseForge projectId not found")
        self.items["01"]["project_id"] = str(modid)
        download_page = CF_PAGE + "/download/8674144"
        self.get(download_page)
        api = f"https://www.curseforge.com/api/v1/mods/{modid}/files/8674144/download"
        with self.get(api, allow_redirects=False, headers={"Accept": "*/*", "Referer": download_page}) as response:
            if response.is_redirect:
                url = urljoin(api, response.headers["Location"])
            elif "json" in response.headers.get("Content-Type", ""):
                data = response.json()
                url = data.get("downloadUrl") or data.get("url") or (data.get("data") or {}).get("downloadUrl")
            else:
                url = api
        if not url:
            raise ValueError("CurseForge did not return a public download URL")
        self.download("01", url, "01_SIM-Georgia", CF_PAGE + "/files/8674144")
        sim = self.items["01"]["files"][0]
        lists = [m for m in sim["members"] if m["name"].endswith("CC.txt") and m["bytes"] < 65536]
        if len(lists) == 1:
            with zipfile.ZipFile(self.pack / sim["path"]) as archive:
                content = archive.read(lists[0]["name"]).decode("utf-8-sig")
            (self.work / "fetch_georgia_creator_cc.txt").write_text(content, encoding="utf-8")

    def fetch_sfs(self, sid, number, label):
        page = f"https://simfileshare.net/download/{sid}/"
        self.get(page)
        self.download(number, f"https://cdn.simfileshare.net/download/{sid}/?dl",
                      f"{number}_{label}", page)

    def fetch_sfs_folder(self, folder_id, number, label, patterns):
        parser = Links()
        parser.feed(self.get(f"https://simfileshare.net/folder/{folder_id}/").text)
        hits = {}
        for href, name in parser.links:
            match = re.search(r"/download/(\d+)/", href)
            if match and any(re.search(pattern, name, re.I) for pattern in patterns):
                hits[match.group(1)] = name.strip()
        self.items[number]["selected_names"] = list(hits.values())
        for pattern in patterns:
            if not any(re.search(pattern, name, re.I) for name in hits.values()):
                raise ValueError(f"SFS folder is missing an expected variant: {pattern}")
        for sid, name in hits.items():
            self.fetch_sfs(sid, number, label + "-" + name)

    def fetch_teeth(self):
        self.fetch_sfs_folder("235489", "03", "MagicBot-teeth", [
            r"(?<!Non-)Default[\s_]+alpha[\s_]+teeth[\s_]+all",
            r"Non-default[\s_]+alpha[\s_]+teeth",
        ])

    def fetch_patreon(self, pid, number, label, pattern):
        document = self.get(f"https://www.patreon.com/api/posts/{pid}",
                            headers={"Accept": "application/json, text/plain, */*"}).json()
        attachments = public_attachments(document)
        self.items[number]["post_title"] = document["data"]["attributes"].get("title")
        self.items[number]["available_attachments"] = [{k: a[k] for k in ("id", "name", "bytes")} for a in attachments]
        selected = [a for a in attachments if attachment_selected(number, a["name"], pattern)]
        self.items[number]["selected_names"] = [a["name"] for a in selected]
        self.log(f"[{number}] {len(selected)}/{len(attachments)} attachments matched; public access confirmed")
        if not selected and number == "21":
            links = post_link_urls(document["data"]["attributes"])
            # Only follow the folder explicitly linked by the public author post.
            if not any(urlsplit(href).hostname in {"simfileshare.net", "www.simfileshare.net"}
                       and urlsplit(href).path.rstrip("/") == "/folder/66108" for href in links):
                raise ValueError("author post no longer links the expected SFS folder 66108")
            self.items[number]["resolved_folder"] = "https://simfileshare.net/folder/66108/"
            self.fetch_sfs_folder("66108", number, label, [
                r"nosemask_N10_lrle\.package$", r"nosemask_N10_overlay\.package$",
                r"nose_presets_3f\.package$",
            ])
            return
        if not selected:
            raise ValueError("no public attachment matches the requested selection")
        errors = []
        for attachment in selected:
            try:
                if not attachment["url"]:
                    raise ValueError(f"public attachment has no download_url: {attachment['name']}")
                self.download(number, attachment["url"], f"{number}_{label}_{attachment['name']}",
                              patreon(pid), attachment["bytes"])
            except Exception as error:
                errors.append(sanitized_error(error))
                self.log(f"[{number}] attachment failure ({attachment['name']}): {error}")
        if errors:
            raise ValueError("; ".join(errors))

    def gdrive_files(self, root):
        """Walk only public subfolders linked from the mapped root; bound recursion."""
        queue, visited, items = [(root, 0)], set(), {}
        while queue:
            folder_id, depth = queue.pop(0)
            if folder_id in visited:
                continue
            if depth > 8 or len(visited) >= 64:
                raise ValueError("Drive folder traversal exceeds safety limit")
            visited.add(folder_id)
            parser = Links()
            parser.feed(self.get(f"https://drive.google.com/embeddedfolderview?id={folder_id}#list").text)
            for href, name in parser.links:
                parsed = urlsplit(href)
                if parsed.scheme not in {"https", "http"} or parsed.hostname != "drive.google.com":
                    continue
                folder = re.fullmatch(r"/drive/(?:u/\d+/)?folders/([A-Za-z0-9_-]+)", parsed.path.rstrip("/"))
                if folder:
                    queue.append((folder.group(1), depth + 1))
                    continue
                match = re.fullmatch(r"/file/d/([A-Za-z0-9_-]+)/view", parsed.path.rstrip("/"))
                if match and Path(name.strip()).suffix.lower() in {".package", ".zip", ".rar", ".7z"}:
                    items[match.group(1)] = name.strip()
                    if len(items) > 128:
                        raise ValueError("Drive file count exceeds safety limit")
        self.items["20"]["resolved_folders"] = sorted(visited)
        return items

    def fetch_gdrive(self):
        items = self.gdrive_files(DRIVE_FOLDER)
        if not items:
            raise ValueError("no public package/archive listed in the creator's Drive folder tree")
        self.items["20"]["selected_names"] = list(items.values())
        self.log(f"[20] {len(items)} files in {len(self.items['20']['resolved_folders'])} public folders")
        errors = []
        for fid, name in items.items():
            try:
                self.download("20", f"https://drive.usercontent.google.com/download?id={fid}&export=download&confirm=t",
                              "20_sims3melancholic-cleavage-" + name,
                              f"https://drive.google.com/file/d/{fid}/view")
            except Exception as error:
                errors.append(sanitized_error(error))
                self.log(f"[20] file failure ({name}): {error}")
        if errors:
            raise ValueError("; ".join(errors))

    def finish(self):
        for item in self.items.values():
            if item["status"] == "pending":
                item["status"] = "failed"
                item["errors"].append("Fetch interrupted before this source was processed.")
        try:
            head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        except subprocess.CalledProcessError:
            head = "unknown"
        run_id = os.environ.get("GITHUB_RUN_ID")
        run_url = (f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{run_id}" if run_id else None)
        manifest = {"schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
                    "checkout_sha": head, "workflow_run": run_url, "items": list(self.items.values())}
        files = [f for item in self.items.values() for f in item["files"]]
        manifest["summary"] = {"files": len(files), "bytes": sum(f["bytes"] for f in files),
                               **{status: sum(i["status"] == status for i in self.items.values())
                                  for status in ("downloaded", "manual", "failed")}}
        contents = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
        (self.pack / "MANIFEST.json").write_text(contents, encoding="utf-8")
        (self.work / "fetch_georgia_manifest.json").write_text(contents, encoding="utf-8")
        (self.pack / "SHA256SUMS.txt").write_text("".join(f"{f['sha256']}  {f['path']}\n" for f in sorted(files, key=lambda f: f["path"])), encoding="utf-8")
        self.log("\n=== SUMMARY " + json.dumps(manifest["summary"]) + " ===")
        (self.work / "fetch_georgia_report.txt").write_text("\n".join(self.lines) + "\n", encoding="utf-8")
        return 1 if manifest["summary"]["failed"] or self.items["01"]["status"] != "downloaded" else 0

    def run(self):
        # Never mix cached files from another run with newly validated downloads.
        if any(self.out.iterdir()):
            raise ValueError(f"{self.out} is not empty; move it aside before fetching again")
        try:
            self.attempt("01", self.fetch_cf_sim)
            self.attempt("06", lambda: self.fetch_sfs("2172979", "06", "GPME-Gold-Makeup-Set-CC31"))
            self.attempt("08", lambda: self.fetch_sfs("568017", "08", "GPME-Gold-Liner-cc10"))
            self.attempt("03", self.fetch_teeth)
            for job in PATREON_JOBS:
                self.attempt(job[1], lambda job=job: self.fetch_patreon(*job))
            self.attempt("20", self.fetch_gdrive)
        finally:
            result = self.finish()
            self.session.close()
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, default=PACK)
    parser.add_argument("--work", type=Path, default=WORK)
    args = parser.parse_args()
    return Fetcher(args.pack, args.work).run()


if __name__ == "__main__":
    sys.exit(main())
