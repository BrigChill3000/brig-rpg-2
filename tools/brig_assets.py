"""GoldSource resource checks shared by migration, CI and release packaging."""
from __future__ import annotations

import hashlib
import struct
import wave
from pathlib import Path


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def cstring(data: bytes) -> str:
    return data.split(b"\0", 1)[0].decode("ascii", errors="replace").replace("\\", "/")


def model_info(data: bytes) -> dict:
    if len(data) < 76 or data[:4] not in (b"IDST", b"IDSQ"):
        raise ValueError("not a GoldSource studio model")
    if struct.unpack_from("<i", data, 4)[0] != 10:
        raise ValueError("studio version is not 10")
    length = struct.unpack_from("<i", data, 72)[0]
    if length != len(data):
        raise ValueError("studio length does not match file size")
    if data[:4] == b"IDSQ":
        return {"kind": "sequence", "groups": [], "sounds": [], "textures": 0}
    if len(data) < 244:
        raise ValueError("truncated studio header")
    bones, boneoff, controllers, controloff, hitboxes, hitoff, seqs, seqoff, groups, groupoff = struct.unpack_from("<10i", data, 140)
    textures, texoff, texdata, skinrefs, families, skinoff, bodies, bodyoff, attachments, attachoff = struct.unpack_from("<10i", data, 180)

    def bounds(count: int, offset: int, size: int, maximum: int):
        if count < 0 or count > maximum or (count and (offset < 0 or offset + count * size > len(data))):
            raise ValueError("studio table exceeds legacy limits or file bounds")

    bounds(bones, boneoff, 112, 128)
    bounds(controllers, controloff, 24, 8)
    bounds(hitboxes, hitoff, 32, 1024)
    bounds(seqs, seqoff, 176, 2048)
    bounds(groups, groupoff, 104, 16)
    bounds(textures, texoff, 80, 100)
    bounds(bodies, bodyoff, 76, 32)
    bounds(attachments, attachoff, 88, 32)
    refs = []
    sounds = []
    for i in range(1, groups):
        pos = groupoff + i * 104 + 32
        refs.append((pos, cstring(data[pos:pos + 64])))
    for i in range(seqs):
        pos = seqoff + i * 176
        events, eventoff = struct.unpack_from("<ii", data, pos + 48)
        bounds(events, eventoff, 76, 1024)
        for j in range(events):
            eventpos = eventoff + j * 76
            event = struct.unpack_from("<i", data, eventpos + 4)[0]
            sample = cstring(data[eventpos + 12:eventpos + 76])
            if event in (1004, 1008, 5004) and sample.lower().endswith((".wav", ".ogg")):
                sounds.append((eventpos + 12, sample))
    for i in range(bodies):
        count, _, offset = struct.unpack_from("<iii", data, bodyoff + i * 76 + 64)
        bounds(count, offset, 112, 32)
        for j in range(count):
            vertices = struct.unpack_from("<i", data, offset + j * 112 + 80)[0]
            if vertices < 0 or vertices > 2048:
                raise ValueError("submodel exceeds MAXSTUDIOVERTS=2048")
    return {"kind": "model", "groups": refs, "sounds": sounds, "textures": textures, "bodies": bodies}


def sprite_check(data: bytes):
    if len(data) < 42 or data[:4] != b"IDSP" or struct.unpack_from("<i", data, 4)[0] != 2:
        raise ValueError("not a GoldSource v2 sprite")
    typ, fmt = struct.unpack_from("<ii", data, 8)
    width, height, frames = struct.unpack_from("<iii", data, 20)
    colors = struct.unpack_from("<H", data, 40)[0]
    if typ not in range(5) or fmt not in range(4) or not (0 < width <= 512 and 0 < height <= 512 and 0 < frames <= 10000 and 0 < colors <= 256):
        raise ValueError("sprite header exceeds legacy limits")
    pos = 42 + colors * 3

    def frame():
        nonlocal pos
        if pos + 16 > len(data):
            raise ValueError("truncated sprite frame")
        w, h = struct.unpack_from("<ii", data, pos + 8)
        if not (0 < w <= width and 0 < h <= height):
            raise ValueError("invalid sprite frame dimensions")
        pos += 16 + w * h
        if pos > len(data):
            raise ValueError("truncated sprite pixels")

    for _ in range(frames):
        if pos + 4 > len(data):
            raise ValueError("truncated sprite frame type")
        kind = struct.unpack_from("<i", data, pos)[0]
        pos += 4
        if kind == 0:
            frame()
        elif kind == 1:
            count = struct.unpack_from("<i", data, pos)[0]
            pos += 4
            if not 0 < count <= 10000 or pos + count * 4 > len(data):
                raise ValueError("invalid sprite group")
            intervals = struct.unpack_from(f"<{count}f", data, pos)
            if any(t <= 0 for t in intervals):
                raise ValueError("invalid sprite intervals")
            pos += count * 4
            for _ in range(count):
                frame()
        else:
            raise ValueError("unknown sprite frame type")
    if pos != len(data):
        raise ValueError("unexpected trailing sprite data")


def wave_check(path: Path):
    with wave.open(str(path), "rb") as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() not in (1, 2) or wav.getframerate() not in (11025, 22050, 44100):
            raise ValueError("requires mono PCM WAV at 11025/22050/44100 Hz, 8/16 bit")
        size = wav.getnframes() * wav.getnchannels() * wav.getsampwidth()
        if len(wav.readframes(wav.getnframes())) != size:
            raise ValueError("truncated WAV data")


def pe_check(path: Path, required_exports: tuple[str, ...]):
    data = path.read_bytes()
    if data[:2] != b"MZ" or len(data) < 64:
        raise ValueError(f"{path}: missing Windows DLL")
    pe = struct.unpack_from("<I", data, 60)[0]
    if data[pe:pe + 4] != b"PE\0\0" or struct.unpack_from("<H", data, pe + 4)[0] != 0x14C:
        raise ValueError(f"{path}: expected Win32 x86 PE")
    flags = struct.unpack_from("<H", data, pe + 22)[0]
    if not flags & 0x2000 or struct.unpack_from("<H", data, pe + 24)[0] != 0x10B:
        raise ValueError(f"{path}: expected a PE32 DLL")
    # Export names are also checked after the linker has produced the DLL; never
    # accept an empty placeholder or a Sven/CS game binary as a release payload.
    for export in required_exports:
        if export.encode() + b"\0" not in data:
            raise ValueError(f"{path}: missing export {export}")
