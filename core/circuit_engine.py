"""
Factorio 2.0 Circuit Engine (Space Age Uyumlu)
==============================================
Telif / Lisans: Factorio 2.0 Video-to-Blueprint Projesi
- 6 Esnek ROM Konumlandırma Modu (Tek/Çift Blok Yatay & Dikey)
- Bağımsız Yeşil Veri Yolu Şeritleri (Row/Column Striping)
- Sıfır Çakışmalı Trafo Şebekesi (Gömülü ve Genişletilmiş 18x18 Karo)
- Tek Merkezî Saat Devresi (Master Clock, signal-F)
- Modüler ROM Bölme / Parçalama (Slicing 1-16 Parça)
- Kopyalama Kolaylığı (+1 Ortak Sütun / Hizalama ve Otomatik Kablo Bağlantı Desteği)
"""

import os
import json
import zlib
import base64
import math
import io
from typing import List, Tuple, Dict, Any, Optional, Union, Callable
from PIL import Image

# Sabit Port ve Yön Tanımları
WIRE_RED = 1
WIRE_GREEN = 2

COMB_IN_RED = 1
COMB_IN_GREEN = 2
COMB_OUT_RED = 3
COMB_OUT_GREEN = 4
POLE_COPPER = 5

DIR_NORTH = 0
DIR_EAST = 4
DIR_SOUTH = 8
DIR_WEST = 12

def _bytes_to_image(b: bytes) -> Image.Image:
    """Bytes formatındaki resmi PIL Image nesnesine dönüştürür."""
    return Image.open(io.BytesIO(b)).convert("RGB")

def _load_curated_signals() -> List[Tuple[str, str]]:
    """Base oyunda kesinlikle çalışan güvenli sinyalleri yükler."""
    json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "safe_signals_pool.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                raw_list = json.load(f)
                pool = []
                for item in raw_list:
                    if isinstance(item, (list, tuple)) and len(item) >= 2:
                        pool.append((str(item[0]), str(item[1])))
                    elif isinstance(item, dict) and "name" in item and "type" in item:
                        pool.append((str(item["name"]), str(item["type"])))
                if pool:
                    return pool
        except Exception:
            pass

    # Yedek güvenli liste
    fallback = []
    for c in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        fallback.append((f"signal-{c}", "virtual"))
    for color in ["red", "green", "blue", "yellow", "pink", "cyan", "white", "grey", "black"]:
        fallback.append((f"signal-{color}", "virtual"))
    base_items = [
        "iron-plate", "copper-plate", "steel-plate", "electronic-circuit",
        "advanced-circuit", "processing-unit", "coal", "stone", "iron-ore",
        "copper-ore", "uranium-ore", "wood", "water", "crude-oil"
    ]
    for it in base_items:
        fallback.append((it, "item"))
    return fallback

SIGNAL_POOL: List[Tuple[str, str]] = _load_curated_signals()
QUALITIES = ["normal", "uncommon", "rare", "epic", "legendary", "quality-unknown"]
MAX_PIXELS_PER_STRIPE: int = len(SIGNAL_POOL) * len(QUALITIES)

def get_signal_for_pixel(l_idx: int) -> Tuple[str, str, str]:
    """Piksel indeksini (l_idx) sinyal adı, türü ve Factorio 2.0 kalitesine eşler."""
    base_idx = l_idx // len(QUALITIES)
    q_idx = l_idx % len(QUALITIES)
    sig_name, sig_type = SIGNAL_POOL[base_idx % len(SIGNAL_POOL)]
    sig_quality = QUALITIES[q_idx]
    return sig_name, sig_type, sig_quality

def get_signal_for_index(idx: int) -> Tuple[str, str]:
    """İndekse karşılık gelen sinyali döndürür."""
    return SIGNAL_POOL[idx % len(SIGNAL_POOL)]

def pack_rgb(r: int, g: int, b: int) -> int:
    """RGB değerlerini Factorio 2.0 Packed RGB 32-bit tamsayısına dönüştürür."""
    r = max(0, min(255, int(r)))
    g = max(0, min(255, int(g)))
    b = max(0, min(255, int(b)))
    return (r << 16) | (g << 8) | b


def compile_blueprint(
    frames: List[Union[Image.Image, bytes]],
    fps: int = 5,
    rom_mode: str = "horizontal_right",
    part_idx: int = 0,
    num_parts: int = 1,
    copy_convenience: bool = True,
    progress_callback: Optional[Callable[[str, float], None]] = None,
    compact_rom: bool = True,
    fill_all_rows: bool = False,
) -> Tuple[str, Dict[str, Any]]:
    """
    Video/GIF karelerinden Factorio 2.0 Space Age uyumlu tam fonksiyonel Monitör Blueprint'i derler.
    
    Özellikler:
    - 6 Esnek ROM Konumlandırma Modu (horizontal_right, horizontal_left, horizontal_both,
      vertical_top, vertical_bottom, vertical_both)
    - Modüler Parçalama (num_parts 1..16):
        * part_idx == 0 (Parça 1): Monitör ekranı + Merkezî Saat Devresi + İlk ROM dilimi
        * part_idx > 0 (Parça 2+): Sadece ilgili dilimin ROM kombinatörleri
    - Kopyalama Kolaylığı (copy_convenience):
        * part_idx > 0 iken önceki parçanın son sütunu (veya dikeyde satırı) kopyaya eklenir.
        * Oyuncu bu ortak sütunu oyun içinde bir önceki parçanın üzerine getirdiğinde
          tüm kırmızı saat ve yeşil veri kabloları otomatik olarak bağlanır!
    """
    valid_modes = [
        "horizontal_right", "horizontal_left", "horizontal_both",
        "vertical_top", "vertical_bottom", "vertical_both"
    ]
    if rom_mode not in valid_modes:
        rom_mode = "horizontal_right"

    # İlk kare boyut bilgisi
    first_frame = frames[0] if isinstance(frames[0], Image.Image) else _bytes_to_image(frames[0])
    width, height = first_frame.size
    total_frames = len(frames)
    safe_fps = max(1, min(60, int(round(fps))))
    g = math.gcd(safe_fps, 60)
    mult = safe_fps // g
    div = 60 // g
    total_ticks = math.ceil(total_frames * div / mult)
    ticks_per_frame = 60.0 / safe_fps

    # Parça / Dilim Hesaplamaları
    num_parts = max(1, min(16, int(num_parts)))
    part_idx = max(0, min(num_parts - 1, int(part_idx)))
    copy_convenience = bool(copy_convenience)

    f_start = (total_frames * part_idx) // num_parts
    f_end = (total_frames * (part_idx + 1)) // num_parts
    if f_start >= f_end:
        f_start = min(part_idx, total_frames - 1)
        f_end = min(part_idx + 1, total_frames)

    include_monitor = (part_idx == 0)
    include_clock = (part_idx == 0)

    # Kopyalama kolaylığı: Parça 2 ve sonrası için önceki parçanın son sütununu ekle
    if part_idx > 0 and copy_convenience:
        compile_f_start = max(0, f_start - 1)
    else:
        compile_f_start = f_start
    compile_f_end = f_end

    entities: List[Dict[str, Any]] = []
    wires: List[List[int]] = []
    entity_id = 1

    is_horizontal = rom_mode.startswith("horizontal")
    is_both = rom_mode.endswith("both")
    is_left = (rom_mode == "horizontal_left")
    is_bottom = (rom_mode == "vertical_bottom")

    step = 18
    half_reach = 9

    # 1. Şerit ve Boyut Hesaplamaları
    if is_horizontal:
        if is_both:
            w_left = math.ceil(width / 2)
            w_right = width - w_left
            max_w_sub = max(w_left, w_right)
            if max_w_sub > MAX_PIXELS_PER_STRIPE:
                raise ValueError(
                    f"Genişlik ({width} px / her blok {max_w_sub} px) sinyal kapasitesini ({MAX_PIXELS_PER_STRIPE}) aşıyor! "
                    f"Lütfen 'Dikey: Çift Blok' seçin veya video çözünürlüğünü düşürün."
                )
            rows_per_stripe = min(8, max(1, MAX_PIXELS_PER_STRIPE // max_w_sub))
        else:
            w_left = width
            w_right = 0
            if width > MAX_PIXELS_PER_STRIPE:
                raise ValueError(
                    f"Genişlik ({width} px) tek blok sinyal kapasitesini ({MAX_PIXELS_PER_STRIPE}) aşıyor! "
                    f"Lütfen 'Yatay: Çift Blok' seçin ({MAX_PIXELS_PER_STRIPE * 2} px'e kadar) veya çözünürlüğü düşürün."
                )
            if width * height <= MAX_PIXELS_PER_STRIPE:
                rows_per_stripe = height
            else:
                rows_per_stripe = min(8, max(1, MAX_PIXELS_PER_STRIPE // width))
        num_stripes = math.ceil(height / rows_per_stripe)
    else: # vertical
        if is_both:
            h_top = math.ceil(height / 2)
            h_bottom = height - h_top
            max_h_sub = max(h_top, h_bottom)
            if max_h_sub > MAX_PIXELS_PER_STRIPE:
                raise ValueError(
                    f"Yükseklik ({height} px / her blok {max_h_sub} px) sinyal kapasitesini ({MAX_PIXELS_PER_STRIPE}) aşıyor! "
                    f"Lütfen video çözünürlüğünü düşürün."
                )
            cols_per_stripe = min(8, max(1, MAX_PIXELS_PER_STRIPE // max_h_sub))
        else:
            h_top = height
            h_bottom = 0
            if height > MAX_PIXELS_PER_STRIPE:
                raise ValueError(
                    f"Yükseklik ({height} px) tek blok dikey sinyal kapasitesini ({MAX_PIXELS_PER_STRIPE}) aşıyor! "
                    f"Lütfen 'Dikey: Çift Blok' seçin ({MAX_PIXELS_PER_STRIPE * 2} px'e kadar) veya çözünürlüğü düşürün."
                )
            if width * height <= MAX_PIXELS_PER_STRIPE:
                cols_per_stripe = width
            else:
                cols_per_stripe = min(8, max(1, MAX_PIXELS_PER_STRIPE // height))
        num_stripes = math.ceil(width / cols_per_stripe)

    if progress_callback:
        stripe_desc = f"{rows_per_stripe} satır/şerit" if is_horizontal else f"{cols_per_stripe} sütun/şerit"
        part_desc = f"Parça {part_idx + 1}/{num_parts} (Kare {compile_f_start}..{compile_f_end - 1})"
        progress_callback(f"Mimari hazırlandı: {num_stripes} şerit ({stripe_desc}) - {part_desc}...", 0.1)

    # 2. Global Trafo Şebekesi Koordinat Alanı
    # Koordinatların tüm parçalarda birebir aynı kalması için toplam kare sayısına göre ayrılır
    comb_span = total_frames * 3.5 + 10.0
    if is_horizontal:
        if is_both:
            min_x_sub = int(-comb_span - 4)
            max_x_sub = int(width + comb_span + 4)
        elif is_left:
            min_x_sub = int(-comb_span - 4)
            max_x_sub = int(width + 4)
        else:
            min_x_sub = -2
            max_x_sub = int(width + comb_span + 4)
        min_y_sub = -4
        max_y_sub = int(height + 6)
    else: # vertical
        min_x_sub = -8
        max_x_sub = int(width + 6)
        if is_both:
            min_y_sub = int(-comb_span - 4)
            max_y_sub = int(height + comb_span + 4)
        elif is_bottom:
            min_y_sub = -2
            max_y_sub = int(height + comb_span + 4)
        else:
            min_y_sub = int(-comb_span - 4)
            max_y_sub = int(height + 4)

    x_start = -2
    while x_start > min_x_sub:
        x_start -= step
    x_coords = []
    x = x_start
    while x - half_reach <= max_x_sub:
        x_coords.append(x)
        x += step

    y_start = -2
    while y_start > min_y_sub:
        y_start -= step
    y_coords = []
    y = y_start
    while y - half_reach <= max_y_sub:
        y_coords.append(y)
        y += step

    # Ekran içi trafo çakışmalarını önle (Mod 2 Gömülü Trafo)
    occupied_lamp_tiles = set()
    for ty in y_coords:
        for tx in x_coords:
            for dtx in (0, 1):
                for dty in (0, 1):
                    px = tx + dtx
                    py = ty + dty
                    if 0 <= px < width and 0 <= py < height:
                        occupied_lamp_tiles.add((px, py))

    # 3. Monitör Ekranı Lambaları ve Kablolama (SADECE PARÇA 1'DE)
    lamp_grid: Dict[Tuple[int, int], int] = {}
    stripe_feed_lamps_A: Dict[int, int] = {}
    stripe_feed_lamps_B: Dict[int, int] = {}

    if include_monitor:
        if progress_callback:
            progress_callback(f"{width}x{height} Ekran matrisi örülüyor...", 0.25)

        if is_horizontal:
            for s in range(num_stripes):
                ys = s * rows_per_stripe
                ye = min(height, (s + 1) * rows_per_stripe)

                if is_both:
                    # Sol Blok: x in [0, w_left - 1]
                    for row_y in range(ys, ye):
                        for lx in range(w_left):
                            if (lx, row_y) in occupied_lamp_tiles:
                                continue
                            l_idx = (row_y - ys) * w_left + lx
                            sig_name, sig_type, sig_quality = get_signal_for_pixel(l_idx)
                            lid = entity_id; entity_id += 1
                            lamp_grid[(lx, row_y)] = lid
                            entities.append({
                                "entity_number": lid, "name": "small-lamp",
                                "position": {"x": float(lx + 0.5), "y": float(row_y + 0.5)},
                                "always_on": True,
                                "control_behavior": {
                                    "use_colors": True, "color_mode": 2,
                                    "rgb_signal": {"type": sig_type, "name": sig_name, "quality": sig_quality}
                                }
                            })
                        r_lamps = [lamp_grid[(lx, row_y)] for lx in range(w_left) if (lx, row_y) in lamp_grid]
                        for i in range(len(r_lamps) - 1):
                            wires.append([r_lamps[i], WIRE_GREEN, r_lamps[i + 1], WIRE_GREEN])

                    leftmost_lamps = []
                    for row_y in range(ys, ye):
                        r_lamps = [lamp_grid[(lx, row_y)] for lx in range(w_left) if (lx, row_y) in lamp_grid]
                        if r_lamps:
                            leftmost_lamps.append(r_lamps[0])
                    for i in range(len(leftmost_lamps) - 1):
                        wires.append([leftmost_lamps[i], WIRE_GREEN, leftmost_lamps[i + 1], WIRE_GREEN])

                    r0_left = [lamp_grid[(lx, ys)] for lx in range(w_left) if (lx, ys) in lamp_grid]
                    if r0_left:
                        stripe_feed_lamps_B[s] = r0_left[0]

                    # Sağ Blok: x in [w_left, width - 1]
                    for row_y in range(ys, ye):
                        for lx in range(w_left, width):
                            if (lx, row_y) in occupied_lamp_tiles:
                                continue
                            l_idx = (row_y - ys) * w_right + (lx - w_left)
                            sig_name, sig_type, sig_quality = get_signal_for_pixel(l_idx)
                            lid = entity_id; entity_id += 1
                            lamp_grid[(lx, row_y)] = lid
                            entities.append({
                                "entity_number": lid, "name": "small-lamp",
                                "position": {"x": float(lx + 0.5), "y": float(row_y + 0.5)},
                                "always_on": True,
                                "control_behavior": {
                                    "use_colors": True, "color_mode": 2,
                                    "rgb_signal": {"type": sig_type, "name": sig_name, "quality": sig_quality}
                                }
                            })
                        r_lamps = [lamp_grid[(lx, row_y)] for lx in range(w_left, width) if (lx, row_y) in lamp_grid]
                        for i in range(len(r_lamps) - 1):
                            wires.append([r_lamps[i], WIRE_GREEN, r_lamps[i + 1], WIRE_GREEN])

                    rightmost_lamps = []
                    for row_y in range(ys, ye):
                        r_lamps = [lamp_grid[(lx, row_y)] for lx in range(w_left, width) if (lx, row_y) in lamp_grid]
                        if r_lamps:
                            rightmost_lamps.append(r_lamps[-1])
                    for i in range(len(rightmost_lamps) - 1):
                        wires.append([rightmost_lamps[i], WIRE_GREEN, rightmost_lamps[i + 1], WIRE_GREEN])

                    r0_right = [lamp_grid[(lx, ys)] for lx in range(w_left, width) if (lx, ys) in lamp_grid]
                    if r0_right:
                        stripe_feed_lamps_A[s] = r0_right[-1]

                else: # Tek blok (sağ veya sol)
                    for row_y in range(ys, ye):
                        for lx in range(width):
                            if (lx, row_y) in occupied_lamp_tiles:
                                continue
                            l_idx = (row_y - ys) * width + lx
                            sig_name, sig_type, sig_quality = get_signal_for_pixel(l_idx)
                            lid = entity_id; entity_id += 1
                            lamp_grid[(lx, row_y)] = lid
                            entities.append({
                                "entity_number": lid, "name": "small-lamp",
                                "position": {"x": float(lx + 0.5), "y": float(row_y + 0.5)},
                                "always_on": True,
                                "control_behavior": {
                                    "use_colors": True, "color_mode": 2,
                                    "rgb_signal": {"type": sig_type, "name": sig_name, "quality": sig_quality}
                                }
                            })
                        r_lamps = [lamp_grid[(lx, row_y)] for lx in range(width) if (lx, row_y) in lamp_grid]
                        for i in range(len(r_lamps) - 1):
                            wires.append([r_lamps[i], WIRE_GREEN, r_lamps[i + 1], WIRE_GREEN])

                    edge_lamps = []
                    for row_y in range(ys, ye):
                        r_lamps = [lamp_grid[(lx, row_y)] for lx in range(width) if (lx, row_y) in lamp_grid]
                        if r_lamps:
                            edge_lamps.append(r_lamps[0] if is_left else r_lamps[-1])
                    for i in range(len(edge_lamps) - 1):
                        wires.append([edge_lamps[i], WIRE_GREEN, edge_lamps[i + 1], WIRE_GREEN])

                    r0 = [lamp_grid[(lx, ys)] for lx in range(width) if (lx, ys) in lamp_grid]
                    if r0:
                        stripe_feed_lamps_A[s] = r0[0] if is_left else r0[-1]

        else: # VERTICAL MODES
            for s in range(num_stripes):
                xs = s * cols_per_stripe
                xe = min(width, (s + 1) * cols_per_stripe)

                if is_both:
                    # Üst Blok: y in [0, h_top - 1]
                    for col_x in range(xs, xe):
                        for y in range(h_top):
                            if (col_x, y) in occupied_lamp_tiles:
                                continue
                            l_idx = (col_x - xs) * h_top + y
                            sig_name, sig_type, sig_quality = get_signal_for_pixel(l_idx)
                            lid = entity_id; entity_id += 1
                            lamp_grid[(col_x, y)] = lid
                            entities.append({
                                "entity_number": lid, "name": "small-lamp",
                                "position": {"x": float(col_x + 0.5), "y": float(y + 0.5)},
                                "always_on": True,
                                "control_behavior": {
                                    "use_colors": True, "color_mode": 2,
                                    "rgb_signal": {"type": sig_type, "name": sig_name, "quality": sig_quality}
                                }
                            })
                        c_lamps = [lamp_grid[(col_x, y)] for y in range(h_top) if (col_x, y) in lamp_grid]
                        for i in range(len(c_lamps) - 1):
                            wires.append([c_lamps[i], WIRE_GREEN, c_lamps[i + 1], WIRE_GREEN])

                    topmost_lamps = []
                    for col_x in range(xs, xe):
                        c_lamps = [lamp_grid[(col_x, y)] for y in range(h_top) if (col_x, y) in lamp_grid]
                        if c_lamps:
                            topmost_lamps.append(c_lamps[0])
                    for i in range(len(topmost_lamps) - 1):
                        wires.append([topmost_lamps[i], WIRE_GREEN, topmost_lamps[i + 1], WIRE_GREEN])

                    c0_top = [lamp_grid[(xs, y)] for y in range(h_top) if (xs, y) in lamp_grid]
                    if c0_top:
                        stripe_feed_lamps_A[s] = c0_top[0]

                    # Alt Blok: y in [h_top, height - 1]
                    for col_x in range(xs, xe):
                        for y in range(h_top, height):
                            if (col_x, y) in occupied_lamp_tiles:
                                continue
                            l_idx = (col_x - xs) * h_bottom + (y - h_top)
                            sig_name, sig_type, sig_quality = get_signal_for_pixel(l_idx)
                            lid = entity_id; entity_id += 1
                            lamp_grid[(col_x, y)] = lid
                            entities.append({
                                "entity_number": lid, "name": "small-lamp",
                                "position": {"x": float(col_x + 0.5), "y": float(y + 0.5)},
                                "always_on": True,
                                "control_behavior": {
                                    "use_colors": True, "color_mode": 2,
                                    "rgb_signal": {"type": sig_type, "name": sig_name, "quality": sig_quality}
                                }
                            })
                        c_lamps = [lamp_grid[(col_x, y)] for y in range(h_top, height) if (col_x, y) in lamp_grid]
                        for i in range(len(c_lamps) - 1):
                            wires.append([c_lamps[i], WIRE_GREEN, c_lamps[i + 1], WIRE_GREEN])

                    bottommost_lamps = []
                    for col_x in range(xs, xe):
                        c_lamps = [lamp_grid[(col_x, y)] for y in range(h_top, height) if (col_x, y) in lamp_grid]
                        if c_lamps:
                            bottommost_lamps.append(c_lamps[-1])
                    for i in range(len(bottommost_lamps) - 1):
                        wires.append([bottommost_lamps[i], WIRE_GREEN, bottommost_lamps[i + 1], WIRE_GREEN])

                    c0_bottom = [lamp_grid[(xs, y)] for y in range(h_top, height) if (xs, y) in lamp_grid]
                    if c0_bottom:
                        stripe_feed_lamps_B[s] = c0_bottom[-1]

                else: # Tek dikey blok (üst veya alt)
                    for col_x in range(xs, xe):
                        for y in range(height):
                            if (col_x, y) in occupied_lamp_tiles:
                                continue
                            l_idx = (col_x - xs) * height + y
                            sig_name, sig_type, sig_quality = get_signal_for_pixel(l_idx)
                            lid = entity_id; entity_id += 1
                            lamp_grid[(col_x, y)] = lid
                            entities.append({
                                "entity_number": lid, "name": "small-lamp",
                                "position": {"x": float(col_x + 0.5), "y": float(y + 0.5)},
                                "always_on": True,
                                "control_behavior": {
                                    "use_colors": True, "color_mode": 2,
                                    "rgb_signal": {"type": sig_type, "name": sig_name, "quality": sig_quality}
                                }
                            })
                        c_lamps = [lamp_grid[(col_x, y)] for y in range(height) if (col_x, y) in lamp_grid]
                        for i in range(len(c_lamps) - 1):
                            wires.append([c_lamps[i], WIRE_GREEN, c_lamps[i + 1], WIRE_GREEN])

                    edge_lamps = []
                    for col_x in range(xs, xe):
                        c_lamps = [lamp_grid[(col_x, y)] for y in range(height) if (col_x, y) in lamp_grid]
                        if c_lamps:
                            edge_lamps.append(c_lamps[-1] if is_bottom else c_lamps[0])
                    for i in range(len(edge_lamps) - 1):
                        wires.append([edge_lamps[i], WIRE_GREEN, edge_lamps[i + 1], WIRE_GREEN])

                    col0 = [lamp_grid[(xs, y)] for y in range(height) if (xs, y) in lamp_grid]
                    if col0:
                        stripe_feed_lamps_A[s] = col0[-1] if is_bottom else col0[0]

    # 2.1. Şerit Koordinat Haritalaması (Trafolar kombinatörlerin arasına girmesin, aradaki boşluklara/koridorlara girsin)
    sub_y_bands = [(float(ty), float(ty + 2.0)) for ty in y_coords]
    sub_x_bands = [(float(tx), float(tx + 2.0)) for tx in x_coords]

    stripe_y_map: Dict[int, float] = {}
    prev_y: Optional[float] = None
    for s in range(num_stripes):
        target_y = float(s * rows_per_stripe + 0.5) if is_horizontal else 0.5
        comb_y = target_y
        if prev_y is not None and comb_y < prev_y + 1.0:
            comb_y = prev_y + 1.0

        for s0, s1 in sub_y_bands:
            if not (comb_y + 0.5 <= s0 or comb_y - 0.5 >= s1):
                cand_above = s0 - 0.5
                min_allowed = (prev_y + 1.0) if prev_y is not None else 0.5
                if cand_above >= min_allowed:
                    comb_y = cand_above
                else:
                    comb_y = s1 + 0.5
                break
        if prev_y is not None and comb_y > prev_y + 8.5:
            cand_low = prev_y + 8.5
            safe = True
            for s0, s1 in sub_y_bands:
                if not (cand_low + 0.5 <= s0 or cand_low - 0.5 >= s1):
                    safe = False
                    break
            if safe:
                comb_y = cand_low
        stripe_y_map[s] = comb_y
        prev_y = comb_y

    stripe_x_map: Dict[int, float] = {}
    prev_x: Optional[float] = None
    for s in range(num_stripes):
        target_x = float(s * cols_per_stripe + 0.5) if not is_horizontal else 0.5
        comb_x = target_x
        if prev_x is not None and comb_x < prev_x + 1.0:
            comb_x = prev_x + 1.0

        for s0, s1 in sub_x_bands:
            if not (comb_x + 0.5 <= s0 or comb_x - 0.5 >= s1):
                cand_left = s0 - 0.5
                min_allowed = (prev_x + 1.0) if prev_x is not None else 0.5
                if cand_left >= min_allowed:
                    comb_x = cand_left
                else:
                    comb_x = s1 + 0.5
                break
        if prev_x is not None and comb_x > prev_x + 8.5:
            cand_left = prev_x + 8.5
            safe = True
            for s0, s1 in sub_x_bands:
                if not (cand_left + 0.5 <= s0 or cand_left - 0.5 >= s1):
                    safe = False
                    break
            if safe:
                comb_x = cand_left
        stripe_x_map[s] = comb_x
        prev_x = comb_x

    # 4. ROM Kombinatör Bankaları İnşası (Kare aralığı: compile_f_start .. compile_f_end - 1)
    if progress_callback:
        progress_callback("ROM kombinatör bankaları inşa ediliyor...", 0.6)

    deciders_A: List[int] = []
    deciders_B: List[int] = []

    substations_list = [(tx, ty) for ty in y_coords for tx in x_coords]

    if is_horizontal:
        start_x_A = float(width + 0.0) if compact_rom else float(width + 2.0)
        start_x_B = 0.0 if compact_rom else -2.0
        pos_x_A = [start_x_A + f_idx * 3.0 for f_idx in range(total_frames)]
        pos_x_B = [start_x_B - f_idx * 3.0 for f_idx in range(total_frames)]

        first_col_x_A = None
        first_col_x_B = None

        # Sağ ROM Bankası (A)
        if rom_mode in ("horizontal_right", "horizontal_both"):
            for s in range(num_stripes):
                ys = s * rows_per_stripe
                ye = min(height, (s + 1) * rows_per_stripe)
                Hs = ye - ys
                s_decs = []
                x_start_p = w_left if is_both else 0

                if fill_all_rows:
                    stripe_cells_A = []
                    c = 0
                    while len(stripe_cells_A) < total_frames:
                        rem_list = list(range(Hs)) if (c % 2 == 0) else list(reversed(range(Hs)))
                        for r in rem_list:
                            row_y = ys + r
                            x_pos = start_x_A + 3.0 * c
                            collides = False
                            for tx, ty in substations_list:
                                if ty <= row_y < ty + 2:
                                    if not (x_pos + 3.0 <= tx or x_pos >= tx + 2.0):
                                        collides = True
                                        break
                            if not collides:
                                stripe_cells_A.append((x_pos, float(row_y + 0.5)))
                                if len(stripe_cells_A) == total_frames:
                                    break
                        c += 1
                    if s == 0 and first_col_x_A is None and stripe_cells_A:
                        first_col_x_A = stripe_cells_A[0][0]

                for f_idx in range(compile_f_start, compile_f_end):
                    frame_data = frames[f_idx]
                    frame = frame_data if isinstance(frame_data, Image.Image) else _bytes_to_image(frame_data)
                    if fill_all_rows:
                        xf, y_pos = stripe_cells_A[f_idx]
                    else:
                        y_pos = stripe_y_map[s]
                        xf = pos_x_A[f_idx]
                    filters = []
                    for py in range(ys, ye):
                        for px in range(x_start_p, width):
                            if (px, py) in occupied_lamp_tiles:
                                continue
                            r, g, b = frame.getpixel((px, py))[:3]
                            packed = pack_rgb(r, g, b)
                            l_idx = (py - ys) * (w_right if is_both else width) + (px - x_start_p)
                            sig_name, sig_type, sig_quality = get_signal_for_pixel(l_idx)
                            filters.append({"type": sig_type, "name": sig_name, "quality": sig_quality, "comparator": "=", "count": packed})

                    sections = []
                    for chunk_i in range(0, max(1, len(filters)), 1000):
                        sec_f = [dict(item, index=idx) for idx, item in enumerate(filters[chunk_i:chunk_i+1000], start=1)]
                        sections.append({"index": len(sections) + 1, "filters": sec_f})

                    dec_id = entity_id; entity_id += 1
                    s_decs.append(dec_id)
                    entities.append({
                        "entity_number": dec_id, "name": "decider-combinator",
                        "position": {"x": xf + 1.0, "y": y_pos}, "direction": DIR_WEST,
                        "control_behavior": {
                            "decider_conditions": {
                                "conditions": [{"first_signal": {"type": "virtual", "name": "signal-F"}, "comparator": "=", "constant": f_idx, "first_signal_networks": {"red": True, "green": False}}],
                                "outputs": [{"signal": {"type": "virtual", "name": "signal-everything"}, "copy_count_from_input": True, "networks": {"red": False, "green": True}}]
                            }
                        }
                    })
                    cc_id = entity_id; entity_id += 1
                    entities.append({"entity_number": cc_id, "name": "constant-combinator", "position": {"x": xf + 2.5, "y": y_pos}, "control_behavior": {"sections": {"sections": sections}}})
                    wires.append([cc_id, WIRE_GREEN, dec_id, COMB_IN_GREEN])

                if s_decs:
                    deciders_A.append(s_decs[0])
                    for i in range(len(s_decs) - 1):
                        wires.append([s_decs[i], COMB_IN_RED, s_decs[i + 1], COMB_IN_RED])
                        wires.append([s_decs[i], COMB_OUT_GREEN, s_decs[i + 1], COMB_OUT_GREEN])
                    if include_monitor and s in stripe_feed_lamps_A:
                        wires.append([s_decs[0], COMB_OUT_GREEN, stripe_feed_lamps_A[s], WIRE_GREEN])

        # Sol ROM Bankası (B)
        if rom_mode in ("horizontal_left", "horizontal_both"):
            for s in range(num_stripes):
                ys = s * rows_per_stripe
                ye = min(height, (s + 1) * rows_per_stripe)
                Hs = ye - ys
                s_decs = []
                x_end_p = w_left if is_both else width

                if fill_all_rows:
                    stripe_cells_B = []
                    c = 0
                    while len(stripe_cells_B) < total_frames:
                        rem_list = list(range(Hs)) if (c % 2 == 0) else list(reversed(range(Hs)))
                        for r in rem_list:
                            row_y = ys + r
                            x_pos = start_x_B - 3.0 * c
                            collides = False
                            for tx, ty in substations_list:
                                if ty <= row_y < ty + 2:
                                    if not (x_pos <= tx or x_pos - 3.0 >= tx + 2.0):
                                        collides = True
                                        break
                            if not collides:
                                stripe_cells_B.append((x_pos, float(row_y + 0.5)))
                                if len(stripe_cells_B) == total_frames:
                                    break
                        c += 1
                    if s == 0 and first_col_x_B is None and stripe_cells_B:
                        first_col_x_B = stripe_cells_B[0][0]

                for f_idx in range(compile_f_start, compile_f_end):
                    frame_data = frames[f_idx]
                    frame = frame_data if isinstance(frame_data, Image.Image) else _bytes_to_image(frame_data)
                    if fill_all_rows:
                        xf, y_pos = stripe_cells_B[f_idx]
                    else:
                        y_pos = stripe_y_map[s]
                        xf = pos_x_B[f_idx]
                    filters = []
                    for py in range(ys, ye):
                        for px in range(0, x_end_p):
                            if (px, py) in occupied_lamp_tiles:
                                continue
                            r, g, b = frame.getpixel((px, py))[:3]
                            packed = pack_rgb(r, g, b)
                            l_idx = (py - ys) * (w_left if is_both else width) + px
                            sig_name, sig_type, sig_quality = get_signal_for_pixel(l_idx)
                            filters.append({"type": sig_type, "name": sig_name, "quality": sig_quality, "comparator": "=", "count": packed})

                    sections = []
                    for chunk_i in range(0, max(1, len(filters)), 1000):
                        sec_f = [dict(item, index=idx) for idx, item in enumerate(filters[chunk_i:chunk_i+1000], start=1)]
                        sections.append({"index": len(sections) + 1, "filters": sec_f})

                    dec_id = entity_id; entity_id += 1
                    s_decs.append(dec_id)
                    entities.append({
                        "entity_number": dec_id, "name": "decider-combinator",
                        "position": {"x": xf - 1.0, "y": y_pos}, "direction": DIR_EAST,
                        "control_behavior": {
                            "decider_conditions": {
                                "conditions": [{"first_signal": {"type": "virtual", "name": "signal-F"}, "comparator": "=", "constant": f_idx, "first_signal_networks": {"red": True, "green": False}}],
                                "outputs": [{"signal": {"type": "virtual", "name": "signal-everything"}, "copy_count_from_input": True, "networks": {"red": False, "green": True}}]
                            }
                        }
                    })
                    cc_id = entity_id; entity_id += 1
                    entities.append({"entity_number": cc_id, "name": "constant-combinator", "position": {"x": xf - 2.5, "y": y_pos}, "control_behavior": {"sections": {"sections": sections}}})
                    wires.append([cc_id, WIRE_GREEN, dec_id, COMB_IN_GREEN])

                if s_decs:
                    target_dec_list = deciders_B if is_both else deciders_A
                    target_dec_list.append(s_decs[0])
                    for i in range(len(s_decs) - 1):
                        wires.append([s_decs[i], COMB_IN_RED, s_decs[i + 1], COMB_IN_RED])
                        wires.append([s_decs[i], COMB_OUT_GREEN, s_decs[i + 1], COMB_OUT_GREEN])
                    if include_monitor:
                        feed_target = stripe_feed_lamps_B.get(s) if is_both else stripe_feed_lamps_A.get(s)
                        if feed_target:
                            wires.append([s_decs[0], COMB_OUT_GREEN, feed_target, WIRE_GREEN])

        if fill_all_rows:
            if first_col_x_A is not None:
                pos_x_A[0] = first_col_x_A
            if first_col_x_B is not None:
                pos_x_B[0] = first_col_x_B

    else: # VERTICAL MODES
        start_y_A = 0.0 if compact_rom else -2.0
        start_y_B = float(height) if compact_rom else float(height + 2.0)
        pos_y_A = [start_y_A - f_idx * 3.0 for f_idx in range(total_frames)]
        pos_y_B = [start_y_B + f_idx * 3.0 for f_idx in range(total_frames)]

        first_row_y_A = None
        first_row_y_B = None

        # Üst ROM Bankası (A)
        if rom_mode in ("vertical_top", "vertical_both"):
            for s in range(num_stripes):
                xs = s * cols_per_stripe
                xe = min(width, (s + 1) * cols_per_stripe)
                Ws = xe - xs
                s_decs = []
                y_end_p = h_top if is_both else height

                if fill_all_rows:
                    stripe_cells_A = []
                    r_idx = 0
                    while len(stripe_cells_A) < total_frames:
                        rem_list = list(range(Ws)) if (r_idx % 2 == 0) else list(reversed(range(Ws)))
                        for c_idx in rem_list:
                            col_x = xs + c_idx
                            y_pos = start_y_A - 3.0 * r_idx
                            collides = False
                            for tx, ty in substations_list:
                                if tx <= col_x < tx + 2:
                                    if not (y_pos <= ty or y_pos - 3.0 >= ty + 2.0):
                                        collides = True
                                        break
                            if not collides:
                                stripe_cells_A.append((float(col_x + 0.5), y_pos))
                                if len(stripe_cells_A) == total_frames:
                                    break
                        r_idx += 1
                    if s == 0 and first_row_y_A is None and stripe_cells_A:
                        first_row_y_A = stripe_cells_A[0][1]

                for f_idx in range(compile_f_start, compile_f_end):
                    frame_data = frames[f_idx]
                    frame = frame_data if isinstance(frame_data, Image.Image) else _bytes_to_image(frame_data)
                    if fill_all_rows:
                        x_pos, yf = stripe_cells_A[f_idx]
                    else:
                        x_pos = stripe_x_map[s]
                        yf = pos_y_A[f_idx]
                    filters = []
                    for px in range(xs, xe):
                        for py in range(0, y_end_p):
                            if (px, py) in occupied_lamp_tiles:
                                continue
                            r, g, b = frame.getpixel((px, py))[:3]
                            packed = pack_rgb(r, g, b)
                            l_idx = (px - xs) * (h_top if is_both else height) + py
                            sig_name, sig_type, sig_quality = get_signal_for_pixel(l_idx)
                            filters.append({"type": sig_type, "name": sig_name, "quality": sig_quality, "comparator": "=", "count": packed})

                    sections = []
                    for chunk_i in range(0, max(1, len(filters)), 1000):
                        sec_f = [dict(item, index=idx) for idx, item in enumerate(filters[chunk_i:chunk_i+1000], start=1)]
                        sections.append({"index": len(sections) + 1, "filters": sec_f})

                    dec_id = entity_id; entity_id += 1
                    s_decs.append(dec_id)
                    entities.append({
                        "entity_number": dec_id, "name": "decider-combinator",
                        "position": {"x": x_pos, "y": yf - 1.0}, "direction": DIR_SOUTH,
                        "control_behavior": {
                            "decider_conditions": {
                                "conditions": [{"first_signal": {"type": "virtual", "name": "signal-F"}, "comparator": "=", "constant": f_idx, "first_signal_networks": {"red": True, "green": False}}],
                                "outputs": [{"signal": {"type": "virtual", "name": "signal-everything"}, "copy_count_from_input": True, "networks": {"red": False, "green": True}}]
                            }
                        }
                    })
                    cc_id = entity_id; entity_id += 1
                    entities.append({"entity_number": cc_id, "name": "constant-combinator", "position": {"x": x_pos, "y": yf - 2.5}, "control_behavior": {"sections": {"sections": sections}}})
                    wires.append([cc_id, WIRE_GREEN, dec_id, COMB_IN_GREEN])

                if s_decs:
                    deciders_A.append(s_decs[0])
                    for i in range(len(s_decs) - 1):
                        wires.append([s_decs[i], COMB_IN_RED, s_decs[i + 1], COMB_IN_RED])
                        wires.append([s_decs[i], COMB_OUT_GREEN, s_decs[i + 1], COMB_OUT_GREEN])
                    if include_monitor and s in stripe_feed_lamps_A:
                        wires.append([s_decs[0], COMB_OUT_GREEN, stripe_feed_lamps_A[s], WIRE_GREEN])

        # Alt ROM Bankası (B)
        if rom_mode in ("vertical_bottom", "vertical_both"):
            for s in range(num_stripes):
                xs = s * cols_per_stripe
                xe = min(width, (s + 1) * cols_per_stripe)
                Ws = xe - xs
                s_decs = []
                y_start_p = h_top if is_both else 0

                if fill_all_rows:
                    stripe_cells_B = []
                    r_idx = 0
                    while len(stripe_cells_B) < total_frames:
                        rem_list = list(range(Ws)) if (r_idx % 2 == 0) else list(reversed(range(Ws)))
                        for c_idx in rem_list:
                            col_x = xs + c_idx
                            y_pos = start_y_B + 3.0 * r_idx
                            collides = False
                            for tx, ty in substations_list:
                                if tx <= col_x < tx + 2:
                                    if not (y_pos + 3.0 <= ty or y_pos >= ty + 2.0):
                                        collides = True
                                        break
                            if not collides:
                                stripe_cells_B.append((float(col_x + 0.5), y_pos))
                                if len(stripe_cells_B) == total_frames:
                                    break
                        r_idx += 1
                    if s == 0 and first_row_y_B is None and stripe_cells_B:
                        first_row_y_B = stripe_cells_B[0][1]

                for f_idx in range(compile_f_start, compile_f_end):
                    frame_data = frames[f_idx]
                    frame = frame_data if isinstance(frame_data, Image.Image) else _bytes_to_image(frame_data)
                    if fill_all_rows:
                        x_pos, yf = stripe_cells_B[f_idx]
                    else:
                        x_pos = stripe_x_map[s]
                        yf = pos_y_B[f_idx]
                    filters = []
                    for px in range(xs, xe):
                        for py in range(y_start_p, height):
                            if (px, py) in occupied_lamp_tiles:
                                continue
                            r, g, b = frame.getpixel((px, py))[:3]
                            packed = pack_rgb(r, g, b)
                            l_idx = (px - xs) * (h_bottom if is_both else height) + (py - y_start_p)
                            sig_name, sig_type, sig_quality = get_signal_for_pixel(l_idx)
                            filters.append({"type": sig_type, "name": sig_name, "quality": sig_quality, "comparator": "=", "count": packed})

                    sections = []
                    for chunk_i in range(0, max(1, len(filters)), 1000):
                        sec_f = [dict(item, index=idx) for idx, item in enumerate(filters[chunk_i:chunk_i+1000], start=1)]
                        sections.append({"index": len(sections) + 1, "filters": sec_f})

                    dec_id = entity_id; entity_id += 1
                    s_decs.append(dec_id)
                    entities.append({
                        "entity_number": dec_id, "name": "decider-combinator",
                        "position": {"x": x_pos, "y": yf + 1.0}, "direction": DIR_NORTH,
                        "control_behavior": {
                            "decider_conditions": {
                                "conditions": [{"first_signal": {"type": "virtual", "name": "signal-F"}, "comparator": "=", "constant": f_idx, "first_signal_networks": {"red": True, "green": False}}],
                                "outputs": [{"signal": {"type": "virtual", "name": "signal-everything"}, "copy_count_from_input": True, "networks": {"red": False, "green": True}}]
                            }
                        }
                    })
                    cc_id = entity_id; entity_id += 1
                    entities.append({"entity_number": cc_id, "name": "constant-combinator", "position": {"x": x_pos, "y": yf + 2.5}, "control_behavior": {"sections": {"sections": sections}}})
                    wires.append([cc_id, WIRE_GREEN, dec_id, COMB_IN_GREEN])

                if s_decs:
                    target_dec_list = deciders_B if is_both else deciders_A
                    target_dec_list.append(s_decs[0])
                    for i in range(len(s_decs) - 1):
                        wires.append([s_decs[i], COMB_IN_RED, s_decs[i + 1], COMB_IN_RED])
                        wires.append([s_decs[i], COMB_OUT_GREEN, s_decs[i + 1], COMB_OUT_GREEN])
                    if include_monitor:
                        feed_target = stripe_feed_lamps_B.get(s) if is_both else stripe_feed_lamps_A.get(s)
                        if feed_target:
                            wires.append([s_decs[0], COMB_OUT_GREEN, feed_target, WIRE_GREEN])

        if fill_all_rows:
            if first_row_y_A is not None:
                pos_y_A[0] = first_row_y_A
            if first_row_y_B is not None:
                pos_y_B[0] = first_row_y_B

    # 5. Merkezî Saat Devresi (SADECE PARÇA 1'DE)
    arith_clock_id: Optional[int] = None
    if include_clock:
        if progress_callback:
            progress_callback("Merkezî saat devresi inşa ediliyor...", 0.75)

        if is_horizontal:
            if rom_mode == "horizontal_left":
                x_clock = pos_x_B[0] - 4.0
                y_clock = -5.5

                cc_clock_id = entity_id; entity_id += 1
                entities.append({
                    "entity_number": cc_clock_id, "name": "constant-combinator",
                    "position": {"x": x_clock - 6.0, "y": y_clock},
                    "control_behavior": {
                        "sections": {"sections": [{"index": 1, "filters": [
                            {"index": 1, "type": "virtual", "name": "signal-C", "quality": "normal", "comparator": "=", "count": 1}
                        ]}]}
                    }
                })

                dec_clock_id = entity_id; entity_id += 1
                entities.append({
                    "entity_number": dec_clock_id, "name": "decider-combinator",
                    "position": {"x": x_clock - 4.0, "y": y_clock}, "direction": DIR_EAST,
                    "control_behavior": {
                        "decider_conditions": {
                            "conditions": [{"first_signal": {"type": "virtual", "name": "signal-C"}, "comparator": "<", "constant": total_ticks, "first_signal_networks": {"red": False, "green": True}}],
                            "outputs": [{"signal": {"type": "virtual", "name": "signal-C"}, "copy_count_from_input": True, "networks": {"red": False, "green": True}}]
                        }
                    }
                })
                wires.append([cc_clock_id, WIRE_GREEN, dec_clock_id, COMB_IN_GREEN])
                wires.append([dec_clock_id, COMB_OUT_GREEN, dec_clock_id, COMB_IN_GREEN])

                arith_sub1 = entity_id; entity_id += 1
                entities.append({
                    "entity_number": arith_sub1, "name": "arithmetic-combinator",
                    "position": {"x": x_clock - 2.0, "y": y_clock}, "direction": DIR_EAST,
                    "control_behavior": {
                        "arithmetic_conditions": {
                            "first_signal": {"type": "virtual", "name": "signal-C"},
                            "second_constant": 1, "operation": "-", "output_signal": {"type": "virtual", "name": "signal-C"}
                        }
                    }
                })
                wires.append([dec_clock_id, COMB_OUT_GREEN, arith_sub1, COMB_IN_GREEN])

                if mult > 1:
                    arith_mul = entity_id; entity_id += 1
                    entities.append({
                        "entity_number": arith_mul, "name": "arithmetic-combinator",
                        "position": {"x": x_clock + 0.0, "y": y_clock}, "direction": DIR_EAST,
                        "control_behavior": {
                            "arithmetic_conditions": {
                                "first_signal": {"type": "virtual", "name": "signal-C"},
                                "second_constant": mult, "operation": "*", "output_signal": {"type": "virtual", "name": "signal-C"}
                            }
                        }
                    })
                    wires.append([arith_sub1, COMB_OUT_GREEN, arith_mul, COMB_IN_GREEN])

                    arith_div = entity_id; entity_id += 1
                    entities.append({
                        "entity_number": arith_div, "name": "arithmetic-combinator",
                        "position": {"x": x_clock + 2.0, "y": y_clock}, "direction": DIR_EAST,
                        "control_behavior": {
                            "arithmetic_conditions": {
                                "first_signal": {"type": "virtual", "name": "signal-C"},
                                "second_constant": div, "operation": "/", "output_signal": {"type": "virtual", "name": "signal-F"}
                            }
                        }
                    })
                    wires.append([arith_mul, COMB_OUT_GREEN, arith_div, COMB_IN_GREEN])
                else:
                    arith_div = entity_id; entity_id += 1
                    entities.append({
                        "entity_number": arith_div, "name": "arithmetic-combinator",
                        "position": {"x": x_clock + 0.0, "y": y_clock}, "direction": DIR_EAST,
                        "control_behavior": {
                            "arithmetic_conditions": {
                                "first_signal": {"type": "virtual", "name": "signal-C"},
                                "second_constant": div, "operation": "/", "output_signal": {"type": "virtual", "name": "signal-F"}
                            }
                        }
                    })
                    wires.append([arith_sub1, COMB_OUT_GREEN, arith_div, COMB_IN_GREEN])

                arith_clock_id = arith_div

            else: # right or both
                x_clock = pos_x_A[0] + 4.0
                y_clock = -3.5

                cc_clock_id = entity_id; entity_id += 1
                entities.append({
                    "entity_number": cc_clock_id, "name": "constant-combinator",
                    "position": {"x": x_clock + 6.0, "y": y_clock},
                    "control_behavior": {
                        "sections": {"sections": [{"index": 1, "filters": [
                            {"index": 1, "type": "virtual", "name": "signal-C", "quality": "normal", "comparator": "=", "count": 1}
                        ]}]}
                    }
                })

                dec_clock_id = entity_id; entity_id += 1
                entities.append({
                    "entity_number": dec_clock_id, "name": "decider-combinator",
                    "position": {"x": x_clock + 4.0, "y": y_clock}, "direction": DIR_WEST,
                    "control_behavior": {
                        "decider_conditions": {
                            "conditions": [{"first_signal": {"type": "virtual", "name": "signal-C"}, "comparator": "<", "constant": total_ticks, "first_signal_networks": {"red": False, "green": True}}],
                            "outputs": [{"signal": {"type": "virtual", "name": "signal-C"}, "copy_count_from_input": True, "networks": {"red": False, "green": True}}]
                        }
                    }
                })
                wires.append([cc_clock_id, WIRE_GREEN, dec_clock_id, COMB_IN_GREEN])
                wires.append([dec_clock_id, COMB_OUT_GREEN, dec_clock_id, COMB_IN_GREEN])

                arith_sub1 = entity_id; entity_id += 1
                entities.append({
                    "entity_number": arith_sub1, "name": "arithmetic-combinator",
                    "position": {"x": x_clock + 2.0, "y": y_clock}, "direction": DIR_WEST,
                    "control_behavior": {
                        "arithmetic_conditions": {
                            "first_signal": {"type": "virtual", "name": "signal-C"},
                            "second_constant": 1, "operation": "-", "output_signal": {"type": "virtual", "name": "signal-C"}
                        }
                    }
                })
                wires.append([dec_clock_id, COMB_OUT_GREEN, arith_sub1, COMB_IN_GREEN])

                if mult > 1:
                    arith_mul = entity_id; entity_id += 1
                    entities.append({
                        "entity_number": arith_mul, "name": "arithmetic-combinator",
                        "position": {"x": x_clock + 0.0, "y": y_clock}, "direction": DIR_WEST,
                        "control_behavior": {
                            "arithmetic_conditions": {
                                "first_signal": {"type": "virtual", "name": "signal-C"},
                                "second_constant": mult, "operation": "*", "output_signal": {"type": "virtual", "name": "signal-C"}
                            }
                        }
                    })
                    wires.append([arith_sub1, COMB_OUT_GREEN, arith_mul, COMB_IN_GREEN])

                    arith_div = entity_id; entity_id += 1
                    entities.append({
                        "entity_number": arith_div, "name": "arithmetic-combinator",
                        "position": {"x": x_clock - 2.0, "y": y_clock}, "direction": DIR_WEST,
                        "control_behavior": {
                            "arithmetic_conditions": {
                                "first_signal": {"type": "virtual", "name": "signal-C"},
                                "second_constant": div, "operation": "/", "output_signal": {"type": "virtual", "name": "signal-F"}
                            }
                        }
                    })
                    wires.append([arith_mul, COMB_OUT_GREEN, arith_div, COMB_IN_GREEN])
                else:
                    arith_div = entity_id; entity_id += 1
                    entities.append({
                        "entity_number": arith_div, "name": "arithmetic-combinator",
                        "position": {"x": x_clock + 0.0, "y": y_clock}, "direction": DIR_WEST,
                        "control_behavior": {
                            "arithmetic_conditions": {
                                "first_signal": {"type": "virtual", "name": "signal-C"},
                                "second_constant": div, "operation": "/", "output_signal": {"type": "virtual", "name": "signal-F"}
                            }
                        }
                    })
                    wires.append([arith_sub1, COMB_OUT_GREEN, arith_div, COMB_IN_GREEN])

                arith_clock_id = arith_div

        else: # VERTICAL MODES
            y_dec0 = pos_y_A[0] - 1.0 if (rom_mode in ("vertical_top", "vertical_both")) else pos_y_B[0] + 1.0
            x_clock = -4.5
            y_clock = y_dec0

            cc_clock_id = entity_id; entity_id += 1
            entities.append({
                "entity_number": cc_clock_id, "name": "constant-combinator",
                "position": {"x": x_clock, "y": y_clock - 6.0},
                "control_behavior": {
                    "sections": {"sections": [{"index": 1, "filters": [
                        {"index": 1, "type": "virtual", "name": "signal-C", "quality": "normal", "comparator": "=", "count": 1}
                    ]}]}
                }
            })

            dec_clock_id = entity_id; entity_id += 1
            entities.append({
                "entity_number": dec_clock_id, "name": "decider-combinator",
                "position": {"x": x_clock, "y": y_clock - 4.0}, "direction": DIR_SOUTH,
                "control_behavior": {
                    "decider_conditions": {
                        "conditions": [{"first_signal": {"type": "virtual", "name": "signal-C"}, "comparator": "<", "constant": total_ticks, "first_signal_networks": {"red": False, "green": True}}],
                        "outputs": [{"signal": {"type": "virtual", "name": "signal-C"}, "copy_count_from_input": True, "networks": {"red": False, "green": True}}]
                    }
                }
            })
            wires.append([cc_clock_id, WIRE_GREEN, dec_clock_id, COMB_IN_GREEN])
            wires.append([dec_clock_id, COMB_OUT_GREEN, dec_clock_id, COMB_IN_GREEN])

            arith_sub1 = entity_id; entity_id += 1
            entities.append({
                "entity_number": arith_sub1, "name": "arithmetic-combinator",
                "position": {"x": x_clock, "y": y_clock - 2.0}, "direction": DIR_SOUTH,
                "control_behavior": {
                    "arithmetic_conditions": {
                        "first_signal": {"type": "virtual", "name": "signal-C"},
                        "second_constant": 1, "operation": "-", "output_signal": {"type": "virtual", "name": "signal-C"}
                    }
                }
            })
            wires.append([dec_clock_id, COMB_OUT_GREEN, arith_sub1, COMB_IN_GREEN])

            if mult > 1:
                arith_mul = entity_id; entity_id += 1
                entities.append({
                    "entity_number": arith_mul, "name": "arithmetic-combinator",
                    "position": {"x": x_clock, "y": y_clock + 0.0}, "direction": DIR_SOUTH,
                    "control_behavior": {
                        "arithmetic_conditions": {
                            "first_signal": {"type": "virtual", "name": "signal-C"},
                            "second_constant": mult, "operation": "*", "output_signal": {"type": "virtual", "name": "signal-C"}
                        }
                    }
                })
                wires.append([arith_sub1, COMB_OUT_GREEN, arith_mul, COMB_IN_GREEN])

                arith_div = entity_id; entity_id += 1
                entities.append({
                    "entity_number": arith_div, "name": "arithmetic-combinator",
                    "position": {"x": x_clock, "y": y_clock + 2.0}, "direction": DIR_SOUTH,
                    "control_behavior": {
                        "arithmetic_conditions": {
                            "first_signal": {"type": "virtual", "name": "signal-C"},
                            "second_constant": div, "operation": "/", "output_signal": {"type": "virtual", "name": "signal-F"}
                        }
                    }
                })
                wires.append([arith_mul, COMB_OUT_GREEN, arith_div, COMB_IN_GREEN])
            else:
                arith_div = entity_id; entity_id += 1
                entities.append({
                    "entity_number": arith_div, "name": "arithmetic-combinator",
                    "position": {"x": x_clock, "y": y_clock + 0.0}, "direction": DIR_SOUTH,
                    "control_behavior": {
                        "arithmetic_conditions": {
                            "first_signal": {"type": "virtual", "name": "signal-C"},
                            "second_constant": div, "operation": "/", "output_signal": {"type": "virtual", "name": "signal-F"}
                        }
                    }
                })
                wires.append([arith_sub1, COMB_OUT_GREEN, arith_div, COMB_IN_GREEN])

            arith_clock_id = arith_div

    # 6. Güç Dağıtımı ve Trafolar (Substations)
    # Sadece bu parçada yer alan varlıkların alanını kapsayacak trafolar yerleştirilir
    substations: Dict[Tuple[int, int], Dict[str, Any]] = {}
    if entities:
        if progress_callback:
            progress_callback("Elektrik şebekesi ve trafolar yerleştiriliyor...", 0.85)

        all_x = [e["position"]["x"] for e in entities]
        all_y = [e["position"]["y"] for e in entities]
        min_x_act = min(all_x); max_x_act = max(all_x)
        min_y_act = min(all_y); max_y_act = max(all_y)

        final_x_coords = []
        x = x_start
        while x - half_reach <= max_x_act:
            if x + half_reach >= min_x_act:
                final_x_coords.append(x)
            x += step

        final_y_coords = []
        y = y_start
        while y - half_reach <= max_y_act:
            if y + half_reach >= min_y_act:
                final_y_coords.append(y)
            y += step

        sub_list: List[Dict[str, Any]] = []
        for ty in final_y_coords:
            for tx in final_x_coords:
                sid = entity_id; entity_id += 1
                cx = float(tx + 1.0)
                cy = float(ty + 1.0)
                sub = {
                    "entity_number": sid, "name": "substation",
                    "position": {"x": cx, "y": cy},
                    "tx": tx, "ty": ty
                }
                substations[(tx, ty)] = sub
                sub_list.append(sub)
                entities.append(sub)

        for sub in sub_list:
            for dx, dy in [(step, 0), (0, step)]:
                neighbor = substations.get((sub["tx"] + dx, sub["ty"] + dy))
                if neighbor:
                    dist = math.hypot(sub["position"]["x"] - neighbor["position"]["x"],
                                      sub["position"]["y"] - neighbor["position"]["y"])
                    if dist <= 18.5:
                        wires.append([sub["entity_number"], POLE_COPPER, neighbor["entity_number"], POLE_COPPER])

        # 6.1. Sol Üst Hizalama Trafosu (Alignment Substation Reference)
        # Monitörün sol üstündeki ana trafonun (tx=-2, ty=-2 -> x=-1.0, y=-1.0) hemen 2 kare yukarısına
        # (tx=-2, ty=-4 -> x=-1.0, y=-3.0) bir trafo daha eklenir.
        # Bu iki trafo, çok parçalı dilimlerde (Part 2, 3...) yapıştırma sırasında dünya koordinatlarını
        # ve monitörün konumunu birebir eşleştirmek için referans çapa (anchor) görevi görür.
        align_tx = -2
        align_ty = -4
        align_sub_id = entity_id; entity_id += 1
        align_sub = {
            "entity_number": align_sub_id,
            "name": "substation",
            "position": {"x": -1.0, "y": -3.0},
            "tx": align_tx,
            "ty": align_ty
        }
        entities.append(align_sub)

        main_tl_sub = substations.get((-2, -2))
        if main_tl_sub:
            wires.append([align_sub_id, POLE_COPPER, main_tl_sub["entity_number"], POLE_COPPER])
        elif not include_monitor:
            tl_sub_id = entity_id; entity_id += 1
            tl_sub = {
                "entity_number": tl_sub_id,
                "name": "substation",
                "position": {"x": -1.0, "y": -1.0},
                "tx": -2,
                "ty": -2
            }
            entities.append(tl_sub)
            wires.append([align_sub_id, POLE_COPPER, tl_sub_id, POLE_COPPER])

    # 7. Saat Sinyali Kırmızı Kablo Dağıtımı (SADECE PARÇA 1'DE)
    if include_clock and arith_clock_id is not None:
        ent_map = {e["entity_number"]: e for e in entities}
        if deciders_A:
            for i in range(len(deciders_A) - 1):
                p1 = ent_map[deciders_A[i]]["position"]
                p2 = ent_map[deciders_A[i + 1]]["position"]
                if math.hypot(p1["x"] - p2["x"], p1["y"] - p2["y"]) <= 9.0:
                    wires.append([deciders_A[i], COMB_IN_RED, deciders_A[i + 1], COMB_IN_RED])
                elif sub_list:
                    bridge = min(sub_list, key=lambda s: math.hypot(s["position"]["x"] - p1["x"], s["position"]["y"] - p1["y"]) + math.hypot(s["position"]["x"] - p2["x"], s["position"]["y"] - p2["y"]))
                    wires.append([deciders_A[i], COMB_IN_RED, bridge["entity_number"], WIRE_RED])
                    wires.append([bridge["entity_number"], WIRE_RED, deciders_A[i + 1], COMB_IN_RED])
                else:
                    wires.append([deciders_A[i], COMB_IN_RED, deciders_A[i + 1], COMB_IN_RED])
            wires.append([arith_clock_id, COMB_OUT_RED, deciders_A[0], COMB_IN_RED])

        if deciders_B:
            for i in range(len(deciders_B) - 1):
                p1 = ent_map[deciders_B[i]]["position"]
                p2 = ent_map[deciders_B[i + 1]]["position"]
                if math.hypot(p1["x"] - p2["x"], p1["y"] - p2["y"]) <= 9.0:
                    wires.append([deciders_B[i], COMB_IN_RED, deciders_B[i + 1], COMB_IN_RED])
                elif sub_list:
                    bridge = min(sub_list, key=lambda s: math.hypot(s["position"]["x"] - p1["x"], s["position"]["y"] - p1["y"]) + math.hypot(s["position"]["x"] - p2["x"], s["position"]["y"] - p2["y"]))
                    wires.append([deciders_B[i], COMB_IN_RED, bridge["entity_number"], WIRE_RED])
                    wires.append([bridge["entity_number"], WIRE_RED, deciders_B[i + 1], COMB_IN_RED])
                else:
                    wires.append([deciders_B[i], COMB_IN_RED, deciders_B[i + 1], COMB_IN_RED])

        # Sadece Bank B varsa (horizontal_left):
        if not deciders_A and deciders_B:
            wires.append([arith_clock_id, COMB_OUT_RED, deciders_B[0], COMB_IN_RED])

        # Çift blok modlarında uzak bloğa kırmızı saat kablosu köprüsü (Trafo Port 1 Kırmızı Bus)
        if is_both and deciders_B and substations:
            if is_horizontal and final_y_coords and final_x_coords:
                top_ty = final_y_coords[0]
                top_subs = [substations[(tx, top_ty)] for tx in final_x_coords if (tx, top_ty) in substations]
                top_subs.sort(key=lambda s: s["tx"])
                if top_subs:
                    for i in range(len(top_subs) - 1):
                        wires.append([top_subs[i]["entity_number"], WIRE_RED, top_subs[i + 1]["entity_number"], WIRE_RED])
                    clk_pos = {e["entity_number"]: e for e in entities}[arith_clock_id]["position"]
                    nearest_clock_sub = min(top_subs, key=lambda s: math.hypot(s["position"]["x"] - clk_pos["x"], s["position"]["y"] - clk_pos["y"]))
                    wires.append([arith_clock_id, COMB_OUT_RED, nearest_clock_sub["entity_number"], WIRE_RED])
                    e_b0 = {e["entity_number"]: e for e in entities}[deciders_B[0]]
                    nearest_b0_sub = min(top_subs, key=lambda s: math.hypot(s["position"]["x"] - e_b0["position"]["x"], s["position"]["y"] - e_b0["position"]["y"]))
                    wires.append([nearest_b0_sub["entity_number"], WIRE_RED, deciders_B[0], COMB_IN_RED])
            elif not is_horizontal and final_x_coords and final_y_coords: # vertical_both
                left_tx = final_x_coords[0]
                left_subs = [substations[(left_tx, ty)] for ty in final_y_coords if (left_tx, ty) in substations]
                left_subs.sort(key=lambda s: s["ty"])
                if left_subs:
                    for i in range(len(left_subs) - 1):
                        wires.append([left_subs[i]["entity_number"], WIRE_RED, left_subs[i + 1]["entity_number"], WIRE_RED])
                    clk_pos = {e["entity_number"]: e for e in entities}[arith_clock_id]["position"]
                    nearest_clock_sub = min(left_subs, key=lambda s: math.hypot(s["position"]["x"] - clk_pos["x"], s["position"]["y"] - clk_pos["y"]))
                    wires.append([arith_clock_id, COMB_OUT_RED, nearest_clock_sub["entity_number"], WIRE_RED])
                    e_b0 = {e["entity_number"]: e for e in entities}[deciders_B[0]]
                    nearest_b0_sub = min(left_subs, key=lambda s: math.hypot(s["position"]["x"] - e_b0["position"]["x"], s["position"]["y"] - e_b0["position"]["y"]))
                    wires.append([nearest_b0_sub["entity_number"], WIRE_RED, deciders_B[0], COMB_IN_RED])

    # 8. Blueprint Sıkıştırma ve Çıktı Üretimi
    if progress_callback:
        progress_callback("Blueprint JSON paketleniyor ve sıkıştırılıyor...", 0.95)

    out = io.StringIO()
    out.write('{"blueprint":{"icons":[{"signal":{"name":"small-lamp"},"index":1},'
              '{"signal":{"name":"decider-combinator"},"index":2}],"entities":[')
    for i, ent in enumerate(entities):
        if i > 0:
            out.write(',')
        out.write(json.dumps(ent, separators=(',', ':')))

    out.write('],"wires":[')
    for i, wire in enumerate(wires):
        if i > 0:
            out.write(',')
        out.write(json.dumps(wire, separators=(',', ':')))

    out.write('],"item":"blueprint","version":562954249306113}}')
    json_str = out.getvalue()
    out = None

    json_bytes = json_str.encode('utf-8')
    json_str = None
    compressed = zlib.compress(json_bytes, level=9)
    json_bytes = None
    bp_string = "0" + base64.b64encode(compressed).decode('utf-8')
    compressed = None

    metadata = {
        "width": width,
        "height": height,
        "fps": fps,
        "total_frames": total_frames,
        "ticks_per_frame": ticks_per_frame,
        "rom_mode": rom_mode,
        "num_stripes": num_stripes,
        "num_entities": len(entities),
        "num_wires": len(wires),
        "blueprint_length": len(bp_string),
        "part_idx": part_idx,
        "num_parts": num_parts,
        "copy_convenience": copy_convenience,
        "f_start": f_start,
        "f_end": f_end,
        "compile_f_start": compile_f_start,
        "compile_f_end": compile_f_end,
        "include_monitor": include_monitor,
        "include_clock": include_clock,
        "compact_rom": compact_rom,
        "fill_all_rows": fill_all_rows,
    }

    if progress_callback:
        progress_callback("Hazır!", 1.0)

    return bp_string, metadata
