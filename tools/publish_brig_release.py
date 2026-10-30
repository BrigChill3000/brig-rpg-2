"""Publish only verified archives, with tag-to-commit checks and no overwrites."""
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from brig_assets import digest


def gh(*args, allow_missing=False):
    result = subprocess.run(["gh", *args], text=True, capture_output=True)
    if result.returncode:
        if allow_missing and "HTTP 404" in result.stderr:
            return None
        raise RuntimeError(result.stderr)
    return result.stdout


def main():
    tag = os.environ["RELEASE_TAG"]
    commit = os.environ["RELEASE_COMMIT"]
    repo = os.environ["GITHUB_REPOSITORY"]
    if not re.fullmatch(r"v[A-Za-z0-9][A-Za-z0-9._-]{0,79}", tag) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("invalid tag or commit")
    prefix = f"repos/{repo}"
    reference = gh("api", f"{prefix}/git/ref/tags/{tag}", allow_missing=True)
    if reference:
        obj = json.loads(reference)["object"]
        while obj["type"] == "tag":
            obj = json.loads(gh("api", f"{prefix}/git/tags/{obj['sha']}"))["object"]
        if obj["type"] != "commit" or obj["sha"] != commit:
            raise ValueError("tag points to a different commit; refusing to publish mismatched DLLs/assets")
    # An existing release is deliberately never overwritten by a manual run.
    if gh("api", f"{prefix}/releases/tags/{tag}", allow_missing=True):
        raise ValueError("release already exists; choose a new version tag")
    archive = Path("dist") / f"brig-{tag}-windows-x86.zip"
    checksum = archive.with_name(archive.name + ".sha256")
    if checksum.read_text(encoding="ascii").strip() != digest(archive) + "  " + archive.name:
        raise ValueError("downloaded release archive checksum mismatch")
    notes = f"""Install: extract `brig/` beside `hl.exe` in your Steam Half-Life installation, select **steam_legacy**, restart Steam, then run **Brig RPG 2** or `hl.exe -game brig -console`.

Includes the mod resources and both Windows x86 game DLLs compiled from `{commit}`. The Steam Half-Life engine is required. Sven Co-op and Counter-Strike installations are not required.

SHA-256 is attached beside the ZIP. Preserved `_Extra` options are inactive; unsupported Sven maps/configs are archived and never loaded as HL1 gameplay. CI checks assets, DLL format and ZIP CRC; a real steam_legacy in-game smoke test is still required.
"""
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "notes.md"
        path.write_text(notes, encoding="utf-8")
        # Upload everything while draft, then expose the complete release.
        gh("release", "create", tag, str(archive), str(checksum), "--repo", repo, "--target", commit,
           "--draft", "--title", f"Brig RPG 2 {tag}", "--notes-file", str(path))
        print(gh("release", "edit", tag, "--repo", repo, "--draft=false"))


if __name__ == "__main__":
    main()
