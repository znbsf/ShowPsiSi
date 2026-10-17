"""Targeted WCAG regression for both authored workbench themes.

Resolve the supported CSS root cascade and QML literal/theme expressions rather
than flattening light and dark declarations together. This is not a full CSS/QML
interpreter or an accessibility-conformance audit; native/disabled rendering and
assistive technology still need separate validation.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
HEX = r'#[\da-fA-F]{6}'
THEMES = ('dark', 'light')
TABLES = ('PAT', 'PMT', 'CAT', 'NIT', 'SDT', 'BAT', 'EIT', 'TDT', 'TOT', 'AIT', 'DSMCC')


def luminance(color):
    rgb = [int(color[i:i+2], 16) / 255 for i in (1, 3, 5)]
    return sum((c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4) * weight
               for c, weight in zip(rgb, (0.2126, 0.7152, 0.0722)))


def contrast(first, second):
    high, low = sorted((luminance(first), luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def css_rules(css):
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    return [(selector.strip(), body) for selector, body in re.findall(r'([^{}]+)\{([^{}]*)\}', css)]


def web_palettes(css):
    base, light = {}, {}
    for selector, body in css_rules(css):
        # Root-only declarations. Descendant rules must never change root tokens.
        if selector in (':root', ':root[data-theme="light"]'):
            target = base if selector == ':root' else light
            target.update(re.findall(r'--([\w-]+):\s*(' + HEX + r')\b', body))
    if not base or not light:
        raise AssertionError('Missing explicit dark or light CSS root palette')
    return {'dark': base, 'light': dict(base, **light)}


def qt_palettes(qml):
    result = {theme: {} for theme in THEMES}
    for name, expression in re.findall(r'property color (\w+):\s*([^\n]+)', qml):
        pair = re.fullmatch(r'lightTheme \? "(' + HEX + r')" : "(' + HEX + r')"', expression.strip())
        literal = re.fullmatch(r'"(' + HEX + r')"', expression.strip())
        alias = expression.strip() if expression.strip() in result['dark'] else None
        if not pair and not literal and not alias:
            raise AssertionError(f'Unsupported authored QML color expression: {name}')
        for theme in THEMES:
            result[theme][name] = pair.group(1 if theme == 'light' else 2) if pair else literal.group(1) if literal else result[theme][alias]
    return result


def table_palettes(qml, css):
    dark = dict(re.findall(r'(\w+):\["(' + HEX + r')","[^"]+",', qml))
    dsm = re.search(r'return \["(' + HEX + r')","▥","DSM-CC data"\]', qml)
    if not dsm:
        raise AssertionError('Missing fixed DSM-CC category')
    dark['DSMCC'] = dsm.group(1)
    light_map = re.search(r'function tableColor\(name\).*?let dark = \{([^}]+)\}', qml, re.S)
    if not light_map:
        raise AssertionError('Missing QML light category palette')
    light = dict(re.findall(r'(\w+):"(' + HEX + r')"', light_map.group(1)))
    light['DSMCC'] = re.search(r'\? "(' + HEX + r')" : "' + HEX + r'"\)\) : tableCategory', qml).group(1)
    web = {theme: {} for theme in THEMES}
    backgrounds = {theme: {} for theme in THEMES}
    for selector, body in css_rules(css):
        names = re.findall(r'\.category-([\w-]+)', selector)
        if not names:
            continue
        themes = ('light',) if ':root[data-theme="light"]' in selector else THEMES
        color = re.search(r'(?:^|;)\s*color:\s*(' + HEX + r')', body)
        background = re.search(r'(?:^|;)\s*background:\s*(' + HEX + r')', body)
        for theme in themes:
            for name in names:
                if color:
                    web[theme][name.upper()] = color.group(1)
                if background:
                    backgrounds[theme][name.upper()] = background.group(1)
    # The later light table-kind/table-icon rule overrides category badge fills.
    badge = re.search(r':root\[data-theme="light"\] \.table-kind,\s*:root\[data-theme="light"\] \.table-icon\s*\{\s*background:\s*(' + HEX + r')', css)
    if not badge:
        raise AssertionError('Missing light category badge background')
    backgrounds['light'].update({name: badge.group(1) for name in TABLES})
    return {'dark': dark, 'light': light}, web, backgrounds


class WorkbenchContrastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qml = (ROOT / 'ui/qt/Main.qml').read_text()
        cls.css = (ROOT / 'ui/tauri/web/style.css').read_text()
        cls.qt = qt_palettes(cls.qml)
        cls.web = web_palettes(cls.css)

    def assert_ratio(self, foreground, background, minimum, context):
        self.assertGreaterEqual(contrast(foreground, background), minimum,
                                f'{context}: {foreground} on {background}')

    def test_web_authored_text_focus_and_input_tokens(self):
        for theme, tokens in self.web.items():
            for background in ('bg', 'surface', 'raised', 'selected', 'hover', 'input'):
                for foreground in ('text', 'muted', 'green', 'red', 'accent', 'syntax-label',
                                   'syntax-value', 'syntax-private', 'syntax-tag', 'syntax-string'):
                    with self.subTest(theme=theme, foreground=foreground, background=background):
                        self.assert_ratio(tokens[foreground], tokens[background], 4.5, 'Web text')
                for foreground in ('accent', 'control-border', 'control-border-hover'):
                    with self.subTest(theme=theme, control=foreground, background=background):
                        self.assert_ratio(tokens[foreground], tokens[background], 3, 'Web control')
        primary = [body for selector, body in css_rules(self.css)
                   if selector in ('.btn.primary', '.btn.primary:hover:not(:disabled)')]
        self.assertEqual(len(primary), 2)
        for body in primary:
            background = re.search(r'background:\s*(' + HEX + r')', body)
            self.assertIsNotNone(background)
            self.assert_ratio('#ffffff', background.group(1), 4.5, 'Web primary button label')

    def test_fixed_table_types_have_distinct_readable_tokens_in_both_themes(self):
        qt, web, badges = table_palettes(self.qml, self.css)
        symbols = re.findall(r'\w+:\["' + HEX + r'","([^"]+)",', self.qml) + ['▥']
        self.assertEqual(len(set(symbols)), 11)
        for theme in THEMES:
            self.assertEqual(len({qt[theme][name] for name in TABLES}), 11)
            self.assertEqual(len({web[theme][name] for name in TABLES}), 11)
            for name in TABLES:
                with self.subTest(theme=theme, table=name):
                    if theme == 'dark':
                        self.assertEqual(qt[theme][name], web[theme][name], 'Shared dark category identity')
                    for background in ('surface', 'panel', 'raised', 'selectionSurface', 'hoverSurface'):
                        self.assert_ratio(qt[theme][name], self.qt[theme][background], 4.5, 'Qt category')
                    for background in ('bg', 'surface', 'raised', 'selected', 'hover'):
                        self.assert_ratio(web[theme][name], self.web[theme][background], 4.5, 'Web category')
                    self.assert_ratio(web[theme][name], badges[theme][name], 4.5, 'Web category badge')
        self.assertTrue('color: nav.foreground' in self.qml, 'Navigation must use semantic foreground')

    def test_qt_authored_text_focus_and_input_tokens(self):
        for theme, tokens in self.qt.items():
            for background in ('surface', 'panel', 'raised', 'selectionSurface', 'hoverSurface'):
                for foreground in ('ink', 'muted', 'addedColor', 'removedColor', 'changedColor', 'warningColor'):
                    with self.subTest(theme=theme, foreground=foreground, background=background):
                        self.assert_ratio(tokens[foreground], tokens[background], 4.5, 'Qt text')
                for foreground in ('blue', 'controlBorder'):
                    with self.subTest(theme=theme, control=foreground, background=background):
                        self.assert_ratio(tokens[foreground], tokens[background], 3, 'Qt control')
            # Actual action-hover and semantic tree expressions stay bound to tested surfaces.
            self.assertTrue('(control.hovered ? hoverSurface : raised)' in self.qml, 'Action hover surface changed; update coverage')
            self.assertTrue('nav.highlighted ? selectionSurface : nav.hovered ? hoverSurface' in self.qml, 'Navigation surfaces changed; update coverage')
            inline = re.findall(r'\(lightTheme \? "(' + HEX + r')" : "(' + HEX + r')"\)', self.qml)
            for light, dark in inline:
                for background in ('panel', 'selectionSurface', 'hoverSurface'):
                    self.assert_ratio(light if theme == 'light' else dark, tokens[background], 4.5, 'Qt semantic tree')
        primary = re.search(r'control.hovered \? "(' + HEX + r')" : "(' + HEX + r')"', self.qml)
        self.assertIsNotNone(primary, 'Missing primary-button colors')
        for background in primary.groups():
            self.assert_ratio('#ffffff', background, 4.5, 'Primary button label')

    def test_xml_syntax_uses_readable_theme_palette(self):
        source = (ROOT / 'ui/qt/XmlHighlighter.h').read_text()
        colors = re.findall(r'"(' + HEX + r')", "(' + HEX + r')"\}', source)
        self.assertEqual(len(colors), 4)
        comments = re.search(r'QColor\(light_\?"(' + HEX + r')":"(' + HEX + r')"\)', source)
        self.assertIsNotNone(comments)
        colors.append((comments.group(2), comments.group(1)))
        for theme in THEMES:
            for dark, light in colors:
                for background in ('panel', 'surface'):
                    self.assert_ratio(light if theme == 'light' else dark, self.qt[theme][background], 4.5, 'XML syntax')

    def test_palette_parsers_preserve_theme_scope_and_fail_closed(self):
        palettes = web_palettes(':root {--text:#ffffff;--bg:#000000;} :root {--text:#dddddd;} '
                                ':root[data-theme="light"] {--text:#111111;--bg:#eeeeee;} '
                                ':root[data-theme="light"] .child {--text:#ff0000;}')
        self.assertEqual(palettes['dark']['text'], '#dddddd')
        self.assertEqual(palettes['light']['text'], '#111111')
        with self.assertRaises(AssertionError):
            qt_palettes('property color ink: externalColor')


if __name__ == '__main__':
    unittest.main()
