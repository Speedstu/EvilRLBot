"""Appearance editing: reading and writing v4 looks.cfg and v5 loadout.toml."""
from __future__ import annotations

import shutil
import tempfile
import tomllib
import unittest
from pathlib import Path

from ui import loadout

ROOT = Path(__file__).resolve().parents[1]


class LoadoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_v4_round_trip_keeps_comments(self):
        bot = self.tmp / "v4"
        shutil.copytree(ROOT / "legacy_bot", bot)
        (bot / "looks.cfg").write_text("# keep me\n" + (bot / "looks.cfg").read_text())
        data = loadout.load(bot / "bot.cfg")
        self.assertEqual(23, data["blue"]["car_id"])
        self.assertEqual(3, data["orange"]["team_color_id"])
        data["blue"]["car_id"] = 403
        data["orange_paint"]["wheels_paint_id"] = 1
        loadout.save(bot / "bot.cfg", data)
        text = (bot / "looks.cfg").read_text()
        self.assertIn("# keep me", text)
        self.assertIn("primary_color_lookup = None", text)
        again = loadout.load(bot / "bot.cfg")
        self.assertEqual(403, again["blue"]["car_id"])
        self.assertEqual(23, again["orange"]["car_id"])
        self.assertEqual(1, again["orange_paint"]["wheels_paint_id"])

    def test_v5_round_trip_is_valid_toml(self):
        bot = self.tmp / "v5"
        bot.mkdir()
        shutil.copy2(ROOT / "src/bot.toml", bot / "bot.toml")
        shutil.copy2(ROOT / "src/loadout.toml", bot / "loadout.toml")
        data = loadout.load(bot / "bot.toml")
        data["orange"]["boost_id"] = 63
        data["blue_paint"]["car_paint_id"] = 5
        loadout.save(bot / "bot.toml", data)
        parsed = tomllib.loads((bot / "loadout.toml").read_text())
        self.assertEqual(63, parsed["orange_loadout"]["boost_id"])
        self.assertEqual(5, parsed["blue_loadout"]["paint"]["car_paint_id"])
        self.assertIn("# Car type", (bot / "loadout.toml").read_text())

    def test_missing_loadout_is_created_and_referenced(self):
        bot = self.tmp / "bare"
        bot.mkdir()
        (bot / "bot.toml").write_text('[settings]\nname = "Bare"\nagent_id = "x/bare"\n')
        data = loadout.load(bot / "bot.toml")
        data["blue"]["car_id"] = 4284
        loadout.save(bot / "bot.toml", data)
        settings = tomllib.loads((bot / "bot.toml").read_text())["settings"]
        self.assertEqual("loadout.toml", settings["loadout_file"])
        self.assertEqual(4284, loadout.load(bot / "bot.toml")["blue"]["car_id"])

    def test_items_and_decals(self):
        self.assertEqual("Octane", loadout.item_name("Body", 23))
        decals = dict(loadout.decals_for(23))
        self.assertTrue(decals)
        self.assertNotIn(288, decals)  # "Backfire: Flames" does not fit an Octane
        data = {k: dict(v) for k, v in loadout.DEFAULT.items()}
        loadout.randomize("blue", data)
        car = data["blue"]["car_id"]
        self.assertIn(data["blue"]["decal_id"], dict(loadout.decals_for(car)) | {0: ""})


if __name__ == "__main__":
    unittest.main()
