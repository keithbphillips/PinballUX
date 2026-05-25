import os
from PyInstaller.utils.hooks import collect_all

# SPECPATH is set by PyInstaller to the directory containing this spec file
# (packaging/appimage/), so walk up two levels to reach the project root.
project_root = os.path.abspath(os.path.join(SPECPATH, '..', '..'))
pinballux_pkg = os.path.join(project_root, 'pinballux')

block_cipher = None

# Collect all PyQt6 components: data files, binaries, and hidden imports.
# This ensures Qt platform plugins, translations, and WebEngine bits are included.
pyqt6_datas, pyqt6_binaries, pyqt6_hiddenimports = collect_all('PyQt6')

# Hidden imports shared by all three entry points.
# Listed explicitly because the try/except import pattern in each script
# can cause PyInstaller's static analyser to miss the fallback branch.
shared_hiddenimports = [
    *pyqt6_hiddenimports,
    'src.core.application',
    'src.core.config',
    'src.core.logger',
    'src.core.single_instance',
    'src.core.vpx_launcher',
    'src.displays.backglass_display',
    'src.displays.base_display',
    'src.displays.dmd_display',
    'src.displays.monitor_manager',
    'src.displays.topper_display',
    'src.input.input_manager',
    'src.media.manager',
    'src.media.service',
    'src.ui.main_window',
    'src.ui.media_widgets',
    'src.ui.wheel_widget',
    'src.database.models',
    'src.database.service',
    'src.database.table_scanner',
    'src.database.vpx_parser',
    'src.database.pinballx_database_parser',
    'sqlalchemy.dialects.sqlite',
    'sqlalchemy.dialects.sqlite.pysqlite',
    'pydantic',
    'pydantic_core',
    'pygame',
    'PIL',
    'PIL.Image',
    'olefile',
    'watchdog.observers',
    'watchdog.observers.inotify',
    'watchdog.events',
    'dateutil',
    'dateutil.parser',
]

shared_pathex = [project_root, pinballux_pkg]

shared_datas = [
    *pyqt6_datas,
    (os.path.join(pinballux_pkg, 'data'), 'pinballux/data'),
]

# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------

a_main = Analysis(
    [os.path.join(pinballux_pkg, 'src', 'main.py')],
    pathex=shared_pathex,
    binaries=pyqt6_binaries,
    datas=shared_datas,
    hiddenimports=shared_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz_main = PYZ(a_main.pure, a_main.zipped_data, cipher=block_cipher)

exe_main = EXE(
    pyz_main,
    a_main.scripts,
    [],
    exclude_binaries=True,
    name='pinballux',
    debug=False,
    strip=False,
    upx=False,
    console=False,
)

# ---------------------------------------------------------------------------
# Setup / configuration tool
# ---------------------------------------------------------------------------

a_setup = Analysis(
    [os.path.join(project_root, 'setup_gui.py')],
    pathex=shared_pathex,
    binaries=pyqt6_binaries,
    datas=shared_datas,
    hiddenimports=shared_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz_setup = PYZ(a_setup.pure, a_setup.zipped_data, cipher=block_cipher)

exe_setup = EXE(
    pyz_setup,
    a_setup.scripts,
    [],
    exclude_binaries=True,
    name='pinballux-setup',
    debug=False,
    strip=False,
    upx=False,
    console=False,
)

# ---------------------------------------------------------------------------
# Table manager
# ---------------------------------------------------------------------------

a_manager = Analysis(
    [os.path.join(project_root, 'table_manager.py')],
    pathex=shared_pathex,
    binaries=pyqt6_binaries,
    datas=shared_datas,
    hiddenimports=shared_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz_manager = PYZ(a_manager.pure, a_manager.zipped_data, cipher=block_cipher)

exe_manager = EXE(
    pyz_manager,
    a_manager.scripts,
    [],
    exclude_binaries=True,
    name='pinballux-manager',
    debug=False,
    strip=False,
    upx=False,
    console=False,
)

# ---------------------------------------------------------------------------
# Single COLLECT — all three executables share one set of libraries/data
# ---------------------------------------------------------------------------

coll = COLLECT(
    exe_main,
    exe_setup,
    exe_manager,
    a_main.binaries + a_setup.binaries + a_manager.binaries,
    a_main.zipfiles + a_setup.zipfiles + a_manager.zipfiles,
    a_main.datas + a_setup.datas + a_manager.datas,
    strip=False,
    upx=False,
    name='pinballux',
)
