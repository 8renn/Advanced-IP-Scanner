import os
import platform
import shlex
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from ui.app_shell import AppShellWindow
from ui.launcher import LauncherWindow


def _maybe_macos_relaunch_elevated() -> None:
    """
    MTR needs raw ICMP on macOS (root). Replace this process with osascript so the
    non-root Python GUI cannot continue after the prompt; the elevated child is the app.
    """
    if platform.system() != "Darwin" or os.geteuid() == 0:
        return
    # Frozen: real binary is argv[0] inside the .app (not always the same as sys.executable).
    # Dev: run the same interpreter + script/args.
    if getattr(sys, "frozen", False):
        shell_cmd = shlex.join(sys.argv)
    else:
        shell_cmd = shlex.join([sys.executable, *sys.argv])
    inner = shell_cmd.replace("\\", "\\\\").replace('"', '\\"')
    applescript = f'do shell script "{inner}" with administrator privileges'
    try:
        os.execvp("osascript", ["osascript", "-e", applescript])
    except OSError as e:
        print(f"Failed to elevate: {e}", file=sys.stderr)
        # Continue without elevation; MTR tab will explain and disable Start.


def main() -> int:
    _maybe_macos_relaunch_elevated()

    app = QApplication(sys.argv)

    # Set application icon (works for taskbar, window title bar, alt-tab)
    if getattr(sys, "frozen", False):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).resolve().parent

    if sys.platform == "darwin":
        # macOS: .icns if present; else bundle icon from .app
        icns_path = base_path / "assets" / "app.icns"
        if icns_path.exists():
            app.setWindowIcon(QIcon(str(icns_path)))
    else:
        icon_path = base_path / "assets" / "app.ico"
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))

    launcher = LauncherWindow()

    def _open_app() -> None:
        window = AppShellWindow()
        window.show()
        # prevent garbage collection
        app.setProperty("_main_window", window)

    launcher.launch_app.connect(_open_app)
    launcher.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
