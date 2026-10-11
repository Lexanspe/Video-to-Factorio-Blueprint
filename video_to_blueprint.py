#!/usr/bin/env python3
"""
Factorio 2.0 Video-to-Blueprint Dönüştürücü
=========================================
Bu araç, herhangi bir video veya GIF dosyasını Factorio 2.0 (Space Age) lambaları, 
sabit kombinatörleri (ROM), karar kombinatörleri (kapılar), saat devresi ve
trafolardan oluşan eksiksiz ve çalışan bir 'Monitör / Video Oynatıcı' blueprint'ine dönüştürür.
"""

import os
import sys
import argparse
import subprocess
from typing import List
from PIL import Image

# Windows konsolunda UTF-8 karakterlerin sorunsuz basılmasını sağla
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from core.video_processor import extract_video_frames, generate_procedural_demo, get_media_dimensions
from core.circuit_engine_v3 import compile_blueprint_v3
from core.circuit_engine_v2 import compile_blueprint_v2
from core.circuit_engine import compile_blueprint as compile_blueprint_v1

def build_video_blueprint(frames: List[Image.Image], fps: int = 5, engine: str = "v3") -> str:
    """Verilen video karelerinden Factorio 2.0 Monitör Blueprint'ini derler."""
    if engine == "v1":
        compile_fn = compile_blueprint_v1
    elif engine == "v2":
        compile_fn = compile_blueprint_v2
    else:
        compile_fn = compile_blueprint_v3
    bp_string, _ = compile_fn(frames, fps=fps)
    return bp_string

def copy_to_clipboard(text: str) -> bool:
    """Windows panosuna metni kopyalar."""
    try:
        process = subprocess.Popen('clip', stdin=subprocess.PIPE, shell=True)
        process.communicate(text.encode('utf-8'))
        return True
    except Exception:
        return False

def main():
    parser = argparse.ArgumentParser(description="Factorio 2.0 Video-to-Blueprint Dönüştürücü")
    parser.add_argument("input", nargs="?", default=None, help="Girdi video veya GIF dosyası yolu (belirtilmezse demo üretir)")
    parser.add_argument("-H", "--height", type=int, default=16, help="Monitör yüksekliği (satır sayısı, varsayılan 16)")
    parser.add_argument("-w", "--width", type=int, default=None, help="Monitör genişliği (piksel, belirtilmezse en-boy oranından otomatik hesaplanır)")
    parser.add_argument("--fps", type=int, default=5, help="Oynatma hızı FPS (1-60, varsayılan 5)")
    parser.add_argument("--max-frames", type=int, default=60, help="Maksimum kare sayısı (0 = sınırsız, varsayılan 60)")
    parser.add_argument("-e", "--engine", type=str, default="v3", choices=["v1", "v2", "v3"],
                        help="Kullanılacak devre motoru: v3 (16 kare/sinyal 2-bit), v2 (27-bit), v1 (RGB24) (varsayılan: v3)")
    parser.add_argument("-m", "--rom-mode", type=str, default="horizontal_right",
                        choices=["horizontal_right", "horizontal_left", "horizontal_both", "vertical_top", "vertical_bottom", "vertical_both"],
                        help="ROM kombinatör yerleşimi (varsayılan: horizontal_right)")
    parser.add_argument("--fill-all-rows", action="store_true", default=False,
                        help="ROM kombinatörlerini tüm satırlara/sütunlara dağıtarak kompakt 2D ızgara halinde yerleştir")
    parser.add_argument("--substation-quality", type=str, default="legendary",
                        choices=["none", "normal", "uncommon", "rare", "epic", "legendary"],
                        help="Trafo (Substation) niteliği: none, normal, uncommon, rare, epic, legendary (varsayılan: legendary)")
    parser.add_argument("-o", "--output", type=str, default="blueprint.txt", help="Çıktı blueprint metin dosyası")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("FACTORIO 2.0 VIDEO-TO-BLUEPRINT DÖNÜŞTÜRÜCÜ")
    print("=" * 60)
    
    height = args.height
    if args.input and os.path.exists(args.input):
        print(f"[*] Dosya açılıyor: {args.input}")
        orig_w, orig_h = get_media_dimensions(args.input)
        if args.width is None:
            width = max(4, int(round(height * (orig_w / orig_h))))
            print(f"[*] Orijinal oran ({orig_w}:{orig_h}) baz alınarak genişlik otomatik hesaplandı: {width} px")
        else:
            width = args.width
        frames = extract_video_frames(args.input, width, height, target_fps=args.fps, max_frames=args.max_frames)
    else:
        width = 16 if args.width is None else args.width
        print(f"[*] Girdi dosyası belirtilmedi. {width}x{height} boyutunda {args.fps} FPS hızında DEMO animasyon üretiliyor...")
        frames = generate_procedural_demo(width, height, fps=args.fps, max_frames=args.max_frames)
        
    print(f"[+] Toplam {len(frames)} kare işlendi. (Çözünürlük: {width}x{height}, {args.fps} FPS, ROM Modu: {args.rom_mode})")
    print("[*] Devre ağı, ROM bankası, saat devresi ve lambalar derleniyor...")
    
    if args.engine == "v1":
        compile_fn = compile_blueprint_v1
    elif args.engine == "v2":
        compile_fn = compile_blueprint_v2
    else:
        compile_fn = compile_blueprint_v3

    compile_kwargs = {"fps": args.fps, "rom_mode": args.rom_mode}
    if args.engine in ("v2", "v3"):
        compile_kwargs["fill_all_rows"] = args.fill_all_rows
    if args.engine == "v3":
        compile_kwargs["substation_quality"] = args.substation_quality
    bp_string, meta = compile_fn(frames, **compile_kwargs)
    
    output_path = os.path.abspath(args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(bp_string)
        
    print(f"[V] Başarılı! Blueprint kaydedildi: {output_path}")
    print(f"[i] ROM Yerleşimi: {meta.get('rom_mode', args.rom_mode)}")
    if "substation_quality" in meta:
        print(f"[i] Trafo Niteliği: {meta['substation_quality']} (Kapsama/Adım: {meta.get('substation_step', 18)}x{meta.get('substation_step', 18)} karo, Tel Menzili: {meta.get('substation_reach', 18.0)} karo)")
    total_ents = meta.get('total_entities', meta.get('num_entities', 'N/A'))
    total_wrs = meta.get('total_wires', meta.get('num_wires', 'N/A'))
    print(f"[i] Toplam Varlık Sayısı: {total_ents}")
    print(f"[i] Toplam Tel Bağlantısı: {total_wrs}")
    print(f"[i] Blueprint String Karakter Sayısı: {len(bp_string):,}")
    
    if copy_to_clipboard(bp_string):
        print("[V] Blueprint string otomatik olarak PANONUZA (Clipboard) KOPYALANDI! Oyunda 'Ctrl + V' ile doğrudan yapıştırabilirsiniz.")
    else:
        print("[i] Blueprint stringini dosyadan kopyalayabilirsiniz.")

if __name__ == "__main__":
    main()
