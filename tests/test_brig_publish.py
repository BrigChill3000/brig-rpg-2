import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import publish_brig_release as publish
from brig_assets import digest


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {
            "RELEASE_TAG": "v1.0.0", "RELEASE_COMMIT": "a" * 40,
            "GITHUB_REPOSITORY": "example/brig",
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_annotated_tag_for_another_commit_cannot_be_published(self):
        with patch.object(publish, "gh", side_effect=[
            json.dumps({"object": {"type": "tag", "sha": "c" * 40}}),
            json.dumps({"object": {"type": "commit", "sha": "b" * 40}}),
        ]) as command:
            with self.assertRaisesRegex(ValueError, "different commit"):
                publish.main()
            self.assertEqual(command.call_count, 2)

    def test_existing_release_is_not_overwritten(self):
        with patch.object(publish, "gh", side_effect=[None, '{"id": 123}']) as command:
            with self.assertRaisesRegex(ValueError, "already exists"):
                publish.main()
            self.assertEqual(command.call_count, 2)

    def test_complete_release_is_uploaded_as_draft_before_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            old = Path.cwd()
            try:
                os.chdir(temp)
                Path("dist").mkdir()
                archive = Path("dist/brig-v1.0.0-windows-x86.zip")
                archive.write_bytes(b"fixture artifact from the validated package job")
                archive.with_name(archive.name + ".sha256").write_text(digest(archive) + "  " + archive.name + "\n")
                with patch.object(publish, "gh", side_effect=[None, None, "", ""]) as command, contextlib.redirect_stdout(io.StringIO()):
                    publish.main()
                    create = command.call_args_list[2].args
                    edit = command.call_args_list[3].args
                    self.assertEqual(create[:2], ("release", "create"))
                    self.assertIn("--draft", create)
                    self.assertIn("a" * 40, create)
                    self.assertEqual(edit[:2], ("release", "edit"))
                    self.assertIn("--draft=false", edit)
            finally:
                os.chdir(old)


if __name__ == "__main__":
    unittest.main()
