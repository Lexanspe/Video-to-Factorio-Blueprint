"""
Factorio 2.0 Circuit Engine V3 — Yeni Nesil Dinamik Shift & 6 Kalite Mimarisi
=============================================================================
MİMARİ ÖZELLİKLERİ:
1. 6 KALİTE GENİŞLETİLMİŞ SİNYAL HAVUZU (13.008 Piksel / Şerit):
   - Factorio 2.0 Space Age sinyalleri (item, entity, recipe, fluid, virtual, space-location vb.)
     ve 6 kalite seviyesi (normal, uncommon, rare, epic, legendary, quality-unknown) kullanılarak
     2.168 benzersiz temel sinyal 6 katına çıkarılır: 2.168 x 6 = 13.008 benzersiz piksel sinyali.
   - 32x32 (1024 px), 64x64 (4096 px), 80x60 (4800 px) ve 100x100 (10000 px) monitörler TEK BİR ŞERİTTE tamamlanır!

2. EN ALT BİTTEN 2-BİT ZAMANSAL PAKETLEME (Bit 0'dan Başlayan Paketleme):
   - k = frame % 16 için piksel verisi (v & 3) << (2 * k) ile paketlenir.
   - k = 0  -> << 0  (Bit 0-1)
   - k = 1  -> << 2  (Bit 2-3)
   - ...
   - k = 15 -> << 30 (Bit 30-31)

3. DİNAMİK SHIFT HESAPLAYICI (Merkezî Saatte 2 Kombinatör):
   - signal-F % 16 -> signal-F (kare içi indeks k)
   - signal-F * 2  -> signal-S (dinamik shift miktarı: 0, 2, 4, ..., 30)
   - Kırmızı saat hattı hem signal-F hem de signal-S taşır.

4. ULTRA KOMPAKT ROM PAKETLERİ (16 Kare Başına YALNIZCA 2 KOMBİNATÖR!):
   - ROM paketlerinde artık sadece 2 kombinatör (1 Decider + 1 CC = 3 karo) yer alır.
   - Shift (`>> signal-S`) ve Maske (`AND 3`) aritmetik kombinatörleri her şeridin başında
     uyarlayıcının (`* 5592405`) önünde şerit başına YALNIZCA 1 KEZ kullanılır!
   - ROM genişliğinde %57, kombinatör sayısında devasa küçülme sağlanır!

5. SIFIR ÇAKIŞMA, MONİTÖRDE SIFIR KIRMIZI KABLO:
   - Kombinatör düzeyinde sürekli kaydırma (Per-combinator continuous clearance).
   - Monitör içi trafolardan hiçbir kırmızı devre kablosu geçmez.
"""

import os
import sys
import json
import zlib
import base64
import math
import io
from typing import List, Tuple, Dict, Any, Optional, Union, Callable
from PIL import Image

# Port ve Yön sabitleri (Factorio 2.0)
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

FRAMES_PER_SIGNAL = 16
ADAPTER_MULTIPLIER = 5592405   # 0x555555: 2-bit -> 24-bit TrueColor
QUALITIES = ["normal", "uncommon", "rare", "epic", "legendary", "quality-unknown"]


def _bytes_to_image(b: bytes) -> Image.Image:
    return Image.open(io.BytesIO(b)).convert("RGB")


def _load_curated_signals() -> List[Tuple[str, str]]:
    json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "safe_signals_pool.json")
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
    fallback = []
    for c in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        fallback.append((f"signal-{c}", "virtual"))
    for color in ["red", "green", "blue", "yellow", "pink", "cyan", "white", "grey", "black"]:
        fallback.append((f"signal-{color}", "virtual"))
    return fallback


SIGNAL_POOL: List[Tuple[str, str]] = _load_curated_signals()
# 5 kalite ile genişletilmiş sinyal kapasitesi: 2.168 * 5 = 10.840
MAX_PIXELS_PER_STRIPE: int = len(SIGNAL_POOL) * len(QUALITIES)


def get_signal_for_pixel(l_idx: int) -> Tuple[str, str, str]:
    """
    Piksel indeksini (l_idx) sinyal adı, türü ve Factorio 2.0 kalitesine eşler.
    l_idx = 0..(MAX_PIXELS_PER_STRIPE - 1)
    """
    base_idx = l_idx // len(QUALITIES)
    q_idx = l_idx % len(QUALITIES)
    sig_name, sig_type = SIGNAL_POOL[base_idx]
    sig_quality = QUALITIES[q_idx]
    return sig_name, sig_type, sig_quality


def pack_2bit_grayscale(r: int, g: int, b: int) -> int:
    y = (r * 299 + g * 587 + b * 114) // 1000
    return min(3, max(0, (y * 3 + 127) // 255))


def pack_16frames_to_int32(vals_16: List[int]) -> int:
    """
    16 karelik 2-bit parlaklık değerlerini bit 0'dan başlayarak int32 içine paketler.
    k=0  -> bit 0-1
    k=1  -> bit 2-3
    ...
    k=15 -> bit 30-31
    """
    val = 0
    for k in range(16):
        v = vals_16[k] if k < len(vals_16) else 0
        val |= (v & 0x3) << (2 * k)
    if val >= 0x80000000:
        val -= 0x100000000
    return val


def _place_one_combinator(
    cur_p: float,
    w: float,
    direction: int,
    sub_intervals: List[Tuple[float, float]]
) -> Tuple[float, float]:
    """
    Kombinatör düzeyinde sürekli kaydırma (Per-combinator continuous clearance).
    Tüm bloğu kaydırmak yerine sadece ve sadece trafo ile çakışan kombinatörü
    trafonun öbür tarafına kaydırır. Aralarda gereksiz boşluk bırakılmaz.

    direction = +1 : cur_p artar (sağa / aşağı).
    direction = -1 : cur_p azalır (sola / yukarı).
    """
    if direction == 1:
        while True:
            collides = False
            for st, en in sub_intervals:
                if max(st, cur_p) < min(en, cur_p + w) - 0.001:
                    collides = True
                    cur_p = en
                    break
            if not collides:
                break
        center = cur_p + w / 2.0
        new_cur_p = cur_p + w
    else:
        while True:
            collides = False
            for st, en in sub_intervals:
                if max(st, cur_p - w) < min(en, cur_p) - 0.001:
                    collides = True
                    cur_p = st
                    break
            if not collides:
                break
        center = cur_p - w / 2.0
        new_cur_p = cur_p - w
    return center, new_cur_p


def compile_blueprint_v3(
    frames: List[Union[Image.Image, bytes]],
    fps: int = 5,
    rom_mode: str = "horizontal_right",
    part_idx: int = 0,
    num_parts: int = 1,
    copy_convenience: bool = True,
    progress_callback: Optional[Callable[[str, float], None]] = None,
    total_parts: Optional[int] = None,
    compact_rom: bool = True,
    fill_all_rows: bool = False,
    substation_quality: str = "legendary",
) -> Tuple[str, Dict[str, Any]]:
    """
    Factorio 2.0 Video-to-Blueprint V3 Derleyicisi — Dinamik Shift & 5 Kalite Mimarisi.
    """
    if not frames:
        raise ValueError("En az bir kare (frame) sağlanmalıdır.")

    valid_qualities = ["none", "normal", "uncommon", "rare", "epic", "legendary"]
    if not substation_quality or substation_quality not in valid_qualities:
        substation_quality = "legendary"

    f0 = frames[0]
    first_img = f0 if isinstance(f0, Image.Image) else _bytes_to_image(f0)
    width, height = first_img.size
    total_frames = len(frames)

    valid_modes = [
        "horizontal_right", "horizontal_left", "horizontal_both",
        "vertical_top", "vertical_bottom", "vertical_both"
    ]
    if rom_mode not in valid_modes:
        rom_mode = "horizontal_right"

    is_horizontal = rom_mode.startswith("horizontal")
    is_both = rom_mode.endswith("both")
    is_left = (rom_mode == "horizontal_left")
    is_bottom = (rom_mode == "vertical_bottom")

    safe_fps = max(1, min(60, int(round(fps))))
    g = math.gcd(safe_fps, 60)
    clk_mult = safe_fps // g
    clk_div = 60 // g
    total_ticks = math.ceil(total_frames * clk_div / clk_mult)
    ticks_per_frame = 60.0 / safe_fps

    # 1. Şerit (Stripe) Hesaplamaları (1425 piksel kapasitesi ile)
    if is_horizontal:
        if is_both:
            w_left = math.ceil(width / 2)
            w_right = width - w_left
            max_w_sub = max(w_left, w_right)
            if max_w_sub > MAX_PIXELS_PER_STRIPE:
                raise ValueError(f"Genişlik ({max_w_sub} px) sinyal sınırını ({MAX_PIXELS_PER_STRIPE}) aşıyor!")
            rows_per_stripe = min(height, max(1, MAX_PIXELS_PER_STRIPE // max_w_sub))
        else:
            w_left = width; w_right = 0
            if width > MAX_PIXELS_PER_STRIPE:
                raise ValueError(f"Genişlik ({width} px) sinyal sınırını ({MAX_PIXELS_PER_STRIPE}) aşıyor!")
            rows_per_stripe = height if width * height <= MAX_PIXELS_PER_STRIPE else min(height, max(1, MAX_PIXELS_PER_STRIPE // width))
        num_stripes = math.ceil(height / rows_per_stripe)
        cols_per_stripe = 0
    else:
        if is_both:
            h_top = math.ceil(height / 2)
            h_bottom = height - h_top
            max_h_sub = max(h_top, h_bottom)
            if max_h_sub > MAX_PIXELS_PER_STRIPE:
                raise ValueError(f"Yükseklik ({max_h_sub} px) sinyal sınırını ({MAX_PIXELS_PER_STRIPE}) aşıyor!")
            cols_per_stripe = min(width, max(1, MAX_PIXELS_PER_STRIPE // max_h_sub))
        else:
            h_top = height; h_bottom = 0
            if height > MAX_PIXELS_PER_STRIPE:
                raise ValueError(f"Yükseklik ({height} px) sinyal sınırını ({MAX_PIXELS_PER_STRIPE}) aşıyor!")
            cols_per_stripe = width if width * height <= MAX_PIXELS_PER_STRIPE else min(width, max(1, MAX_PIXELS_PER_STRIPE // height))
        num_stripes = math.ceil(width / cols_per_stripe)
        rows_per_stripe = 0

    # 2. Parçalama (Slicing) — Paket (Pack) Düzeyinde
    total_packs = math.ceil(total_frames / FRAMES_PER_SIGNAL)
    num_parts = max(1, min(16, int(num_parts))) if num_parts is not None else (total_parts if total_parts is not None else 1)
    part_idx = max(0, min(num_parts - 1, int(part_idx)))
    copy_convenience = bool(copy_convenience)

    # Parçalar paket bazında ayrılır
    packs_per_part = math.ceil(total_packs / num_parts)
    p_start = part_idx * packs_per_part
    p_end = min(total_packs, (part_idx + 1) * packs_per_part)
    if p_start >= p_end:
        p_start = min(part_idx, total_packs - 1)
        p_end = min(part_idx + 1, total_packs)

    # Kopyalama kolaylığı: part_idx > 0 ise bir önceki paketi de referans olarak ekle
    compile_p_start = max(0, p_start - 1) if (part_idx > 0 and copy_convenience) else p_start
    compile_p_end = p_end

    f_start = p_start * FRAMES_PER_SIGNAL
    f_end = min(total_frames, p_end * FRAMES_PER_SIGNAL)
    compile_f_start = compile_p_start * FRAMES_PER_SIGNAL
    compile_f_end = min(total_frames, compile_p_end * FRAMES_PER_SIGNAL)

    include_monitor = (part_idx == 0)
    include_clock = (part_idx == 0)

    if progress_callback:
        progress_callback(
            f"V3 [{rom_mode}]: {num_stripes} şerit, {total_frames} kare ({total_packs} paket), "
            f"Parça {part_idx + 1}/{num_parts} (Paket {compile_p_start}..{compile_p_end - 1})...", 0.05
        )

    # Her paket 2 kombinatör (Decider 2 karo + CC 1 karo = 3 karo)
    if fill_all_rows:
        if is_horizontal:
            max_lanes_est = max(1, min(height, rows_per_stripe))
            curled_cols = math.ceil(total_packs / max(1, height))
        else:
            max_lanes_est = max(1, min(width, cols_per_stripe))
            curled_cols = math.ceil(total_packs / max(1, width))
    else:
        max_lanes_est = 1
        curled_cols = 0

    # 3. Trafo Izgara Koordinatları (Nitelik Menzili ve Kapsama Alanı)
    if substation_quality == "none":
        step = 999999
        reach = 0.0
        half_reach = 0
        x_coords: List[int] = []
        y_coords: List[int] = []
        substations_list: List[Tuple[int, int]] = []
        occupied_lamp_tiles: set = set()
    else:
        SUBSTATION_SPECS = {
            "normal": {"reach": 18.0, "supply": 18, "step": 18},
            "uncommon": {"reach": 20.0, "supply": 20, "step": 20},
            "rare": {"reach": 22.0, "supply": 22, "step": 22},
            "epic": {"reach": 24.0, "supply": 24, "step": 24},
            "legendary": {"reach": 28.0, "supply": 28, "step": 28},
        }
        sub_spec = SUBSTATION_SPECS.get(substation_quality, SUBSTATION_SPECS["normal"])
        step = sub_spec["step"]
        reach = sub_spec["reach"]
        half_reach = step // 2

        if fill_all_rows:
            cols_main = math.ceil(total_packs / max_lanes_est)
            cols_est = cols_main + curled_cols + 4
            comb_span = cols_est * 4.0 + (cols_est * 4.0 / float(step)) * 2.0 + 30.0
        else:
            comb_span = total_packs * 4.0 + (total_packs * 4.0 / float(step)) * 2.0 + 30.0

        if is_horizontal:
            if is_both:
                min_x_sub = int(-comb_span - 4); max_x_sub = int(width + comb_span + 4)
            elif is_left:
                min_x_sub = int(-comb_span - 4); max_x_sub = int(width + 4)
            else:
                min_x_sub = -4; max_x_sub = int(width + comb_span + 4)
            min_y_sub = -4; max_y_sub = int(height + 6)
        else:
            min_x_sub = -8; max_x_sub = int(width + 6)
            if is_both:
                min_y_sub = int(-comb_span - 4); max_y_sub = int(height + comb_span + 4)
            elif is_bottom:
                min_y_sub = -4; max_y_sub = int(height + comb_span + 4)
            else:
                min_y_sub = int(-comb_span - 4); max_y_sub = int(height + 4)

        x_start_g = -2
        while x_start_g > min_x_sub:
            x_start_g -= step
        x_coords = []
        cx = x_start_g
        while cx - half_reach <= max_x_sub:
            x_coords.append(cx); cx += step

        y_start_g = -2
        while y_start_g > min_y_sub:
            y_start_g -= step
        y_coords = []
        cy = y_start_g
        while cy - half_reach <= max_y_sub:
            y_coords.append(cy); cy += step

        substations_list = [(tx, ty) for ty in y_coords for tx in x_coords]

        # Ekran içi lambalarla çakışan trafo kareleri
        occupied_lamp_tiles = set()
        for tx, ty in substations_list:
            for dtx in (0, 1):
                for dty in (0, 1):
                    px = tx + dtx; py = ty + dty
                    if 0 <= px < width and 0 <= py < height:
                        occupied_lamp_tiles.add((px, py))

    # 4. Varlıklar ve Kablo Listeleri
    entities: List[Dict[str, Any]] = []
    wires: List[List[int]] = []
    wire_set: set = set()
    entity_id = 1

    def add_wire(id1: int, pin1: int, id2: int, pin2: int):
        w = [id1, pin1, id2, pin2] if (id1, pin1) <= (id2, pin2) else [id2, pin2, id1, pin1]
        t = tuple(w)
        if t not in wire_set:
            wire_set.add(t)
            wires.append(w)

    stripe_feed_lamps_A: Dict[int, int] = {}
    stripe_feed_lamps_B: Dict[int, int] = {}

    # Trafolar (Substations)
    substation_map: Dict[Tuple[int, int], int] = {}
    substations_list_entities: List[Dict[str, Any]] = []

    for ty in y_coords:
        for tx in x_coords:
            sid = entity_id; entity_id += 1
            substation_map[(tx, ty)] = sid
            se = {
                "entity_number": sid,
                "name": "substation",
                "position": {"x": float(tx + 1.0), "y": float(ty + 1.0)}
            }
            if substation_quality not in ("normal", "none"):
                se["quality"] = substation_quality
            entities.append(se)
            substations_list_entities.append(se)

    # 5. Monitör Lambaları (Yalnızca Parça 0)
    if include_monitor:
        if progress_callback:
            progress_callback(f"{width}x{height} Ekran matrisi örülüyor...", 0.15)

        lamp_grid: Dict[Tuple[int, int], int] = {}

        def _add_lamp(lx: int, ly: int, l_idx: int) -> Optional[int]:
            nonlocal entity_id
            if (lx, ly) in occupied_lamp_tiles:
                return None
            if l_idx >= MAX_PIXELS_PER_STRIPE:
                return None
            sig_name, sig_type, sig_quality = get_signal_for_pixel(l_idx)
            lid = entity_id; entity_id += 1
            lamp_grid[(lx, ly)] = lid
            entities.append({
                "entity_number": lid, "name": "small-lamp",
                "position": {"x": float(lx + 0.5), "y": float(ly + 0.5)},
                "always_on": True,
                "control_behavior": {
                    "use_colors": True, "color_mode": 2,
                    "rgb_signal": {"type": sig_type, "name": sig_name, "quality": sig_quality}
                }
            })
            return lid

        def _chain_green(ids: List[int]):
            for i in range(len(ids) - 1):
                add_wire(ids[i], WIRE_GREEN, ids[i + 1], WIRE_GREEN)

        if is_horizontal:
            for s in range(num_stripes):
                ys = s * rows_per_stripe; ye = min(height, ys + rows_per_stripe)
                if is_both:
                    # Sol blok (B)
                    for ry in range(ys, ye):
                        row = []
                        for lx in range(w_left):
                            lid = _add_lamp(lx, ry, (ry - ys) * w_left + lx)
                            if lid: row.append(lid)
                        _chain_green(row)
                    ll = [lamp_grid[(lx, ys)] for lx in range(w_left) if (lx, ys) in lamp_grid]
                    col_chain = [lamp_grid[(0, ry)] for ry in range(ys, ye) if (0, ry) in lamp_grid]
                    _chain_green(col_chain)
                    if ll: stripe_feed_lamps_B[s] = ll[0]

                    # Sağ blok (A)
                    for ry in range(ys, ye):
                        row = []
                        for lx in range(w_left, width):
                            lid = _add_lamp(lx, ry, (ry - ys) * w_right + (lx - w_left))
                            if lid: row.append(lid)
                        _chain_green(row)
                    rl = [lamp_grid[(width - 1, ry)] for ry in range(ys, ye) if (width - 1, ry) in lamp_grid]
                    _chain_green(rl)
                    rr0 = [lamp_grid[(lx, ys)] for lx in range(w_left, width) if (lx, ys) in lamp_grid]
                    if rr0: stripe_feed_lamps_A[s] = rr0[-1]
                else:
                    for ry in range(ys, ye):
                        row = []
                        for lx in range(width):
                            lid = _add_lamp(lx, ry, (ry - ys) * width + lx)
                            if lid: row.append(lid)
                        _chain_green(row)
                    edge = []
                    for ry in range(ys, ye):
                        if is_left and (0, ry) in lamp_grid: edge.append(lamp_grid[(0, ry)])
                        elif not is_left and (width - 1, ry) in lamp_grid: edge.append(lamp_grid[(width - 1, ry)])
                    _chain_green(edge)
                    r0 = [lamp_grid[(lx, ys)] for lx in range(width) if (lx, ys) in lamp_grid]
                    if r0:
                        if is_left: stripe_feed_lamps_B[s] = r0[0]
                        else: stripe_feed_lamps_A[s] = r0[-1]
        else:
            for s in range(num_stripes):
                xs = s * cols_per_stripe; xe = min(width, xs + cols_per_stripe)
                if is_both:
                    # Üst blok (A)
                    for cx in range(xs, xe):
                        col = []
                        for y in range(h_top):
                            lid = _add_lamp(cx, y, (cx - xs) * h_top + y)
                            if lid: col.append(lid)
                        _chain_green(col)
                    top_row = [lamp_grid[(cx, 0)] for cx in range(xs, xe) if (cx, 0) in lamp_grid]
                    _chain_green(top_row)
                    if top_row: stripe_feed_lamps_A[s] = top_row[0]

                    # Alt blok (B)
                    for cx in range(xs, xe):
                        col = []
                        for y in range(h_top, height):
                            lid = _add_lamp(cx, y, (cx - xs) * h_bottom + (y - h_top))
                            if lid: col.append(lid)
                        _chain_green(col)
                    bot_row = [lamp_grid[(cx, height - 1)] for cx in range(xs, xe) if (cx, height - 1) in lamp_grid]
                    _chain_green(bot_row)
                    if bot_row: stripe_feed_lamps_B[s] = bot_row[0]
                else:
                    for cx in range(xs, xe):
                        col = []
                        for y in range(height):
                            lid = _add_lamp(cx, y, (cx - xs) * height + y)
                            if lid: col.append(lid)
                        _chain_green(col)
                    edge = []
                    for cx in range(xs, xe):
                        if is_bottom and (cx, height - 1) in lamp_grid: edge.append(lamp_grid[(cx, height - 1)])
                        elif not is_bottom and (cx, 0) in lamp_grid: edge.append(lamp_grid[(cx, 0)])
                    _chain_green(edge)
                    c0 = [lamp_grid[(xs, y)] for y in range(height) if (xs, y) in lamp_grid]
                    if c0:
                        if is_bottom: stripe_feed_lamps_B[s] = c0[-1]
                        else: stripe_feed_lamps_A[s] = c0[0]

    # 6. Kare Verilerini 2-Bit Önbelleğe Al
    if progress_callback:
        progress_callback("Kare verileri önbelleğe alınıyor...", 0.35)

    cached_2bit: List[List[List[int]]] = []
    for frm in frames:
        img = frm if isinstance(frm, Image.Image) else _bytes_to_image(frm)
        pixels = img.load()
        f_mat: List[List[int]] = []
        for y in range(height):
            row: List[int] = []
            for x in range(width):
                px = pixels[x, y]
                if isinstance(px, tuple) and len(px) >= 3:
                    row.append(pack_2bit_grayscale(px[0], px[1], px[2]))
                else:
                    row.append(pack_2bit_grayscale(int(px), int(px), int(px)))
            f_mat.append(row)
        cached_2bit.append(f_mat)

    # 7. ROM ve Decoder İnşası (Yeni Dinamik Decoder Modeli)
    if progress_callback:
        progress_callback("Yeni Dinamik ROM & Decoder üniteleri inşa ediliyor...", 0.5)

    stripe_first_deciders: List[int] = []
    stripe_spine_ends: List[int] = []
    bank_first_deciders: Dict[str, List[int]] = {}
    bank_spine_ends: Dict[str, List[int]] = {}
    bank_first_packs: Dict[str, List[Dict[str, int]]] = {}
    stripe_max_reach: Dict[str, float] = {}

    def build_stripe_rom(
        s: int,
        bank_id: str,
        pixels_coords: List[Tuple[int, int]],
        sec_range: Tuple[int, int],
        comb_dir: int,
        is_primary_x: bool,
        primary_dir: int
    ):
        nonlocal entity_id

        # Bu şeridin kullanabileceği şerit koordinatları (lane'ler / satırlar veya sütunlar)
        if fill_all_rows:
            sec_coords = [float(c + 0.5) for c in range(sec_range[0], sec_range[1])]
        else:
            sec_coords = [float(sec_range[0] + 0.5)]

        num_lanes = max(1, len(sec_coords))

        def get_sub_intervals(sec_v: float) -> List[Tuple[float, float]]:
            if is_primary_x:
                return [(float(tx), float(tx + 2)) for tx, ty in substations_list if ty <= sec_v < ty + 2.0]
            else:
                return [(float(ty), float(ty + 2)) for tx, ty in substations_list if tx <= sec_v < tx + 2.0]

        sub_intervals_by_lane = [get_sub_intervals(sec_coords[l]) for l in range(num_lanes)]

        def make_pos(pri: float, sec: float) -> Dict[str, float]:
            return {"x": pri, "y": sec} if is_primary_x else {"x": sec, "y": pri}

        # Başlangıç noktası
        if is_primary_x:
            base_p = float(width) if primary_dir == 1 else 0.0
        else:
            base_p = float(height) if primary_dir == 1 else 0.0

        # Uyarlayıcı & Dekoder Zinciri (Şerit Başına 1 Adet, Lane 0'da: Multiplier -> Mask -> Shift)
        adapter_center, cur_p_after_adapter = _place_one_combinator(base_p, 2.0, primary_dir, sub_intervals_by_lane[0])
        mask_center, cur_p_after_mask = _place_one_combinator(cur_p_after_adapter, 2.0, primary_dir, sub_intervals_by_lane[0])
        shift_center, cur_p_after_shift = _place_one_combinator(cur_p_after_mask, 2.0, primary_dir, sub_intervals_by_lane[0])

        adapter_id = None
        mask_id = None
        shift_id = None

        if include_monitor:
            adapter_id = entity_id; entity_id += 1
            mask_id = entity_id; entity_id += 1
            shift_id = entity_id; entity_id += 1

            # 1. Multiplier Combinator (* ADAPTER_MULTIPLIER)
            entities.append({
                "entity_number": adapter_id,
                "name": "arithmetic-combinator",
                "position": make_pos(adapter_center, sec_coords[0]),
                "direction": comb_dir,
                "control_behavior": {
                    "arithmetic_conditions": {
                        "first_signal": {"type": "virtual", "name": "signal-each"},
                        "second_constant": ADAPTER_MULTIPLIER,
                        "operation": "*",
                        "output_signal": {"type": "virtual", "name": "signal-each"},
                        "first_signal_networks": {"red": False, "green": True}
                    }
                }
            })
            feed_lamp = (stripe_feed_lamps_A if bank_id == 'A' else stripe_feed_lamps_B).get(s)
            if feed_lamp:
                add_wire(adapter_id, COMB_OUT_GREEN, feed_lamp, WIRE_GREEN)

            # 2. Mask Combinator (AND 3)
            entities.append({
                "entity_number": mask_id,
                "name": "arithmetic-combinator",
                "position": make_pos(mask_center, sec_coords[0]),
                "direction": comb_dir,
                "control_behavior": {
                    "arithmetic_conditions": {
                        "first_signal": {"type": "virtual", "name": "signal-each"},
                        "second_constant": 3,
                        "operation": "AND",
                        "output_signal": {"type": "virtual", "name": "signal-each"},
                        "first_signal_networks": {"red": False, "green": True}
                    }
                }
            })
            add_wire(mask_id, COMB_OUT_GREEN, adapter_id, COMB_IN_GREEN)

            # 3. Shift Combinator (>> signal-S)
            entities.append({
                "entity_number": shift_id,
                "name": "arithmetic-combinator",
                "position": make_pos(shift_center, sec_coords[0]),
                "direction": comb_dir,
                "control_behavior": {
                    "arithmetic_conditions": {
                        "first_signal": {"type": "virtual", "name": "signal-each"},
                        "second_signal": {"type": "virtual", "name": "signal-S"},
                        "operation": ">>",
                        "output_signal": {"type": "virtual", "name": "signal-each"},
                        "first_signal_networks": {"red": False, "green": True},
                        "second_signal_networks": {"red": True, "green": False}
                    }
                }
            })
            add_wire(shift_id, COMB_OUT_GREEN, mask_id, COMB_IN_GREEN)

        # Her lane (satır/sütun) için cursor konumu
        # Lane 0 shift kombinatöründen sonra başlar. Diğer lane'ler de aynı hizada başlar.
        cur_p_by_lane: List[float] = [cur_p_after_shift] * num_lanes

        # P_turn tespiti (yalnızca bu şeridin satır sayısı ana şeritlerden azsa ve önceki şeritler varsa)
        P_turn = None
        prior_reach = stripe_max_reach.get(bank_id)
        if fill_all_rows and (num_lanes < max_lanes_est) and (prior_reach is not None):
            P_turn = prior_reach

        # Tüm paketlerin pozisyonlarını hesapla
        # Her paket için 2 eleman: Decider (w=2), CC (w=1) -> Toplam 3 karo
        pack_positions: Dict[int, Dict[str, Any]] = {}
        is_curling = False
        cur_col_p = None
        cur_sec = sec_coords[-1]
        sec_center = (float(height) / 2.0) if is_primary_x else (float(width) / 2.0)
        delta_sec = -1.0 if sec_coords[-1] >= sec_center else 1.0
        sec_min = 0.5
        sec_max = float(height - 0.5) if is_primary_x else float(width - 0.5)
        is_first_curled = True

        for p in range(total_packs):
            lane_idx = p % num_lanes
            col_idx = p // num_lanes

            if not is_curling:
                if P_turn is not None:
                    cur_p = cur_p_by_lane[lane_idx]
                    exceeds = (cur_p >= P_turn) if primary_dir == 1 else (cur_p <= P_turn)
                    if exceeds:
                        is_curling = True
                        cur_col_p = cur_p
                        cur_sec = sec_coords[lane_idx]
                        is_first_curled = True

            if not is_curling:
                sec_val = sec_coords[lane_idx]
                subs = sub_intervals_by_lane[lane_idx]

                dp, cur_p_by_lane[lane_idx] = _place_one_combinator(cur_p_by_lane[lane_idx], 2.0, primary_dir, subs)
                cp, cur_p_by_lane[lane_idx] = _place_one_combinator(cur_p_by_lane[lane_idx], 1.0, primary_dir, subs)

                pack_positions[p] = {
                    "dec": dp, "cc": cp,
                    "sec": sec_val, "lane": lane_idx, "col": col_idx,
                    "is_curled": False
                }
            else:
                # Kıvrılma Modu (Curling/Snaking): Boş kalan ekranda dikey olarak kıvrıl
                if is_first_curled:
                    next_sec = cur_sec
                    is_first_curled = False
                else:
                    next_sec = cur_sec + delta_sec

                # Sınır kontrolü (ekranın tepesine veya dibine ulaşıldı mı?)
                if next_sec < sec_min:
                    cur_col_p += primary_dir * 3.0
                    delta_sec = 1.0
                    next_sec = sec_min
                elif next_sec > sec_max:
                    cur_col_p += primary_dir * 3.0
                    delta_sec = -1.0
                    next_sec = sec_max

                # Trafo çakışma kontrolü
                for sx, sy in substations_list:
                    sub_p = float(sx if is_primary_x else sy)
                    sub_s = float(sy if is_primary_x else sx)
                    col_st = min(cur_col_p, cur_col_p + primary_dir * 3.0)
                    col_en = max(cur_col_p, cur_col_p + primary_dir * 3.0)
                    if max(col_st, sub_p) < min(col_en, sub_p + 2.0):
                        if max(next_sec - 0.5, sub_s) < min(next_sec + 0.5, sub_s + 2.0):
                            if delta_sec < 0:
                                next_sec = sub_s - 0.5
                            else:
                                next_sec = sub_s + 2.5

                cur_sec = next_sec

                if primary_dir == 1:
                    dp = cur_col_p + 1.0
                    cp = cur_col_p + 2.5
                else:
                    dp = cur_col_p - 1.0
                    cp = cur_col_p - 2.5

                pack_positions[p] = {
                    "dec": dp, "cc": cp,
                    "sec": cur_sec, "lane": 0, "col": 90000 + p,
                    "is_curled": True
                }

        # Bu parçada inşa edilecek paketler (compile_p_start .. compile_p_end)
        active_packs = list(range(compile_p_start, compile_p_end))
        pack_entities: Dict[int, Dict[str, int]] = {}

        for p in active_packs:
            ppos = pack_positions[p]
            sec_pos = ppos["sec"]

            # 1. Decider Combinator (Blok Aktivatörü: signal-F in [p*16, (p+1)*16))
            dec_id = entity_id; entity_id += 1
            conds = []
            if total_packs == 1 or p == 0:
                conds.append({
                    "first_signal": {"type": "virtual", "name": "signal-F"},
                    "comparator": "<",
                    "constant": 16,
                    "first_signal_networks": {"red": True, "green": False}
                })
            else:
                conds.append({
                    "first_signal": {"type": "virtual", "name": "signal-F"},
                    "comparator": ">=",
                    "constant": p * FRAMES_PER_SIGNAL,
                    "first_signal_networks": {"red": True, "green": False}
                })
                conds.append({
                    "first_signal": {"type": "virtual", "name": "signal-F"},
                    "comparator": "<",
                    "constant": (p + 1) * FRAMES_PER_SIGNAL,
                    "compare_type": "and",
                    "first_signal_networks": {"red": True, "green": False}
                })

            entities.append({
                "entity_number": dec_id,
                "name": "decider-combinator",
                "position": make_pos(ppos["dec"], sec_pos),
                "direction": comb_dir,
                "control_behavior": {
                    "decider_conditions": {
                        "conditions": conds,
                        "outputs": [{
                            "signal": {"type": "virtual", "name": "signal-everything"},
                            "networks": {"red": False, "green": True}
                        }],
                        "else_outputs": []
                    }
                }
            })

            # 2. Constant Combinator (ROM CC - 5 Kalite ile 1425 piksele kadar)
            cc_id = entity_id; entity_id += 1
            f_p_start = p * FRAMES_PER_SIGNAL
            filters = []
            for l_idx, (px_x, px_y) in enumerate(pixels_coords):
                if l_idx >= MAX_PIXELS_PER_STRIPE:
                    break
                sig_name, sig_type, sig_quality = get_signal_for_pixel(l_idx)
                vals_16 = [
                    cached_2bit[f_p_start + k][px_y][px_x] if (f_p_start + k < total_frames) else 0
                    for k in range(16)
                ]
                packed_val = pack_16frames_to_int32(vals_16)
                if packed_val != 0:
                    filters.append({
                        "type": sig_type,
                        "name": sig_name,
                        "quality": sig_quality,
                        "comparator": "=",
                        "count": packed_val
                    })

            # Factorio 2.0 Section Sınırı: Tek bir section en fazla 1000 filtre alabilir (1 <= index <= 1000).
            SECTION_SIZE = 1000
            sections = []
            if not filters:
                sections.append({
                    "index": 1,
                    "filters": []
                })
            else:
                for s_idx in range(0, len(filters), SECTION_SIZE):
                    chunk = filters[s_idx:s_idx + SECTION_SIZE]
                    sec_filters = []
                    for f_idx, flt in enumerate(chunk):
                        flt_copy = dict(flt)
                        flt_copy["index"] = f_idx + 1
                        sec_filters.append(flt_copy)
                    sections.append({
                        "index": (s_idx // SECTION_SIZE) + 1,
                        "filters": sec_filters
                    })

            entities.append({
                "entity_number": cc_id,
                "name": "constant-combinator",
                "position": make_pos(ppos["cc"], sec_pos),
                "control_behavior": {
                    "sections": {"sections": sections}
                }
            })

            # Paket İçi Dahili Bağlantı:
            # CC Yeşil Çıkış (Pin 2) -> Decider Yeşil Giriş (Pin 2)
            add_wire(cc_id, WIRE_GREEN, dec_id, COMB_IN_GREEN)

            pack_entities[p] = {"dec": dec_id, "cc": cc_id}

        # Paketler Arası Ağ Bağlantısı (Main Bus Yanda + Yatay Satır Dallanmaları + Kıvrılma Hattı):
        horiz_active_packs = [p for p in active_packs if not pack_positions[p].get("is_curled")]
        curled_active_packs = [p for p in active_packs if pack_positions[p].get("is_curled")]

        # 1. Yatay paketleri satır (lane) ve sütun (col) bazında grupla
        packs_by_col: Dict[int, List[int]] = {}
        packs_by_lane: Dict[int, List[int]] = {}
        for p in horiz_active_packs:
            c = pack_positions[p]["col"]
            l = pack_positions[p]["lane"]
            packs_by_col.setdefault(c, []).append(p)
            packs_by_lane.setdefault(l, []).append(p)

        for c in packs_by_col:
            packs_by_col[c].sort(key=lambda p: pack_positions[p]["lane"])
        for l in packs_by_lane:
            packs_by_lane[l].sort(key=lambda p: pack_positions[p]["col"])

        # 2. Main Bus: Yanda (Monitör kenarındaki ilk sütun boyunca dikey hat)
        sorted_cols = sorted(packs_by_col.keys())
        first_col = sorted_cols[0] if sorted_cols else 0
        spine_packs = packs_by_col.get(first_col, [])

        for i in range(len(spine_packs) - 1):
            p_curr = spine_packs[i]
            p_next = spine_packs[i + 1]
            add_wire(pack_entities[p_curr]["dec"], COMB_OUT_GREEN, pack_entities[p_next]["dec"], COMB_OUT_GREEN)
            add_wire(pack_entities[p_curr]["dec"], COMB_IN_RED, pack_entities[p_next]["dec"], COMB_IN_RED)

        # 3. Yatay Satır Dallanmaları (Her satırda sütunlar arası bağlantı):
        for l_idx, row_packs in packs_by_lane.items():
            for i in range(len(row_packs) - 1):
                p1 = row_packs[i]
                p2 = row_packs[i + 1]
                pos1_dec = make_pos(pack_positions[p1]["dec"], pack_positions[p1]["sec"])
                pos2_dec = make_pos(pack_positions[p2]["dec"], pack_positions[p2]["sec"])
                d_dec = math.hypot(pos1_dec["x"] - pos2_dec["x"], pos1_dec["y"] - pos2_dec["y"])

                if d_dec <= 9.0:
                    add_wire(pack_entities[p1]["dec"], COMB_OUT_GREEN, pack_entities[p2]["dec"], COMB_OUT_GREEN)
                    add_wire(pack_entities[p1]["dec"], COMB_IN_RED, pack_entities[p2]["dec"], COMB_IN_RED)
                else:
                    pole_id = entity_id; entity_id += 1
                    p1_pri = pack_positions[p1]["dec"]
                    p2_pri = pack_positions[p2]["dec"]
                    min_p, max_p = min(p1_pri, p2_pri), max(p1_pri, p2_pri)
                    pole_pri = (p1_pri + p2_pri) / 2.0
                    for st, en in sub_intervals_by_lane[l_idx]:
                        if min_p <= st <= max_p:
                            pole_pri = (st - 0.5) if primary_dir == 1 else (en + 0.5)
                            break
                    pole_pos = make_pos(pole_pri, pack_positions[p1]["sec"])
                    entities.append({
                        "entity_number": pole_id,
                        "name": "small-electric-pole",
                        "position": pole_pos
                    })
                    add_wire(pack_entities[p1]["dec"], COMB_OUT_GREEN, pole_id, WIRE_GREEN)
                    add_wire(pole_id, WIRE_GREEN, pack_entities[p2]["dec"], COMB_OUT_GREEN)
                    add_wire(pack_entities[p1]["dec"], COMB_IN_RED, pole_id, WIRE_RED)
                    add_wire(pole_id, WIRE_RED, pack_entities[p2]["dec"], COMB_IN_RED)

        # 4. Kıvrılan Paketlerin Bağlantısı (Curled/Snaking Chain):
        if curled_active_packs:
            for i in range(len(curled_active_packs) - 1):
                cp1 = curled_active_packs[i]
                cp2 = curled_active_packs[i + 1]
                add_wire(pack_entities[cp1]["dec"], COMB_OUT_GREEN, pack_entities[cp2]["dec"], COMB_OUT_GREEN)
                add_wire(pack_entities[cp1]["dec"], COMB_IN_RED, pack_entities[cp2]["dec"], COMB_IN_RED)

            if horiz_active_packs:
                first_curled = curled_active_packs[0]
                closest_horiz = min(horiz_active_packs, key=lambda p: math.hypot(
                    pack_positions[p]["dec"] - pack_positions[first_curled]["dec"],
                    pack_positions[p]["sec"] - pack_positions[first_curled]["sec"]
                ))
                add_wire(pack_entities[closest_horiz]["dec"], COMB_OUT_GREEN, pack_entities[first_curled]["dec"], COMB_OUT_GREEN)
                add_wire(pack_entities[closest_horiz]["dec"], COMB_IN_RED, pack_entities[first_curled]["dec"], COMB_IN_RED)
            else:
                if shift_id:
                    add_wire(pack_entities[curled_active_packs[0]]["dec"], COMB_OUT_GREEN, shift_id, COMB_IN_GREEN)
                    add_wire(pack_entities[curled_active_packs[0]]["dec"], COMB_IN_RED, shift_id, COMB_IN_RED)

        # 5. Main Bus çıkışı -> Adapter Shift girişi:
        if spine_packs and shift_id:
            add_wire(pack_entities[spine_packs[0]]["dec"], COMB_OUT_GREEN, shift_id, COMB_IN_GREEN)
            add_wire(pack_entities[spine_packs[0]]["dec"], COMB_IN_RED, shift_id, COMB_IN_RED)
        elif active_packs and shift_id:
            add_wire(pack_entities[active_packs[0]]["dec"], COMB_OUT_GREEN, shift_id, COMB_IN_GREEN)
            add_wire(pack_entities[active_packs[0]]["dec"], COMB_IN_RED, shift_id, COMB_IN_RED)

        # 6. Saat hattı başlangıç ve bitiş kombinatörleri (Bank bazlı gruplama):
        f_pack = pack_entities[spine_packs[0]] if spine_packs else pack_entities[active_packs[0]]
        e_pack = pack_entities[spine_packs[-1]] if spine_packs else pack_entities[active_packs[-1]]
        first_dec = shift_id if shift_id else f_pack["dec"]
        end_dec = e_pack["dec"]

        bank_first_deciders.setdefault(bank_id, []).append(first_dec)
        bank_spine_ends.setdefault(bank_id, []).append(end_dec)
        bank_first_packs.setdefault(bank_id, []).append({"dec": first_dec})

        stripe_first_deciders.append(first_dec)
        stripe_spine_ends.append(end_dec)

        # Kaydet: Bu şeridin ana gövdede ulaştığı en uç koordinat (öbür şeritler kıvrılma referansı alsın)
        if pack_positions and (num_lanes >= max_lanes_est or prior_reach is None):
            if primary_dir == 1:
                cur_reach = max(p["cc"] + 0.5 for p in pack_positions.values())
                stripe_max_reach[bank_id] = max(stripe_max_reach.get(bank_id, -1e9), cur_reach)
            else:
                cur_reach = min(p["cc"] - 0.5 for p in pack_positions.values())
                stripe_max_reach[bank_id] = min(stripe_max_reach.get(bank_id, 1e9), cur_reach)

    # 8. Şeritleri Yerleştir
    if is_horizontal:
        for s in range(num_stripes):
            ys = s * rows_per_stripe; ye = min(height, ys + rows_per_stripe)

            if is_both:
                pixels_B = [(lx, ry) for ry in range(ys, ye) for lx in range(w_left)]
                build_stripe_rom(s, 'B', pixels_B, (ys, ye), DIR_EAST, True, -1)
                pixels_A = [(lx, ry) for ry in range(ys, ye) for lx in range(w_left, width)]
                build_stripe_rom(s, 'A', pixels_A, (ys, ye), DIR_WEST, True, +1)
            elif is_left:
                pixels = [(lx, ry) for ry in range(ys, ye) for lx in range(width)]
                build_stripe_rom(s, 'B', pixels, (ys, ye), DIR_EAST, True, -1)
            else:
                pixels = [(lx, ry) for ry in range(ys, ye) for lx in range(width)]
                build_stripe_rom(s, 'A', pixels, (ys, ye), DIR_WEST, True, +1)
    else:
        for s in range(num_stripes):
            xs = s * cols_per_stripe; xe = min(width, xs + cols_per_stripe)

            if is_both:
                pixels_A = [(cx, y) for cx in range(xs, xe) for y in range(h_top)]
                build_stripe_rom(s, 'A', pixels_A, (xs, xe), DIR_SOUTH, False, -1)
                pixels_B = [(cx, y) for cx in range(xs, xe) for y in range(h_top, height)]
                build_stripe_rom(s, 'B', pixels_B, (xs, xe), DIR_NORTH, False, +1)
            elif is_bottom:
                pixels = [(cx, y) for cx in range(xs, xe) for y in range(height)]
                build_stripe_rom(s, 'B', pixels, (xs, xe), DIR_NORTH, False, +1)
            else:
                pixels = [(cx, y) for cx in range(xs, xe) for y in range(height)]
                build_stripe_rom(s, 'A', pixels, (xs, xe), DIR_SOUTH, False, -1)

    # 9. Master Clock & Dinamik Shift Üreticisi (Yalnızca Parça 0)
    clock_out_id = None
    if include_clock:
        if progress_callback:
            progress_callback("Merkezi saat ve dinamik shift devresi inşa ediliyor...", 0.8)

        clock_x = -3.0
        clock_y = -17.0

        # 1. Sabit Kombinatör: signal-C = 1
        cc_clk = entity_id; entity_id += 1
        entities.append({
            "entity_number": cc_clk,
            "name": "constant-combinator",
            "position": {"x": clock_x, "y": clock_y},
            "control_behavior": {
                "sections": {"sections": [{"index": 1, "filters": [
                    {"index": 1, "type": "virtual", "name": "signal-C", "quality": "normal", "comparator": "=", "count": 1}
                ]}]}
            }
        })

        # 2. Karar Kombinatörü: signal-C < total_ticks -> signal-C (giriş adedini kopyala)
        dec_clk = entity_id; entity_id += 1
        entities.append({
            "entity_number": dec_clk,
            "name": "decider-combinator",
            "position": {"x": clock_x, "y": clock_y + 2.0},
            "direction": DIR_SOUTH,
            "control_behavior": {
                "decider_conditions": {
                    "conditions": [{
                        "first_signal": {"type": "virtual", "name": "signal-C"},
                        "comparator": "<",
                        "constant": total_ticks,
                        "first_signal_networks": {"red": False, "green": True}
                    }],
                    "outputs": [{
                        "signal": {"type": "virtual", "name": "signal-C"},
                        "copy_count_from_input": True,
                        "networks": {"red": False, "green": True}
                    }],
                    "else_outputs": []
                }
            }
        })
        add_wire(cc_clk, WIRE_GREEN, dec_clk, COMB_IN_GREEN)
        add_wire(dec_clk, COMB_OUT_GREEN, dec_clk, COMB_IN_GREEN)

        # 3. Aritmetik Kombinatör: signal-C - 1 -> signal-C (0 tabanlı tick)
        arith_sub1 = entity_id; entity_id += 1
        entities.append({
            "entity_number": arith_sub1,
            "name": "arithmetic-combinator",
            "position": {"x": clock_x, "y": clock_y + 4.0},
            "direction": DIR_SOUTH,
            "control_behavior": {
                "arithmetic_conditions": {
                    "first_signal": {"type": "virtual", "name": "signal-C"},
                    "second_constant": 1,
                    "operation": "-",
                    "output_signal": {"type": "virtual", "name": "signal-C"}
                }
            }
        })
        add_wire(dec_clk, COMB_OUT_GREEN, arith_sub1, COMB_IN_GREEN)

        cur_comb = arith_sub1
        cur_y = clock_y + 4.0

        # 4. Çarpan Kombinatörü (Eğer clk_mult > 1 ise, örn: 24, 25, 50 FPS)
        if clk_mult > 1:
            arith_mul = entity_id; entity_id += 1
            cur_y += 2.0
            entities.append({
                "entity_number": arith_mul,
                "name": "arithmetic-combinator",
                "position": {"x": clock_x, "y": cur_y},
                "direction": DIR_SOUTH,
                "control_behavior": {
                    "arithmetic_conditions": {
                        "first_signal": {"type": "virtual", "name": "signal-C"},
                        "second_constant": clk_mult,
                        "operation": "*",
                        "output_signal": {"type": "virtual", "name": "signal-C"}
                    }
                }
            })
            add_wire(cur_comb, COMB_OUT_GREEN, arith_mul, COMB_IN_GREEN)
            cur_comb = arith_mul

        # 5. Bölen Kombinatörü: signal-C / clk_div -> signal-F (Kare indeksi)
        arith_div = entity_id; entity_id += 1
        cur_y += 2.0
        entities.append({
            "entity_number": arith_div,
            "name": "arithmetic-combinator",
            "position": {"x": clock_x, "y": cur_y},
            "direction": DIR_SOUTH,
            "control_behavior": {
                "arithmetic_conditions": {
                    "first_signal": {"type": "virtual", "name": "signal-C"},
                    "second_constant": clk_div,
                    "operation": "/",
                    "output_signal": {"type": "virtual", "name": "signal-F"}
                }
            }
        })
        add_wire(cur_comb, COMB_OUT_GREEN, arith_div, COMB_IN_GREEN)

        # 6. Dinamik Shift Modulo Kombinatörü: signal-F % 16 -> signal-F (k = f % 16)
        arith_shift_mod = entity_id; entity_id += 1
        cur_y += 2.0
        entities.append({
            "entity_number": arith_shift_mod,
            "name": "arithmetic-combinator",
            "position": {"x": clock_x, "y": cur_y},
            "direction": DIR_SOUTH,
            "control_behavior": {
                "arithmetic_conditions": {
                    "first_signal": {"type": "virtual", "name": "signal-F"},
                    "second_constant": 16,
                    "operation": "%",
                    "output_signal": {"type": "virtual", "name": "signal-F"}
                }
            }
        })
        add_wire(arith_div, COMB_OUT_GREEN, arith_shift_mod, COMB_IN_GREEN)

        # 7. Dinamik Shift Çarpan Kombinatörü: signal-F * 2 -> signal-S (S = k * 2)
        arith_shift_mul = entity_id; entity_id += 1
        cur_y += 2.0
        entities.append({
            "entity_number": arith_shift_mul,
            "name": "arithmetic-combinator",
            "position": {"x": clock_x, "y": cur_y},
            "direction": DIR_SOUTH,
            "control_behavior": {
                "arithmetic_conditions": {
                    "first_signal": {"type": "virtual", "name": "signal-F"},
                    "second_constant": 2,
                    "operation": "*",
                    "output_signal": {"type": "virtual", "name": "signal-S"}
                }
            }
        })
        # Modulo'nun kırmızı çıkışı -> Çarpanın kırmızı girişi
        add_wire(arith_shift_mod, COMB_OUT_RED, arith_shift_mul, COMB_IN_RED)

        # 8. Sinyal F Geciktirme Kombinatörü (Tick Alignment): signal-F / 1 -> signal-F
        # signal-S iki işlemden (mod 16 -> * 2) geçtiği için signal-F'i de 1 tick geciktirerek
        # decider ve shift kombinatörlerinde tam senkron (asenkronluksuz) hizalama sağlıyoruz.
        arith_f_delay = entity_id; entity_id += 1
        cur_y += 2.0
        entities.append({
            "entity_number": arith_f_delay,
            "name": "arithmetic-combinator",
            "position": {"x": clock_x, "y": cur_y},
            "direction": DIR_SOUTH,
            "control_behavior": {
                "arithmetic_conditions": {
                    "first_signal": {"type": "virtual", "name": "signal-F"},
                    "second_constant": 1,
                    "operation": "/",
                    "output_signal": {"type": "virtual", "name": "signal-F"}
                }
            }
        })
        # arith_div yeşil çıkışı -> arith_f_delay yeşil girişi
        add_wire(arith_div, COMB_OUT_GREEN, arith_f_delay, COMB_IN_GREEN)

        # Saat çıkışı: arith_f_delay (geciktirilmiş signal-F) ve arith_shift_mul (signal-S) birlikte kırmızı hatta basılır!
        add_wire(arith_f_delay, COMB_OUT_RED, arith_shift_mul, COMB_OUT_RED)
        clock_out_id = arith_f_delay

    # 10. Trafolar (Substations) Kablolaması
    if progress_callback:
        progress_callback("Trafo ızgarası örülüyor...", 0.88)

    def is_in_monitor(px: float, py: float) -> bool:
        return (0.0 <= px <= float(width)) and (0.0 <= py <= float(height))

    min_y_coord = min(y_coords) if y_coords else -2

    # 10. Trafolar (Substations) Kablolaması
    # Bakır tel tüm komşu trafolar arasına çekilir (2D güç ızgarası).
    # Kırmızı saat teli ise YALNIZCA en dış hat trafolarına çekilir (ty == -2 üst hat ve tx == -2 sol hat).
    min_x_sub_val = min(x_coords) if x_coords else -2
    min_y_sub_val = min(y_coords) if y_coords else -2

    for (tx, ty), sid in substation_map.items():
        # Bakır Güç Kablosu: Tüm komşu trafolar arası 2D ızgara
        if (tx + step, ty) in substation_map:
            add_wire(sid, POLE_COPPER, substation_map[(tx + step, ty)], POLE_COPPER)
        if (tx, ty + step) in substation_map:
            add_wire(sid, POLE_COPPER, substation_map[(tx, ty + step)], POLE_COPPER)

    # Hizalama Çapa Trafoları (Anchor Substations):
    # Kopyalama kolaylığı açıksa veya trafo kalitesi "none" değilse DAİMA yerleştirilir.
    include_anchors = copy_convenience or (substation_quality != "none")
    anchor1_id = None
    anchor2_id = None

    if include_anchors:
        if (-2, -2) in substation_map:
            anchor1_id = substation_map[(-2, -2)]
        else:
            anchor1_id = entity_id; entity_id += 1
            sub1 = {"entity_number": anchor1_id, "name": "substation", "position": {"x": -1.0, "y": -1.0}}
            if substation_quality not in ("normal", "none"):
                sub1["quality"] = substation_quality
            entities.append(sub1)

        if substation_quality != "none":
            anchor2_id = entity_id; entity_id += 1
            sub2 = {"entity_number": anchor2_id, "name": "substation", "position": {"x": -1.0, "y": -3.0}}
            if substation_quality != "normal":
                sub2["quality"] = substation_quality
            entities.append(sub2)
            add_wire(anchor1_id, POLE_COPPER, anchor2_id, POLE_COPPER)
            add_wire(anchor1_id, WIRE_RED, anchor2_id, WIRE_RED)

        # Güç için en yakın monitör/saha trafosuna bakır tel çek (varsa)
        if substation_quality != "none" and substations_list_entities:
            SUBSTATION_REACH = {"normal": 18.0, "uncommon": 20.0, "rare": 22.0, "epic": 24.0, "legendary": 28.0}
            sub_reach = SUBSTATION_REACH.get(substation_quality, 18.0)
            nsub_pwr = min(substations_list_entities, key=lambda s: (s["position"]["x"] + 1.0)**2 + (s["position"]["y"] + 1.0)**2)
            d_pwr = math.hypot(nsub_pwr["position"]["x"] - (-1.0), nsub_pwr["position"]["y"] - (-1.0))
            if d_pwr <= sub_reach:
                add_wire(anchor1_id, POLE_COPPER, nsub_pwr["entity_number"], POLE_COPPER)

    # Master Clock çıkışını anchor1'e bağla
    ent_by_id = {e["entity_number"]: e for e in entities}
    if include_clock and clock_out_id:
        if anchor1_id:
            add_wire(clock_out_id, COMB_OUT_RED, anchor1_id, WIRE_RED)

    # 11. Saat Dağıtımı: Ekranın En Alt Lamba Şeridi ve Kenar Hatları Üzerinden
    clock_origin = anchor1_id if anchor1_id else clock_out_id
    clock_origin_pin = WIRE_RED if anchor1_id else COMB_OUT_RED

    clock_border_lamp_ids = []
    if include_monitor and lamp_grid:
        left_lamps = [lamp_grid[(0, y)] for y in range(height) if (0, y) in lamp_grid]
        bot_lamps = [lamp_grid[(x, height - 1)] for x in range(width) if (x, height - 1) in lamp_grid]
        right_lamps = [lamp_grid[(width - 1, y)] for y in range(height) if (width - 1, y) in lamp_grid]

        # Saat kaynağını sol üst lambaya bağla:
        if clock_origin and left_lamps:
            add_wire(clock_origin, clock_origin_pin, left_lamps[0], WIRE_RED)

        # Sol kenar boyunca aşağı in: (0, 0) -> ... -> (0, height - 1)
        for i in range(len(left_lamps) - 1):
            add_wire(left_lamps[i], WIRE_RED, left_lamps[i + 1], WIRE_RED)

        # Ekranın en alt lamba şeridi boyunca sağa geç: (0, height - 1) -> ... -> (width - 1, height - 1)
        for i in range(len(bot_lamps) - 1):
            add_wire(bot_lamps[i], WIRE_RED, bot_lamps[i + 1], WIRE_RED)

        # Sağ kenar boyunca yukarı çık: (width - 1, height - 1) -> ... -> (width - 1, 0)
        for i in range(len(right_lamps) - 1):
            add_wire(right_lamps[i], WIRE_RED, right_lamps[i + 1], WIRE_RED)

        clock_border_lamp_ids = list(dict.fromkeys(left_lamps + bot_lamps + right_lamps))

    # Bank bazında şeritler arası dikey saat omurgası (Column 0 Spine Deciders):
    for b_id, dec_list in bank_first_deciders.items():
        ends_list = bank_spine_ends.get(b_id, [])
        for i in range(len(dec_list) - 1):
            end_d = ends_list[i] if i < len(ends_list) else dec_list[i]
            next_d = dec_list[i + 1]
            p_end = ent_by_id[end_d]["position"]
            p_next = ent_by_id[next_d]["position"]
            dist_spine = math.hypot(p_end["x"] - p_next["x"], p_end["y"] - p_next["y"])
            if dist_spine <= 9.0:
                add_wire(end_d, COMB_IN_RED, next_d, COMB_IN_RED)
            elif substation_quality != "none":
                num_hops = math.ceil(dist_spine / 8.0)
                prev_id = end_d
                for h in range(1, num_hops):
                    t = h / float(num_hops)
                    rx = p_end["x"] + (p_next["x"] - p_end["x"]) * t
                    ry = p_end["y"] + (p_next["y"] - p_end["y"]) * t
                    pole_id = entity_id; entity_id += 1
                    pole_ent = {
                        "entity_number": pole_id,
                        "name": "small-electric-pole",
                        "position": {"x": round(rx, 1), "y": round(ry, 1)}
                    }
                    entities.append(pole_ent)
                    ent_by_id[pole_id] = pole_ent
                    add_wire(prev_id, COMB_IN_RED if prev_id == end_d else 1, pole_id, 1)
                    prev_id = pole_id
                add_wire(prev_id, 1, next_d, COMB_IN_RED)

    # Her bankın ve şeridin ilk kombinatörüne saat sinyalini ulaştır:
    clock_sources = []
    if clock_border_lamp_ids:
        clock_sources = [ent_by_id[lid] for lid in clock_border_lamp_ids]
    elif clock_origin and clock_origin in ent_by_id:
        clock_sources = [ent_by_id[clock_origin]]

    # Outermost substations (yalnızca substation_quality != "none" ve lambasız parçalarda yedek olarak)
    outermost_sub_list = []
    if substation_quality != "none":
        outermost_sub_list = [
            s for s in substations_list_entities
            if (s["position"]["y"] == -1.0 or s["position"]["x"] == -1.0)
        ]
        if not outermost_sub_list:
            outermost_sub_list = [s for s in substations_list_entities if not is_in_monitor(s["position"]["x"], s["position"]["y"])]
        if anchor1_id and ent_by_id.get(anchor1_id):
            outermost_sub_list.append(ent_by_id[anchor1_id])

    for b_id, pack_list in bank_first_packs.items():
        if not pack_list:
            continue
        for p_info in pack_list:
            dec_id = p_info["dec"]
            dec_pos = ent_by_id[dec_id]["position"]

            if clock_sources:
                best_src = min(clock_sources, key=lambda s: (s["position"]["x"] - dec_pos["x"])**2 + (s["position"]["y"] - dec_pos["y"])**2)
                s_pos = best_src["position"]
                s_id = best_src["entity_number"]
                s_pin = COMB_OUT_RED if (include_clock and s_id == clock_out_id) else WIRE_RED
                d_to_dec = math.hypot(dec_pos["x"] - s_pos["x"], dec_pos["y"] - s_pos["y"])

                if d_to_dec <= 9.0:
                    add_wire(s_id, s_pin, dec_id, COMB_IN_RED)
                elif substation_quality != "none" and outermost_sub_list:
                    sub_bound_id = entity_id; entity_id += 1
                    if is_horizontal:
                        bx = dec_pos["x"] - 2.0
                        by = -1.0
                    else:
                        bx = -1.0
                        by = dec_pos["y"] - 2.0
                    sub_bound = {"entity_number": sub_bound_id, "name": "substation", "position": {"x": bx, "y": by}}
                    if substation_quality != "normal":
                        sub_bound["quality"] = substation_quality
                    entities.append(sub_bound)
                    ent_by_id[sub_bound_id] = sub_bound

                    closest_outer = min(outermost_sub_list, key=lambda s: (s["position"]["x"] - bx)**2 + (s["position"]["y"] - by)**2)
                    add_wire(sub_bound_id, POLE_COPPER, closest_outer["entity_number"], POLE_COPPER)
                    add_wire(sub_bound_id, WIRE_RED, closest_outer["entity_number"], WIRE_RED)
                    outermost_sub_list.append(sub_bound)

                    add_wire(sub_bound_id, WIRE_RED, dec_id, COMB_IN_RED)

    # 12. Blueprint JSON Paketleme
    if progress_callback:
        progress_callback("Blueprint JSON paketleniyor ve sıkıştırılıyor...", 0.95)

    out = io.StringIO()
    out.write('{"blueprint":{"icons":[{"signal":{"name":"small-lamp"},"index":1},'
              '{"signal":{"name":"arithmetic-combinator"},"index":2}],"entities":[')
    for i, ent in enumerate(entities):
        if i > 0: out.write(',')
        out.write(json.dumps(ent, separators=(',', ':')))
    out.write('],"wires":[')
    for i, wire in enumerate(wires):
        if i > 0: out.write(',')
        out.write(json.dumps(wire, separators=(',', ':')))
    out.write('],"item":"blueprint","version":562954249306113}}')

    json_bytes = out.getvalue().encode('utf-8')
    out = None
    compressed = zlib.compress(json_bytes, level=9)
    json_bytes = None
    bp_string = "0" + base64.b64encode(compressed).decode('utf-8')
    compressed = None

    metadata = {
        "width": width, "height": height, "fps": fps,
        "total_frames": total_frames, "ticks_per_frame": ticks_per_frame,
        "rom_mode": rom_mode, "num_stripes": num_stripes,
        "num_entities": len(entities), "total_entities": len(entities),
        "num_wires": len(wires), "total_wires": len(wires),
        "blueprint_length": len(bp_string),
        "part_idx": part_idx, "num_parts": num_parts,
        "copy_convenience": copy_convenience,
        "f_start": f_start, "f_end": f_end,
        "compile_f_start": compile_f_start, "compile_f_end": compile_f_end,
        "include_monitor": include_monitor, "include_clock": include_clock,
        "engine": "v3",
        "fill_all_rows": fill_all_rows,
        "substation_quality": substation_quality,
        "substation_step": 0 if substation_quality == "none" else step,
        "substation_reach": 0.0 if substation_quality == "none" else reach
    }

    if progress_callback:
        progress_callback("Hazır!", 1.0)

    return bp_string, metadata
