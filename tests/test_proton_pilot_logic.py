import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("proton_pilot", ROOT / "proton-pilot.py")
proton_pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(proton_pilot)


class ProtonPilotLogicTests(unittest.TestCase):
    def test_compose_does_not_add_mangohud_when_unselected(self):
        command = proton_pilot.compose_launch(
            ["GAMEMODE", "HDR", "WAYLAND", "PROTONHDR", "FSR4", "GAMESCOPE", "REALRES", "ADAPTIVE", "UEHDR"],
            "",
            "",
            {"width": 2560, "height": 1440, "refresh": 180},
        )

        self.assertIn("gamemoderun %command%", command)
        self.assertIn("--hdr-enabled", command)
        self.assertIn("-W 2560 -H 1440 -w 2560 -h 1440 -r 180", command)
        self.assertNotIn("--mangoapp", command)
        self.assertNotIn("mangohud", command)

    def test_unreal_hdr_is_side_effect_only(self):
        command = proton_pilot.compose_launch(["UEHDR"], "", "", {})

        self.assertEqual(command, "%command%")
        self.assertIn("UEHDR", proton_pilot.SIDE_EFFECT_OPTIONS)

    def test_detect_gamescope_resolution(self):
        command = "gamescope -f --force-windows-fullscreen -W 2560 -H 1440 -w 2560 -h 1440 -r 180 -- %command%"

        self.assertEqual(
            proton_pilot.detect_gamescope_resolution(command),
            {"width": 2560, "height": 1440, "refresh": 180},
        )

    def test_detect_flags_do_not_infer_recommended_options(self):
        command = "ENABLE_GAMESCOPE_WSI=1 DXVK_HDR=1 gamescope -f --hdr-enabled -- %command%"
        flags = proton_pilot.detect_flags(command)

        self.assertTrue(flags["HDR"])
        self.assertFalse(flags["MANGOHUD"])
        self.assertFalse(flags["GAMEMODE"])

    def test_vrr_cap_uses_refresh_minus_margin(self):
        command = proton_pilot.compose_launch(
            ["GAMESCOPE", "ADAPTIVE", "CAPVRR"],
            "",
            "",
            {"refresh": 180},
        )

        self.assertIn("--adaptive-sync", command)
        self.assertIn("MANGOHUD_CONFIG=fps_limit=177,no_display", command)
        self.assertIn("gamescope -f", command)
        self.assertIn("-- mangohud %command%", command)
        self.assertNotIn("--framerate-limit 177", command)

    def test_vrr_cap_detection_does_not_confuse_fixed_caps(self):
        self.assertTrue(
            proton_pilot.detect_flags("MANGOHUD_CONFIG=fps_limit=177,no_display gamescope -f -- mangohud %command%")[
                "CAPVRR"
            ]
        )
        self.assertFalse(
            proton_pilot.detect_flags("MANGOHUD_CONFIG=fps_limit=177,no_display gamescope -f -- mangohud %command%")[
                "MANGOHUD"
            ]
        )
        self.assertTrue(proton_pilot.detect_flags("gamescope -f --framerate-limit 177 -- %command%")["CAPVRR"])
        self.assertFalse(proton_pilot.detect_flags("gamescope -f --framerate-limit 72 -- %command%")["CAPVRR"])
        self.assertFalse(proton_pilot.detect_flags("gamescope -f --framerate-limit 60 -- %command%")["CAPVRR"])

    def test_builtin_presets_rebuild_to_expected_features(self):
        config = {}
        proton_pilot.ensure_builtin_presets(config)
        proton_pilot.ensure_game_builtin_presets(config, "1172710")
        proton_pilot.ensure_display_preset(config, "1172710", {"width": 2560, "height": 1440, "refresh": 180})

        for name, preset in config["presets"]["1172710"].items():
            with self.subTest(preset=name):
                rebuilt = proton_pilot.compose_launch(
                    preset.get("options", []),
                    preset.get("custom_pre", ""),
                    preset.get("custom_post", ""),
                    preset.get("gamescope_res", {}),
                )
                options = set(preset.get("options", []))
                self.assertIn("%command%", rebuilt)
                self.assertEqual("--mangoapp" in rebuilt or "mangohud" in rebuilt, "MANGOHUD" in options)
                self.assertEqual("gamemoderun" in rebuilt, "GAMEMODE" in options)
                self.assertEqual("PROTON_FSR4_UPGRADE=1" in rebuilt, "FSR4" in options)

    def test_steam_shortcut_add_and_update_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "Steam"
            cfg = root / "userdata/1/config"
            cfg.mkdir(parents=True)
            (cfg / "localconfig.vdf").write_text('"UserLocalConfigStore"\n{\n\t"apps"\n\t{\n\t}\n}\n')

            added = proton_pilot.add_steam_shortcut(root, "Test Game", "/tmp/Test.exe", "mangohud %command%")
            data = proton_pilot.load_shortcuts(added["path"])
            self.assertEqual(data["shortcuts"]["0"]["AppName"], "Test Game")
            self.assertEqual(data["shortcuts"]["0"]["LaunchOptions"], "mangohud %command%")

            updated = proton_pilot.update_steam_shortcut_launch_options(
                root, "Test Game", "/tmp/Test.exe", "gamemoderun %command%"
            )
            self.assertIsNotNone(updated["backup"])
            data = proton_pilot.load_shortcuts(added["path"])
            self.assertEqual(data["shortcuts"]["0"]["LaunchOptions"], "gamemoderun %command%")

    def test_protondb_tier_helpers(self):
        summary = {"tier": "gold", "total": 182}

        self.assertEqual(proton_pilot.protondb_tier_label(summary), "GOLD")
        self.assertEqual(proton_pilot.protondb_tier_color("gold"), ("#ffe082", "#5f4300"))


if __name__ == "__main__":
    unittest.main()
