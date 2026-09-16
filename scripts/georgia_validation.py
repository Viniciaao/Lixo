#!/usr/bin/env python3
"""Offline structural validation; never executes or installs downloaded content."""
from __future__ import annotations

import hashlib
import shutil
import struct
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

MAX_FILE_BYTES = 512 * 1024 * 1024
MAX_EXPANDED_BYTES = 2 * 1024 * 1024 * 1024
MAX_MEMBERS = 5000
TRAY_EXTENSIONS = {".trayitem", ".householdbinary", ".hhi", ".sgi", ".blueprint", ".bpi"}
DANGEROUS_EXTENSIONS = {".exe", ".dll", ".bat", ".cmd", ".ps1", ".sh", ".js", ".ts4script"}


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def sniff_extension(head: bytes) -> str:
    if head.startswith(b"DBPF"):
        return ".package"
    if head.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        return ".zip"
    if head.startswith((b"Rar!\x1a\x07\x00", b"Rar!\x1a\x07\x01\x00")):
        return ".rar"
    if head.startswith(b"7z\xbc\xaf\x27\x1c"):
        return ".7z"
    raise ValueError("payload is not a DBPF package, ZIP, RAR or 7z (HTML/JSON/LFS pointers rejected)")


def validate_dbpf(head: bytes, size: int) -> None:
    if len(head) < 96 or head[:4] != b"DBPF":
        raise ValueError("missing/truncated DBPF header")
    if struct.unpack_from("<II", head, 4) != (2, 1):
        raise ValueError("not a supported The Sims 4 DBPF version (2.1)")
    count, offset_low, index_size = struct.unpack_from("<III", head, 36)
    offset = struct.unpack_from("<Q", head, 64)[0] or offset_low
    if not count or not index_size or offset < 96 or offset + index_size > size:
        raise ValueError("empty or out-of-bounds DBPF resource index (possibly truncated)")


def safe_member(name: str) -> None:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if (not normalized or path.is_absolute() or ".." in path.parts
            or ":" in normalized or any(ord(c) < 32 for c in normalized)):
        raise ValueError(f"unsafe archive member: {name!r}")
    if path.suffix.lower() in DANGEROUS_EXTENSIONS:
        raise ValueError(f"unexpected executable/script in CC archive: {name!r}")


def validate_member(name: str, payload: bytes) -> dict:
    safe_member(name)
    suffix = PurePosixPath(name).suffix.lower()
    if suffix == ".package":
        validate_dbpf(payload[:96], len(payload))
    elif suffix in TRAY_EXTENSIONS and not payload:
        raise ValueError(f"empty Tray member: {name}")
    return {"name": name, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}


def validate_archive(path: Path, extension: str) -> list[dict]:
    members = []
    if extension == ".zip":
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_MEMBERS or sum(x.file_size for x in entries) > MAX_EXPANDED_BYTES:
                raise ValueError("archive exceeds member/expanded-size limit")
            names = set()
            for entry in entries:
                safe_member(entry.filename)
                if entry.filename.casefold() in names:
                    raise ValueError(f"duplicate archive member: {entry.filename}")
                names.add(entry.filename.casefold())
                if entry.flag_bits & 1 or (entry.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError("encrypted members/symlinks are not accepted")
                if entry.is_dir():
                    continue
                if entry.file_size > MAX_FILE_BYTES:
                    raise ValueError("archive member exceeds size limit")
                # ZipFile.read checks CRC, including for non-package members.
                members.append(validate_member(entry.filename, archive.read(entry)))
    else:
        tool = shutil.which("7zz") or shutil.which("7z")
        if not tool:
            raise ValueError("7-Zip is required to validate RAR/7z CRC and member contents")
        listing = subprocess.run([tool, "l", "-slt", "-ba", str(path.resolve())],
                                 capture_output=True, text=True, check=True, timeout=120).stdout
        entries = []
        for block in listing.strip().split("\n\n"):
            entry = dict(line.split(" = ", 1) for line in block.splitlines() if " = " in line)
            if "Path" not in entry:
                continue
            safe_member(entry["Path"])
            if (entry.get("Encrypted") == "+" or entry.get("Symbolic Link")
                    or entry.get("Hard Link")):
                raise ValueError("encrypted members/links are not accepted")
            if entry.get("Folder") == "+" or entry.get("Attributes", "").startswith("D"):
                continue
            size = int(entry.get("Size", "0"))
            if size > MAX_FILE_BYTES:
                raise ValueError("archive member exceeds size limit")
            entries.append((entry["Path"], size))
        if len(entries) > MAX_MEMBERS or sum(s for _, s in entries) > MAX_EXPANDED_BYTES:
            raise ValueError("archive exceeds member/expanded-size limit")
        if len({n.casefold() for n, _ in entries}) != len(entries):
            raise ValueError("duplicate archive members")
        subprocess.run([tool, "t", "-bd", str(path.resolve())], capture_output=True,
                       check=True, timeout=300)
        # Stream each member to stdout, not to filesystem paths supplied by the archive.
        for name, size in entries:
            payload = subprocess.run([tool, "x", "-so", "-spd", str(path.resolve()), name],
                                     capture_output=True, check=True, timeout=180).stdout
            if len(payload) != size:
                raise ValueError(f"archive member size mismatch: {name}")
            members.append(validate_member(name, payload))
    if not members:
        raise ValueError("empty archive")
    if not any(PurePosixPath(m["name"]).suffix.lower() in TRAY_EXTENSIONS | {".package"}
               for m in members):
        raise ValueError("archive contains no Sims 4 package/Tray files")
    return members


def validate_file(path: Path, *, household: bool = False) -> dict:
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        raise ValueError("download exceeds size limit")
    with path.open("rb") as stream:
        head = stream.read(96)
    extension = sniff_extension(head)
    if path.suffix.lower() not in {extension, ".part"}:
        raise ValueError("filename extension does not match the payload")
    members = []
    if extension == ".package":
        validate_dbpf(head, size)
    else:
        members = validate_archive(path, extension)
    if household:
        suffixes = {PurePosixPath(m["name"]).suffix.lower() for m in members}
        if not {".trayitem", ".householdbinary"}.issubset(suffixes):
            raise ValueError("household ZIP lacks .trayitem/.householdbinary files")
    return {"bytes": size, "sha256": sha256(path), "format": extension[1:], "members": members}
