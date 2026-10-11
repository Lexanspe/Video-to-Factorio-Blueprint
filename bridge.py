import os
import sys
import json
import math
import io
import base64
from typing import Dict, Any, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.video_processor import (
    extract_video_frames,
    generate_procedural_demo,
    get_media_info,
    frame_bytes_to_image
)
from core.circuit_engine_v3 import compile_blueprint_v3, MAX_PIXELS_PER_STRIPE
from core.circuit_engine_v2 import compile_blueprint_v2
from core.circuit_engine import compile_blueprint as compile_blueprint_v1

def cmd_info(args: List[str]):
    if not args:
        print(json.dumps({"success": False, "error": "Dosya yolu belirtilmedi."}))
        return
    path = args[0]
    if not os.path.exists(path):
        print(json.dumps({"success": False, "error": f"Dosya bulunamadı: {path}"}))
        return
    try:
        info = get_media_info(path)
        w = info.get("width") or info.get("orig_w") or 16
        h = info.get("height") or info.get("orig_h") or 16
        print(json.dumps({
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
        }))
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))

def cmd_demo_info():
    print(json.dumps({
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
            "filename": "Dahili Demo Animasyon"
        }
    }))

def cmd_preview_frame(args: List[str]):
    """Bir karenin base64 JPEG önizlemesini döner."""
    if not args:
        return
    path = args[0]
    h = int(args[1]) if len(args) > 1 else 16
    f_idx = int(args[2]) if len(args) > 2 else 0
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
        print(json.dumps({"success": True, "image": f"data:image/jpeg;base64,{b64}"}))
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))

def cmd_estimate_stats(args: List[str]):
    """Hızlı anlık istatistik hesaplama (video extract etmeden)."""
    try:
        raw_input = args[0] if args else sys.stdin.read()
        p = json.loads(raw_input)
        
        orig_w = int(p.get("orig_w") or p.get("width") or 16)
        orig_h = int(p.get("orig_h") or p.get("height") or 16)
        video_path = p.get("video_path")
        if video_path and os.path.exists(video_path) and video_path != "__demo__":
            try:
                v_info = get_media_info(video_path)
                real_w = v_info.get("width") or v_info.get("orig_w")
                real_h = v_info.get("height") or v_info.get("orig_h")
                if real_w and real_h and (orig_w == 16 and orig_h == 16):
                    orig_w, orig_h = real_w, real_h
            except Exception:
                pass
        target_h = int(p.get("target_h", 16))
        engine = p.get("engine", "v3")
        fps = int(p.get("fps", 5))
        total_frames = int(p.get("total_frames", 16))
        rom_mode = p.get("rom_mode", "horizontal_right")
        num_parts = max(1, int(p.get("num_parts", 1)))
        compact_rom = bool(p.get("compact_rom", True))
        fill_all_rows = bool(p.get("fill_all_rows", True))
        sub_quality = p.get("substation_quality", "legendary")
        
        # En boy hesaplama
        calc_w = max(1, int(round(target_h * (orig_w / max(1, orig_h)))))
        w, h = calc_w, target_h
        lamps_count = w * h
        
        # Paket ve şerit hesabı
        is_horiz = rom_mode.startswith("horizontal")
        is_both = rom_mode.endswith("both")
        
        if engine == "v3":
            frames_per_pack = 16
            comb_per_pack = 2  # 1 Decider + 1 CC
            head_comb_per_stripe = 3 # Shift + Mask + Adapter
        elif engine == "v2":
            frames_per_pack = 3
            comb_per_pack = 7  # 1 CC + 3 Deciders + 3 Shifters
            head_comb_per_stripe = 12  # 12 TrueColor adapter combinators
        else: # v1
            frames_per_pack = 1
            comb_per_pack = 1
            head_comb_per_stripe = 0
            
        total_packs = math.ceil(total_frames / frames_per_pack)
        packs_per_part = math.ceil(total_packs / num_parts)
        
        if is_horiz:
            sub_w = math.ceil(w / 2) if is_both else w
            rows_per_stripe = min(h, max(1, MAX_PIXELS_PER_STRIPE // max(1, sub_w)))
            num_stripes = math.ceil(h / max(1, rows_per_stripe))
        else:
            sub_h = math.ceil(h / 2) if is_both else h
            cols_per_stripe = min(w, max(1, MAX_PIXELS_PER_STRIPE // max(1, sub_h)))
            num_stripes = math.ceil(w / max(1, cols_per_stripe))
            
        if is_both:
            num_stripes *= 2
            
        # Toplam kombinatör tahmini:
        # Clock devresi (~8) + Şerit başları + Paketler
        clock_combs = 8 if engine == "v3" else (4 if engine == "v2" else 2)
        total_rom_combs = (total_packs * comb_per_pack * (2 if is_both else 1)) + (num_stripes * head_comb_per_stripe)
        total_combs = clock_combs + total_rom_combs
        
        # Parça başı kombinatör tahmini
        combs_per_part = []
        for part_idx in range(num_parts):
            p_cnt = min(total_packs, (part_idx + 1) * packs_per_part) - (part_idx * packs_per_part)
            if part_idx > 0:
                p_cnt += 1 # Kopyalama kolaylığı ortak paketi
            p_combs = (p_cnt * comb_per_pack * (2 if is_both else 1))
            if part_idx == 0:
                p_combs += clock_combs + (num_stripes * head_comb_per_stripe)
            combs_per_part.append(max(1, p_combs))
            
        res = {
            "success": True,
            "width": w,
            "height": h,
            "lamps": lamps_count,
            "total_frames": total_frames,
            "total_packs": total_packs,
            "num_stripes": num_stripes,
            "total_combinators": total_combs,
            "combs_per_part": combs_per_part,
            "num_parts": num_parts
        }
        print(json.dumps(res))
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))

def cmd_compile(args: List[str]):
    try:
        raw_input = args[0] if args else sys.stdin.read()
        p = json.loads(raw_input)
        
        video_path = p.get("video_path")
        orig_w = int(p.get("orig_w") or p.get("width") or 16)
        orig_h = int(p.get("orig_h") or p.get("height") or 16)
        target_h = int(p.get("target_h", 16))
        
        if video_path and os.path.exists(video_path) and video_path != "__demo__":
            try:
                v_info = get_media_info(video_path)
                real_w = v_info.get("width") or v_info.get("orig_w")
                real_h = v_info.get("height") or v_info.get("orig_h")
                if real_w and real_h and (orig_w == 16 and orig_h == 16):
                    orig_w, orig_h = real_w, real_h
            except Exception:
                pass
                
        fps = int(p.get("fps", 5))
        max_frames = p.get("max_frames", None)
        engine = p.get("engine", "v3")
        rom_mode = p.get("rom_mode", "horizontal_right")
        part_idx = int(p.get("part_idx", 0))
        num_parts = max(1, int(p.get("num_parts", 1)))
        compact_rom = bool(p.get("compact_rom", True))
        fill_all_rows = bool(p.get("fill_all_rows", True))
        sub_quality = p.get("substation_quality", "legendary")
        
        calc_w = max(1, int(round(target_h * (orig_w / max(1, orig_h)))))
        
        def progress_cb(text: str, frac: float):
            sys.stdout.write(json.dumps({"type": "progress", "msg": text, "fraction": round(frac, 3)}) + "\n")
            sys.stdout.flush()
            
        progress_cb("Kareler ayıklanıyor...", 0.05)
        
        if not video_path or video_path == "__demo__":
            frames = generate_procedural_demo(calc_w, target_h, num_frames=max_frames or 16)
        else:
            frames = extract_video_frames(
                video_path, calc_w, target_h, target_fps=fps,
                max_frames=max_frames,
                progress_callback=lambda cur, tot: progress_cb(f"Kare ayıklanıyor ({cur}/{tot})...", 0.05 + 0.25 * (cur / max(1, tot)))
            )
            
        progress_cb("Blueprint derleniyor...", 0.35)
        
        compile_kwargs = {
            "fps": fps,
            "rom_mode": rom_mode,
            "part_idx": part_idx,
            "num_parts": num_parts,
            "copy_convenience": True,  # Daima aktif
            "compact_rom": compact_rom,
            "fill_all_rows": fill_all_rows,
            "progress_callback": lambda text, frac: progress_cb(text, 0.35 + 0.60 * frac)
        }
        
        if engine == "v3":
            compile_kwargs["substation_quality"] = sub_quality
            bp_str, meta = compile_blueprint_v3(frames, **compile_kwargs)
        elif engine == "v1":
            bp_str, meta = compile_blueprint_v1(frames, **compile_kwargs)
        else:
            bp_str, meta = compile_blueprint_v2(frames, **compile_kwargs)
            
        progress_cb("Tamamlandı!", 1.0)
        
        sys.stdout.write(json.dumps({
            "type": "result",
            "success": True,
            "blueprint": bp_str,
            "meta": meta,
            "part_idx": part_idx,
            "total_parts": num_parts
        }) + "\n")
        sys.stdout.flush()
    except Exception as e:
        sys.stdout.write(json.dumps({"type": "result", "success": False, "error": str(e)}) + "\n")
        sys.stdout.flush()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python bridge.py <command> [args...]")
        sys.exit(1)
        
    cmd = sys.argv[1]
    sub_args = sys.argv[2:]
    
    if cmd == "info":
        cmd_info(sub_args)
    elif cmd == "demo_info":
        cmd_demo_info()
    elif cmd == "preview_frame":
        cmd_preview_frame(sub_args)
    elif cmd == "estimate_stats":
        cmd_estimate_stats(sub_args)
    elif cmd == "compile":
        cmd_compile(sub_args)
    else:
        print(json.dumps({"success": False, "error": f"Bilinmeyen komut: {cmd}"}))
