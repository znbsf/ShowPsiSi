"""Targeted WCAG contrast regression for authored workbench tokens.

This is not an accessibility-conformance audit. Native platform rendering,
assistive technology and every semantic/disabled state need separate validation.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


def luminance(color):
    rgb = [int(color[i:i+2], 16) / 255 for i in (1, 3, 5)]
    return sum((c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4) * weight
               for c, weight in zip(rgb, (0.2126, 0.7152, 0.0722)))


def contrast(first, second):
    high, low = sorted((luminance(first), luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


class WorkbenchContrastTests(unittest.TestCase):
    def test_web_authored_text_focus_and_input_tokens(self):
        css = (ROOT / 'ui/tauri/web/style.css').read_text()
        tokens = dict(re.findall(r'--([\w-]+):\s*(#[\da-fA-F]{6})', css))
        for foreground in ('text', 'muted', 'green', 'red'):
            for background in ('bg', 'surface', 'raised', 'selected'):
                with self.subTest(foreground=foreground, background=background):
                    self.assertGreaterEqual(contrast(tokens[foreground], tokens[background]), 4.5)
        for background in ('bg', 'surface', 'raised', 'selected'):
            self.assertGreaterEqual(contrast(tokens['accent'], tokens[background]), 3)
        self.assertGreaterEqual(contrast(tokens['control-border-hover'], '#35445a'), 3)
        for background in ('#14181e', '#2a3341'):
            self.assertGreaterEqual(contrast(tokens['control-border'], background), 3)

    def test_qt_authored_text_focus_and_input_tokens(self):
        qml = (ROOT / 'ui/qt/Main.qml').read_text()
        tokens = dict(re.findall(r'property color (\w+):\s*"(#[\da-fA-F]{6})"', qml))
        for foreground in ('ink', 'muted', 'addedColor', 'removedColor', 'changedColor'):
            for background in ('#181818', '#1f1f1f', '#37373d', '#04395e'):
                with self.subTest(foreground=foreground, background=background):
                    self.assertGreaterEqual(contrast(tokens[foreground], background), 4.5)
        for background in ('#181818', '#252526', '#37373d', '#04395e'):
            self.assertGreaterEqual(contrast(tokens['blue'], background), 3)
        for background in ('#181818', '#252526'):
            self.assertGreaterEqual(contrast(tokens['controlBorder'], background), 3)
        # String values and primary button labels include focus/hover backgrounds.
        string_color = re.search(r'modelData.kind === "string" \? "(#[\da-f]{6})"', qml).group(1)
        self.assertGreaterEqual(contrast(string_color, '#37373d'), 4.5)
        for background in re.findall(r'control.hovered \? "(#[\da-f]{6})" : "(#[\da-f]{6})"', qml)[0]:
            self.assertGreaterEqual(contrast('#ffffff', background), 4.5)


if __name__ == '__main__':
    unittest.main()
