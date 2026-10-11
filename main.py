#!/usr/bin/env python3
"""
Factorio 2.0 Video to Blueprint Generator — Unified Python Entry Point
======================================================================
Usage:
  python main.py             # Launches modern cross-platform Web GUI (Linux/macOS/Windows)
  python main.py --cli ...   # CLI compiler mode (delegates to video_to_blueprint.py)
  python main.py --legacy    # Launches legacy Tkinter desktop window
"""

import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--legacy":
        try:
            from gui.app_window import FactorioVideoApp
            app = FactorioVideoApp()
            app.mainloop()
            return
        except Exception as e:
            print(f"Error launching legacy GUI: {e}")
            sys.exit(1)

    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        import video_to_blueprint
        sys.argv.pop(1)
        video_to_blueprint.main()
        return

    # Default: Modern Cross-Platform Web Server & Browser UI
    from server import start_server
    start_server()


if __name__ == "__main__":
    main()
