"""
Factorio 2.0 Circuit Engine V2 — 27-Bit Zamansal Paketleme (Temporal Bit-Packing)
====================================================================================

MİMARİ:
───────
1. MERKEZÎ SAAT (Master Clock — 1 Adet):
   Tüm şeritler ve ROM blokları için sadece 1 adet saat devresi bulunur.
   - Constant Combinator: signal-C = 1
   - Decider Combinator: signal-C < total_ticks -> signal-C (copy count)
   - Arithmetic Combinator 1: signal-C - 1 -> signal-C
   - Arithmetic Combinator 2: signal-C / div -> signal-F (0..total_frames - 1)
   Saat çıkışı (signal-F) KIRMIZI kablo ile üst trafo hattı köprüsü üzerinden
   tüm ROM bloklarındaki decider'lara ulaştırılır.

2. RENK DEKODERİ (Color Decoder — 285 Sinyal Başına 1 Adet):
   12 adet aritmetik kombinatörden oluşur (9-bit piksel -> 24-bit RGB24 Packed):
   - Kırmızı dal: AND 448 -> >> 6 -> * 36 -> << 16
   - Yeşil dal:   AND 56  -> >> 3 -> * 36 -> << 8
   - Mavi dal:    AND 7   -> * 36 -> * 1  -> * 1
   Dekoder çıkışı (yeşil kablo) monitör lambalarının besleme noktasına bağlanır.
   - Yatay Sağ blok (Bank A): dir = DIR_WEST (12)
   - Yatay Sol blok (Bank B): dir = DIR_EAST (4)
   - Dikey Üst blok (Bank A): dir = DIR_SOUTH (8)
   - Dikey Alt blok (Bank B): dir = DIR_NORTH (0)

3. ROM BİLEŞENİ (1 CC + 3 Dal İkili Kombinatör Bloğu = 7 Eleman):
   13 karo genişlikli/uzunluklu modül:
   - Sabit Kombinatör (CC): 3 ardışık kareyi 27-bit paket olarak tutar.
   - Dal 0 (Kare 3k+0): Decider (F == 3k+0) -> Arith (>> 18)
   - Dal 1 (Kare 3k+1): Decider (F == 3k+1) -> Arith (>> 9)
   - Dal 2 (Kare 3k+2): Decider (F == 3k+2) -> Arith (* 1)
   - Çıkışlar ortak YEŞİL hat ile doğrudan TrueColor adaptörünün girişine (AND 448, AND 56, AND 7) bağlanır.
   - Devre hattı gecikmesi 6 ticktir.

4. DİZİLİM MODLARI (ROM Modes):
   - horizontal_right: Tek blok, ekranın sağında (Bank A).
   - horizontal_left:  Tek blok, ekranın solunda (Bank B).
   - horizontal_both:  Çift blok, sol yarı ekranın solunda (Bank B), sağ yarı ekranın sağında (Bank A).
   - vertical_top:     Tek blok, ekranın üstünde (Bank A).
   - vertical_bottom:  Tek blok, ekranın altında (Bank B).
   - vertical_both:    Çift blok, üst yarı ekranın üstünde (Bank A), alt yarı ekranın altında (Bank B).

5. GÖMÜLÜ TRAFOLAR (Substations):
   Ekran lambaları trafo konumlarında 2x2 boşluk bırakarak örülür.
   Tüm ekranın ortasındaki ve çevresindeki trafolar eksiksiz yerleşir ve 18 karelik bakır hatla bağlanır.
"""

import os
import json
import zlib
import base64
import math
import io
from typing import List, Tuple, Dict, Any, Optional, Union, Callable
from PIL import Image

# ──────────────────────────────────────────────────────────────────────────────
# Sabit port tanımları (Factorio 2.0 wire connector IDs)
# ──────────────────────────────────────────────────────────────────────────────
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

FRAMES_PER_PACK = 3


# ──────────────────────────────────────────────────────────────────────────────
# Sinyal Havuzu
# ──────────────────────────────────────────────────────────────────────────────
def _load_curated_signals() -> List[Tuple[str, str]]:
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
    fallback = []
    for c in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        fallback.append((f"signal-{c}", "virtual"))
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


# ──────────────────────────────────────────────────────────────────────────────
# Piksel Paketleme Yardımcıları
# ──────────────────────────────────────────────────────────────────────────────
def _bytes_to_image(b: bytes) -> Image.Image:
    return Image.open(io.BytesIO(b)).convert("RGB")


def pack_9bit_pixel(r: int, g: int, b: int) -> int:
    """8-bit RGB -> 9-bit [RRR GGG BBB] (her kanal 0-7)."""
    r3 = (max(0, min(255, r)) * 7 + 127) // 255
    g3 = (max(0, min(255, g)) * 7 + 127) // 255
    b3 = (max(0, min(255, b)) * 7 + 127) // 255
    return (r3 << 6) | (g3 << 3) | b3


def pack_3frames_to_signal(pix0: int, pix1: int, pix2: int) -> int:
    """3 adet 9-bit piksel -> 27-bit tamsayı. Bit 26-18: F0, 17-9: F1, 8-0: F2."""
    return ((pix0 & 0x1FF) << 18) | ((pix1 & 0x1FF) << 9) | (pix2 & 0x1FF)


def _build_cc_sections(filters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Factorio 2.0 Constant Combinator section formatı.
    Tek bir section en fazla 1000 filtre kabul edebilir ve her bir section
    içerisindeki filtre index'leri daima 1'den başlamalıdır (1 <= index <= 1000).
    Aksi takdirde oyun 'Index out of bounds: 1001 > 1000 (max)' hatası verir.
    """
    SECTION_SIZE = 1000
    sections = []
    if not filters:
        return [{"index": 1, "filters": []}]
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
    return sections


def _arith_each(op: str, val: int) -> Dict[str, Any]:
    """signal-each [op] val -> signal-each"""
    return {
        "arithmetic_conditions": {
            "first_signal": {"type": "virtual", "name": "signal-each"},
            "second_constant": val,
            "operation": op,
            "output_signal": {"type": "virtual", "name": "signal-each"}
        }
    }


def _make_decider_f(f_val: int) -> Dict[str, Any]:
    """signal-F == f_val (kırmızı hat) -> signal-everything (yeşil hat)"""
    cond: Dict[str, Any] = {
        "first_signal": {"type": "virtual", "name": "signal-F"},
        "comparator": "=",
        "first_signal_networks": {"red": True, "green": False},
        "compare_type": "and",
    }
    if f_val != 0:
        cond["constant"] = f_val
    return {
        "decider_conditions": {
            "conditions": [cond],
            "outputs": [{
                "signal": {"type": "virtual", "name": "signal-everything"},
                "networks": {"red": False, "green": True}
            }],
            "else_outputs": []
        }
    }


# ──────────────────────────────────────────────────────────────────────────────
# Yatay Renk Decoder Bloğu (12 Aritmetik Kombinatör)
# ──────────────────────────────────────────────────────────────────────────────
def _build_color_decoder(
    entities: List[Dict[str, Any]],
    wires: List[List[int]],
    x_start: float,
    y_pos: float,
    feed_lamp_id: Optional[int],
    entity_id_start: int,
    is_left: bool = False,
    compact: bool = True,
    substations_list: Optional[List[Any]] = None,
    placed_pos_map: Optional[Dict[int, Dict[str, Any]]] = None
) -> Tuple[int, int, int, float]:
    """
    Yatay yerleşim için 12 kombinatörlük Renk Dekoderi kurar.
    - is_left=False (Sağ Blok): dir=DIR_WEST (12), sinyal sağdan sola akar.
    - is_left=True  (Sol Blok): dir=DIR_EAST (4),  sinyal soldan sağa akar.
    Dönüş: (decoder_input_combinator_id, decoder_output_combinator_id, next_entity_id, last_x_position)
    """
    eid = entity_id_start
    dir_comb = DIR_EAST if is_left else DIR_WEST

    configs = [
        (0.0,  "<<", 16),   # E1
        (2.0,  "*",  36),   # E2
        (4.0,  ">>", 6),    # E3
        (6.0,  "AND", 448), # E4
        (8.0,  "<<", 8),    # E5
        (10.0, "*",  36),   # E6
        (12.0, ">>", 3),    # E7
        (14.0, "AND", 56),  # E8
        (16.0, "*",  1),    # E9
        (18.0, "*",  1),    # E10
        (20.0, "*",  36),   # E11
        (22.0, "AND", 7),   # E12
    ]

    row_subs_intervals = []
    if substations_list:
        for sb in substations_list:
            if isinstance(sb, dict):
                tx = sb.get("tx", 0)
                ty = sb.get("ty", 0)
            elif isinstance(sb, (list, tuple)):
                tx, ty = sb[0], sb[1]
            else:
                continue
            if ty <= y_pos < ty + 2.0:
                row_subs_intervals.append((tx, tx + 2.0))

    dec_ids: List[int] = []
    cur_x = x_start

    for _, op, val in configs:
        cur_id = eid; eid += 1
        dec_ids.append(cur_id)
        while True:
            collides = False
            for st, en in row_subs_intervals:
                if is_left:
                    if max(st, cur_x - 2.0) < min(en, cur_x) - 0.001:
                        collides = True
                        cur_x = st
                        break
                else:
                    if max(st, cur_x) < min(en, cur_x + 2.0) - 0.001:
                        collides = True
                        cur_x = en
                        break
            if not collides:
                break

        nominal_x = (cur_x - 1.0) if is_left else (cur_x + 1.0)
        cur_x = (cur_x - 2.0) if is_left else (cur_x + 2.0)

        if placed_pos_map is not None:
            placed_pos_map[cur_id] = {"x": nominal_x, "y": y_pos, "name": "arithmetic-combinator"}
        entities.append({
            "entity_number": cur_id,
            "name": "arithmetic-combinator",
            "position": {"x": nominal_x, "y": y_pos},
            "direction": dir_comb,
            "control_behavior": _arith_each(op, val)
        })
    last_x = cur_x

    internal_wires = [
        (1, COMB_IN_GREEN,  2, COMB_OUT_GREEN),
        (1, COMB_OUT_GREEN, 5, COMB_OUT_GREEN),
        (2, COMB_IN_GREEN,  3, COMB_OUT_GREEN),
        (3, COMB_IN_GREEN,  4, COMB_OUT_GREEN),
        (4, COMB_IN_GREEN,  8, COMB_IN_GREEN),
        (5, COMB_IN_GREEN,  6, COMB_OUT_GREEN),
        (5, COMB_OUT_GREEN, 9, COMB_OUT_GREEN),
        (6, COMB_IN_GREEN,  7, COMB_OUT_GREEN),
        (7, COMB_IN_GREEN,  8, COMB_OUT_GREEN),
        (8, COMB_IN_GREEN,  12, COMB_IN_GREEN),
        (9, COMB_IN_GREEN,  10, COMB_OUT_GREEN),
        (10, COMB_IN_GREEN, 11, COMB_OUT_GREEN),
        (11, COMB_IN_GREEN, 12, COMB_OUT_GREEN),
    ]
    for e1_idx, p1, e2_idx, p2 in internal_wires:
        wires.append([dec_ids[e1_idx - 1], p1, dec_ids[e2_idx - 1], p2])

    out_id = dec_ids[0]
    if feed_lamp_id is not None:
        wires.append([out_id, COMB_OUT_GREEN, feed_lamp_id, WIRE_GREEN])

    in_id = dec_ids[11]

    return in_id, out_id, eid, last_x


# ──────────────────────────────────────────────────────────────────────────────
# Dikey Renk Decoder Bloğu (12 Aritmetik Kombinatör)
# ──────────────────────────────────────────────────────────────────────────────
def _build_color_decoder_vertical(
    entities: List[Dict[str, Any]],
    wires: List[List[int]],
    x_pos: float,
    y_start: float,
    feed_lamp_id: Optional[int],
    entity_id_start: int,
    is_bottom: bool = False,
    compact: bool = True,
    substations_list: Optional[List[Any]] = None,
    placed_pos_map: Optional[Dict[int, Dict[str, Any]]] = None
) -> Tuple[int, int, int, float]:
    """
    Dikey yerleşim için 12 kombinatörlük Renk Dekoderi kurar.
    - is_bottom=False (Üst Blok): dir=DIR_SOUTH (8), yukarı uzanır (E1 en altta).
    - is_bottom=True  (Alt Blok): dir=DIR_NORTH (0), aşağı uzanır (E1 en üstte).
    Dönüş: (decoder_input_combinator_id, decoder_output_combinator_id, next_entity_id, last_y_position)
    """
    eid = entity_id_start
    dir_comb = DIR_NORTH if is_bottom else DIR_SOUTH

    configs = [
        (0.0,  "<<", 16),   # E1
        (2.0,  "*",  36),   # E2
        (4.0,  ">>", 6),    # E3
        (6.0,  "AND", 448), # E4
        (8.0,  "<<", 8),    # E5
        (10.0, "*",  36),   # E6
        (12.0, ">>", 3),    # E7
        (14.0, "AND", 56),  # E8
        (16.0, "*",  1),    # E9
        (18.0, "*",  1),    # E10
        (20.0, "*",  36),   # E11
        (22.0, "AND", 7),   # E12
    ]

    col_subs_intervals = []
    if substations_list:
        for sb in substations_list:
            if isinstance(sb, dict):
                tx = sb.get("tx", 0)
                ty = sb.get("ty", 0)
            elif isinstance(sb, (list, tuple)):
                tx, ty = sb[0], sb[1]
            else:
                continue
            if tx <= x_pos < tx + 2.0:
                col_subs_intervals.append((ty, ty + 2.0))

    dec_ids: List[int] = []
    cur_y = y_start

    for _, op, val in configs:
        cur_id = eid; eid += 1
        dec_ids.append(cur_id)
        while True:
            collides = False
            for st, en in col_subs_intervals:
                if is_bottom:
                    if max(st, cur_y) < min(en, cur_y + 2.0) - 0.001:
                        collides = True
                        cur_y = en
                        break
                else:
                    if max(st, cur_y - 2.0) < min(en, cur_y) - 0.001:
                        collides = True
                        cur_y = st
                        break
            if not collides:
                break

        nominal_y = (cur_y + 1.0) if is_bottom else (cur_y - 1.0)
        cur_y = (cur_y + 2.0) if is_bottom else (cur_y - 2.0)

        if placed_pos_map is not None:
            placed_pos_map[cur_id] = {"x": x_pos, "y": nominal_y, "name": "arithmetic-combinator"}
        entities.append({
            "entity_number": cur_id,
            "name": "arithmetic-combinator",
            "position": {"x": x_pos, "y": nominal_y},
            "direction": dir_comb,
            "control_behavior": _arith_each(op, val)
        })
    last_y = cur_y

    internal_wires = [
        (1, COMB_IN_GREEN,  2, COMB_OUT_GREEN),
        (1, COMB_OUT_GREEN, 5, COMB_OUT_GREEN),
        (2, COMB_IN_GREEN,  3, COMB_OUT_GREEN),
        (3, COMB_IN_GREEN,  4, COMB_OUT_GREEN),
        (4, COMB_IN_GREEN,  8, COMB_IN_GREEN),
        (5, COMB_IN_GREEN,  6, COMB_OUT_GREEN),
        (5, COMB_OUT_GREEN, 9, COMB_OUT_GREEN),
        (6, COMB_IN_GREEN,  7, COMB_OUT_GREEN),
        (7, COMB_IN_GREEN,  8, COMB_OUT_GREEN),
        (8, COMB_IN_GREEN,  12, COMB_IN_GREEN),
        (9, COMB_IN_GREEN,  10, COMB_OUT_GREEN),
        (10, COMB_IN_GREEN, 11, COMB_OUT_GREEN),
        (11, COMB_IN_GREEN, 12, COMB_OUT_GREEN),
    ]
    for e1_idx, p1, e2_idx, p2 in internal_wires:
        wires.append([dec_ids[e1_idx - 1], p1, dec_ids[e2_idx - 1], p2])

    out_id = dec_ids[0]
    if feed_lamp_id is not None:
        wires.append([out_id, COMB_OUT_GREEN, feed_lamp_id, WIRE_GREEN])

    in_id = dec_ids[11]

    return in_id, out_id, eid, last_y


# ──────────────────────────────────────────────────────────────────────────────
# Ana Derleyici Fonksiyonu (compile_blueprint_v2)
# ──────────────────────────────────────────────────────────────────────────────
def compile_blueprint_v2(
    frames: List[Union[Image.Image, bytes]],
    fps: int = 5,
    rom_mode: str = "horizontal_right",
    copy_convenience: int = 250,
    part_idx: int = 0,
    progress_callback: Optional[Callable[[str, float], None]] = None,
    total_parts: Optional[int] = None,
    num_parts: Optional[int] = None,
    compact_rom: bool = True,
    fill_all_rows: bool = False,
) -> Tuple[str, Dict[str, Any]]:
    """
    Factorio 2.0 video-to-screen blueprint üreticisi (27-bit Temporal Bit-Packing).
    - 1 adet merkezî saat
    - 285 sinyale kadar 1 adet TrueColor renk dekoderi
    - 7 elemanlı ROM birimi (1 CC + 3 Decider + 3 Shifter = 13 karo) kopyalanarak inşa edilir.
    - rom_mode: 'horizontal_right', 'horizontal_left', 'horizontal_both',
                'vertical_top', 'vertical_bottom', 'vertical_both'
    """
    if not frames:
        raise ValueError("En az bir kare (frame) sağlanmalıdır.")

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
    mult = safe_fps // g
    div = 60 // g
    total_ticks = math.ceil(total_frames * div / mult)

    # 1. Şerit (Stripe) ve Blok Hesaplamaları
    if is_horizontal:
        cols_per_stripe = 0
        if is_both:
            w_left = math.ceil(width / 2)
            w_right = width - w_left
            max_w = max(w_left, w_right)
            if max_w > len(SIGNAL_POOL):
                raise ValueError(
                    f"Yarım ekran genişliği ({max_w} px) sinyal sınırını ({len(SIGNAL_POOL)}) aşıyor!"
                )
            rows_per_stripe = min(8, max(1, len(SIGNAL_POOL) // max(1, max_w)))
            num_stripes = math.ceil(height / max(1, rows_per_stripe))
        else:
            w_left = width
            w_right = 0
            if width > len(SIGNAL_POOL):
                raise ValueError(
                    f"Genişlik ({width} px) tek blok sinyal sınırını ({len(SIGNAL_POOL)}) aşıyor! "
                    f"Lütfen 'Yatay: Çift Blok' seçin veya çözünürlüğü düşürün."
                )
            if width * height <= len(SIGNAL_POOL):
                rows_per_stripe = height
                num_stripes = 1
            else:
                rows_per_stripe = min(8, max(1, MAX_PIXELS_PER_STRIPE // max(1, width)))
                num_stripes = math.ceil(height / max(1, rows_per_stripe))
    else:
        rows_per_stripe = 0
        if is_both:
            h_top = math.ceil(height / 2)
            h_bottom = height - h_top
            max_h = max(h_top, h_bottom)
            if max_h > len(SIGNAL_POOL):
                raise ValueError(
                    f"Yarım ekran yüksekliği ({max_h} px) sinyal sınırını ({len(SIGNAL_POOL)}) aşıyor!"
                )
            cols_per_stripe = min(8, max(1, len(SIGNAL_POOL) // max(1, max_h)))
            num_stripes = math.ceil(width / max(1, cols_per_stripe))
            w_left = width
            w_right = 0
        else:
            h_top = height
            h_bottom = 0
            if height > len(SIGNAL_POOL):
                raise ValueError(
                    f"Yükseklik ({height} px) tek blok sinyal sınırını ({len(SIGNAL_POOL)}) aşıyor! "
                    f"Lütfen 'Dikey: Çift Blok' seçin veya çözünürlüğü düşürün."
                )
            if width * height <= len(SIGNAL_POOL):
                cols_per_stripe = width
                num_stripes = 1
            else:
                cols_per_stripe = min(8, max(1, MAX_PIXELS_PER_STRIPE // max(1, height)))
                num_stripes = math.ceil(width / max(1, cols_per_stripe))
            w_left = width
            w_right = 0

    total_packs = math.ceil(total_frames / FRAMES_PER_PACK)

    # Parçalama (Slicing) hesabı
    num_parts = max(1, min(16, int(num_parts))) if num_parts is not None else (total_parts if total_parts is not None else 1)
    part_idx = max(0, min(num_parts - 1, int(part_idx)))
    copy_convenience = bool(copy_convenience)

    p_start = (total_packs * part_idx) // num_parts
    p_end = (total_packs * (part_idx + 1)) // num_parts
    if p_start >= p_end:
        p_start = min(part_idx, total_packs - 1)
        p_end = min(part_idx + 1, total_packs)

    if part_idx > 0 and copy_convenience:
        compile_p_start = max(0, p_start - 1)
    else:
        compile_p_start = p_start
    compile_p_end = p_end

    pack_start = compile_p_start
    pack_end = compile_p_end

    include_monitor = (part_idx == 0)
    include_clock = (part_idx == 0)

    if progress_callback:
        progress_callback(
            f"V2 Mimari [{rom_mode}]: {num_stripes} şerit, {total_frames} kare ({total_packs} paket), "
            f"Parça {part_idx + 1}/{num_parts} (Paket {pack_start}..{pack_end - 1})...", 0.05
        )

    # 2. Trafo Grid Koordinatları ve Ekran İçi Gömülü Boşluklar (occupied_lamp_tiles)
    step = 18
    half_reach = 9
    x_start = -2
    y_start = -2

    # Global kapsama alanı
    span_val = max(1, rows_per_stripe if is_horizontal else cols_per_stripe)
    dim_val = height if is_horizontal else width
    max_cols_est = math.ceil(total_packs / (span_val if fill_all_rows else dim_val)) if fill_all_rows else total_packs
    comb_span = float(max_cols_est * 24.0 + 40.0)

    if is_horizontal:
        if is_both:
            min_x_sub = int(-comb_span)
            max_x_sub = int(width + comb_span)
        elif is_left:
            min_x_sub = int(-comb_span)
            max_x_sub = int(width + 4.0)
        else:
            min_x_sub = -4
            max_x_sub = int(width + comb_span)

        min_y_sub = -4
        max_y_sub = int(height + 6)
    else:
        min_x_sub = -8
        max_x_sub = int(width + 6)
        if is_both:
            min_y_sub = int(-comb_span - 4)
            max_y_sub = int(height + comb_span + 4)
        elif is_bottom:
            min_y_sub = -4
            max_y_sub = int(height + comb_span + 4)
        else:
            min_y_sub = int(-comb_span - 4)
            max_y_sub = int(height + 4)

    x_coords: List[int] = []
    cx = x_start
    while cx > min_x_sub:
        cx -= step
    while cx - half_reach <= max_x_sub:
        x_coords.append(cx)
        cx += step

    y_coords: List[int] = []
    cy = y_start
    while cy > min_y_sub:
        cy -= step
    while cy - half_reach <= max_y_sub:
        y_coords.append(cy)
        cy += step

    # 2.1. Şerit Koordinatları
    sub_bands_y = [(float(ty), float(ty + 2.0)) for ty in y_coords]
    sub_bands_x = [(float(tx), float(tx + 2.0)) for tx in x_coords]
    stripe_pos_map: Dict[int, float] = {}
    chosen_feed_idx: Dict[int, int] = {}

    candidates: List[List[int]] = []
    for s in range(num_stripes):
        if is_horizontal:
            ys = s * rows_per_stripe
            ye = min(height, (s + 1) * rows_per_stripe)
            valid = [r for r in range(ys, ye) if not any(t0 <= r < t1 for t0, t1 in sub_bands_y)]
            if not valid:
                valid = list(range(ys, ye))
            if not valid:
                valid = [min(ys, max(0, height - 1))]
        else:
            xs = s * cols_per_stripe
            xe = min(width, (s + 1) * cols_per_stripe)
            valid = [c for c in range(xs, xe) if not any(t0 <= c < t1 for t0, t1 in sub_bands_x)]
            if not valid:
                valid = list(range(xs, xe))
            if not valid:
                valid = [min(xs, max(0, width - 1))]
        candidates.append(valid)

    span = rows_per_stripe if is_horizontal else cols_per_stripe

    def _find_stripe_indices(s_idx: int, prev_idx: Optional[int]) -> Optional[List[int]]:
        if s_idx == num_stripes:
            return []
        target = (prev_idx + span) if prev_idx is not None else 2
        c_list = candidates[s_idx] if s_idx < len(candidates) else []
        if not c_list:
            return None
        sorted_cand = sorted(c_list, key=lambda idx: abs(idx - target))
        for idx in sorted_cand:
            if prev_idx is not None and abs(idx - prev_idx) > 8:
                continue
            res = _find_stripe_indices(s_idx + 1, idx)
            if res is not None:
                return [idx] + res
        return None

    sel_indices = _find_stripe_indices(0, None)
    if sel_indices is None:
        sel_indices = [c[0] if c else (s * span) for s, c in enumerate(candidates)]

    for s in range(num_stripes):
        v = int(sel_indices[s]) if s < len(sel_indices) else (s * span)
        chosen_feed_idx[s] = v
        stripe_pos_map[s] = float(v + 0.5)

    # Ekran içi trafo çakışmalarını önle (2x2 gömülü trafo alanı)
    occupied_lamp_tiles = set()
    for ty in y_coords:
        for tx in x_coords:
            for dtx in (0, 1):
                for dty in (0, 1):
                    px = tx + dtx
                    py = ty + dty
                    if 0 <= px < width and 0 <= py < height:
                        occupied_lamp_tiles.add((px, py))

    entities: List[Dict[str, Any]] = []
    wires: List[List[int]] = []
    entity_id = 1
    placed_pos_map: Dict[int, Dict[str, Any]] = {}

    # 2.5. Trafolar (Substations) ve Güç Dağıtımı
    substations: Dict[Tuple[int, int], Dict[str, Any]] = {}
    sub_list: List[Dict[str, Any]] = []

    for ty in y_coords:
        for tx in x_coords:
            sid = entity_id; entity_id += 1
            sub = {
                "entity_number": sid,
                "name": "substation",
                "position": {"x": float(tx + 1.0), "y": float(ty + 1.0)},
                "tx": tx, "ty": ty
            }
            entities.append(sub)
            substations[(tx, ty)] = sub
            sub_list.append(sub)
            placed_pos_map[sid] = {"x": sub["position"]["x"], "y": sub["position"]["y"], "name": "substation"}

    # Trafolar arası bakır kablo bağlantıları
    for sub in sub_list:
        for dx, dy in [(step, 0), (0, step)]:
            neighbor = substations.get((sub["tx"] + dx, sub["ty"] + dy))
            if neighbor:
                dist = math.hypot(sub["position"]["x"] - neighbor["position"]["x"],
                                  sub["position"]["y"] - neighbor["position"]["y"])
                if dist <= 18.5:
                    wires.append([sub["entity_number"], POLE_COPPER, neighbor["entity_number"], POLE_COPPER])

    # 2.6. Sol Üst Hizalama Trafosu
    align_sub_id = entity_id; entity_id += 1
    entities.append({
        "entity_number": align_sub_id,
        "name": "substation",
        "position": {"x": -1.0, "y": -3.0},
        "tx": -2, "ty": -4
    })
    placed_pos_map[align_sub_id] = {"x": -1.0, "y": -3.0, "name": "substation"}
    tl_sub = substations.get((-2, -2))
    if tl_sub:
        wires.append([align_sub_id, POLE_COPPER, tl_sub["entity_number"], POLE_COPPER])
    elif not include_monitor:
        tl_sub_id = entity_id; entity_id += 1
        entities.append({
            "entity_number": tl_sub_id, "name": "substation",
            "position": {"x": -1.0, "y": -1.0}, "tx": -2, "ty": -2
        })
        placed_pos_map[tl_sub_id] = {"x": -1.0, "y": -1.0, "name": "substation"}
        wires.append([align_sub_id, POLE_COPPER, tl_sub_id, POLE_COPPER])

    # 3. Monitör Lambaları (SADECE PARÇA 0'DA)
    lamp_grid: Dict[Tuple[int, int], int] = {}
    stripe_feed_lamps_A: Dict[int, int] = {}
    stripe_feed_lamps_B: Dict[int, int] = {}

    if include_monitor:
        if progress_callback:
            progress_callback(f"{width}x{height} Ekran matrisi örülüyor...", 0.15)

        if is_horizontal:
            for s in range(num_stripes):
                ys = s * rows_per_stripe
                ye = min(height, (s + 1) * rows_per_stripe)
                feed_row = chosen_feed_idx.get(s, ys)

                if is_both:
                    # Sol Blok Lambaları (Bank B): lx in [0, w_left - 1]
                    for ly in range(ys, ye):
                        for lx in range(w_left):
                            if (lx, ly) in occupied_lamp_tiles:
                                continue
                            l_idx = (ly - ys) * w_left + lx
                            sig_name, sig_type, sig_quality = get_signal_for_pixel(l_idx)
                            lid = entity_id; entity_id += 1
                            lamp_grid[(lx, ly)] = lid
                            placed_pos_map[lid] = {"x": float(lx + 0.5), "y": float(ly + 0.5), "name": "small-lamp"}
                            entities.append({
                                "entity_number": lid, "name": "small-lamp",
                                "position": {"x": float(lx + 0.5), "y": float(ly + 0.5)},
                                "always_on": True,
                                "control_behavior": {
                                    "use_colors": True, "color_mode": 2,
                                    "rgb_signal": {"type": sig_type, "name": sig_name, "quality": sig_quality}
                                }
                            })
                        r_lamps = [lamp_grid[(lx, ly)] for lx in range(w_left) if (lx, ly) in lamp_grid]
                        for i in range(len(r_lamps) - 1):
                            wires.append([r_lamps[i], WIRE_GREEN, r_lamps[i + 1], WIRE_GREEN])

                    leftmost_lamps = []
                    for ly in range(ys, ye):
                        r_lamps = [lamp_grid[(lx, ly)] for lx in range(w_left) if (lx, ly) in lamp_grid]
                        if r_lamps:
                            leftmost_lamps.append(r_lamps[0])
                    for i in range(len(leftmost_lamps) - 1):
                        wires.append([leftmost_lamps[i], WIRE_GREEN, leftmost_lamps[i + 1], WIRE_GREEN])

                    if leftmost_lamps:
                        cand_b = [lamp_grid[(lx, feed_row)] for lx in range(w_left) if (lx, feed_row) in lamp_grid]
                        stripe_feed_lamps_B[s] = cand_b[0] if cand_b else leftmost_lamps[0]

                    # Sağ Blok Lambaları (Bank A): lx in [w_left, width - 1]
                    for ly in range(ys, ye):
                        for lx in range(w_left, width):
                            if (lx, ly) in occupied_lamp_tiles:
                                continue
                            l_idx = (ly - ys) * w_right + (lx - w_left)
                            sig_name, sig_type, sig_quality = get_signal_for_pixel(l_idx)
                            lid = entity_id; entity_id += 1
                            lamp_grid[(lx, ly)] = lid
                            placed_pos_map[lid] = {"x": float(lx + 0.5), "y": float(ly + 0.5), "name": "small-lamp"}
                            entities.append({
                                "entity_number": lid, "name": "small-lamp",
                                "position": {"x": float(lx + 0.5), "y": float(ly + 0.5)},
                                "always_on": True,
                                "control_behavior": {
                                    "use_colors": True, "color_mode": 2,
                                    "rgb_signal": {"type": sig_type, "name": sig_name, "quality": sig_quality}
                                }
                            })
                        r_lamps = [lamp_grid[(lx, ly)] for lx in range(w_left, width) if (lx, ly) in lamp_grid]
                        for i in range(len(r_lamps) - 1):
                            wires.append([r_lamps[i], WIRE_GREEN, r_lamps[i + 1], WIRE_GREEN])

                    rightmost_lamps = []
                    for ly in range(ys, ye):
                        r_lamps = [lamp_grid[(lx, ly)] for lx in range(w_left, width) if (lx, ly) in lamp_grid]
                        if r_lamps:
                            rightmost_lamps.append(r_lamps[-1])
                    for i in range(len(rightmost_lamps) - 1):
                        wires.append([rightmost_lamps[i], WIRE_GREEN, rightmost_lamps[i + 1], WIRE_GREEN])

                    if rightmost_lamps:
                        cand_a = [lamp_grid[(lx, feed_row)] for lx in range(w_left, width) if (lx, feed_row) in lamp_grid]
                        stripe_feed_lamps_A[s] = cand_a[-1] if cand_a else rightmost_lamps[-1]

                else:
                    # Tek Blok (Sağ veya Sol)
                    for ly in range(ys, ye):
                        for lx in range(width):
                            if (lx, ly) in occupied_lamp_tiles:
                                continue
                            l_idx = (ly - ys) * width + lx
                            sig_name, sig_type, sig_quality = get_signal_for_pixel(l_idx)
                            lid = entity_id; entity_id += 1
                            lamp_grid[(lx, ly)] = lid
                            placed_pos_map[lid] = {"x": float(lx + 0.5), "y": float(ly + 0.5), "name": "small-lamp"}
                            entities.append({
                                "entity_number": lid, "name": "small-lamp",
                                "position": {"x": float(lx + 0.5), "y": float(ly + 0.5)},
                                "always_on": True,
                                "control_behavior": {
                                    "use_colors": True, "color_mode": 2,
                                    "rgb_signal": {"type": sig_type, "name": sig_name, "quality": sig_quality}
                                }
                            })
                        r_lamps = [lamp_grid[(lx, ly)] for lx in range(width) if (lx, ly) in lamp_grid]
                        for i in range(len(r_lamps) - 1):
                            wires.append([r_lamps[i], WIRE_GREEN, r_lamps[i + 1], WIRE_GREEN])

                    edge_lamps = []
                    for ly in range(ys, ye):
                        r_lamps = [lamp_grid[(lx, ly)] for lx in range(width) if (lx, ly) in lamp_grid]
                        if r_lamps:
                            edge_lamps.append(r_lamps[0] if is_left else r_lamps[-1])
                    for i in range(len(edge_lamps) - 1):
                        wires.append([edge_lamps[i], WIRE_GREEN, edge_lamps[i + 1], WIRE_GREEN])

                    if edge_lamps:
                        cand = [lamp_grid[(lx, feed_row)] for lx in range(width) if (lx, feed_row) in lamp_grid]
                        if is_left:
                            stripe_feed_lamps_B[s] = cand[0] if cand else edge_lamps[0]
                        else:
                            stripe_feed_lamps_A[s] = cand[-1] if cand else edge_lamps[-1]

        else: # Dikey Lambalar
            for s in range(num_stripes):
                xs = s * cols_per_stripe
                xe = min(width, (s + 1) * cols_per_stripe)
                feed_col = chosen_feed_idx.get(s, xs)

                if is_both:
                    # Üst Blok Lambaları (Bank A): ly in range(0, h_top)
                    for lx in range(xs, xe):
                        for ly in range(0, h_top):
                            if (lx, ly) in occupied_lamp_tiles:
                                continue
                            l_idx = (lx - xs) * h_top + ly
                            sig_name, sig_type, sig_quality = get_signal_for_pixel(l_idx)
                            lid = entity_id; entity_id += 1
                            lamp_grid[(lx, ly)] = lid
                            placed_pos_map[lid] = {"x": float(lx + 0.5), "y": float(ly + 0.5), "name": "small-lamp"}
                            entities.append({
                                "entity_number": lid, "name": "small-lamp",
                                "position": {"x": float(lx + 0.5), "y": float(ly + 0.5)},
                                "always_on": True,
                                "control_behavior": {
                                    "use_colors": True, "color_mode": 2,
                                    "rgb_signal": {"type": sig_type, "name": sig_name, "quality": sig_quality}
                                }
                            })
                        c_lamps = [lamp_grid[(lx, ly)] for ly in range(0, h_top) if (lx, ly) in lamp_grid]
                        for i in range(len(c_lamps) - 1):
                            wires.append([c_lamps[i], WIRE_GREEN, c_lamps[i + 1], WIRE_GREEN])

                    top_lamps = []
                    for lx in range(xs, xe):
                        c_lamps = [lamp_grid[(lx, ly)] for ly in range(0, h_top) if (lx, ly) in lamp_grid]
                        if c_lamps:
                            top_lamps.append(c_lamps[0])
                    for i in range(len(top_lamps) - 1):
                        wires.append([top_lamps[i], WIRE_GREEN, top_lamps[i + 1], WIRE_GREEN])

                    if top_lamps:
                        cand_a = [lamp_grid[(feed_col, ly)] for ly in range(0, h_top) if (feed_col, ly) in lamp_grid]
                        stripe_feed_lamps_A[s] = cand_a[0] if cand_a else top_lamps[0]

                    # Alt Blok Lambaları (Bank B): ly in range(h_top, height)
                    for lx in range(xs, xe):
                        for ly in range(h_top, height):
                            if (lx, ly) in occupied_lamp_tiles:
                                continue
                            l_idx = (lx - xs) * h_bottom + (ly - h_top)
                            sig_name, sig_type, sig_quality = get_signal_for_pixel(l_idx)
                            lid = entity_id; entity_id += 1
                            lamp_grid[(lx, ly)] = lid
                            placed_pos_map[lid] = {"x": float(lx + 0.5), "y": float(ly + 0.5), "name": "small-lamp"}
                            entities.append({
                                "entity_number": lid, "name": "small-lamp",
                                "position": {"x": float(lx + 0.5), "y": float(ly + 0.5)},
                                "always_on": True,
                                "control_behavior": {
                                    "use_colors": True, "color_mode": 2,
                                    "rgb_signal": {"type": sig_type, "name": sig_name, "quality": sig_quality}
                                }
                            })
                        c_lamps = [lamp_grid[(lx, ly)] for ly in range(h_top, height) if (lx, ly) in lamp_grid]
                        for i in range(len(c_lamps) - 1):
                            wires.append([c_lamps[i], WIRE_GREEN, c_lamps[i + 1], WIRE_GREEN])

                    bottom_lamps = []
                    for lx in range(xs, xe):
                        c_lamps = [lamp_grid[(lx, ly)] for ly in range(h_top, height) if (lx, ly) in lamp_grid]
                        if c_lamps:
                            bottom_lamps.append(c_lamps[-1])
                    for i in range(len(bottom_lamps) - 1):
                        wires.append([bottom_lamps[i], WIRE_GREEN, bottom_lamps[i + 1], WIRE_GREEN])

                    if bottom_lamps:
                        cand_b = [lamp_grid[(feed_col, ly)] for ly in range(h_top, height) if (feed_col, ly) in lamp_grid]
                        stripe_feed_lamps_B[s] = cand_b[-1] if cand_b else bottom_lamps[0]

                else:
                    # Tek Blok (Dikey Üst veya Alt)
                    for lx in range(xs, xe):
                        for ly in range(height):
                            if (lx, ly) in occupied_lamp_tiles:
                                continue
                            l_idx = (lx - xs) * height + ly
                            sig_name, sig_type, sig_quality = get_signal_for_pixel(l_idx)
                            lid = entity_id; entity_id += 1
                            lamp_grid[(lx, ly)] = lid
                            placed_pos_map[lid] = {"x": float(lx + 0.5), "y": float(ly + 0.5), "name": "small-lamp"}
                            entities.append({
                                "entity_number": lid, "name": "small-lamp",
                                "position": {"x": float(lx + 0.5), "y": float(ly + 0.5)},
                                "always_on": True,
                                "control_behavior": {
                                    "use_colors": True, "color_mode": 2,
                                    "rgb_signal": {"type": sig_type, "name": sig_name, "quality": sig_quality}
                                }
                            })
                        c_lamps = [lamp_grid[(lx, ly)] for ly in range(height) if (lx, ly) in lamp_grid]
                        for i in range(len(c_lamps) - 1):
                            wires.append([c_lamps[i], WIRE_GREEN, c_lamps[i + 1], WIRE_GREEN])

                    edge_lamps = []
                    for lx in range(xs, xe):
                        c_lamps = [lamp_grid[(lx, ly)] for ly in range(height) if (lx, ly) in lamp_grid]
                        if c_lamps:
                            edge_lamps.append(c_lamps[-1] if is_bottom else c_lamps[0])
                    for i in range(len(edge_lamps) - 1):
                        wires.append([edge_lamps[i], WIRE_GREEN, edge_lamps[i + 1], WIRE_GREEN])

                    if edge_lamps:
                        cand = [lamp_grid[(feed_col, ly)] for ly in range(height) if (feed_col, ly) in lamp_grid]
                        if is_bottom:
                            stripe_feed_lamps_B[s] = cand[-1] if cand else edge_lamps[-1]
                        else:
                            stripe_feed_lamps_A[s] = cand[0] if cand else edge_lamps[0]

    # 4. Yerleşim Parametreleri
    if is_horizontal:
        x_dec_start_A = float(width) if compact_rom else float(width + 2.0)
        x_rom_start_A = x_dec_start_A + 24.0
        x_dec_end_B = 0.0 if compact_rom else -2.0
        x_rom_start_B = x_dec_end_B - 24.0
    else:
        y_dec_start_A = 0.0 if compact_rom else -2.0
        y_rom_start_A = y_dec_start_A - 24.0
        y_dec_start_B = float(height) if compact_rom else float(height + 2.0)
        y_rom_start_B = y_dec_start_B + 24.0

    stripe_first_deciders_A: Dict[int, int] = {}
    stripe_first_deciders_B: Dict[int, int] = {}
    stripe_all_deciders_A: Dict[int, List[int]] = {s: [] for s in range(num_stripes)}
    stripe_all_deciders_B: Dict[int, List[int]] = {s: [] for s in range(num_stripes)}
    stripe_decoder_inputs_A: Dict[int, int] = {}
    stripe_decoder_inputs_B: Dict[int, int] = {}

    if is_horizontal:
        has_bank_A = (rom_mode in ("horizontal_right", "horizontal_both"))
        has_bank_B = (rom_mode in ("horizontal_left", "horizontal_both"))
    else:
        has_bank_A = (rom_mode in ("vertical_top", "vertical_both"))
        has_bank_B = (rom_mode in ("vertical_bottom", "vertical_both"))

    def _get_stripe_rows_v2(s_idx: int, rps: int, cur_hs: int) -> List[int]:
        ys = s_idx * rps
        ye = ys + cur_hs
        return list(range(ys, ye))

    wire_set = set(tuple(w) for w in wires)

    def _add_w(e1: int, c1: int, e2: int, c2: int):
        w = [e1, c1, e2, c2] if (e1, c1) <= (e2, c2) else [e2, c2, e1, c1]
        t = tuple(w)
        if t not in wire_set:
            wire_set.add(t)
            wires.append(w)

    # 5. ROM Bankaları ve Renk Dekoderleri İnşası
    for s in range(num_stripes):
        # ──────────────────────────────────────────────────────────────────────
        # A) YATAY MODLAR
        # ──────────────────────────────────────────────────────────────────────
        if is_horizontal:
            ys = s * rows_per_stripe
            ye = min(height, (s + 1) * rows_per_stripe)
            y_stripe = stripe_pos_map[s]

            # ── 5.1. SAĞ BANKA (Bank A - Yatay) ──
            if has_bank_A:
                if fill_all_rows:
                    stripe_rows = _get_stripe_rows_v2(s, rows_per_stripe, ye - ys)
                else:
                    stripe_rows = [int(y_stripe)]

                if not stripe_rows:
                    stripe_rows = [ys]

                dec_row = chosen_feed_idx.get(s, ys)
                y_dec = float(dec_row + 0.5)
                Hs = max(1, len(stripe_rows))

                if include_monitor and s in stripe_feed_lamps_A:
                    dec_in_A, _, entity_id, last_dec_x_A = _build_color_decoder(
                        entities, wires, x_dec_start_A, y_dec, stripe_feed_lamps_A[s], entity_id,
                        is_left=False, compact=compact_rom, substations_list=sub_list,
                        placed_pos_map=placed_pos_map
                    )
                    stripe_decoder_inputs_A[s] = dec_in_A
                    base_x_rom_A = last_dec_x_A
                else:
                    base_x_rom_A = x_rom_start_A

                x_px_start_A = w_left if is_both else 0
                w_block_A = w_right if is_both else width

                cur_x_row_A: Dict[int, float] = {ry: base_x_rom_A for ry in stripe_rows}
                col_units_A: Dict[int, List[Dict[str, Any]]] = {}

                for u in range(pack_start, pack_end):
                    f0_idx = u * FRAMES_PER_PACK + 0
                    f1_idx = u * FRAMES_PER_PACK + 1
                    f2_idx = u * FRAMES_PER_PACK + 2

                    img0 = frames[f0_idx] if f0_idx < total_frames else None
                    img1 = frames[f1_idx] if f1_idx < total_frames else None
                    img2 = frames[f2_idx] if f2_idx < total_frames else None

                    p0_img = (img0 if isinstance(img0, Image.Image) else _bytes_to_image(img0)) if img0 else None
                    p1_img = (img1 if isinstance(img1, Image.Image) else _bytes_to_image(img1)) if img1 else p0_img
                    p2_img = (img2 if isinstance(img2, Image.Image) else _bytes_to_image(img2)) if img2 else p1_img

                    filters = []
                    f_idx_counter = 1
                    for py in range(ys, ye):
                        for px in range(x_px_start_A, width):
                            if (px, py) in occupied_lamp_tiles:
                                continue
                            l_idx = (py - ys) * w_block_A + (px - x_px_start_A)
                            sig_name, sig_type, sig_quality = get_signal_for_pixel(l_idx)

                            r0, g0, b0 = p0_img.getpixel((px, py))[:3] if p0_img else (0, 0, 0)
                            pix0 = pack_9bit_pixel(r0, g0, b0)

                            r1, g1, b1 = p1_img.getpixel((px, py))[:3] if p1_img else (0, 0, 0)
                            pix1 = pack_9bit_pixel(r1, g1, b1)

                            r2, g2, b2 = p2_img.getpixel((px, py))[:3] if p2_img else (0, 0, 0)
                            pix2 = pack_9bit_pixel(r2, g2, b2)

                            packed_val = pack_3frames_to_signal(pix0, pix1, pix2)
                            filters.append({
                                "index": f_idx_counter, "name": sig_name, "type": sig_type,
                                "quality": sig_quality, "comparator": "=", "count": packed_val
                            })
                            f_idx_counter += 1

                    sections = _build_cc_sections(filters)

                    if fill_all_rows:
                        c = u // Hs
                        rem = u % Hs
                        r = rem if (c % 2 == 0) else (Hs - 1 - rem)
                        row_y = stripe_rows[r] if r < len(stripe_rows) else stripe_rows[0]
                        y_pos = float(row_y + 0.5)
                    else:
                        c = u
                        row_y = stripe_rows[0]
                        y_pos = y_stripe

                    unit_configs = [
                        ("a1", "arithmetic-combinator", 2.0, DIR_WEST, _arith_each(">>", 18)),
                        ("d0", "decider-combinator",    2.0, DIR_WEST, _make_decider_f(f0_idx)),
                        ("a4", "arithmetic-combinator", 2.0, DIR_WEST, _arith_each(">>", 9)),
                        ("d1", "decider-combinator",    2.0, DIR_WEST, _make_decider_f(f1_idx)),
                        ("a6", "arithmetic-combinator", 2.0, DIR_WEST, _arith_each("*", 1)),
                        ("d2", "decider-combinator",    2.0, DIR_WEST, _make_decider_f(f2_idx)),
                        ("cc", "constant-combinator",   1.0, DIR_NORTH, {"sections": {"sections": sections}}),
                    ]

                    row_subs = [sb for sb in sub_list if sb["ty"] <= y_pos < sb["ty"] + 2.0]
                    placed_ids = {}
                    cur_x = cur_x_row_A[row_y]

                    for name, ent_type, w, ent_dir, ent_cb in unit_configs:
                        cid = entity_id; entity_id += 1
                        placed_ids[name] = cid

                        while True:
                            collides = False
                            for sb in row_subs:
                                st = sb["tx"]
                                en = sb["tx"] + 2.0
                                if max(st, cur_x) < min(en, cur_x + w) - 0.001:
                                    collides = True
                                    cur_x = en
                                    break
                            if not collides:
                                break

                        center_x = cur_x + w / 2.0
                        cur_x += w

                        placed_pos_map[cid] = {"x": center_x, "y": y_pos, "name": ent_type}
                        entities.append({
                            "entity_number": cid, "name": ent_type,
                            "position": {"x": center_x, "y": y_pos},
                            "direction": ent_dir, "control_behavior": ent_cb
                        })

                    cur_x_row_A[row_y] = cur_x

                    a1_id = placed_ids["a1"]
                    d0_id = placed_ids["d0"]
                    a4_id = placed_ids["a4"]
                    d1_id = placed_ids["d1"]
                    a6_id = placed_ids["a6"]
                    d2_id = placed_ids["d2"]
                    cc_id = placed_ids["cc"]

                    _add_w(a1_id, COMB_IN_GREEN, d0_id, COMB_OUT_GREEN)
                    _add_w(a4_id, COMB_IN_GREEN, d1_id, COMB_OUT_GREEN)
                    _add_w(a6_id, COMB_IN_GREEN, d2_id, COMB_OUT_GREEN)

                    _add_w(a1_id, COMB_OUT_GREEN, a4_id, COMB_OUT_GREEN)
                    _add_w(a4_id, COMB_OUT_GREEN, a6_id, COMB_OUT_GREEN)

                    _add_w(cc_id, WIRE_GREEN, d2_id, COMB_IN_GREEN)
                    _add_w(d2_id, COMB_IN_GREEN, d1_id, COMB_IN_GREEN)
                    _add_w(d1_id, COMB_IN_GREEN, d0_id, COMB_IN_GREEN)

                    _add_w(d0_id, COMB_IN_RED, d1_id, COMB_IN_RED)
                    _add_w(d1_id, COMB_IN_RED, d2_id, COMB_IN_RED)
                    stripe_all_deciders_A[s].extend([d0_id, d1_id, d2_id])

                    if u == pack_start:
                        stripe_first_deciders_A[s] = d0_id

                    if u == pack_start and s in stripe_decoder_inputs_A:
                        dec_pin = stripe_decoder_inputs_A[s]
                        _add_w(a1_id, COMB_OUT_GREEN, dec_pin, COMB_IN_GREEN)

                    unit_entry = {
                        "u": u, "row_y": row_y,
                        "a1": a1_id, "d0": d0_id,
                        "a4": a4_id, "d1": d1_id,
                        "a6": a6_id, "d2": d2_id,
                        "cc": cc_id
                    }
                    col_units_A.setdefault(c, []).append(unit_entry)

                for c_idx, u_list in col_units_A.items():
                    u_list_sorted = sorted(u_list, key=lambda it: it["row_y"])
                    for i in range(len(u_list_sorted) - 1):
                        u_curr = u_list_sorted[i]
                        u_next = u_list_sorted[i + 1]
                        _add_w(u_curr["d0"], COMB_IN_RED, u_next["d0"], COMB_IN_RED)
                        _add_w(u_curr["a1"], COMB_OUT_GREEN, u_next["a1"], COMB_OUT_GREEN)

                all_units_A = [u for u_list in col_units_A.values() for u in u_list]
                row_units_A: Dict[int, List[Dict[str, Any]]] = {}
                for u in all_units_A:
                    row_units_A.setdefault(u["row_y"], []).append(u)

                for ry, r_list in row_units_A.items():
                    r_list_sorted = sorted(r_list, key=lambda it: placed_pos_map[it["a1"]]["x"])
                    for i in range(len(r_list_sorted) - 1):
                        u_curr = r_list_sorted[i]
                        u_next = r_list_sorted[i + 1]

                        greens_curr = [u_curr["a1"], u_curr["a4"], u_curr["a6"]]
                        greens_next = [u_next["a1"], u_next["a4"], u_next["a6"]]
                        pairs_g = [(g1, g2) for g1 in greens_curr for g2 in greens_next if g1 in placed_pos_map and g2 in placed_pos_map]
                        if pairs_g:
                            best_g = min(pairs_g, key=lambda pair: math.hypot(placed_pos_map[pair[0]]["x"] - placed_pos_map[pair[1]]["x"],
                                                                              placed_pos_map[pair[0]]["y"] - placed_pos_map[pair[1]]["y"]))
                            _add_w(best_g[0], COMB_OUT_GREEN, best_g[1], COMB_OUT_GREEN)

                        decs_curr = [u_curr["d0"], u_curr["d1"], u_curr["d2"]]
                        decs_next = [u_next["d0"], u_next["d1"], u_next["d2"]]
                        pairs_r = [(d1, d2) for d1 in decs_curr for d2 in decs_next if d1 in placed_pos_map and d2 in placed_pos_map]
                        if pairs_r:
                            best_r = min(pairs_r, key=lambda pair: math.hypot(placed_pos_map[pair[0]]["x"] - placed_pos_map[pair[1]]["x"],
                                                                              placed_pos_map[pair[0]]["y"] - placed_pos_map[pair[1]]["y"]))
                            _add_w(best_r[0], COMB_IN_RED, best_r[1], COMB_IN_RED)

                all_cols_A = sorted(col_units_A.keys())
                for idx in range(len(all_cols_A) - 1):
                    c_prev = all_cols_A[idx]
                    c_curr = all_cols_A[idx + 1]
                    decs_prev = [it[d] for it in col_units_A[c_prev] for d in ["d0", "d1", "d2"]]
                    decs_curr = [it[d] for it in col_units_A[c_curr] for d in ["d0", "d1", "d2"]]
                    pairs_r = [(d1, d2) for d1 in decs_prev for d2 in decs_curr if d1 in placed_pos_map and d2 in placed_pos_map]
                    if pairs_r:
                        best_r = min(pairs_r, key=lambda pair: math.hypot(placed_pos_map[pair[0]]["x"] - placed_pos_map[pair[1]]["x"],
                                                                          placed_pos_map[pair[0]]["y"] - placed_pos_map[pair[1]]["y"]))
                        _add_w(best_r[0], COMB_IN_RED, best_r[1], COMB_IN_RED)

                    greens_prev = [it[g] for it in col_units_A[c_prev] for g in ["a1", "a4", "a6"]]
                    greens_curr = [it[g] for it in col_units_A[c_curr] for g in ["a1", "a4", "a6"]]
                    pairs_g = [(g1, g2) for g1 in greens_prev for g2 in greens_curr if g1 in placed_pos_map and g2 in placed_pos_map]
                    if pairs_g:
                        best_g = min(pairs_g, key=lambda pair: math.hypot(placed_pos_map[pair[0]]["x"] - placed_pos_map[pair[1]]["x"],
                                                                          placed_pos_map[pair[0]]["y"] - placed_pos_map[pair[1]]["y"]))
                        _add_w(best_g[0], COMB_OUT_GREEN, best_g[1], COMB_OUT_GREEN)

            # ── 5.2. SOL BANKA (Bank B - Yatay) ──
            if has_bank_B:
                if fill_all_rows:
                    stripe_rows = _get_stripe_rows_v2(s, rows_per_stripe, ye - ys)
                else:
                    stripe_rows = [int(y_stripe)]

                if not stripe_rows:
                    stripe_rows = [ys]

                dec_row = chosen_feed_idx.get(s, ys)
                y_dec = float(dec_row + 0.5)
                Hs = max(1, len(stripe_rows))

                if include_monitor and s in stripe_feed_lamps_B:
                    dec_in_B, _, entity_id, last_dec_x_B = _build_color_decoder(
                        entities, wires, x_dec_end_B, y_dec, stripe_feed_lamps_B[s], entity_id,
                        is_left=True, compact=compact_rom, substations_list=sub_list,
                        placed_pos_map=placed_pos_map
                    )
                    stripe_decoder_inputs_B[s] = dec_in_B
                    base_x_rom_B = last_dec_x_B
                else:
                    base_x_rom_B = x_rom_start_B

                w_block_B = w_left if is_both else width

                cur_x_row_B: Dict[int, float] = {ry: base_x_rom_B for ry in stripe_rows}
                col_units_B: Dict[int, List[Dict[str, Any]]] = {}

                for u in range(pack_start, pack_end):
                    f0_idx = u * FRAMES_PER_PACK + 0
                    f1_idx = u * FRAMES_PER_PACK + 1
                    f2_idx = u * FRAMES_PER_PACK + 2

                    img0 = frames[f0_idx] if f0_idx < total_frames else None
                    img1 = frames[f1_idx] if f1_idx < total_frames else None
                    img2 = frames[f2_idx] if f2_idx < total_frames else None

                    p0_img = (img0 if isinstance(img0, Image.Image) else _bytes_to_image(img0)) if img0 else None
                    p1_img = (img1 if isinstance(img1, Image.Image) else _bytes_to_image(img1)) if img1 else p0_img
                    p2_img = (img2 if isinstance(img2, Image.Image) else _bytes_to_image(img2)) if img2 else p1_img

                    filters = []
                    f_idx_counter = 1
                    for py in range(ys, ye):
                        for px in range(0, w_block_B):
                            if (px, py) in occupied_lamp_tiles:
                                continue
                            l_idx = (py - ys) * w_block_B + px
                            sig_name, sig_type, sig_quality = get_signal_for_pixel(l_idx)

                            r0, g0, b0 = p0_img.getpixel((px, py))[:3] if p0_img else (0, 0, 0)
                            pix0 = pack_9bit_pixel(r0, g0, b0)

                            r1, g1, b1 = p1_img.getpixel((px, py))[:3] if p1_img else (0, 0, 0)
                            pix1 = pack_9bit_pixel(r1, g1, b1)

                            r2, g2, b2 = p2_img.getpixel((px, py))[:3] if p2_img else (0, 0, 0)
                            pix2 = pack_9bit_pixel(r2, g2, b2)

                            packed_val = pack_3frames_to_signal(pix0, pix1, pix2)
                            filters.append({
                                "index": f_idx_counter, "name": sig_name, "type": sig_type,
                                "quality": sig_quality, "comparator": "=", "count": packed_val
                            })
                            f_idx_counter += 1

                    sections = _build_cc_sections(filters)

                    if fill_all_rows:
                        c = u // Hs
                        rem = u % Hs
                        r = rem if (c % 2 == 0) else (Hs - 1 - rem)
                        row_y = stripe_rows[r] if r < len(stripe_rows) else stripe_rows[0]
                        y_pos = float(row_y + 0.5)
                    else:
                        c = u
                        row_y = stripe_rows[0]
                        y_pos = y_stripe

                    unit_configs_B = [
                        ("a1", "arithmetic-combinator", 2.0, DIR_EAST, _arith_each(">>", 18)),
                        ("d0", "decider-combinator",    2.0, DIR_EAST, _make_decider_f(f0_idx)),
                        ("a4", "arithmetic-combinator", 2.0, DIR_EAST, _arith_each(">>", 9)),
                        ("d1", "decider-combinator",    2.0, DIR_EAST, _make_decider_f(f1_idx)),
                        ("a6", "arithmetic-combinator", 2.0, DIR_EAST, _arith_each("*", 1)),
                        ("d2", "decider-combinator",    2.0, DIR_EAST, _make_decider_f(f2_idx)),
                        ("cc", "constant-combinator",   1.0, DIR_NORTH, {"sections": {"sections": sections}}),
                    ]

                    row_subs = [sb for sb in sub_list if sb["ty"] <= y_pos < sb["ty"] + 2.0]
                    placed_ids_B = {}
                    cur_x = cur_x_row_B[row_y]

                    for name, ent_type, w, ent_dir, ent_cb in unit_configs_B:
                        cid = entity_id; entity_id += 1
                        placed_ids_B[name] = cid

                        while True:
                            collides = False
                            for sb in row_subs:
                                st = sb["tx"]
                                en = sb["tx"] + 2.0
                                if max(st, cur_x - w) < min(en, cur_x) - 0.001:
                                    collides = True
                                    cur_x = st
                                    break
                            if not collides:
                                break

                        center_x = cur_x - w / 2.0
                        cur_x -= w

                        placed_pos_map[cid] = {"x": center_x, "y": y_pos, "name": ent_type}
                        entities.append({
                            "entity_number": cid, "name": ent_type,
                            "position": {"x": center_x, "y": y_pos},
                            "direction": ent_dir, "control_behavior": ent_cb
                        })

                    cur_x_row_B[row_y] = cur_x

                    a1_id = placed_ids_B["a1"]
                    d0_id = placed_ids_B["d0"]
                    a4_id = placed_ids_B["a4"]
                    d1_id = placed_ids_B["d1"]
                    a6_id = placed_ids_B["a6"]
                    d2_id = placed_ids_B["d2"]
                    cc_id = placed_ids_B["cc"]

                    _add_w(a1_id, COMB_IN_GREEN, d0_id, COMB_OUT_GREEN)
                    _add_w(a4_id, COMB_IN_GREEN, d1_id, COMB_OUT_GREEN)
                    _add_w(a6_id, COMB_IN_GREEN, d2_id, COMB_OUT_GREEN)

                    _add_w(a1_id, COMB_OUT_GREEN, a4_id, COMB_OUT_GREEN)
                    _add_w(a4_id, COMB_OUT_GREEN, a6_id, COMB_OUT_GREEN)

                    _add_w(cc_id, WIRE_GREEN, d2_id, COMB_IN_GREEN)
                    _add_w(d2_id, COMB_IN_GREEN, d1_id, COMB_IN_GREEN)
                    _add_w(d1_id, COMB_IN_GREEN, d0_id, COMB_IN_GREEN)

                    _add_w(d0_id, COMB_IN_RED, d1_id, COMB_IN_RED)
                    _add_w(d1_id, COMB_IN_RED, d2_id, COMB_IN_RED)
                    stripe_all_deciders_B[s].extend([d0_id, d1_id, d2_id])

                    if u == pack_start:
                        stripe_first_deciders_B[s] = d0_id

                    if u == pack_start and s in stripe_decoder_inputs_B:
                        dec_pin = stripe_decoder_inputs_B[s]
                        _add_w(a1_id, COMB_OUT_GREEN, dec_pin, COMB_IN_GREEN)

                    unit_entry_B = {
                        "u": u, "row_y": row_y,
                        "a1": a1_id, "d0": d0_id,
                        "a4": a4_id, "d1": d1_id,
                        "a6": a6_id, "d2": d2_id,
                        "cc": cc_id
                    }
                    col_units_B.setdefault(c, []).append(unit_entry_B)

                for c_idx, u_list in col_units_B.items():
                    u_list_sorted = sorted(u_list, key=lambda it: it["row_y"])
                    for i in range(len(u_list_sorted) - 1):
                        u_curr = u_list_sorted[i]
                        u_next = u_list_sorted[i + 1]
                        _add_w(u_curr["d0"], COMB_IN_RED, u_next["d0"], COMB_IN_RED)
                        _add_w(u_curr["a1"], COMB_OUT_GREEN, u_next["a1"], COMB_OUT_GREEN)

                all_units_B = [u for u_list in col_units_B.values() for u in u_list]
                row_units_B: Dict[int, List[Dict[str, Any]]] = {}
                for u in all_units_B:
                    row_units_B.setdefault(u["row_y"], []).append(u)

                for ry, r_list in row_units_B.items():
                    r_list_sorted = sorted(r_list, key=lambda it: placed_pos_map[it["a1"]]["x"])
                    for i in range(len(r_list_sorted) - 1):
                        u_curr = r_list_sorted[i]
                        u_next = r_list_sorted[i + 1]

                        greens_curr = [u_curr["a1"], u_curr["a4"], u_curr["a6"]]
                        greens_next = [u_next["a1"], u_next["a4"], u_next["a6"]]
                        pairs_g = [(g1, g2) for g1 in greens_curr for g2 in greens_next if g1 in placed_pos_map and g2 in placed_pos_map]
                        if pairs_g:
                            best_g = min(pairs_g, key=lambda pair: math.hypot(placed_pos_map[pair[0]]["x"] - placed_pos_map[pair[1]]["x"],
                                                                              placed_pos_map[pair[0]]["y"] - placed_pos_map[pair[1]]["y"]))
                            _add_w(best_g[0], COMB_OUT_GREEN, best_g[1], COMB_OUT_GREEN)

                        decs_curr = [u_curr["d0"], u_curr["d1"], u_curr["d2"]]
                        decs_next = [u_next["d0"], u_next["d1"], u_next["d2"]]
                        pairs_r = [(d1, d2) for d1 in decs_curr for d2 in decs_next if d1 in placed_pos_map and d2 in placed_pos_map]
                        if pairs_r:
                            best_r = min(pairs_r, key=lambda pair: math.hypot(placed_pos_map[pair[0]]["x"] - placed_pos_map[pair[1]]["x"],
                                                                              placed_pos_map[pair[0]]["y"] - placed_pos_map[pair[1]]["y"]))
                            _add_w(best_r[0], COMB_IN_RED, best_r[1], COMB_IN_RED)

                all_cols_B = sorted(col_units_B.keys())
                for idx in range(len(all_cols_B) - 1):
                    c_prev = all_cols_B[idx]
                    c_curr = all_cols_B[idx + 1]
                    decs_prev = [it[d] for it in col_units_B[c_prev] for d in ["d0", "d1", "d2"]]
                    decs_curr = [it[d] for it in col_units_B[c_curr] for d in ["d0", "d1", "d2"]]
                    pairs_r = [(d1, d2) for d1 in decs_prev for d2 in decs_curr if d1 in placed_pos_map and d2 in placed_pos_map]
                    if pairs_r:
                        best_r = min(pairs_r, key=lambda pair: math.hypot(placed_pos_map[pair[0]]["x"] - placed_pos_map[pair[1]]["x"],
                                                                          placed_pos_map[pair[0]]["y"] - placed_pos_map[pair[1]]["y"]))
                        _add_w(best_r[0], COMB_IN_RED, best_r[1], COMB_IN_RED)

                    greens_prev = [it[g] for it in col_units_B[c_prev] for g in ["a1", "a4", "a6"]]
                    greens_curr = [it[g] for it in col_units_B[c_curr] for g in ["a1", "a4", "a6"]]
                    pairs_g = [(g1, g2) for g1 in greens_prev for g2 in greens_curr if g1 in placed_pos_map and g2 in placed_pos_map]
                    if pairs_g:
                        best_g = min(pairs_g, key=lambda pair: math.hypot(placed_pos_map[pair[0]]["x"] - placed_pos_map[pair[1]]["x"],
                                                                          placed_pos_map[pair[0]]["y"] - placed_pos_map[pair[1]]["y"]))
                        _add_w(best_g[0], COMB_OUT_GREEN, best_g[1], COMB_OUT_GREEN)

        # ──────────────────────────────────────────────────────────────────────
        # B) DİKEY MODLAR
        # ──────────────────────────────────────────────────────────────────────
        else:
            xs = s * cols_per_stripe
            xe = min(width, (s + 1) * cols_per_stripe)
            feed_col = chosen_feed_idx.get(s, xs)
            x_dec = float(feed_col + 0.5)

            # ── 5.1. ÜST BANKA (Bank A - Dikey) ──
            if has_bank_A:
                y_dec_start_A = 0.0 if compact_rom else -2.0

                if include_monitor and s in stripe_feed_lamps_A:
                    dec_in_A, _, entity_id, last_dec_y_A = _build_color_decoder_vertical(
                        entities, wires, x_dec, y_dec_start_A, stripe_feed_lamps_A[s], entity_id,
                        is_bottom=False, compact=compact_rom, substations_list=sub_list,
                        placed_pos_map=placed_pos_map
                    )
                    stripe_decoder_inputs_A[s] = dec_in_A
                    base_y_rom_A = last_dec_y_A
                else:
                    base_y_rom_A = y_dec_start_A - 24.0

                if fill_all_rows:
                    stripe_cols = list(range(xs, xe))
                else:
                    stripe_cols = [feed_col]

                if not stripe_cols:
                    stripe_cols = [xs]

                Ws = max(1, len(stripe_cols))
                cur_y_col_A: Dict[int, float] = {cx: base_y_rom_A for cx in stripe_cols}
                col_units_A: Dict[int, List[Dict[str, Any]]] = {}

                h_block_A = h_top if is_both else height

                for u in range(pack_start, pack_end):
                    f0_idx = u * FRAMES_PER_PACK + 0
                    f1_idx = u * FRAMES_PER_PACK + 1
                    f2_idx = u * FRAMES_PER_PACK + 2

                    img0 = frames[f0_idx] if f0_idx < total_frames else None
                    img1 = frames[f1_idx] if f1_idx < total_frames else None
                    img2 = frames[f2_idx] if f2_idx < total_frames else None

                    p0_img = (img0 if isinstance(img0, Image.Image) else _bytes_to_image(img0)) if img0 else None
                    p1_img = (img1 if isinstance(img1, Image.Image) else _bytes_to_image(img1)) if img1 else p0_img
                    p2_img = (img2 if isinstance(img2, Image.Image) else _bytes_to_image(img2)) if img2 else p1_img

                    filters = []
                    f_idx_counter = 1
                    for px in range(xs, xe):
                        for py in range(0, h_block_A):
                            if (px, py) in occupied_lamp_tiles:
                                continue
                            l_idx = (px - xs) * h_block_A + py
                            sig_name, sig_type, sig_quality = get_signal_for_pixel(l_idx)

                            r0, g0, b0 = p0_img.getpixel((px, py))[:3] if p0_img else (0, 0, 0)
                            pix0 = pack_9bit_pixel(r0, g0, b0)

                            r1, g1, b1 = p1_img.getpixel((px, py))[:3] if p1_img else (0, 0, 0)
                            pix1 = pack_9bit_pixel(r1, g1, b1)

                            r2, g2, b2 = p2_img.getpixel((px, py))[:3] if p2_img else (0, 0, 0)
                            pix2 = pack_9bit_pixel(r2, g2, b2)

                            packed_val = pack_3frames_to_signal(pix0, pix1, pix2)
                            filters.append({
                                "index": f_idx_counter, "name": sig_name, "type": sig_type,
                                "quality": sig_quality, "comparator": "=", "count": packed_val
                            })
                            f_idx_counter += 1

                    sections = _build_cc_sections(filters)

                    if fill_all_rows:
                        c = u // Ws
                        rem = u % Ws
                        col = rem if (c % 2 == 0) else (Ws - 1 - rem)
                        col_x = stripe_cols[col] if col < len(stripe_cols) else stripe_cols[0]
                        x_pos = float(col_x + 0.5)
                    else:
                        c = u
                        col_x = stripe_cols[0]
                        x_pos = float(col_x + 0.5)

                    unit_configs = [
                        ("a1", "arithmetic-combinator", 2.0, DIR_SOUTH, _arith_each(">>", 18)),
                        ("d0", "decider-combinator",    2.0, DIR_SOUTH, _make_decider_f(f0_idx)),
                        ("a4", "arithmetic-combinator", 2.0, DIR_SOUTH, _arith_each(">>", 9)),
                        ("d1", "decider-combinator",    2.0, DIR_SOUTH, _make_decider_f(f1_idx)),
                        ("a6", "arithmetic-combinator", 2.0, DIR_SOUTH, _arith_each("*", 1)),
                        ("d2", "decider-combinator",    2.0, DIR_SOUTH, _make_decider_f(f2_idx)),
                        ("cc", "constant-combinator",   1.0, DIR_NORTH, {"sections": {"sections": sections}}),
                    ]

                    col_subs = [sb for sb in sub_list if sb["tx"] <= x_pos < sb["tx"] + 2.0]
                    placed_ids = {}
                    cur_y = cur_y_col_A[col_x]

                    for name, ent_type, h_dim, ent_dir, ent_cb in unit_configs:
                        cid = entity_id; entity_id += 1
                        placed_ids[name] = cid

                        while True:
                            collides = False
                            for sb in col_subs:
                                st = sb["ty"]
                                en = sb["ty"] + 2.0
                                if max(st, cur_y - h_dim) < min(en, cur_y) - 0.001:
                                    collides = True
                                    cur_y = st
                                    break
                            if not collides:
                                break

                        center_y = cur_y - h_dim / 2.0
                        cur_y -= h_dim

                        placed_pos_map[cid] = {"x": x_pos, "y": center_y, "name": ent_type}
                        entities.append({
                            "entity_number": cid, "name": ent_type,
                            "position": {"x": x_pos, "y": center_y},
                            "direction": ent_dir, "control_behavior": ent_cb
                        })

                    cur_y_col_A[col_x] = cur_y

                    a1_id = placed_ids["a1"]
                    d0_id = placed_ids["d0"]
                    a4_id = placed_ids["a4"]
                    d1_id = placed_ids["d1"]
                    a6_id = placed_ids["a6"]
                    d2_id = placed_ids["d2"]
                    cc_id = placed_ids["cc"]

                    _add_w(a1_id, COMB_IN_GREEN, d0_id, COMB_OUT_GREEN)
                    _add_w(a4_id, COMB_IN_GREEN, d1_id, COMB_OUT_GREEN)
                    _add_w(a6_id, COMB_IN_GREEN, d2_id, COMB_OUT_GREEN)

                    _add_w(a1_id, COMB_OUT_GREEN, a4_id, COMB_OUT_GREEN)
                    _add_w(a4_id, COMB_OUT_GREEN, a6_id, COMB_OUT_GREEN)

                    _add_w(cc_id, WIRE_GREEN, d2_id, COMB_IN_GREEN)
                    _add_w(d2_id, COMB_IN_GREEN, d1_id, COMB_IN_GREEN)
                    _add_w(d1_id, COMB_IN_GREEN, d0_id, COMB_IN_GREEN)

                    _add_w(d0_id, COMB_IN_RED, d1_id, COMB_IN_RED)
                    _add_w(d1_id, COMB_IN_RED, d2_id, COMB_IN_RED)
                    stripe_all_deciders_A[s].extend([d0_id, d1_id, d2_id])

                    if u == pack_start:
                        stripe_first_deciders_A[s] = d0_id

                    if u == pack_start and s in stripe_decoder_inputs_A:
                        dec_pin = stripe_decoder_inputs_A[s]
                        _add_w(a1_id, COMB_OUT_GREEN, dec_pin, COMB_IN_GREEN)

                    unit_entry = {
                        "u": u, "col_x": col_x,
                        "a1": a1_id, "d0": d0_id,
                        "a4": a4_id, "d1": d1_id,
                        "a6": a6_id, "d2": d2_id,
                        "cc": cc_id
                    }
                    col_units_A.setdefault(col_x, []).append(unit_entry)

                for cx_idx, u_list in col_units_A.items():
                    u_list_sorted = sorted(u_list, key=lambda it: it["u"])
                    for i in range(len(u_list_sorted) - 1):
                        u_curr = u_list_sorted[i]
                        u_next = u_list_sorted[i + 1]
                        _add_w(u_curr["d0"], COMB_IN_RED, u_next["d0"], COMB_IN_RED)
                        _add_w(u_curr["a1"], COMB_OUT_GREEN, u_next["a1"], COMB_OUT_GREEN)

                all_cols_A = sorted(col_units_A.keys())
                for idx in range(len(all_cols_A) - 1):
                    c_prev = all_cols_A[idx]
                    c_curr = all_cols_A[idx + 1]
                    decs_prev = [it[d] for it in col_units_A[c_prev] for d in ["d0", "d1", "d2"]]
                    decs_curr = [it[d] for it in col_units_A[c_curr] for d in ["d0", "d1", "d2"]]
                    pairs_r = [(d1, d2) for d1 in decs_prev for d2 in decs_curr if d1 in placed_pos_map and d2 in placed_pos_map]
                    if pairs_r:
                        best_r = min(pairs_r, key=lambda pair: math.hypot(placed_pos_map[pair[0]]["x"] - placed_pos_map[pair[1]]["x"],
                                                                          placed_pos_map[pair[0]]["y"] - placed_pos_map[pair[1]]["y"]))
                        _add_w(best_r[0], COMB_IN_RED, best_r[1], COMB_IN_RED)

                    greens_prev = [it[g] for it in col_units_A[c_prev] for g in ["a1", "a4", "a6"]]
                    greens_curr = [it[g] for it in col_units_A[c_curr] for g in ["a1", "a4", "a6"]]
                    pairs_g = [(g1, g2) for g1 in greens_prev for g2 in greens_curr if g1 in placed_pos_map and g2 in placed_pos_map]
                    if pairs_g:
                        best_g = min(pairs_g, key=lambda pair: math.hypot(placed_pos_map[pair[0]]["x"] - placed_pos_map[pair[1]]["x"],
                                                                          placed_pos_map[pair[0]]["y"] - placed_pos_map[pair[1]]["y"]))
                        _add_w(best_g[0], COMB_OUT_GREEN, best_g[1], COMB_OUT_GREEN)

            # ── 5.2. ALT BANKA (Bank B - Dikey) ──
            if has_bank_B:
                y_dec_start_B = float(height) if compact_rom else float(height + 2.0)

                if include_monitor and s in stripe_feed_lamps_B:
                    dec_in_B, _, entity_id, last_dec_y_B = _build_color_decoder_vertical(
                        entities, wires, x_dec, y_dec_start_B, stripe_feed_lamps_B[s], entity_id,
                        is_bottom=True, compact=compact_rom, substations_list=sub_list,
                        placed_pos_map=placed_pos_map
                    )
                    stripe_decoder_inputs_B[s] = dec_in_B
                    base_y_rom_B = last_dec_y_B
                else:
                    base_y_rom_B = y_dec_start_B + 24.0

                if fill_all_rows:
                    stripe_cols = list(range(xs, xe))
                else:
                    stripe_cols = [feed_col]

                if not stripe_cols:
                    stripe_cols = [xs]

                Ws = max(1, len(stripe_cols))
                cur_y_col_B: Dict[int, float] = {cx: base_y_rom_B for cx in stripe_cols}
                col_units_B: Dict[int, List[Dict[str, Any]]] = {}

                h_start_B = h_top if is_both else 0

                for u in range(pack_start, pack_end):
                    f0_idx = u * FRAMES_PER_PACK + 0
                    f1_idx = u * FRAMES_PER_PACK + 1
                    f2_idx = u * FRAMES_PER_PACK + 2

                    img0 = frames[f0_idx] if f0_idx < total_frames else None
                    img1 = frames[f1_idx] if f1_idx < total_frames else None
                    img2 = frames[f2_idx] if f2_idx < total_frames else None

                    p0_img = (img0 if isinstance(img0, Image.Image) else _bytes_to_image(img0)) if img0 else None
                    p1_img = (img1 if isinstance(img1, Image.Image) else _bytes_to_image(img1)) if img1 else p0_img
                    p2_img = (img2 if isinstance(img2, Image.Image) else _bytes_to_image(img2)) if img2 else p1_img

                    filters = []
                    f_idx_counter = 1
                    for px in range(xs, xe):
                        for py in range(h_start_B, height):
                            if (px, py) in occupied_lamp_tiles:
                                continue
                            l_idx = (px - xs) * (h_bottom if is_both else height) + (py - h_start_B)
                            sig_name, sig_type, sig_quality = get_signal_for_pixel(l_idx)

                            r0, g0, b0 = p0_img.getpixel((px, py))[:3] if p0_img else (0, 0, 0)
                            pix0 = pack_9bit_pixel(r0, g0, b0)

                            r1, g1, b1 = p1_img.getpixel((px, py))[:3] if p1_img else (0, 0, 0)
                            pix1 = pack_9bit_pixel(r1, g1, b1)

                            r2, g2, b2 = p2_img.getpixel((px, py))[:3] if p2_img else (0, 0, 0)
                            pix2 = pack_9bit_pixel(r2, g2, b2)

                            packed_val = pack_3frames_to_signal(pix0, pix1, pix2)
                            filters.append({
                                "index": f_idx_counter, "name": sig_name, "type": sig_type,
                                "quality": sig_quality, "comparator": "=", "count": packed_val
                            })
                            f_idx_counter += 1

                    sections = _build_cc_sections(filters)

                    if fill_all_rows:
                        c = u // Ws
                        rem = u % Ws
                        col = rem if (c % 2 == 0) else (Ws - 1 - rem)
                        col_x = stripe_cols[col] if col < len(stripe_cols) else stripe_cols[0]
                        x_pos = float(col_x + 0.5)
                    else:
                        c = u
                        col_x = stripe_cols[0]
                        x_pos = float(col_x + 0.5)

                    unit_configs_B = [
                        ("a1", "arithmetic-combinator", 2.0, DIR_NORTH, _arith_each(">>", 18)),
                        ("d0", "decider-combinator",    2.0, DIR_NORTH, _make_decider_f(f0_idx)),
                        ("a4", "arithmetic-combinator", 2.0, DIR_NORTH, _arith_each(">>", 9)),
                        ("d1", "decider-combinator",    2.0, DIR_NORTH, _make_decider_f(f1_idx)),
                        ("a6", "arithmetic-combinator", 2.0, DIR_NORTH, _arith_each("*", 1)),
                        ("d2", "decider-combinator",    2.0, DIR_NORTH, _make_decider_f(f2_idx)),
                        ("cc", "constant-combinator",   1.0, DIR_NORTH, {"sections": {"sections": sections}}),
                    ]

                    col_subs = [sb for sb in sub_list if sb["tx"] <= x_pos < sb["tx"] + 2.0]
                    placed_ids_B = {}
                    cur_y = cur_y_col_B[col_x]

                    for name, ent_type, h_dim, ent_dir, ent_cb in unit_configs_B:
                        cid = entity_id; entity_id += 1
                        placed_ids_B[name] = cid

                        while True:
                            collides = False
                            for sb in col_subs:
                                st = sb["ty"]
                                en = sb["ty"] + 2.0
                                if max(st, cur_y) < min(en, cur_y + h_dim) - 0.001:
                                    collides = True
                                    cur_y = en
                                    break
                            if not collides:
                                break

                        center_y = cur_y + h_dim / 2.0
                        cur_y += h_dim

                        placed_pos_map[cid] = {"x": x_pos, "y": center_y, "name": ent_type}
                        entities.append({
                            "entity_number": cid, "name": ent_type,
                            "position": {"x": x_pos, "y": center_y},
                            "direction": ent_dir, "control_behavior": ent_cb
                        })

                    cur_y_col_B[col_x] = cur_y

                    a1_id = placed_ids_B["a1"]
                    d0_id = placed_ids_B["d0"]
                    a4_id = placed_ids_B["a4"]
                    d1_id = placed_ids_B["d1"]
                    a6_id = placed_ids_B["a6"]
                    d2_id = placed_ids_B["d2"]
                    cc_id = placed_ids_B["cc"]

                    _add_w(a1_id, COMB_IN_GREEN, d0_id, COMB_OUT_GREEN)
                    _add_w(a4_id, COMB_IN_GREEN, d1_id, COMB_OUT_GREEN)
                    _add_w(a6_id, COMB_IN_GREEN, d2_id, COMB_OUT_GREEN)

                    _add_w(a1_id, COMB_OUT_GREEN, a4_id, COMB_OUT_GREEN)
                    _add_w(a4_id, COMB_OUT_GREEN, a6_id, COMB_OUT_GREEN)

                    _add_w(cc_id, WIRE_GREEN, d2_id, COMB_IN_GREEN)
                    _add_w(d2_id, COMB_IN_GREEN, d1_id, COMB_IN_GREEN)
                    _add_w(d1_id, COMB_IN_GREEN, d0_id, COMB_IN_GREEN)

                    _add_w(d0_id, COMB_IN_RED, d1_id, COMB_IN_RED)
                    _add_w(d1_id, COMB_IN_RED, d2_id, COMB_IN_RED)
                    stripe_all_deciders_B[s].extend([d0_id, d1_id, d2_id])

                    if u == pack_start:
                        stripe_first_deciders_B[s] = d0_id

                    if u == pack_start and s in stripe_decoder_inputs_B:
                        dec_pin = stripe_decoder_inputs_B[s]
                        _add_w(a1_id, COMB_OUT_GREEN, dec_pin, COMB_IN_GREEN)

                    unit_entry_B = {
                        "u": u, "col_x": col_x,
                        "a1": a1_id, "d0": d0_id,
                        "a4": a4_id, "d1": d1_id,
                        "a6": a6_id, "d2": d2_id,
                        "cc": cc_id
                    }
                    col_units_B.setdefault(col_x, []).append(unit_entry_B)

                for cx_idx, u_list in col_units_B.items():
                    u_list_sorted = sorted(u_list, key=lambda it: it["u"])
                    for i in range(len(u_list_sorted) - 1):
                        u_curr = u_list_sorted[i]
                        u_next = u_list_sorted[i + 1]
                        _add_w(u_curr["d0"], COMB_IN_RED, u_next["d0"], COMB_IN_RED)
                        _add_w(u_curr["a1"], COMB_OUT_GREEN, u_next["a1"], COMB_OUT_GREEN)

                all_cols_B = sorted(col_units_B.keys())
                for idx in range(len(all_cols_B) - 1):
                    c_prev = all_cols_B[idx]
                    c_curr = all_cols_B[idx + 1]
                    decs_prev = [it[d] for it in col_units_B[c_prev] for d in ["d0", "d1", "d2"]]
                    decs_curr = [it[d] for it in col_units_B[c_curr] for d in ["d0", "d1", "d2"]]
                    pairs_r = [(d1, d2) for d1 in decs_prev for d2 in decs_curr if d1 in placed_pos_map and d2 in placed_pos_map]
                    if pairs_r:
                        best_r = min(pairs_r, key=lambda pair: math.hypot(placed_pos_map[pair[0]]["x"] - placed_pos_map[pair[1]]["x"],
                                                                          placed_pos_map[pair[0]]["y"] - placed_pos_map[pair[1]]["y"]))
                        _add_w(best_r[0], COMB_IN_RED, best_r[1], COMB_IN_RED)

                    greens_prev = [it[g] for it in col_units_B[c_prev] for g in ["a1", "a4", "a6"]]
                    greens_curr = [it[g] for it in col_units_B[c_curr] for g in ["a1", "a4", "a6"]]
                    pairs_g = [(g1, g2) for g1 in greens_prev for g2 in greens_curr if g1 in placed_pos_map and g2 in placed_pos_map]
                    if pairs_g:
                        best_g = min(pairs_g, key=lambda pair: math.hypot(placed_pos_map[pair[0]]["x"] - placed_pos_map[pair[1]]["x"],
                                                                          placed_pos_map[pair[0]]["y"] - placed_pos_map[pair[1]]["y"]))
                        _add_w(best_g[0], COMB_OUT_GREEN, best_g[1], COMB_OUT_GREEN)

    # 6. Merkezî Saat Devresi (SADECE PARÇA 0'DA)
    if include_clock:
        if progress_callback:
            progress_callback("Merkezî saat devresi inşa ediliyor...", 0.75)

        y_clk = -3.5

        def _build_clock(x_base: float, is_bank_b: bool) -> int:
            nonlocal entity_id
            dir_c = DIR_EAST if is_bank_b else DIR_WEST
            sign = -1.0 if is_bank_b else 1.0

            cc_clk = entity_id; entity_id += 1
            cc_x = x_base + sign * 6.0
            placed_pos_map[cc_clk] = {"x": cc_x, "y": y_clk, "name": "constant-combinator"}
            entities.append({
                "entity_number": cc_clk, "name": "constant-combinator",
                "position": {"x": cc_x, "y": y_clk},
                "control_behavior": {
                    "sections": {"sections": [{"index": 1, "filters": [
                        {"index": 1, "type": "virtual", "name": "signal-C", "quality": "normal", "comparator": "=", "count": 1}
                    ]}]}
                }
            })

            dec_clk = entity_id; entity_id += 1
            dec_x = x_base + sign * 4.0
            placed_pos_map[dec_clk] = {"x": dec_x, "y": y_clk, "name": "decider-combinator"}
            entities.append({
                "entity_number": dec_clk, "name": "decider-combinator",
                "position": {"x": dec_x, "y": y_clk}, "direction": dir_c,
                "control_behavior": {
                    "decider_conditions": {
                        "conditions": [{"first_signal": {"type": "virtual", "name": "signal-C"}, "comparator": "<", "constant": total_ticks, "first_signal_networks": {"red": False, "green": True}}],
                        "outputs": [{"signal": {"type": "virtual", "name": "signal-C"}, "copy_count_from_input": True, "networks": {"red": False, "green": True}}]
                    }
                }
            })
            _add_w(cc_clk, WIRE_GREEN, dec_clk, COMB_IN_GREEN)
            _add_w(dec_clk, COMB_OUT_GREEN, dec_clk, COMB_IN_GREEN)

            arith_sub1 = entity_id; entity_id += 1
            sub1_x = x_base + sign * 2.0
            placed_pos_map[arith_sub1] = {"x": sub1_x, "y": y_clk, "name": "arithmetic-combinator"}
            entities.append({
                "entity_number": arith_sub1, "name": "arithmetic-combinator",
                "position": {"x": sub1_x, "y": y_clk}, "direction": dir_c,
                "control_behavior": {
                    "arithmetic_conditions": {
                        "first_signal": {"type": "virtual", "name": "signal-C"},
                        "second_constant": 1, "operation": "-", "output_signal": {"type": "virtual", "name": "signal-C"}
                    }
                }
            })
            _add_w(dec_clk, COMB_OUT_GREEN, arith_sub1, COMB_IN_GREEN)

            if mult > 1:
                arith_mul = entity_id; entity_id += 1
                mul_x = x_base + sign * 0.0
                placed_pos_map[arith_mul] = {"x": mul_x, "y": y_clk, "name": "arithmetic-combinator"}
                entities.append({
                    "entity_number": arith_mul, "name": "arithmetic-combinator",
                    "position": {"x": mul_x, "y": y_clk}, "direction": dir_c,
                    "control_behavior": {
                        "arithmetic_conditions": {
                            "first_signal": {"type": "virtual", "name": "signal-C"},
                            "second_constant": mult, "operation": "*", "output_signal": {"type": "virtual", "name": "signal-C"}
                        }
                    }
                })
                _add_w(arith_sub1, COMB_OUT_GREEN, arith_mul, COMB_IN_GREEN)

                arith_div = entity_id; entity_id += 1
                div_x = x_base - sign * 2.0
                placed_pos_map[arith_div] = {"x": div_x, "y": y_clk, "name": "arithmetic-combinator"}
                entities.append({
                    "entity_number": arith_div, "name": "arithmetic-combinator",
                    "position": {"x": div_x, "y": y_clk}, "direction": dir_c,
                    "control_behavior": {
                        "arithmetic_conditions": {
                            "first_signal": {"type": "virtual", "name": "signal-C"},
                            "second_constant": div, "operation": "/", "output_signal": {"type": "virtual", "name": "signal-F"}
                        }
                    }
                })
                _add_w(arith_mul, COMB_OUT_GREEN, arith_div, COMB_IN_GREEN)
            else:
                arith_div = entity_id; entity_id += 1
                div_x = x_base + sign * 0.0
                placed_pos_map[arith_div] = {"x": div_x, "y": y_clk, "name": "arithmetic-combinator"}
                entities.append({
                    "entity_number": arith_div, "name": "arithmetic-combinator",
                    "position": {"x": div_x, "y": y_clk}, "direction": dir_c,
                    "control_behavior": {
                        "arithmetic_conditions": {
                            "first_signal": {"type": "virtual", "name": "signal-C"},
                            "second_constant": div, "operation": "/", "output_signal": {"type": "virtual", "name": "signal-F"}
                        }
                    }
                })
                _add_w(arith_sub1, COMB_OUT_GREEN, arith_div, COMB_IN_GREEN)

            return arith_div

        if is_horizontal:
            if has_bank_A:
                clk_A = _build_clock(x_rom_start_A + 4.0, is_bank_b=False)
                if stripe_first_deciders_A:
                    first_k = min(stripe_first_deciders_A.keys())
                    _add_w(clk_A, COMB_OUT_RED, stripe_first_deciders_A[first_k], COMB_IN_RED)

            if has_bank_B:
                clk_B = _build_clock(x_rom_start_B - 4.0, is_bank_b=True)
                if stripe_first_deciders_B:
                    first_k = min(stripe_first_deciders_B.keys())
                    _add_w(clk_B, COMB_OUT_RED, stripe_first_deciders_B[first_k], COMB_IN_RED)
        else:
            clk_pos_x = -4.5
            if has_bank_A:
                clk_A = _build_clock(clk_pos_x, is_bank_b=False)
                if stripe_first_deciders_A:
                    first_k = min(stripe_first_deciders_A.keys())
                    _add_w(clk_A, COMB_OUT_RED, stripe_first_deciders_A[first_k], COMB_IN_RED)

            if has_bank_B:
                clk_B = _build_clock(clk_pos_x, is_bank_b=True)
                if stripe_first_deciders_B:
                    first_k = min(stripe_first_deciders_B.keys())
                    _add_w(clk_B, COMB_OUT_RED, stripe_first_deciders_B[first_k], COMB_IN_RED)

    # 7. Şeritler arası dikey/yatay kırmızı saat zinciri
    if include_clock:
        def _connect_stripe_chain(all_decs_dict: Dict[int, List[int]], first_decs_dict: Dict[int, int]):
            s_keys = sorted(first_decs_dict.keys())
            for idx in range(len(s_keys) - 1):
                s_curr = s_keys[idx]
                s_next = s_keys[idx + 1]
                decs_curr = all_decs_dict.get(s_curr, [])
                decs_next = all_decs_dict.get(s_next, [])
                if not decs_curr or not decs_next:
                    continue

                pairs = [(d1, d2) for d1 in decs_curr for d2 in decs_next if d1 in placed_pos_map and d2 in placed_pos_map]
                if pairs:
                    best_pair = min(
                        pairs,
                        key=lambda pair: math.hypot(placed_pos_map[pair[0]]["x"] - placed_pos_map[pair[1]]["x"],
                                                    placed_pos_map[pair[0]]["y"] - placed_pos_map[pair[1]]["y"])
                    )
                    _add_w(best_pair[0], COMB_IN_RED, best_pair[1], COMB_IN_RED)

        if has_bank_A:
            _connect_stripe_chain(stripe_all_deciders_A, stripe_first_deciders_A)

        if has_bank_B:
            _connect_stripe_chain(stripe_all_deciders_B, stripe_first_deciders_B)

    # 8. Blueprint JSON Oluşturma ve Sıkıştırma
    bp_data = {
        "blueprint": {
            "item": "blueprint",
            "label": f"Factorio Screen V2 [{width}x{height}] - P{part_idx + 1}/{num_parts}",
            "description": (
                f"Factorio 2.0 27-Bit Temporal Bit-Packing Monitör\n"
                f"Çözünürlük: {width}x{height} | Hız: {fps} FPS | Mod: {rom_mode}\n"
                f"Toplam Kare: {total_frames} | Parça: {part_idx + 1}/{num_parts}"
            ),
            "version": 562954249306113,
            "entities": entities,
            "wires": wires,
            "icons": [
                {"signal": {"type": "item", "name": "small-lamp"}, "index": 1},
                {"signal": {"type": "item", "name": "constant-combinator"}, "index": 2},
                {"signal": {"type": "item", "name": "decider-combinator"}, "index": 3},
                {"signal": {"type": "item", "name": "substation"}, "index": 4},
            ]
        }
    }

    raw_json = json.dumps(bp_data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    compressed = zlib.compress(raw_json, 9)
    bp_string = "0" + base64.b64encode(compressed).decode("ascii")

    metadata = {
        "num_parts": num_parts,
        "current_part": part_idx,
        "part_idx": part_idx,
        "total_frames": total_frames,
        "total_packs": total_packs,
        "frames_per_pack": FRAMES_PER_PACK,
        "entities_count": len(entities),
        "total_entities": len(entities),
        "num_entities": len(entities),
        "total_wires": len(wires),
        "num_wires": len(wires),
        "compile_f_start": pack_start * FRAMES_PER_PACK,
        "compile_f_end": min(total_frames, pack_end * FRAMES_PER_PACK),
        "compile_p_start": pack_start,
        "compile_p_end": pack_end,
        "width": width,
        "height": height,
        "fps": fps,
        "num_stripes": num_stripes,
        "include_monitor": include_monitor,
        "include_clock": include_clock,
        "rom_mode": rom_mode,
        "compact_rom": compact_rom,
        "fill_all_rows": fill_all_rows,
    }

    if progress_callback:
        progress_callback("Blueprint başarıyla derlendi!", 1.0)

    return bp_string, metadata
