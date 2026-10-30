"""One-time, audited migration of tracked need-restock assets (requires ffmpeg).

The source is removed only after the independent validator succeeds. To repeat,
restore _folder/need restock from the pre-migration commit in a separate checkout.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

from brig_assets import digest, model_info, sprite_check, wave_check

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "_folder/need restock"
TARGET = ROOT / "_folder/brig"
MANIFEST = ROOT / "docs/brig-assets.json"
ASSET_ROOTS = {"models", "sound", "sprites", "gfx", "resource", "media", "maps"}
SOUND_EXT = {".wav", ".ogg", ".mp3"}


def extra_path(rel: PurePosixPath) -> str:
    """Short, deterministic variant paths; companions retain their basenames."""
    parts = rel.parts
    ext = rel.suffix.lower()
    kind = ("models" if ext in {".mdl", ".bmp"} and "models" in parts else
            "sound" if ext in SOUND_EXT else "sprites" if ext == ".spr" else
            "resource" if ext == ".res" or "resource" in parts else
            "gfx" if ext in {".tga", ".bmp", ".png", ".jpg"} else "docs")
    group = {"1": "weapons", "2": "npcs", "3": "players", "4": "menu", "5": "music", "6": "audio"}.get(parts[0][0], "misc")
    parent = rel.parent.as_posix()
    variant = hashlib.sha256(parent.encode()).hexdigest()[:10]
    return f"{kind}/_Extra/{group}/{variant}/{rel.name.lower()}"


def choose(group: str, rel: PurePosixPath) -> tuple[str | None, str]:
    """Policy depends on the source, never just the extension of a CS file."""
    parts = rel.parts
    top = parts[0].lower()
    ext = rel.suffix.lower()
    low = rel.as_posix().lower()
    if group in {"cstrike", "cstrike_hd"}:
        if top not in {"models", "sound"} or (top == "models" and len(parts) > 1 and parts[1].lower() == "player"):
            return None, "CS allowlist: models except player, and sound only"
        if top == "models" and ext not in {".mdl", ".bmp"}:
            return None, "CS model assets only"
        return f"{top}/{group}/" + "/".join(parts[1:]).lower(), "resource"
    if group == "Extras":
        return extra_path(rel), "optional"
    if group == "valve":
        if top in {"save", "cl_dlls", "dlls", "hw", "overviews"} or ext in {".nod", ".dem", ".log"}:
            return None, "installed binaries, saves or generated cache"
        if low in {"config.cfg", "autoexec.cfg", "user.scr", "voice_ban.dt", "steam_autocloud.vdf", "cached.wad", "spraypaint.wad", "steam.inf", "steam_appid.txt"}:
            return None, "machine-specific state or personal configuration"
        if ext == ".cfg" and low not in {"skill.cfg", "game.cfg"}:
            return None, "replace inherited configuration with clean brig defaults"
        if low in {"liblist.gam", "valve.rc", "delta.lst"}:
            return None, "generated brig metadata or source-matched network schema"
        return low, "base"
    if group == "valve_russian":
        return low, "base"
    if group == "valve_hd":
        return f"{top}/_Extra/valve_hd/" + "/".join(parts[1:]).lower(), "optional"
    if group == "svencoop_addon":
        if top == "models" and ext in {".mdl", ".bmp"}:
            return "models/svencoop/" + "/".join(parts[1:]).lower(), "addon"
        if top == "sound" and ext in SOUND_EXT:
            return "sound/svencoop/" + "/".join(parts[1:]).lower(), "addon"
        if top == "sprites" and ext == ".spr":
            return low, "addon"
        # Preserve every byte of incompatible map configs/replacement lists,
        # UI definitions and maps without making them engine entry points.
        return "_Extra/svencoop_addon/" + rel.as_posix(), "archive"
    if group.startswith("svencoop_event_"):
        if "models" in parts and ext in {".mdl", ".bmp"}:
            i = parts.index("models")
            variant = "" if i == 0 else "variants/" + hashlib.sha256("/".join(parts[:i]).encode()).hexdigest()[:8] + "/"
            return f"models/{group}/" + variant + "/".join(parts[i + 1:]).lower(), "resource"
        if top == "sound" and ext in SOUND_EXT:
            return f"sound/{group}/" + "/".join(parts[1:]).lower(), "resource"
        return "docs/_Extra/" + group + "/" + rel.as_posix(), "archive"
    if group == "svencoop":
        if top == "models" and ext in {".mdl", ".bmp"}:
            return "models/svencoop/" + "/".join(parts[1:]).lower(), "resource"
        if top == "sound" and ext in SOUND_EXT:
            return "sound/svencoop/" + "/".join(parts[1:]).lower(), "resource"
        if top == "sprites" and ext == ".spr":
            return low, "resource"
        return None, "Sven engine/UI/scripts/maps/configs are not HL1 resources"
    return None, "downloaded map metadata is not an HL1 asset"


def preserve_loops(original: bytes, converted: Path):
    """ffmpeg drops RIFF loop markers; restore them with resampled positions."""
    if original[:4] != b"RIFF" or original[8:12] != b"WAVE":
        return
    chunks = []
    rate = None
    pos = 12
    while pos + 8 <= len(original):
        tag, length = struct.unpack_from("<4sI", original, pos)
        payload = original[pos + 8:pos + 8 + length]
        if tag == b"fmt " and len(payload) >= 8:
            rate = struct.unpack_from("<I", payload, 4)[0]
        if tag in {b"cue ", b"smpl", b"LIST"}:
            chunks.append((tag, bytearray(payload)))
        pos += 8 + length + length % 2
    if not rate:
        return
    for tag, payload in chunks:
        if tag == b"cue " and len(payload) >= 4:
            for i in range(struct.unpack_from("<I", payload)[0]):
                for offset in (8 + i * 24, 24 + i * 24):
                    if offset + 4 <= len(payload):
                        value = struct.unpack_from("<I", payload, offset)[0]
                        struct.pack_into("<I", payload, offset, round(value * 22050 / rate))
        if tag == b"smpl" and len(payload) >= 36:
            struct.pack_into("<I", payload, 8, round(1e9 / 22050))
            for i in range(struct.unpack_from("<I", payload, 28)[0]):
                for offset in (44 + i * 24, 48 + i * 24):
                    if offset + 4 <= len(payload):
                        value = struct.unpack_from("<I", payload, offset)[0]
                        struct.pack_into("<I", payload, offset, round(value * 22050 / rate))
    data = bytearray(converted.read_bytes())
    for tag, payload in chunks:
        data += struct.pack("<4sI", tag, len(payload)) + payload + (b"\0" if len(payload) % 2 else b"")
    struct.pack_into("<I", data, 4, len(data) - 8)
    converted.write_bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remove-source", action="store_true")
    args = parser.parse_args()
    if not SOURCE.is_dir() or TARGET.exists():
        sys.exit("need restock must exist and brig must not exist; refusing to overwrite")
    files = subprocess.check_output(["git", "ls-files", "-z", "--", "_folder/need restock"], cwd=ROOT).decode().rstrip("\0").split("\0")
    entries = {}
    excluded = []
    source_hashes = {}
    converted = 0
    TARGET.mkdir(parents=True)

    def put(source: str, dest: str, kind: str, data: bytes | None = None):
        src = ROOT / source
        dst = TARGET / dest
        dst.parent.mkdir(parents=True, exist_ok=True)
        if data is None:
            shutil.copyfile(src, dst)
        else:
            dst.write_bytes(data)
        entries[dest] = {"source": source, "sha256": digest(dst), "kind": kind}

    def archive(source: str, reason: str):
        rel = PurePosixPath(source).relative_to("_folder/need restock")
        dest = "_Extra/originals/" + rel.as_posix()
        put(source, dest, "archive")
        entries[dest]["reason"] = reason

    priority = {"valve": 0, "valve_russian": 1, "svencoop": 2, "svencoop_addon": 4}
    files.sort(key=lambda p: (priority.get(PurePosixPath(p).parts[2], 3), p))
    for source in files:
        rel = PurePosixPath(source).relative_to("_folder/need restock")
        group, tail = rel.parts[0], PurePosixPath(*rel.parts[1:])
        src = ROOT / source
        source_hashes[source] = digest(src)
        dest, kind = choose(group, tail)
        if dest is None:
            excluded.append({"source": source, "reason": kind})
            continue
        if kind != "archive" and tail.suffix.lower() in SOUND_EXT and len(dest.encode()) >= 64:
            short = hashlib.sha256(dest.encode()).hexdigest()[:16]
            dest = f"sound/svencoop/_long/{short}{tail.suffix.lower()}"
        if kind != "archive" and tail.suffix.lower() in {".mdl", ".spr"}:
            try:
                if len(dest.encode("ascii")) >= 64:
                    raise ValueError("resource path exceeds MAX_QPATH=64")
                if tail.suffix.lower() == ".mdl":
                    model_info(src.read_bytes())
                else:
                    sprite_check(src.read_bytes())
            except (ValueError, UnicodeError, struct.error) as error:
                archive(source, str(error))
                continue
        if dest in entries:
            if not (group == "svencoop_addon" and dest.startswith(("sound/svencoop/", "models/svencoop/"))):
                if group == "svencoop_addon":
                    archive(source, "base sprite is protected")
                else:
                    excluded.append({"source": source, "reason": "base sprite is protected"})
                continue
        if kind != "archive" and tail.suffix.lower() in {".wav", ".ogg"}:
            try:
                if tail.suffix.lower() != ".wav":
                    raise ValueError("OGG needs conversion for steam_legacy")
                wave_check(src)
            except (ValueError, EOFError, __import__("wave").Error):
                archive(source, "unconverted audio original")
                dest = str(PurePosixPath(dest).with_suffix(".wav"))
                dst = TARGET / dest
                dst.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-map_metadata", "-1", "-ac", "1", "-ar", "22050", "-c:a", "pcm_s16le", str(dst)], check=True)
                preserve_loops(src.read_bytes(), dst)
                entries[dest] = {"source": source, "sha256": digest(dst), "kind": kind, "transform": "mono PCM16 22050Hz; RIFF loop markers retained"}
                converted += 1
                continue
        put(source, dest, kind)

    # Update fixed-width MDL sequence/sound paths after moving model families.
    # Sprite binaries never enter this code and remain byte-for-byte identical.
    by_source = {entry["source"].lower(): dest for dest, entry in entries.items() if entry["kind"] != "archive"}
    for dest, entry in list(entries.items()):
        if not dest.endswith(".mdl") or entry["kind"] == "archive":
            continue
        path = TARGET / dest
        data = bytearray(path.read_bytes())
        info = model_info(data)
        if info["kind"] != "model":
            continue
        group = PurePosixPath(entry["source"]).parts[2]
        if group in {"valve", "valve_russian"}:
            continue
        sourcebase = "_folder/need restock/" + group + "/"
        broken = None
        changed = False
        for offset, ref in info["groups"]:
            # Several shipped Sven variants still name models/foo01.mdl in
            # their header although foo01.mdl is beside the variant itself.
            sibling = str(PurePosixPath(entry["source"]).parent / PurePosixPath(ref).name)
            mapped = by_source.get(sibling.lower()) or by_source.get((sourcebase + ref).lower())
            if not mapped or len(mapped.encode()) >= 64:
                broken = "missing or oversized sequence group: " + ref
                break
            data[offset:offset + 64] = mapped.encode().ljust(64, b"\0")
            changed = True
        if info["bodies"] and info["textures"] == 0:
            companion = str(PurePosixPath(dest).with_suffix("")) + "t.mdl"
            if companion not in entries:
                broken = "missing external texture companion"
        for offset, sample in info["sounds"]:
            # Extras use the matching sound option when present, otherwise the
            # integrated Sven collection, then the protected HL sound bank.
            mapped = by_source.get((sourcebase + "sound/" + sample).lower())
            if mapped is None:
                candidate = "sound/svencoop/" + str(PurePosixPath(sample.lower()).with_suffix(".wav"))
                mapped = candidate if candidate in entries else None
            if mapped:
                name = mapped.removeprefix("sound/")
                if len(name.encode()) < 64:
                    data[offset:offset + 64] = name.encode().ljust(64, b"\0")
                    changed = True
        if broken:
            archive(entry["source"], broken)
            path.unlink()
            del entries[dest]
        elif changed:
            path.write_bytes(data)
            entry["sha256"] = digest(path)
            entry["transform"] = "remap fixed-width studio event/sequence resource paths"

    for source, dest in (("network/delta.lst", "delta.lst"), ("LICENSE", "license.txt")):
        put(source, dest, "project")
    defaults = ROOT / "tools/brig-defaults"
    for src in sorted(defaults.rglob("*")):
        if src.is_file():
            dest = src.relative_to(defaults).as_posix()
            put(src.relative_to(ROOT).as_posix(), dest, "project")

    # All addon and Extras originals must still exist, even when a playable
    # representation was converted or its fixed-width model paths changed.
    present_hashes = {entry["sha256"] for entry in entries.values()}
    for source, original_hash in source_hashes.items():
        group = PurePosixPath(source).parts[2]
        if group in {"svencoop_addon", "Extras"} and original_hash not in present_hashes:
            archive(source, "original preserved alongside adapted resource")
            present_hashes.add(original_hash)

    manifest = {"schema": 1, "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "source_files": len(files), "converted_audio": converted,
                "files": dict(sorted(entries.items())), "excluded": excluded,
                "preserved_sources": {source: sha for source, sha in source_hashes.items() if PurePosixPath(source).parts[2] in {"svencoop_addon", "Extras"}}}
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "tools/validate_brig.py")], cwd=ROOT, check=True)
    if args.remove_source:
        shutil.rmtree(SOURCE)
    print(json.dumps({"source_files": len(files), "output_files": len(entries), "converted_audio": converted, "excluded": len(excluded), "source_removed": args.remove_source, "kinds": dict(collections.Counter(x["kind"] for x in entries.values()))}, indent=2))


if __name__ == "__main__":
    main()
