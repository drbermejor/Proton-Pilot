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

    def test_custom_launch_option_can_add_pre_gamescope_and_post_args(self):
        option = {
            "id": "custom-test",
            "pre": "PROTON_LOG=1",
            "gamescope": "--expose-wayland",
            "post": "-NoLauncher",
        }
        key = proton_pilot.custom_option_key(option)

        command = proton_pilot.compose_launch([key], "", "", {}, [option])

        self.assertIn("PROTON_LOG=1", command)
        self.assertIn("gamescope -f --expose-wayland --", command)
        self.assertIn("%command% -NoLauncher", command)
        self.assertTrue(proton_pilot.custom_option_matches_command(option, command))

    def test_update_check_only_treats_higher_version_as_newer(self):
        self.assertTrue(proton_pilot.is_newer_version("0.10.3", "0.10.2"))
        self.assertFalse(proton_pilot.is_newer_version("0.10.1", "0.10.2"))
        self.assertFalse(proton_pilot.is_newer_version("0.10.2", "0.10.2"))

    def test_launch_option_categories_are_goal_oriented(self):
        self.assertEqual(
            proton_pilot.OPTION_GROUP_TITLES,
            [
                "Base y rendimiento",
                "Gamescope, pantalla y VRR",
                "HDR",
                "Escalado y handheld",
                "Compatibilidad avanzada",
                "Personalizadas / otros",
            ],
        )
        self.assertEqual(proton_pilot.normalize_option_category("Pantalla, HDR y Gamescope"), "Gamescope, pantalla y VRR")
        self.assertEqual(proton_pilot.normalize_option_category("Categoria rara"), "Personalizadas / otros")

    def test_detect_gamescope_resolution(self):
        command = "gamescope -f --force-windows-fullscreen -W 2560 -H 1440 -w 2560 -h 1440 -r 180 -- %command%"

        self.assertEqual(
            proton_pilot.detect_gamescope_resolution(command),
            {"width": 2560, "height": 1440, "refresh": 180},
        )

    def test_detect_flags_do_not_infer_recommended_options(self):
        command = "ENABLE_HDR_WSI=1 ENABLE_GAMESCOPE_WSI=1 DXVK_HDR=1 gamescope -f --hdr-enabled -- %command%"
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

    def test_empty_launch_options_match_plain_command(self):
        self.assertTrue(proton_pilot.launch_commands_equivalent("", "%command%"))
        self.assertTrue(proton_pilot.launch_commands_equivalent("   ", " %command% "))
        self.assertFalse(proton_pilot.launch_commands_equivalent("", "gamemoderun %command%"))

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

    def test_compat_tool_mapping_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "config.vdf"
            config.write_text(
                '"InstallConfigStore"\n{\n\t"Software"\n\t{\n\t\t"Valve"\n\t\t{\n\t\t\t"Steam"\n\t\t\t{\n\t\t\t\t"CompatToolMapping"\n\t\t\t\t{\n\t\t\t\t}\n\t\t\t}\n\t\t}\n\t}\n}\n'
            )

            proton_pilot.set_compat_tool(config, "1172710", "GE-Proton10-34")
            text = config.read_text()
            self.assertEqual(proton_pilot.current_compat_tool(text, "1172710"), "GE-Proton10-34")

            proton_pilot.set_compat_tool(config, "1172710", "")
            text = config.read_text()
            self.assertEqual(proton_pilot.current_compat_tool(text, "1172710"), "")

    def test_recommends_cachy_proton_on_cachyos(self):
        system = {
            "os": {"id": "cachyos", "name": "CachyOS"},
            "gpu": "amd",
            "session": {"type": "wayland"},
            "display": {"hdr": "enabled"},
        }
        tools = [
            {"name": "GE-Proton10-34", "compat": "GE-Proton10-34"},
            {"name": "proton-cachyos-11.0", "compat": "proton-cachyos-slr"},
        ]

        self.assertEqual(proton_pilot.recommended_proton_tool(system, tools), "proton-cachyos-slr")

    def test_external_icon_cache_path_is_stable_per_exe(self):
        first = proton_pilot.external_icon_cache_path(Path("/games/One/Game.exe"))
        second = proton_pilot.external_icon_cache_path(Path("/games/One/Game.exe"))
        other = proton_pilot.external_icon_cache_path(Path("/games/Two/Game.exe"))

        self.assertEqual(first, second)
        self.assertNotEqual(first, other)
        self.assertEqual(first.suffix, ".png")
        self.assertIn("icons", first.parts)

    def test_protondb_tier_helpers(self):
        summary = {"tier": "gold", "total": 182}

        self.assertEqual(proton_pilot.protondb_tier_label(summary), "GOLD")
        self.assertEqual(proton_pilot.protondb_tier_color("gold"), ("#ffd54f", "#4e3500"))
        self.assertEqual(proton_pilot.protondb_tier_color("platinum"), ("#e5e4e2", "#263238"))

    def test_system_recommends_vrr_and_hdr_when_available(self):
        system = {
            "tools": {"gamemoderun": True, "mangohud": True, "gamescope": True},
            "gamescope_wsi": True,
            "session": {"type": "wayland"},
            "display": {"width": 2560, "height": 1440, "refresh": 180, "hdr": "enabled", "vrr": "automatic"},
            "device": {"is_handheld": False},
            "gpu": "amd",
        }

        keys = proton_pilot.system_recommended_keys(system)

        self.assertIn("HDR", keys)
        self.assertIn("PROTONHDR", keys)
        self.assertIn("ADAPTIVE", keys)
        self.assertIn("CAPVRR", keys)
        self.assertTrue(proton_pilot.display_hdr_enabled(system["display"]))
        self.assertTrue(proton_pilot.display_vrr_available(system["display"]))

    def test_system_preset_contains_detected_recommended_options(self):
        system = {
            "tools": {"gamemoderun": True, "mangohud": True, "gamescope": True},
            "gamescope_wsi": True,
            "session": {"type": "wayland"},
            "display": {"width": 2560, "height": 1440, "refresh": 180, "hdr": "enabled", "vrr": "automatic"},
            "device": {"is_handheld": False},
            "gpu": "amd",
        }
        config = {}

        proton_pilot.ensure_system_shared_preset(config, system)
        preset = config["shared_presets"][proton_pilot.system_preset_name()]

        self.assertIn("HDR", preset["options"])
        self.assertIn("CAPVRR", preset["options"])
        self.assertIn("MANGOHUD_CONFIG=fps_limit=177", preset["command"])
        self.assertEqual(preset["gamescope_res"]["width"], 2560)

    def test_clean_gpu_name_prefers_human_readable_bracket(self):
        line = "03:00.0 VGA compatible controller: Advanced Micro Devices, Inc. [AMD/ATI] Navi 48 [Radeon RX 9070/9070 XT/9070 GRE] [1002:7550] (rev c0)"

        self.assertEqual(proton_pilot.clean_gpu_name(line), "Radeon RX 9070/9070 XT/9070 GRE")


if __name__ == "__main__":
    unittest.main()
