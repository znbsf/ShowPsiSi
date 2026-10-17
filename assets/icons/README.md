# Application icon

Original ShowPsiSi artwork, covered by the repository's MIT license. No external
logo, font or stock asset is used. The packet stack branches into three PSI/SI
tree nodes; the illustration does not imply additional decoder capabilities.

`showpsisi.svg` is the editable master. The neutral tile provides contrast on
both light and dark desktops. Seven RGBA PNG sizes and a multi-resolution Windows
ICO are committed so end-user builds need no graphics toolchain.

Regenerate with `python scripts/generate_icons.py`; verify reproducibility with
`python scripts/generate_icons.py --check`. Generation uses Inkscape 1.4 and
Pillow 12.3.0 in the development environment; other renderer versions can change
antialiasing. The ICO includes separately rasterized 16/24/32/48/64/128/256-pixel
frames. Tauri's default PNG/ICO are byte-identical copies of these assets.

Qt embeds PNG resources (no runtime SVG plugin needed) and the Windows executable
embeds the ICO. Linux CMake install registers the desktop entry and hicolor PNG
and scalable icons. Tauri explicitly references the original assets in its bundle
configuration, while bundling remains disabled until the existing delivery gates
are satisfied. Windows portable staging includes the editable SVG, PNG and ICO in
`assets/icons/`; their bytes remain covered by the package manifest. Windows portable validation
checks that the real executable embeds all seven matching icon frames. No license or
runtime validation gate is bypassed by adding the icon.
