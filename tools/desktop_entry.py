"""PyInstaller entry point — launches the Streamlit ingest app inside the bundle.

Built into a double-clickable Mac .app / Windows .exe so users don't need
Python or a terminal. See tools/build_desktop.md for build instructions.
"""
import os
import sys


def _resource_dir() -> str:
    # When frozen by PyInstaller, data files live under sys._MEIPASS.
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def main() -> None:
    from streamlit.web import cli as stcli

    app_path = os.path.join(_resource_dir(), "ingest_app.py")
    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--global.developmentMode=false",
        "--server.headless=false",
        "--browser.gatherUsageStats=false",
    ]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
