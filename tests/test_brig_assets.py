import struct
import sys
import tempfile
import unittest
import wave
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from brig_assets import model_info, pe_check, sprite_check, wave_check
from migrate_brig import choose, extra_path, preserve_loops


class ContentPolicyTests(unittest.TestCase):
    def test_cs_cannot_import_gameplay_even_with_asset_extension(self):
        for group in ("cstrike", "cstrike_hd"):
            for name in ("classes/marine.mdl", "cfg/sound.wav", "maps/arena.bsp", "events/ak47.sc", "models/player/gign/gign.mdl", "Models/PLAYER/leet/leet.mdl", "liblist.gam"):
                self.assertIsNone(choose(group, PurePosixPath(name))[0], (group, name))
            self.assertEqual(choose(group, PurePosixPath("models/v_ak47.mdl"))[0], f"models/{group}/v_ak47.mdl")

    def test_sven_gameplay_is_filtered_and_addon_is_preserved_inactive(self):
        for name in ("scripts/plugins/assistant.as", "maps/custom.bsp", "server.cfg", "resource/GameMenu.res"):
            self.assertIsNone(choose("svencoop", PurePosixPath(name))[0])
            dest, kind = choose("svencoop_addon", PurePosixPath(name))
            self.assertEqual(kind, "archive")
            self.assertTrue(dest.startswith("_Extra/svencoop_addon/"))

    def test_addon_overlays_the_same_sven_audio_namespace(self):
        rel = PurePosixPath("sound/weapons/reload.wav")
        self.assertEqual(choose("svencoop", rel)[0], choose("svencoop_addon", rel)[0])
        self.assertEqual(choose("svencoop", rel)[0], "sound/svencoop/weapons/reload.wav")

    def test_event_variants_cannot_replace_base_models(self):
        for group in ("svencoop_event_xmas", "svencoop_event_anniv"):
            self.assertEqual(choose(group, PurePosixPath("models/v_crowbar.mdl"))[0], f"models/{group}/v_crowbar.mdl")

    def test_extra_variants_are_short_distinct_and_keep_companions_together(self):
        a = PurePosixPath("1 - Weapons and Arms Options/Very Long Optional Variant Name/models/v_test.mdl")
        b = a.with_name("v_testt.mdl")
        self.assertLess(len(extra_path(a)), 64)
        self.assertEqual(PurePosixPath(extra_path(a)).parent, PurePosixPath(extra_path(b)).parent)
        self.assertNotEqual(extra_path(a), extra_path(PurePosixPath("2 - NPC Options/Other/models/v_test.mdl")))


class BinaryChecks(unittest.TestCase):
    def test_sprite_pixels_are_validated_not_just_magic(self):
        header = struct.pack("<4siiifiiifiH", b"IDSP", 2, 2, 0, 1.0, 2, 2, 1, 0.0, 0, 256)
        sprite = header + bytes(768) + struct.pack("<iiiii", 0, 0, 0, 2, 2) + bytes(4)
        sprite_check(sprite)
        with self.assertRaises(ValueError):
            sprite_check(sprite[:-1])

    def test_legacy_model_version_and_length_are_required(self):
        data = bytearray(76)
        struct.pack_into("<4si", data, 0, b"IDSQ", 10)
        struct.pack_into("<i", data, 72, 76)
        self.assertEqual(model_info(data)["kind"], "sequence")
        struct.pack_into("<i", data, 4, 9)
        with self.assertRaises(ValueError):
            model_info(data)

    def test_stereo_audio_is_rejected_before_packaging(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "test.wav"
            with wave.open(str(path), "wb") as wav:
                wav.setparams((2, 2, 22050, 0, "NONE", "not compressed"))
                wav.writeframes(bytes(64))
            with self.assertRaises(ValueError):
                wave_check(path)

    def test_resampling_keeps_loop_cue_position(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "test.wav"
            with wave.open(str(path), "wb") as wav:
                wav.setparams((1, 2, 22050, 0, "NONE", "not compressed"))
                wav.writeframes(bytes(64))
            original = bytearray(path.read_bytes())
            struct.pack_into("<I", original, 24, 44100)
            cue = struct.pack("<III4sIII", 1, 1, 200, b"data", 0, 0, 200)
            original += b"cue " + struct.pack("<I", len(cue)) + cue
            preserve_loops(original, path)
            result = path.read_bytes()
            pos = result.index(b"cue ") + 8
            self.assertEqual(struct.unpack_from("<I", result, pos + 24)[0], 100)

    def test_missing_dll_is_never_a_valid_release(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "client.dll"
            path.write_bytes(b"not a DLL")
            with self.assertRaises(ValueError):
                pe_check(path, ("Initialize",))


if __name__ == "__main__":
    unittest.main()
