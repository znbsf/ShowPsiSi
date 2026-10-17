"""Dependency-free icon structure, resource wiring and distribution checks."""
import json
from pathlib import Path
import struct
import unittest
import xml.etree.ElementTree as ET
import zlib

ROOT = Path(__file__).resolve().parents[1]
ICONS = ROOT / 'assets/icons'
SIZES = (16, 24, 32, 48, 64, 128, 256)


def png_size(data):
    assert data[:8] == b'\x89PNG\r\n\x1a\n'
    width, height, depth, color = struct.unpack('>IIBB', data[16:26])
    assert (depth, color) == (8, 6), 'RGBA icon required'
    offset = 8
    while offset < len(data):
        length, = struct.unpack('>I', data[offset:offset + 4])
        chunk = data[offset + 4:offset + 8 + length]
        expected, = struct.unpack('>I', data[offset + 8 + length:offset + 12 + length])
        assert zlib.crc32(chunk) == expected, 'Corrupt PNG chunk'
        offset += 12 + length
    assert offset == len(data)
    return width, height


class ApplicationIconTests(unittest.TestCase):
    def test_svg_is_original_self_contained_vector(self):
        svg = ET.parse(ICONS / 'showpsisi.svg').getroot()
        self.assertEqual(svg.attrib['viewBox'], '0 0 256 256')
        for element in svg.iter():
            self.assertNotIn(element.tag.split('}')[-1], ('image', 'script', 'foreignObject', 'text'))
            self.assertFalse(any('href' in key for key in element.attrib))

    def test_png_dimensions_and_integrity(self):
        for size in SIZES:
            with self.subTest(size=size):
                self.assertEqual(png_size((ICONS / f'showpsisi-{size}.png').read_bytes()), (size, size))

    def test_ico_contains_every_native_size(self):
        data = (ICONS / 'showpsisi.ico').read_bytes()
        self.assertEqual(struct.unpack('<HHH', data[:6]), (0, 1, len(SIZES)))
        last_end = 6 + 16 * len(SIZES)
        for index, size in enumerate(SIZES):
            width, height, colors, reserved, planes, bits, length, offset = struct.unpack(
                '<BBBBHHII', data[6 + 16 * index:22 + 16 * index])
            self.assertEqual((width or 256, height or 256, colors, reserved, planes, bits),
                             (size, size, 0, 0, 1, 32))
            self.assertEqual(offset, last_end)
            self.assertEqual(data[offset:offset + length], (ICONS / f'showpsisi-{size}.png').read_bytes())
            last_end = offset + length
        self.assertEqual(last_end, len(data))

    def test_tauri_embeds_same_icon_without_enabling_bundle(self):
        directory = ROOT / 'ui/tauri/src-tauri'
        config = json.loads((directory / 'tauri.conf.json').read_text())
        self.assertFalse(config['bundle']['active'])
        self.assertEqual(config['bundle']['icon'], ['icons/icon.png', 'icons/icon.ico'])
        self.assertEqual((directory / 'icons/icon.png').read_bytes(), (ICONS / 'showpsisi-256.png').read_bytes())
        self.assertEqual((directory / 'icons/icon.ico').read_bytes(), (ICONS / 'showpsisi.ico').read_bytes())

    def test_qt_windows_and_linux_registration(self):
        cmake = (ROOT / 'CMakeLists.txt').read_text()
        for size in SIZES:
            self.assertIn(f'assets/icons/showpsisi-{size}.png', cmake)
        self.assertIn('assets/icons/showpsisi.rc', cmake)
        self.assertIn('PREFIX "/icons" BASE "assets/icons"', cmake)
        self.assertIn('ICON "showpsisi.ico"', (ICONS / 'showpsisi.rc').read_text())
        desktop = (ROOT / 'assets/linux/org.showpsisi.ShowPsiSi.desktop').read_text()
        self.assertIn('Exec=showpsisi-qt', desktop)
        self.assertIn('Icon=org.showpsisi.ShowPsiSi', desktop)


if __name__ == '__main__':
    unittest.main()
