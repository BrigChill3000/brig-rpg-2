"""Fail CI/release packaging on missing, changed or incompatible brig assets."""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
import wave
from pathlib import Path, PurePosixPath

from brig_assets import cstring, digest, model_info, pe_check, sprite_check, wave_check

ROOT = Path(__file__).resolve().parents[1]


def validate(mod: Path, manifest: Path, require_dlls: bool = False) -> dict:
    audit = json.loads(manifest.read_text(encoding="utf-8"))
    errors = []
    # File synchronization tools may keep dot-prefixed partial copies beside
    # large assets. They are never engine resources or release payload files.
    actual = {p.relative_to(mod).as_posix(): p for p in mod.rglob("*")
              if p.is_file() and not any(part.startswith(".") for part in p.relative_to(mod).parts)}
    expected = audit["files"]
    folded = {}
    counts = {"models": 0, "sprites": 0, "waves": 0, "maps": 0}
    for name, path in actual.items():
        if path.is_symlink() or name.lower() in folded:
            errors.append(f"symlink or case-insensitive duplicate: {name}")
        folded[name.lower()] = name
    generated = {"cl_dlls/client.dll", "dlls/hl.dll", "BUILD.json"}
    for name in sorted(actual.keys() - expected.keys() - generated):
        errors.append(f"untracked payload: {name}")
    for name, record in expected.items():
        path = actual.get(name)
        if path is None:
            errors.append(f"missing resource: {name}")
            continue
        if digest(path) != record["sha256"]:
            errors.append(f"checksum changed: {name}")
        source = PurePosixPath(record["source"])
        if "need restock" in source.parts and len(source.parts) >= 4 and source.parts[2] in {"cstrike", "cstrike_hd"}:
            tail = source.parts[3:]
            if tail[0].lower() not in {"models", "sound"} or (tail[0].lower() == "models" and len(tail) > 1 and tail[1].lower() == "player"):
                errors.append(f"forbidden CS source: {source}")
        if record["kind"] == "archive":
            if not (name.startswith("_Extra/") or "/_Extra/" in name):
                errors.append(f"archive in active path: {name}")
            continue
        ext = path.suffix.lower()
        try:
            if ext in {".mdl", ".spr", ".wav"} and len(name.encode("ascii")) >= 64:
                raise ValueError("path exceeds MAX_QPATH=64")
            if ext == ".mdl":
                info = model_info(path.read_bytes())
                counts["models"] += 1
                if info["kind"] == "model":
                    for _, ref in info["groups"]:
                        if ref.lower() not in folded:
                            raise ValueError(f"missing sequence group {ref}")
                    if info["bodies"] and info["textures"] == 0:
                        companion = str(PurePosixPath(name).with_suffix("")) + "t.mdl"
                        if companion.lower() not in folded:
                            raise ValueError(f"missing texture companion {companion}")
            elif ext == ".spr":
                sprite_check(path.read_bytes())
                counts["sprites"] += 1
            elif ext == ".wav":
                wave_check(path)
                counts["waves"] += 1
            elif ext == ".ogg":
                raise ValueError("OGG is not playable by steam_legacy")
            elif ext == ".bsp":
                data = path.read_bytes()
                if len(data) < 124 or struct.unpack_from("<i", data)[0] != 30:
                    raise ValueError("expected GoldSource BSP v30")
                for i in range(15):
                    start, size = struct.unpack_from("<ii", data, 4 + i * 8)
                    if start < 0 or size < 0 or start + size > len(data):
                        raise ValueError("BSP lump outside file")
                counts["maps"] += 1
        except (ValueError, struct.error, wave.Error, EOFError, UnicodeError) as error:
            errors.append(f"{name}: {error}")
    present = {x["sha256"] for x in expected.values()}
    for source, sha in audit["preserved_sources"].items():
        if sha not in present:
            errors.append(f"original addon/Extras file was lost: {source}")
    for name in ("liblist.gam", "valve.rc", "default.cfg", "skill.cfg", "delta.lst", "titles.txt", "maps/c0a0.bsp", "maps/t0a0.bsp", "maps/crossfire.bsp", "sprites/hud.txt", "models/player.mdl"):
        if name not in actual:
            errors.append(f"required startup file missing: {name}")
    info = (mod / "liblist.gam").read_text(encoding="utf-8")
    for key, val in (("game", "Brig RPG 2"), ("gamedll", "dlls\\hl.dll"), ("startmap", "c0a0"), ("trainmap", "t0a0")):
        if not re.search(rf'^\s*{key}\s+"{re.escape(val)}"', info, re.M):
            errors.append(f"incorrect liblist.gam {key}")
    if (mod / "delta.lst").read_bytes() != (ROOT / "network/delta.lst").read_bytes():
        errors.append("delta.lst does not match the source network schema")
    if any(name in actual for name in ("config.cfg", "autoexec.cfg", "steam_autocloud.vdf")):
        errors.append("personal configuration included")
    # HUD definitions reference SPR basenames; verify both 320/640 variants.
    for text in (mod / "sprites").glob("*.txt"):
        for line in text.read_text(errors="replace").splitlines():
            row = line.split()
            if len(row) >= 7 and row[1] in {"320", "640"} and "sprites/" + row[2].lower() + ".spr" not in folded:
                errors.append(f"{text.name}: missing sprite {row[2]}")
    if require_dlls:
        for name, exports in (("cl_dlls/client.dll", ("Initialize", "HUD_Init", "HUD_VidInit")), ("dlls/hl.dll", ("GiveFnptrsToDll", "GetEntityAPI2"))):
            try:
                pe_check(mod / name, exports)
            except (ValueError, OSError, struct.error) as error:
                errors.append(str(error))
    if errors:
        raise ValueError("\n".join(errors[:80]) + (f"\n... {len(errors)} errors total" if len(errors) > 80 else ""))
    return {"files": len(actual), **counts, "preserved_originals": len(audit["preserved_sources"]), "dlls_required": require_dlls}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mod", type=Path, default=ROOT / "_folder/brig")
    parser.add_argument("--manifest", type=Path, default=ROOT / "docs/brig-assets.json")
    parser.add_argument("--require-dlls", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(validate(args.mod, args.manifest, args.require_dlls), indent=2))
    except (ValueError, OSError) as error:
        sys.exit(str(error))


if __name__ == "__main__":
    main()
