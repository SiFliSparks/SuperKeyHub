import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from custom_key_manager import (
    CustomKeyManager,
    KeyCode,
    Modifier,
    get_modifier_display_name,
    get_modifier_options,
)


class CustomKeyManagerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.config_path = Path(self.temp_dir.name) / "custom_keys.json"
        path_patch = patch.object(
            CustomKeyManager, "_get_config_path", return_value=self.config_path
        )
        path_patch.start()
        self.addCleanup(path_patch.stop)

    def test_modifier_options_cover_every_hid_modifier_combination(self) -> None:
        options = get_modifier_options()

        self.assertEqual(len(options), 16)
        self.assertEqual({value for _, value in options}, set(range(16)))
        self.assertEqual(
            sum(value == Modifier.GUI | Modifier.SHIFT for _, value in options),
            1,
        )

    def test_gui_shift_uses_platform_appropriate_name(self) -> None:
        for system_name, expected_name in (
            ("Darwin", "Cmd+Shift"),
            ("Windows", "Win+Shift"),
        ):
            with (
                self.subTest(system_name=system_name),
                patch("custom_key_manager.platform.system", return_value=system_name),
            ):
                self.assertEqual(
                    get_modifier_display_name(Modifier.GUI | Modifier.SHIFT),
                    expected_name,
                )
                self.assertIn(
                    (expected_name, Modifier.GUI | Modifier.SHIFT),
                    get_modifier_options(),
                )

    def test_gui_shift_combo_is_saved_displayed_and_encoded(self) -> None:
        manager = CustomKeyManager()
        modifier = Modifier.GUI | Modifier.SHIFT

        self.assertTrue(manager.set_combo(0, 0, modifier, KeyCode.N4))
        self.assertTrue(manager.config.keys[0].enabled)
        self.assertIn("Shift", manager.get_combo_display_text(0, 0))
        self.assertIn("4", manager.get_combo_display_text(0, 0))
        self.assertEqual(
            manager.generate_command(0),
            'sys_set custom_key "0,0,0x0A,0x21,0x00,0x00,0x00,0x00,0x00,0x00"',
        )

        reloaded_manager = CustomKeyManager()
        self.assertEqual(reloaded_manager.get_combo(0, 0), (modifier, KeyCode.N4))


if __name__ == "__main__":
    unittest.main()
