# PinballUX Installed Package Structure

## Main Installation Directory: /opt/pinballux/

```
/opt/pinballux/
├── __init__.py
├── setup_gui.py
├── table_manager.py
├── run_pinballux.py
├── requirements.txt
├── README.md
│
├── src/
│   ├── __init__.py
│   ├── main.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── application.py
│   │   ├── config.py
│   │   ├── logger.py
│   │   └── vpx_launcher.py
│   │
│   ├── database/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── service.py
│   │   ├── table_manager.py
│   │   └── vpx_parser.py
│   │
│   ├── displays/
│   │   ├── __init__.py
│   │   ├── backglass_display.py
│   │   ├── base_display.py
│   │   ├── dmd_display.py
│   │   ├── monitor_manager.py
│   │   └── topper_display.py
│   │
│   ├── input/
│   │   ├── __init__.py
│   │   └── input_manager.py
│   │
│   ├── media/
│   │   ├── __init__.py
│   │   ├── manager.py
│   │   └── service.py
│   │
│   └── ui/
│       ├── __init__.py
│       ├── main_window.py
│       ├── media_widgets.py
│       └── wheel_widget.py
│
├── data/
│   ├── tables/          (empty, user-writable 777)
│   ├── roms/            (empty, user-writable 777)
│   │
│   └── media/           (all user-writable 777)
│       ├── images/
│       │   ├── default/
│       │   │   ├── .gitkeep
│       │   │   └── About this folder.txt
│       │   ├── real_dmd/
│       │   │   └── .gitkeep
│       │   ├── ui/
│       │   │   ├── PinballUX.png
│       │   │   └── TableManager.png
│       │   ├── table/       (empty, for user media)
│       │   ├── backglass/   (empty, for user media)
│       │   ├── wheel/       (empty, for user media)
│       │   ├── dmd/         (empty, for user media)
│       │   └── topper/      (empty, for user media)
│       │
│       ├── videos/
│       │   ├── table/       (empty, for user media)
│       │   ├── backglass/   (empty, for user media)
│       │   ├── dmd/         (empty, for user media)
│       │   ├── real_dmd/    (empty, for user media)
│       │   ├── real_dmd_color/ (empty, for user media)
│       │   └── topper/      (empty, for user media)
│       │
│       ├── audio/
│       │   ├── table/       (empty, for user media)
│       │   ├── launch/      (empty, for user media)
│       │   └── ui/          (empty, for user media)
│       │
│       └── packs/           (empty, for downloaded media packs)
│
├── vpinball/                (empty, user-writable 777 for VPinball installation)
│
├── docs/                    (empty)
│
└── tests/                   (empty)
```

## System Binaries: /usr/bin/

```
/usr/bin/
├── pinballux            (wrapper script → python3 /opt/pinballux/run_pinballux.py)
├── pinballux-setup      (wrapper script → python3 /opt/pinballux/setup_gui.py)
└── pinballux-manager    (wrapper script → python3 /opt/pinballux/table_manager.py)
```

## Desktop Integration: /usr/share/

```
/usr/share/
├── applications/
│   ├── pinballux.desktop
│   ├── pinballux-setup.desktop
│   └── pinballux-manager.desktop
│
└── pixmaps/
    ├── pinballux.png         (copy of PinballUX.png)
    └── pinballux-manager.png (copy of TableManager.png)
```

## User Configuration: ~/.config/pinballux/

```
~/.config/pinballux/
├── config.json           (created on first run)
├── tables.db             (SQLite database, created on first run)
├── pinballux.log         (application log file)
└── ftp_downloads_temp/   (temporary download directory)
```

## Important Notes

1. **No nested pinballux/ directory** - Contents are directly in /opt/pinballux/
2. **User-writable directories** (777 permissions):
   - /opt/pinballux/data/ (and all subdirectories)
   - /opt/pinballux/vpinball/
3. **Path calculations** in code use:
   - `Path(__file__).parents[2]` from /opt/pinballux/src/core/config.py → /opt/pinballux/
4. **Media directories** are empty by default, filled by:
   - Table Manager downloads
   - User manual placement
