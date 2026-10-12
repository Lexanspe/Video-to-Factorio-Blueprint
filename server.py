#!/usr/bin/env python3
"""
Factorio 2.0 Video to Blueprint Generator — Cross-Platform Web Server
=====================================================================
Provides cross-platform support for Linux, macOS, and Windows.
Serves the modern cyberpunk web interface and provides real-time API
bridges for video frame extraction and circuit blueprint compilation.
"""

import os
import sys
import json
import base64
import urllib.parse
import webbrowser
import threading
import tempfile
import socket
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Dict, Any, List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.video_processor import (
    extract_video_frames,
    generate_procedural_demo,
    get_media_info,
    frame_bytes_to_image
)
from core.circuit_engine_v3 import compile_blueprint_v3, MAX_PIXELS_PER_STRIPE
from core.circuit_engine_v2 import compile_blueprint_v2
from core.circuit_engine import compile_blueprint as compile_blueprint_v1

_v2f_dir = os.path.join(BASE_DIR, "VideoToFactorioBlueprint", "wwwroot")
WWWROOT_DIR = _v2f_dir if os.path.exists(_v2f_dir) else os.path.join(BASE_DIR, "FactorioVideoToBlueprint", "wwwroot")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

active_compile_aborted = False

def find_available_port(start_port: int = 5000, max_attempts: int = 50) -> int:
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
    return start_port

class CrossPlatformHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        # Clean terminal output: only log API actions and errors
        if "/api/" in str(args[0]) or "404" in str(args[1]) or "500" in str(args[1]):
            super().log_message(format, *args)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.lstrip("/")

        # Serve static assets
        if path.startswith("assets/"):
            rel_path = path[len("assets/"):]
            full_path = os.path.join(ASSETS_DIR, rel_path)
            if os.path.exists(full_path) and os.path.isfile(full_path):
                self.serve_file(full_path)
                return

        # Serve wwwroot static files
        if not path or path == "index.html":
            full_path = os.path.join(WWWROOT_DIR, "index.html")
        else:
            full_path = os.path.join(WWWROOT_DIR, path)

        if os.path.exists(full_path) and os.path.isfile(full_path):
            self.serve_file(full_path)
        else:
            self.send_error(404, f"File not found: {self.path}")

    def serve_file(self, full_path: str):
        ext = os.path.splitext(full_path)[1].lower()
        content_types = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
            ".json": "application/json; charset=utf-8",
        }
        ct = content_types.get(ext, "application/octet-stream")

        try:
            with open(full_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ct)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Error reading file: {e}")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        api_path = parsed.path

        if api_path == "/api/load_demo":
            self.handle_load_demo()
        elif api_path == "/api/get_preview":
            self.handle_get_preview()
        elif api_path == "/api/estimate_stats":
            self.handle_estimate_stats()
        elif api_path == "/api/compile":
            self.handle_compile()
        elif api_path == "/api/abort":
            self.handle_abort()
        elif api_path == "/api/upload":
            self.handle_upload()
        elif api_path == "/api/select_file":
            self.handle_select_file()
        else:
            self.send_error(404, f"Unknown API endpoint: {api_path}")

    def read_json_body(self) -> Dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        if not body:
            return {}
        try:
            return json.loads(body.decode("utf-8"))
        except Exception:
            return {}

    def send_json_response(self, data: Dict[str, Any], status: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def handle_load_demo(self):
        self.send_json_response({
            "success": True,
            "info": {
                "width": 16,
                "height": 16,
                "orig_w": 16,
                "orig_h": 16,
                "fps": 5.0,
                "total_frames": 16,
                "duration": 3.2,
                "path": "__demo__",
                "filename": "Built-in Demo Animation"
            }
        })

    def handle_get_preview(self):
        data = self.read_json_body()
        path = data.get("path", "__demo__")
        h = int(data.get("target_h", 16))
        f_idx = int(data.get("frame_idx", 0))

        try:
            if path == "__demo__":
                frames = generate_procedural_demo(h, h, num_frames=16)
            else:
                info = get_media_info(path)
                orig_w = info.get("width") or info.get("orig_w") or 16
                orig_h = info.get("height") or info.get("orig_h") or 16
                calc_w = max(1, int(round(h * (orig_w / max(1, orig_h)))))
                frames = extract_video_frames(path, calc_w, h, max_frames=f_idx + 1)

            idx = min(len(frames) - 1, max(0, f_idx))
            fb = frames[idx]
            b64 = base64.b64encode(fb).decode("ascii")
            self.send_json_response({
                "success": True,
                "image": f"data:image/jpeg;base64,{b64}"
            })
        except Exception as e:
            self.send_json_response({"success": False, "error": str(e)}, status=500)

    def handle_estimate_stats(self):
        p = self.read_json_body()
        try:
            orig_w = int(p.get("orig_w") or p.get("width") or 16)
            orig_h = int(p.get("orig_h") or p.get("height") or 16)
            video_path = p.get("video_path")
            
            if video_path and os.path.exists(video_path) and video_path != "__demo__":
                try:
                    info = get_media_info(video_path)
                    if info.get("orig_w"): orig_w = info["orig_w"]
                    if info.get("orig_h"): orig_h = info["orig_h"]
                except Exception:
                    pass

            target_h = int(p.get("target_h", 16))
            calc_w = max(1, int(round(target_h * (orig_w / max(1, orig_h)))))
            num_lamps = calc_w * target_h
            
            engine = p.get("engine", "v3")
            rom_mode = p.get("rom_mode") or p.get("rom_placement") or "horizontal_right"
            rom_dir = p.get("rom_direction") or ("vertical" if rom_mode.startswith("vertical") else "horizontal")
            compact_rom = bool(p.get("compact_rom", True))
            fill_all_rows = bool(p.get("fill_all_rows", True))
            sub_quality = p.get("substation_quality", "legendary")
            num_parts = max(1, int(p.get("num_parts", 1)))
            total_frames = int(p.get("total_frames", 16))
            fps = float(p.get("fps", 5))
            safe_fps = max(1, min(60, int(round(fps))))

            frames_per_pack = 16 if engine == "v3" else (3 if engine == "v2" else 1)
            num_packs = (total_frames + frames_per_pack - 1) // frames_per_pack

            max_lamps_per_stripe = 13008
            num_stripes = (num_lamps + max_lamps_per_stripe - 1) // max_lamps_per_stripe

            if engine == "v3":
                combs_per_pack = 2  # 1 Constant Combinator + 1 Decider Combinator
                decoder_combs = 4 * num_stripes  # 4 combinators per stripe head decoder
                clock_combs = 6  # Central selector clock
                total_rom_combs = num_packs * combs_per_pack * num_stripes
                total_combs = total_rom_combs + decoder_combs + clock_combs
            elif engine == "v2":
                combs_per_pack = 7  # 1 Constant Combinator + 3 Deciders + 3 Shifters
                decoder_combs = 12 * num_stripes  # 12 combinators per stripe TrueColor adapter
                clock_combs = 6  # Central selector clock
                total_rom_combs = num_packs * combs_per_pack * num_stripes
                total_combs = total_rom_combs + decoder_combs + clock_combs
            else:
                total_combs = num_packs * 2 * num_stripes + 4

            part_combs = [total_combs // num_parts] * num_parts
            part_combs[0] += total_combs % num_parts

            self.send_json_response({
                "success": True,
                "width": calc_w,
                "calc_width": calc_w,
                "height": target_h,
                "calc_height": target_h,
                "lamps": num_lamps,
                "monitor_lamps": num_lamps,
                "total_frames": total_frames,
                "fps": safe_fps,
                "rom_mode": rom_mode,
                "num_stripes": num_stripes,
                "total_packs": num_packs,
                "frames_per_pack": frames_per_pack,
                "total_combinators": total_combs,
                "combs_per_part": part_combs,
                "part_combinators": part_combs,
                "num_parts": num_parts
            })
        except Exception as e:
            self.send_json_response({"success": False, "error": str(e)}, status=500)

    def handle_compile(self):
        global active_compile_aborted
        active_compile_aborted = False
        p = self.read_json_body()

        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        def stream_msg(obj: Dict[str, Any]):
            line = (json.dumps(obj) + "\n").encode("utf-8")
            self.wfile.write(line)
            self.wfile.flush()

        try:
            stream_msg({"type": "progress", "msg": "Starting compilation...", "fraction": 0.05})

            video_path = p.get("video_path", "__demo__")
            target_h = int(p.get("target_h", 16))
            orig_w = int(p.get("orig_w") or 16)
            orig_h = int(p.get("orig_h") or 16)
            fps = float(p.get("fps", 5))
            safe_fps = max(1, min(60, int(round(fps))))
            max_frames = int(p.get("max_frames", 16))
            engine = p.get("engine", "v3")
            rom_mode = p.get("rom_mode") or p.get("rom_placement") or "horizontal_right"
            rom_dir = p.get("rom_direction") or ("vertical" if rom_mode.startswith("vertical") else "horizontal")
            compact_rom = bool(p.get("compact_rom", True))
            fill_all_rows = bool(p.get("fill_all_rows", True))
            sub_quality = p.get("substation_quality", "legendary")
            num_parts = max(1, int(p.get("num_parts", 1)))

            calc_w = max(1, int(round(target_h * (orig_w / max(1, orig_h)))))

            # Extract frames
            stream_msg({"type": "progress", "msg": f"Extracting frames for {calc_w}x{target_h} ({safe_fps} FPS)...", "fraction": 0.15})
            if video_path == "__demo__":
                frames = generate_procedural_demo(calc_w, target_h, num_frames=max_frames, fps=safe_fps)
            else:
                frames = extract_video_frames(video_path, calc_w, target_h, target_fps=safe_fps, max_frames=max_frames)

            if not frames:
                stream_msg({"type": "error", "error": "No frames could be extracted from media source."})
                return

            if active_compile_aborted:
                stream_msg({"type": "aborted", "msg": "Compilation aborted by user."})
                return

            stream_msg({"type": "progress", "msg": f"Compiling circuit blueprint ({len(frames)} frames @ {safe_fps} FPS)...", "fraction": 0.60})

            # Compile according to selected engine and slice parts
            for p_idx in range(num_parts):
                if active_compile_aborted:
                    stream_msg({"type": "aborted", "msg": "Compilation aborted by user."})
                    return

                stream_msg({
                    "type": "progress",
                    "msg": f"Compiling circuit blueprint (Part {p_idx + 1}/{num_parts})...",
                    "fraction": 0.40 + 0.50 * (p_idx / max(1, num_parts))
                })

                compile_kwargs = {
                    "fps": safe_fps,
                    "rom_mode": rom_mode,
                    "part_idx": p_idx,
                    "num_parts": num_parts,
                    "copy_convenience": True,
                    "compact_rom": compact_rom,
                    "fill_all_rows": fill_all_rows,
                }

                if engine == "v3":
                    compile_kwargs["substation_quality"] = sub_quality
                    bp_str, meta = compile_blueprint_v3(frames, **compile_kwargs)
                elif engine == "v1":
                    bp_str, meta = compile_blueprint_v1(frames, **compile_kwargs)
                else:
                    bp_str, meta = compile_blueprint_v2(frames, **compile_kwargs)

                if active_compile_aborted:
                    stream_msg({"type": "aborted", "msg": "Compilation aborted by user."})
                    return

                stream_msg({
                    "type": "result",
                    "success": True,
                    "part_idx": p_idx,
                    "total_parts": num_parts,
                    "blueprint": bp_str,
                    "meta": meta
                })

            stream_msg({"type": "progress", "msg": "Compilation complete!", "fraction": 1.0})

        except Exception as e:
            stream_msg({"type": "error", "error": str(e)})

    def handle_abort(self):
        global active_compile_aborted
        active_compile_aborted = True
        self.send_json_response({"success": True, "aborted": True})

    def handle_upload(self):
        """Accepts file upload from drag-and-drop or browser file input."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0:
                self.send_json_response({"success": False, "error": "Empty file"}, status=400)
                return

            filename = self.headers.get("X-Filename", "uploaded_media.mp4")
            # Sanitize filename
            filename = os.path.basename(urllib.parse.unquote(filename))
            ext = os.path.splitext(filename)[1] or ".mp4"

            # Create temp file
            temp_fd, temp_path = tempfile.mkstemp(suffix=ext, prefix="factorio_vid_")
            with os.fdopen(temp_fd, "wb") as f:
                remaining = content_length
                chunk_size = 64 * 1024
                while remaining > 0:
                    read_bytes = min(remaining, chunk_size)
                    chunk = self.rfile.read(read_bytes)
                    if not chunk:
                        break
                    f.write(chunk)
                    remaining -= len(chunk)

            # Analyze media info
            info = get_media_info(temp_path)
            w = info.get("width") or info.get("orig_w") or 16
            h = info.get("height") or info.get("orig_h") or 16

            self.send_json_response({
                "success": True,
                "info": {
                    "width": w,
                    "height": h,
                    "orig_w": w,
                    "orig_h": h,
                    "fps": round(info.get("fps", 30), 2),
                    "total_frames": info.get("total_frames", 16),
                    "duration": round(info.get("duration", 0), 2),
                    "path": temp_path,
                    "filename": filename
                }
            })
        except Exception as e:
            self.send_json_response({"success": False, "error": str(e)}, status=500)

    def handle_select_file(self):
        """Tries native OS file dialog if available on host machine."""
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            filetypes = [
                ("Video & Animation Files", "*.mp4 *.webm *.avi *.mov *.gif *.mkv"),
                ("All Files", "*.*")
            ]
            path = filedialog.askopenfilename(filetypes=filetypes)
            root.destroy()

            if path and os.path.exists(path):
                info = get_media_info(path)
                w = info.get("width") or info.get("orig_w") or 16
                h = info.get("height") or info.get("orig_h") or 16
                self.send_json_response({
                    "success": True,
                    "info": {
                        "width": w,
                        "height": h,
                        "orig_w": w,
                        "orig_h": h,
                        "fps": round(info.get("fps", 30), 2),
                        "total_frames": info.get("total_frames", 16),
                        "duration": round(info.get("duration", 0), 2),
                        "path": path,
                        "filename": os.path.basename(path)
                    }
                })
            else:
                self.send_json_response({"success": False, "cancelled": True})
        except Exception:
            # Headless or tkinter not installed; browser file input will handle it
            self.send_json_response({"success": False, "fallback_to_browser": True})

def start_server(host: str = "127.0.0.1", port: int = 5000, open_browser: bool = True):
    actual_port = find_available_port(port)
    server_address = (host, actual_port)
    httpd = HTTPServer(server_address, CrossPlatformHandler)
    url = f"http://{host}:{actual_port}/"

    print("=" * 72)
    print("⚡ Factorio 2.0 Video-to-Blueprint Generator — Cross-Platform Server")
    print("=" * 72)
    print(f"🌐 Server running at: {url}")
    print(f"💻 Platform: {sys.platform.capitalize()} | Python: {sys.version.split()[0]}")
    print("✨ Supports Linux, macOS, and Windows")
    print("Press Ctrl+C to stop the server.")
    print("=" * 72)

    if open_browser:
        def launch_browser():
            import time
            time.sleep(0.5)
            webbrowser.open(url)
        threading.Thread(target=launch_browser, daemon=True).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down server gracefully...")
        httpd.shutdown()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Factorio 2.0 Video-to-Blueprint Web Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="Port to listen on (default: 5000)")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")
    args = parser.parse_args()

    start_server(host=args.host, port=args.port, open_browser=not args.no_browser)
