"""Reproduce Windows Git autocrlf behavior on any CI host."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class CheckoutBytesTests(unittest.TestCase):
    def test_windows_checkout_preserves_audited_resource_bytes(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            shutil.copyfile(root / ".gitattributes", repo / ".gitattributes")
            fixtures = {
                "_folder/brig/events/crowbar.sc": b"event\nline\n",
                "_folder/brig/_Extra/addon/maps/map.cfg": b"archived\nconfig\n",
                "_folder/brig/sprites/test.spr": b"IDSP\0\x02\n\x80\x00\xff\n",
                "network/delta.lst": b"clientdata_t none\n{\n}\n",
                "tools/brig-defaults/default.cfg": b'bind "w" "+forward"\n',
            }
            for name, data in fixtures.items():
                path = repo / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)

            def git(*args):
                subprocess.run(["git", "-C", str(repo), *args], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

            git("init", "-q")
            git("config", "core.autocrlf", "true")
            git("add", ".")
            for name in fixtures:
                (repo / name).unlink()
            git("checkout-index", "--all")
            for name, data in fixtures.items():
                self.assertEqual((repo / name).read_bytes(), data, name)


if __name__ == "__main__":
    unittest.main()
