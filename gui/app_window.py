"""
Factorio 2.0 Video to Blueprint Generator GUI
=============================================
CustomTkinter ile inşa edilmiş modern, şık ve interaktif mimari & ROM dilimleme arayüzü.
- Akıllı Monitör ve ROM Konumlandırma Görselleştiricisi
- Modüler ROM Dilimleme (1-16 Parça)
- Kopyalama Kolaylığı (+1 Ortak Sütun / Hizalama ve Otomatik Kablo Bağlantı Desteği)
- Ultra Hızlı ve Düşük RAM Tüketimli Mimari
"""

import os
import sys
import threading
import time
import math
from typing import List, Optional, Tuple, Dict, Any
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

from core.video_processor import extract_video_frames, generate_procedural_demo, get_media_dimensions, get_media_info, frame_bytes_to_image
from core.circuit_engine_v3 import compile_blueprint_v3
from core.circuit_engine_v2 import compile_blueprint_v2, SIGNAL_POOL
from core.circuit_engine import compile_blueprint as compile_blueprint_v1

# Windows pano kopyalama
import subprocess

def copy_to_clipboard(text: str) -> bool:
    try:
        process = subprocess.Popen('clip', stdin=subprocess.PIPE, shell=True)
        process.communicate(text.encode('utf-8'))
        return True
    except Exception:
        return False


class FactorioVideoApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Görünüm & Tema
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.title("Factorio 2.0 Video-to-Blueprint Dönüştürücü & Modüler ROM Tasarımcısı")
        self.geometry("1240x800")
        self.minsize(1050, 720)

        # Durum Değişkenleri
        self.selected_file_path: Optional[str] = None
        self.media_orig_size: Tuple[int, int] = (16, 16)
        self.loaded_frames: List[Any] = []
        self.total_frames_count: int = 16

        # Dilimleme (Slicing) Değişkenleri
        self.num_parts: int = 2
        self.selected_part_idx: int = 0
        self.copy_convenience: bool = True

        # Blueprint Önbelleği (RAM dostu ve anlık geçişler için)
        self.part_blueprints: Dict[int, Tuple[str, Dict[str, Any]]] = {}
        self.is_compiling: bool = False
        self._load_thread: Optional[threading.Thread] = None
        self._load_cancelled: bool = False
        self._loaded_fps: Optional[int] = 5
        self.selected_engine: str = "v3"
        self.compact_rom: bool = True
        self.fill_all_rows: bool = False
        self.substation_quality: str = "legendary"

        # Canvas Etkileşim Alanları (Hitboxes for mouse click & hover)
        self._slice_hitboxes: List[Dict[str, Any]] = []

        # Arayüzü Kur
        self._create_layout()

        # Başlangıçta varsayılan demo animasyonu yükle
        self._load_demo_animation()

    def _create_layout(self):
        # 2 Sütunlu Ana Izgara: Sol (Ayarlar & Kontroller), Sağ (Mimarî Şema & Dilim Seçici)
        self.grid_columnconfigure(0, weight=0, minsize=400)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ===================================================================
        # SOL PANEL: AYARLAR VE KONTROLLER
        # ===================================================================
        self.sidebar_frame = ctk.CTkScrollableFrame(self, corner_radius=0, width=390)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.sidebar_frame.grid_columnconfigure(0, weight=1)

        # Başlık
        title_label = ctk.CTkLabel(
            self.sidebar_frame,
            text="⚡ FACTORIO 2.0\nVIDEO & ROM BUILDER",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#f39c12",
            justify="center"
        )
        title_label.pack(padx=16, pady=(16, 10))

        # --- BÖLÜM 1: DOSYA SEÇİMİ ---
        file_box = ctk.CTkFrame(self.sidebar_frame)
        file_box.pack(fill="x", padx=12, pady=5)

        ctk.CTkLabel(file_box, text="1. Video / GIF Kaynağı", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=12, pady=(8, 4))

        btn_row = ctk.CTkFrame(file_box, fg_color="transparent")
        btn_row.pack(fill="x", padx=10, pady=4)

        self.btn_select_file = ctk.CTkButton(
            btn_row,
            text="📁 Video Seç",
            command=self._on_select_file,
            width=140,
            fg_color="#2980b9",
            hover_color="#3498db"
        )
        self.btn_select_file.pack(side="left", padx=4, expand=True, fill="x")

        self.btn_demo = ctk.CTkButton(
            btn_row,
            text="✨ Demo Yükle",
            command=self._load_demo_animation,
            width=140,
            fg_color="#7f8c8d",
            hover_color="#95a5a6"
        )
        self.btn_demo.pack(side="right", padx=4, expand=True, fill="x")

        self.lbl_file_name = ctk.CTkLabel(
            file_box,
            text="Aktif: Dahili Demo Animasyon",
            font=ctk.CTkFont(size=12),
            text_color="#bdc3c7",
            wraplength=340,
            justify="left"
        )
        self.lbl_file_name.pack(anchor="w", padx=12, pady=(4, 8))

        # --- BÖLÜM 2: DEVRE MOTORU (CIRCUIT ENGINE) ---
        eng_box = ctk.CTkFrame(self.sidebar_frame)
        eng_box.pack(fill="x", padx=12, pady=5)

        ctk.CTkLabel(eng_box, text="2. Devre Motoru (Circuit Engine)", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=12, pady=(8, 4))

        self.engine_mode_labels = [
            "Engine V3 (2-Bit Grayscale • 16 Kare/Sinyal • Yeni)",
            "Engine V2 (27-Bit Zamansal Paketleme • 9-Bit Renk)",
            "Engine V1 (Klasik RGB24 • Doğrudan Sinyal)"
        ]
        self.engine_mode_map = {
            "Engine V3 (2-Bit Grayscale • 16 Kare/Sinyal • Yeni)": "v3",
            "Engine V2 (27-Bit Zamansal Paketleme • 9-Bit Renk)": "v2",
            "Engine V1 (Klasik RGB24 • Doğrudan Sinyal)": "v1"
        }

        self.opt_engine = ctk.CTkOptionMenu(
            eng_box, values=self.engine_mode_labels, command=self._on_engine_change, height=30
        )
        self.opt_engine.set("Engine V3 (2-Bit Grayscale • 16 Kare/Sinyal • Yeni)")
        self.opt_engine.pack(fill="x", padx=12, pady=(4, 4))

        self.lbl_engine_hint = ctk.CTkLabel(
            eng_box,
            text="🚀 V3: 16 kare/sinyal 2-bit gri tonlama, tek kombinatörlük TrueColor uyarlayıcı (* 5592405), Selector saat.",
            font=ctk.CTkFont(size=11), text_color="#2ecc71", wraplength=340, justify="left"
        )
        self.lbl_engine_hint.pack(anchor="w", padx=12, pady=(2, 8))

        # --- BÖLÜM 3: MONİTÖR YÜKSEKLİĞİ ---
        res_box = ctk.CTkFrame(self.sidebar_frame)
        res_box.pack(fill="x", padx=12, pady=5)

        ctk.CTkLabel(res_box, text="3. Monitör Çözünürlüğü (Yükseklik)", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=12, pady=(8, 4))

        # Hazır Preset Butonları
        preset_row1 = ctk.CTkFrame(res_box, fg_color="transparent")
        preset_row1.pack(fill="x", padx=10, pady=2)
        for name, h_val in [("16p", 16), ("24p", 24), ("32p", 32), ("48p", 48), ("64p", 64)]:
            ctk.CTkButton(
                preset_row1, text=name, width=48, height=24, font=ctk.CTkFont(size=11),
                command=lambda h=h_val: self._set_height_preset(h)
            ).pack(side="left", padx=2, expand=True)

        preset_row2 = ctk.CTkFrame(res_box, fg_color="transparent")
        preset_row2.pack(fill="x", padx=10, pady=(2, 4))
        for name, h_val in [("96p", 96), ("128p", 128), ("240p", 240), ("360p", 360), ("480p", 480)]:
            ctk.CTkButton(
                preset_row2, text=name, width=48, height=24, font=ctk.CTkFont(size=11),
                fg_color="#34495e", hover_color="#415b76",
                command=lambda h=h_val: self._set_height_preset(h)
            ).pack(side="left", padx=2, expand=True)

        # Yükseklik Textbox
        input_row = ctk.CTkFrame(res_box, fg_color="transparent")
        input_row.pack(fill="x", padx=12, pady=(4, 4))
        ctk.CTkLabel(input_row, text="Özel Yükseklik:").pack(side="left")

        self.btn_apply_h = ctk.CTkButton(
            input_row, text="Uygula", width=65, height=28,
            command=self._on_height_change, fg_color="#2980b9", hover_color="#3498db"
        )
        self.btn_apply_h.pack(side="right", padx=(6, 0))

        self.entry_height = ctk.CTkEntry(
            input_row, width=75, height=28,
            font=ctk.CTkFont(size=13, weight="bold"), justify="center"
        )
        self.entry_height.insert(0, "16")
        self.entry_height.pack(side="right")
        self.entry_height.bind("<Return>", lambda e: self._on_height_change())

        self.lbl_calc_res = ctk.CTkLabel(
            res_box, text="Çözünürlük: 16 x 16 (256 Lamba)",
            font=ctk.CTkFont(size=12, weight="bold"), text_color="#f39c12",
            wraplength=340, justify="left"
        )
        self.lbl_calc_res.pack(anchor="w", padx=12, pady=(2, 8))

        # --- BÖLÜM 4: ROM DEVRESİ KONUMU ---
        rom_box = ctk.CTkFrame(self.sidebar_frame)
        rom_box.pack(fill="x", padx=12, pady=5)

        ctk.CTkLabel(rom_box, text="4. ROM Devresi Konumu", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=12, pady=(8, 4))

        self.rom_mode_labels = [
            "Yatay: Sağda (Varsayılan)",
            "Yatay: Solda",
            "Yatay: Çift Blok (Sağ + Sol / 570 px)",
            "Dikey: Yukarıda (Varsayılan Dikey / 16:9)",
            "Dikey: Aşağıda",
            "Dikey: Çift Blok (Yukarı + Aşağı / 480p+)"
        ]

        self.rom_mode_map = {
            "Yatay: Sağda (Varsayılan)": "horizontal_right",
            "Yatay: Solda": "horizontal_left",
            "Yatay: Çift Blok (Sağ + Sol / 570 px)": "horizontal_both",
            "Dikey: Yukarıda (Varsayılan Dikey / 16:9)": "vertical_top",
            "Dikey: Aşağıda": "vertical_bottom",
            "Dikey: Çift Blok (Yukarı + Aşağı / 480p+)": "vertical_both"
        }

        self.opt_rom_mode = ctk.CTkOptionMenu(
            rom_box, values=self.rom_mode_labels, command=self._on_rom_mode_change, height=30
        )
        self.opt_rom_mode.set("Yatay: Sağda (Varsayılan)")
        self.opt_rom_mode.pack(fill="x", padx=12, pady=(4, 4))

        self.lbl_rom_hint = ctk.CTkLabel(
            rom_box, text="Yatay sağda tek blok ROM. Maks 285 sinyal.",
            font=ctk.CTkFont(size=11), text_color="#95a5a6", wraplength=340, justify="left"
        )
        self.lbl_rom_hint.pack(anchor="w", padx=12, pady=(2, 6))

        self.chk_compact_rom = ctk.CTkCheckBox(
            rom_box, text="📦 Kompakt ROM (0'a 0 Boşluksuz)",
            command=self._on_compact_rom_toggle,
            font=ctk.CTkFont(size=12, weight="bold"), text_color="#f39c12"
        )
        self.chk_compact_rom.pack(anchor="w", padx=12, pady=(2, 2))
        self.chk_compact_rom.select()

        self.lbl_compact_hint = ctk.CTkLabel(
            rom_box, text="ROM'lar ve kombinatörler arasındaki tüm boşlukları sıfırlar, minimum yer kaplar.",
            font=ctk.CTkFont(size=10), text_color="#7f8c8d", wraplength=340, justify="left"
        )
        self.lbl_compact_hint.pack(anchor="w", padx=12, pady=(0, 4))

        self.chk_fill_rows = ctk.CTkCheckBox(
            rom_box, text="🗄️ Tüm Satırları Doldur (Çok Satırlı ROM)",
            command=self._on_fill_rows_toggle,
            font=ctk.CTkFont(size=12, weight="bold"), text_color="#2ecc71"
        )
        self.chk_fill_rows.pack(anchor="w", padx=12, pady=(2, 2))

        self.lbl_fill_rows_hint = ctk.CTkLabel(
            rom_box, text="Kombinatörleri tek satırda uzatmak yerine ekran boyunca tüm satırlara yılan (serpentine) şeklinde yayar. Trafoların etrafından kaydırarak yerleştirir.",
            font=ctk.CTkFont(size=10), text_color="#7f8c8d", wraplength=340, justify="left"
        )
        self.lbl_fill_rows_hint.pack(anchor="w", padx=12, pady=(0, 4))

        # Trafo Niteliği Seçimi
        sub_qual_row = ctk.CTkFrame(rom_box, fg_color="transparent")
        sub_qual_row.pack(fill="x", padx=12, pady=(4, 2))
        ctk.CTkLabel(sub_qual_row, text="⚡ Trafo Niteliği:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")

        self.substation_quality_labels = [
            "Trafo Yok (No Substation)",
            "Normal (Standart)",
            "Sıra Dışı (Uncommon)",
            "Nadir (Rare)",
            "Epik (Epic)",
            "Efsanevi (Legendary)"
        ]
        self.substation_quality_map = {
            "Trafo Yok (No Substation)": "none",
            "Normal (Standart)": "normal",
            "Sıra Dışı (Uncommon)": "uncommon",
            "Nadir (Rare)": "rare",
            "Epik (Epic)": "epic",
            "Efsanevi (Legendary)": "legendary"
        }
        self.opt_substation_quality = ctk.CTkOptionMenu(
            sub_qual_row, values=self.substation_quality_labels,
            command=self._on_substation_quality_change, width=170, height=28
        )
        self.opt_substation_quality.set("Efsanevi (Legendary)")
        self.opt_substation_quality.pack(side="right")

        self.lbl_sub_qual_hint = ctk.CTkLabel(
            rom_box, text="⚡ Efsanevi: 28x28 geniş alan, 28 tel menzili! (Ekranda çok daha az lamba kesintisi).",
            font=ctk.CTkFont(size=10), text_color="#f39c12", wraplength=340, justify="left"
        )
        self.lbl_sub_qual_hint.pack(anchor="w", padx=12, pady=(0, 6))

        # --- BÖLÜM 5: FPS VE KARE SINIRI ---
        play_box = ctk.CTkFrame(self.sidebar_frame)
        play_box.pack(fill="x", padx=12, pady=5)

        ctk.CTkLabel(play_box, text="5. FPS ve Kare Sayısı", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=12, pady=(8, 4))

        fps_row = ctk.CTkFrame(play_box, fg_color="transparent")
        fps_row.pack(fill="x", padx=12, pady=2)
        ctk.CTkLabel(fps_row, text="Kare Hızı (FPS):").pack(side="left")

        self.entry_fps = ctk.CTkEntry(fps_row, width=45, height=26, font=ctk.CTkFont(size=12, weight="bold"), justify="center")
        self.entry_fps.insert(0, "5")
        self.entry_fps.pack(side="right", padx=(4, 0))
        self.entry_fps.bind("<Return>", lambda e: self._on_fps_entry_change())

        self.lbl_fps_val = ctk.CTkLabel(fps_row, text="12 tick", font=ctk.CTkFont(size=12, weight="bold"), text_color="#e67e22")
        self.lbl_fps_val.pack(side="right", padx=(0, 6))

        self.slider_fps = ctk.CTkSlider(play_box, from_=1, to=60, number_of_steps=59, command=self._on_fps_change)
        self.slider_fps.set(5)
        self.slider_fps.pack(fill="x", padx=12, pady=(2, 6))
        self.slider_fps.bind("<ButtonRelease-1>", lambda e: self._on_fps_slider_release())

        mf_row = ctk.CTkFrame(play_box, fg_color="transparent")
        mf_row.pack(fill="x", padx=12, pady=2)
        ctk.CTkLabel(mf_row, text="Maksimum Kare:").pack(side="left")

        self.btn_apply_mf = ctk.CTkButton(
            mf_row, text="Uygula", width=55, height=26,
            command=self._on_max_frames_apply, fg_color="#2980b9", hover_color="#3498db",
            font=ctk.CTkFont(size=11)
        )
        self.btn_apply_mf.pack(side="right", padx=(4, 0))

        self.entry_max_frames = ctk.CTkEntry(mf_row, width=65, height=26, font=ctk.CTkFont(size=12, weight="bold"), justify="center")
        self.entry_max_frames.insert(0, "60")
        self.entry_max_frames.pack(side="right")
        self.entry_max_frames.bind("<Return>", lambda e: self._on_max_frames_apply())

        self.chk_unlimited = ctk.CTkCheckBox(
            play_box, text="♾️ Sınırsız Kare (Tüm Video)",
            command=self._on_unlimited_toggle, font=ctk.CTkFont(size=12, weight="bold"), text_color="#2ecc71"
        )
        self.chk_unlimited.pack(anchor="w", padx=12, pady=(4, 4))

        self.lbl_mf_val = ctk.CTkLabel(play_box, text="60 Kare (~12.0 sn)", font=ctk.CTkFont(size=11), text_color="#bdc3c7")
        self.lbl_mf_val.pack(anchor="w", padx=12, pady=(0, 6))

        # --- BÖLÜM 6: ROM PARÇALAMA & KOPYALAMA KOLAYLIĞI ---
        slice_box = ctk.CTkFrame(self.sidebar_frame)
        slice_box.pack(fill="x", padx=12, pady=5)

        ctk.CTkLabel(slice_box, text="6. ROM Parçalama (Modüler Dilimler)", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=12, pady=(8, 4))

        # Parça Sayısı Slider / Seçici
        parts_header = ctk.CTkFrame(slice_box, fg_color="transparent")
        parts_header.pack(fill="x", padx=12, pady=2)
        ctk.CTkLabel(parts_header, text="Parça Sayısı (2 - 16):").pack(side="left")
        self.lbl_num_parts_val = ctk.CTkLabel(parts_header, text="2 Parça", font=ctk.CTkFont(weight="bold"), text_color="#f39c12")
        self.lbl_num_parts_val.pack(side="right")

        self.slider_parts = ctk.CTkSlider(
            slice_box, from_=1, to=16, number_of_steps=15,
            command=self._on_num_parts_change
        )
        self.slider_parts.set(2)
        self.slider_parts.pack(fill="x", padx=12, pady=(2, 6))

        # Hızlı Parça Seçim Butonları
        quick_parts = ctk.CTkFrame(slice_box, fg_color="transparent")
        quick_parts.pack(fill="x", padx=10, pady=2)
        for p_val in [1, 2, 4, 8, 12, 16]:
            ctk.CTkButton(
                quick_parts, text=f"{p_val}P", width=38, height=22, font=ctk.CTkFont(size=10),
                fg_color="#34495e", hover_color="#415b76",
                command=lambda p=p_val: self._set_num_parts_val(p)
            ).pack(side="left", padx=2, expand=True)

        # Kopyalama Kolaylığı Checkbox
        self.chk_convenience = ctk.CTkCheckBox(
            slice_box,
            text="✨ Kopyalama Kolaylığı (+1 Ortak Sütun)",
            command=self._on_convenience_toggle,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#3498db"
        )
        self.chk_convenience.select()
        self.chk_convenience.pack(anchor="w", padx=12, pady=(6, 2))

        lbl_conv_desc = ctk.CTkLabel(
            slice_box,
            text="2. ve sonraki parçalara önceki parçanın son sütunu eklenir. Oyunda üst üste yapıştırıldığında tüm kablolar otomatik bağlı kalır!",
            font=ctk.CTkFont(size=10),
            text_color="#95a5a6",
            wraplength=340,
            justify="left"
        )
        lbl_conv_desc.pack(anchor="w", padx=12, pady=(0, 8))

        # Parça Seçimi Gezinti Butonları
        nav_row = ctk.CTkFrame(slice_box, fg_color="transparent")
        nav_row.pack(fill="x", padx=10, pady=(2, 8))

        self.btn_prev_part = ctk.CTkButton(
            nav_row, text="◀ Önceki Parça", width=110, height=28,
            command=self._on_prev_part, fg_color="#34495e", hover_color="#415b76"
        )
        self.btn_prev_part.pack(side="left", padx=4)

        self.lbl_active_part_nav = ctk.CTkLabel(
            nav_row, text="Parça 1 / 2", font=ctk.CTkFont(size=12, weight="bold"), text_color="#ecf0f1"
        )
        self.lbl_active_part_nav.pack(side="left", expand=True)

        self.btn_next_part = ctk.CTkButton(
            nav_row, text="Sonraki Parça ▶", width=110, height=28,
            command=self._on_next_part, fg_color="#34495e", hover_color="#415b76"
        )
        self.btn_next_part.pack(side="right", padx=4)

        # --- BÖLÜM 6: DERLEME BUTONU & DURUM ---
        self.btn_generate = ctk.CTkButton(
            self.sidebar_frame,
            text="⚡ SEÇİLİ PARÇAYI OLUŞTUR",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=46,
            fg_color="#e67e22",
            hover_color="#d35400",
            command=self._start_generation_thread
        )
        self.btn_generate.pack(fill="x", padx=12, pady=(12, 6))

        self.progress_bar = ctk.CTkProgressBar(self.sidebar_frame)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=12, pady=4)

        self.lbl_status = ctk.CTkLabel(
            self.sidebar_frame, text="Hazır.", font=ctk.CTkFont(size=12), text_color="#95a5a6"
        )
        self.lbl_status.pack(padx=12, pady=(2, 16))

        # ===================================================================
        # SAĞ PANEL: İNTERAKTİF MİMARÎ ŞEMA VE ROM DİLİM SEÇİCİ
        # ===================================================================
        self.preview_container = ctk.CTkFrame(self)
        self.preview_container.grid(row=0, column=1, sticky="nsew", padx=12, pady=12)
        self.preview_container.grid_columnconfigure(0, weight=1)
        self.preview_container.grid_rowconfigure(1, weight=1)

        # Üst Başlık ve Aktif Parça Rozeti
        header_frame = ctk.CTkFrame(self.preview_container, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 6))

        ctk.CTkLabel(
            header_frame,
            text="📐 FACTORIO DEVRE MİMARİSİ VE ROM DİLİM ŞEMASI",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#3498db"
        ).pack(side="left")

        self.lbl_part_badge = ctk.CTkLabel(
            header_frame,
            text="★ SEÇİLİ: PARÇA 1 / 2 (Monitör + ROM 1)",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#f39c12"
        )
        self.lbl_part_badge.pack(side="right")

        # Şematik Canvas (Etkileşimli Tıklanabilir & Hover Destekli)
        self.canvas_frame = ctk.CTkFrame(self.preview_container, fg_color="#0e0e12")
        self.canvas_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=8)
        self.canvas_frame.grid_columnconfigure(0, weight=1)
        self.canvas_frame.grid_rowconfigure(0, weight=1)

        self.schematic_canvas = tk.Canvas(
            self.canvas_frame,
            bg="#0d0e14",
            highlightthickness=0
        )
        self.schematic_canvas.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.schematic_canvas.bind("<Configure>", lambda e: self._render_schematic())
        self.schematic_canvas.bind("<Button-1>", self._on_canvas_click)
        self.schematic_canvas.bind("<Motion>", self._on_canvas_motion)

        # Alt Bilgi ve Dışa Aktarma Paneli
        bottom_frame = ctk.CTkFrame(self.preview_container)
        bottom_frame.grid(row=2, column=0, sticky="ew", padx=16, pady=(6, 12))
        bottom_frame.grid_columnconfigure(0, weight=1)

        self.lbl_part_info = ctk.CTkLabel(
            bottom_frame,
            text="Parça 1/2: Monitör + Kare 0-7 (8 kare) | Saat devresi dahil",
            font=ctk.CTkFont(size=12),
            text_color="#bdc3c7",
            anchor="w"
        )
        self.lbl_part_info.pack(side="left", padx=14, pady=10)

        self.btn_copy = ctk.CTkButton(
            bottom_frame,
            text="📋 Seçili Parçayı Kopyala",
            width=180,
            fg_color="#2980b9",
            hover_color="#3498db",
            command=self._on_copy_clipboard
        )
        self.btn_copy.pack(side="right", padx=(6, 12), pady=8)

        self.btn_save = ctk.CTkButton(
            bottom_frame,
            text="💾 Dosyaya Kaydet",
            width=140,
            fg_color="#34495e",
            hover_color="#415b76",
            command=self._on_save_file
        )
        self.btn_save.pack(side="right", padx=6, pady=8)

    # =======================================================================
    # DEĞER VE EVENT İŞLEYİCİLERİ
    # =======================================================================
    def _on_select_file(self):
        filetypes = [
            ("Video & Animasyon Dosyaları", "*.mp4 *.gif *.avi *.webm *.mov"),
            ("Tüm Dosyalar", "*.*")
        ]
        path = filedialog.askopenfilename(title="Video veya GIF Seç", filetypes=filetypes)
        if path:
            self.selected_file_path = path
            info = get_media_info(path)
            self.media_orig_size = (info["width"], info["height"])

            # Videonun FPS değerini otomatik algıla ve UI kontrollerine aktar
            detected_fps = max(1, min(60, int(round(info["fps"]))))
            self.entry_fps.delete(0, "end")
            self.entry_fps.insert(0, str(detected_fps))
            self.slider_fps.set(detected_fps)
            self._update_fps_display(detected_fps)

            # Dosya etiketinde video detaylarını göster
            fname = os.path.basename(path)
            dur_str = f"{info['duration']:.1f} sn" if info.get('duration') else f"{info['total_frames']} kare"
            self.lbl_file_name.configure(
                text=f"Aktif: {fname} ({info['width']}x{info['height']} | {info['fps']:.1f} FPS | {info['total_frames']} kare / {dur_str})"
            )

            self.part_blueprints.clear()
            self._reload_video_frames()

    def _load_demo_animation(self):
        self.selected_file_path = None
        self.media_orig_size = (16, 16)
        self.lbl_file_name.configure(text="Aktif: Dahili Demo Animasyon")
        w, h = self._get_current_dimensions()
        try:
            fps = int(self.entry_fps.get().strip())
        except Exception:
            fps = 5
        mf = self._get_max_frames_val()
        self.loaded_frames = generate_procedural_demo(width=w, height=h, fps=fps, max_frames=mf)
        self.total_frames_count = len(self.loaded_frames)
        self._loaded_fps = fps
        self.part_blueprints.clear()
        self._render_schematic()
        self._update_part_info_label()

    def _on_engine_change(self, choice: str):
        self.selected_engine = self.engine_mode_map.get(choice, "v3")
        if self.selected_engine == "v3":
            hint = "🚀 V3: 16 kare/sinyal 2-bit gri tonlama, tek kombinatörlük TrueColor uyarlayıcı (* 5592405), Selector saat."
            text_col = "#2ecc71"
        elif self.selected_engine == "v2":
            hint = "✨ V2: 3 kare/paket, 12'li RGB renk dekoderi, %67 daha az kombinatör, hassas saat."
            text_col = "#3498db"
        else:
            hint = "⚡ V1: Her kare için ayrı kombinatör (1 kare/kombinatör), doğrudan 24-bit RGB (dekodersiz)."
            text_col = "#e67e22"
        if hasattr(self, "lbl_engine_hint"):
            self.lbl_engine_hint.configure(text=hint, text_color=text_col)
        self.part_blueprints.clear()
        self._update_part_info_label()

    def _on_rom_mode_change(self, choice: str):
        self.part_blueprints.clear()
        self._get_current_dimensions()
        self._render_schematic()
        self._update_part_info_label()

    def _on_compact_rom_toggle(self):
        self.compact_rom = bool(self.chk_compact_rom.get())
        self.part_blueprints.clear()
        self._render_schematic()
        self._update_part_info_label()

    def _on_fill_rows_toggle(self):
        self.fill_all_rows = bool(self.chk_fill_rows.get())
        self.part_blueprints.clear()
        self._render_schematic()
        self._update_part_info_label()

    def _on_substation_quality_change(self, choice: str):
        self.substation_quality = self.substation_quality_map.get(choice, "legendary")
        hints = {
            "none": "🚫 Trafo Yok: Hiçbir trafo yerleştirilmez. %100 piksel doluluğu, sıfır lamba kesintisi!",
            "normal": "Normal: 18x18 besleme alanı, 18 tel menzili.",
            "uncommon": "Sıra Dışı: 20x20 besleme alanı, 20 tel menzili.",
            "rare": "Nadir: 22x22 besleme alanı, 22 tel menzili.",
            "epic": "Epik: 24x24 besleme alanı, 24 tel menzili.",
            "legendary": "⚡ Efsanevi: 28x28 geniş alan, 28 tel menzili! (Ekranda çok daha az lamba kesintisi)."
        }
        if hasattr(self, "lbl_sub_qual_hint"):
            hint_color = "#3498db" if self.substation_quality == "none" else ("#f39c12" if self.substation_quality == "legendary" else "#7f8c8d")
            self.lbl_sub_qual_hint.configure(
                text=hints.get(self.substation_quality, hints["normal"]),
                text_color=hint_color
            )
        self.part_blueprints.clear()
        self._render_schematic()
        self._update_part_info_label()

    def _set_height_preset(self, h: int):
        self.entry_height.delete(0, "end")
        self.entry_height.insert(0, str(h))
        self._on_height_change()

    def _on_height_change(self):
        w, h = self._get_current_dimensions()
        current_txt = self.entry_height.get().strip()
        if current_txt != str(h):
            self.entry_height.delete(0, "end")
            self.entry_height.insert(0, str(h))
        self.part_blueprints.clear()
        self._reload_video_frames()

    def _update_fps_display(self, fps: int):
        safe_fps = max(1, min(60, fps))
        g = math.gcd(safe_fps, 60)
        mult = safe_fps // g
        div = 60 // g
        if mult == 1:
            txt = f"{div} tick ({safe_fps} FPS • 1.0x)"
        else:
            txt = f"~{div/mult:.2f} tick ({safe_fps} FPS • 1.0x)"
        self.lbl_fps_val.configure(text=txt)
        self._update_mf_label()

    def _on_fps_change(self, val):
        fps = max(1, min(60, int(round(val))))
        self.entry_fps.delete(0, "end")
        self.entry_fps.insert(0, str(fps))
        self._update_fps_display(fps)

    def _on_fps_slider_release(self):
        self.part_blueprints.clear()
        self._reload_video_frames()

    def _on_fps_entry_change(self):
        try:
            fps = int(self.entry_fps.get().strip())
            fps = max(1, min(60, fps))
        except Exception:
            fps = 5
        self.entry_fps.delete(0, "end")
        self.entry_fps.insert(0, str(fps))
        self.slider_fps.set(fps)
        self._update_fps_display(fps)
        self.part_blueprints.clear()
        self._reload_video_frames()

    def _on_unlimited_toggle(self):
        if self.chk_unlimited.get():
            self.entry_max_frames.configure(state="disabled")
            self.btn_apply_mf.configure(state="disabled")
            self.lbl_mf_val.configure(text="Sınır yok: Tüm video kareleri işlenecek.")
        else:
            self.entry_max_frames.configure(state="normal")
            self.btn_apply_mf.configure(state="normal")
            self._update_mf_label()
        self.part_blueprints.clear()
        self._reload_video_frames()

    def _get_max_frames_val(self) -> Optional[int]:
        if hasattr(self, "chk_unlimited") and self.chk_unlimited.get():
            return None
        if hasattr(self, "entry_max_frames"):
            try:
                val = int(self.entry_max_frames.get().strip())
                return val if val > 0 else None
            except Exception:
                return 60
        return 60

    def _update_mf_label(self):
        if hasattr(self, "chk_unlimited") and self.chk_unlimited.get():
            self.lbl_mf_val.configure(text="Sınır yok: Tüm video kareleri işlenecek.")
            return
        mf = self._get_max_frames_val()
        try:
            fps = int(self.entry_fps.get().strip())
        except Exception:
            fps = 5
        if mf is not None and mf > 0:
            dur = mf / fps if fps > 0 else 0
            self.lbl_mf_val.configure(text=f"{mf} Kare (~{dur:.1f} sn)")
        else:
            self.lbl_mf_val.configure(text="Sınır yok: Tüm video kareleri işlenecek.")

    def _on_max_frames_apply(self):
        self._update_mf_label()
        self.part_blueprints.clear()
        self._reload_video_frames()

    def _set_num_parts_val(self, p: int):
        self.slider_parts.set(p)
        self._on_num_parts_change(p)

    def _on_num_parts_change(self, val):
        self.num_parts = max(1, min(16, int(round(val))))
        self.lbl_num_parts_val.configure(text=f"{self.num_parts} Parça")
        if self.selected_part_idx >= self.num_parts:
            self.selected_part_idx = self.num_parts - 1
        self.lbl_active_part_nav.configure(text=f"Parça {self.selected_part_idx + 1} / {self.num_parts}")
        self._render_schematic()
        self._update_part_info_label()

    def _on_convenience_toggle(self):
        self.copy_convenience = self.chk_convenience.get()
        self.part_blueprints.clear()
        self._render_schematic()
        self._update_part_info_label()

    def _on_prev_part(self):
        if self.selected_part_idx > 0:
            self.selected_part_idx -= 1
            self.lbl_active_part_nav.configure(text=f"Parça {self.selected_part_idx + 1} / {self.num_parts}")
            self._render_schematic()
            self._update_part_info_label()
            self._trigger_auto_copy_if_ready()

    def _on_next_part(self):
        if self.selected_part_idx < self.num_parts - 1:
            self.selected_part_idx += 1
            self.lbl_active_part_nav.configure(text=f"Parça {self.selected_part_idx + 1} / {self.num_parts}")
            self._render_schematic()
            self._update_part_info_label()
            self._trigger_auto_copy_if_ready()

    def _get_current_dimensions(self) -> Tuple[int, int]:
        try:
            val_str = self.entry_height.get().strip()
            h = int(val_str)
            if h < 4: h = 4
        except Exception:
            h = 16

        orig_w, orig_h = self.media_orig_size
        if orig_h > 0:
            w = max(4, int(round(h * (orig_w / orig_h))))
        else:
            w = h

        rom_mode = "horizontal_right"
        if hasattr(self, "opt_rom_mode") and hasattr(self, "rom_mode_map"):
            rom_mode = self.rom_mode_map.get(self.opt_rom_mode.get(), "horizontal_right")

        capacity_ok, warning_res, hint_msg = self._check_signal_capacity(w, h, rom_mode)

        if hasattr(self, "lbl_calc_res"):
            self.lbl_calc_res.configure(
                text=f"Çözünürlük: {w} x {h} ({w * h:,} Lamba){warning_res}",
                text_color="#e74c3c" if not capacity_ok else "#f39c12"
            )

        self._set_generate_btn_state(capacity_ok, hint_msg)
        return w, h

    def _check_signal_capacity(self, w: int, h: int, rom_mode: str):
        MAX_SINGLE = len(SIGNAL_POOL)
        MAX_DOUBLE = len(SIGNAL_POOL) * 2

        if rom_mode in ("horizontal_right", "horizontal_left"):
            if w > MAX_SINGLE:
                return (False, f" ❌ Genişlik {w} > {MAX_SINGLE}! Sinyal yetersiz.",
                        f"❌ Yatay tek blok {MAX_SINGLE} px genişliğe kadar destekler.\n→ 'Yatay: Çift Blok' seçin ({MAX_DOUBLE} px'e kadar)\n→ veya 'Dikey: Yukarıda' seçin ({MAX_SINGLE} px yüksekliğe kadar)")
        elif rom_mode == "horizontal_both":
            if w > MAX_DOUBLE:
                return (False, f" ❌ Genişlik {w} > {MAX_DOUBLE}! Sinyal yetersiz.",
                        f"❌ Yatay çift blok {MAX_DOUBLE} px genişliğe kadar destekler.\n→ 'Dikey: Çift Blok' seçin ({MAX_DOUBLE} px yüksekliğe kadar)\n→ veya video çözünürlüğünü düşürün")
        elif rom_mode in ("vertical_top", "vertical_bottom"):
            if h > MAX_SINGLE:
                return (False, f" ❌ Yükseklik {h} > {MAX_SINGLE}! Sinyal yetersiz.",
                        f"❌ Dikey tek blok {MAX_SINGLE} px yüksekliğe kadar destekler.\n→ 'Dikey: Çift Blok' seçin ({MAX_DOUBLE} px'e kadar)\n→ veya 'Yatay: Sağda' seçin ({MAX_SINGLE} px genişliğe kadar)")
        elif rom_mode == "vertical_both":
            if h > MAX_DOUBLE:
                return (False, f" ❌ Yükseklik {h} > {MAX_DOUBLE}! Sinyal yetersiz.",
                        f"❌ Dikey çift blok {MAX_DOUBLE} px yüksekliğe kadar destekler.\n→ 'Yatay: Çift Blok' seçin ({MAX_DOUBLE} px genişliğe kadar)\n→ veya video çözünürlüğünü düşürün")

        hints = {
            "horizontal_right": f"✅ Yatay sağda tek blok ROM. Maks {MAX_SINGLE} px genişlik.",
            "horizontal_left":  f"✅ Yatay solda tek blok ROM. Maks {MAX_SINGLE} px genişlik.",
            "horizontal_both":  f"✅ Yatay çift blok ROM (Sağ + Sol). Maks {MAX_DOUBLE} px genişlik.",
            "vertical_top":     f"✅ Dikey yukarıda tek blok ROM. Maks {MAX_SINGLE} px yükseklik.",
            "vertical_bottom":  f"✅ Dikey aşağıda tek blok ROM. Maks {MAX_SINGLE} px yükseklik.",
            "vertical_both":    f"✅ Dikey çift blok ROM (Yukarı + Aşağı). Maks {MAX_DOUBLE} px yükseklik.",
        }
        return (True, "", hints.get(rom_mode, ""))

    def _set_generate_btn_state(self, capacity_ok: bool, hint_msg: str):
        if hasattr(self, "lbl_rom_hint"):
            self.lbl_rom_hint.configure(text=hint_msg, text_color="#e74c3c" if not capacity_ok else "#95a5a6")
        if hasattr(self, "btn_generate"):
            if capacity_ok:
                self.btn_generate.configure(state="normal", text="⚡ SEÇİLİ PARÇAYI OLUŞTUR", fg_color="#e67e22", hover_color="#d35400")
            else:
                self.btn_generate.configure(state="disabled", text="🚫 Sinyal Yetersiz - ROM Modunu Değiştir", fg_color="#7f0000", hover_color="#7f0000")

    def _reload_video_frames(self):
        self._load_cancelled = True
        if self._load_thread and self._load_thread.is_alive():
            self._load_thread.join(timeout=0.1)
        self._load_cancelled = False

        w, h = self._get_current_dimensions()
        try:
            fps = int(self.entry_fps.get().strip())
        except Exception:
            fps = 5
        max_f = self._get_max_frames_val()
        file_path = self.selected_file_path

        if hasattr(self, "lbl_status"):
            self.lbl_status.configure(text="⏳ Video kareleri hazırlanıyor...", text_color="#f39c12")
        if hasattr(self, "progress_bar"):
            self.progress_bar.set(0)
            self.progress_bar.start()

        def _worker():
            try:
                if file_path and os.path.exists(file_path):
                    frames = extract_video_frames(
                        file_path, width=w, height=h, target_fps=fps, max_frames=max_f, keep_aspect=False
                    )
                else:
                    frames = generate_procedural_demo(width=w, height=h, fps=fps, max_frames=max_f)

                if not self._load_cancelled:
                    self.after(0, lambda f=frames: self._on_frames_loaded(f))
            except Exception as e:
                if not self._load_cancelled:
                    err = str(e)
                    self.after(0, lambda msg=err: self._on_frames_load_error(msg))

        self._load_thread = threading.Thread(target=_worker, daemon=True)
        self._load_thread.start()

    def _on_frames_loaded(self, frames: List[Any]):
        try:
            self.progress_bar.stop()
            self.progress_bar.set(1)
        except Exception:
            pass
        self.loaded_frames = frames
        self.total_frames_count = len(frames)
        try:
            self._loaded_fps = int(self.entry_fps.get().strip())
        except Exception:
            self._loaded_fps = int(self.slider_fps.get())
        self.part_blueprints.clear()
        self._render_schematic()
        self._update_part_info_label()
        if hasattr(self, "lbl_status"):
            self.lbl_status.configure(text="Hazır.", text_color="#95a5a6")

    def _on_frames_load_error(self, err_msg: str):
        try:
            self.progress_bar.stop()
            self.progress_bar.set(0)
        except Exception:
            pass
        messagebox.showerror("Hata", f"Video kareleri çıkarılamadı:\n{err_msg}")
        self._load_demo_animation()

    # =======================================================================
    # İNTERAKTİF MİMARÎ ŞEMA VE ROM DİLİM ÇİZİMİ
    # =======================================================================
    def _render_schematic(self):
        """Monitörü merkezde, 4 kenardaki ROM'ları ise duruma göre aktif/sönük ve dilimlenmiş olarak çizer."""
        c = self.schematic_canvas
        c.delete("all")
        self._slice_hitboxes.clear()

        c_w = c.winfo_width()
        c_h = c.winfo_height()
        if c_w <= 30 or c_h <= 30:
            return

        w, h = self._get_current_dimensions()
        rom_mode = "horizontal_right"
        if hasattr(self, "opt_rom_mode") and hasattr(self, "rom_mode_map"):
            rom_mode = self.rom_mode_map.get(self.opt_rom_mode.get(), "horizontal_right")

        # Aktif ROM kenarları
        active_sides = {
            "top": rom_mode in ("vertical_top", "vertical_both"),
            "bottom": rom_mode in ("vertical_bottom", "vertical_both"),
            "left": rom_mode in ("horizontal_left", "horizontal_both"),
            "right": rom_mode in ("horizontal_right", "horizontal_both")
        }

        # Monitör Alanı Boyutlandırma
        margin = 35
        avail_w = c_w - (margin * 2)
        avail_h = c_h - (margin * 2)

        # Merkez Monitör Boyutları (Aspect Ratio orantılı)
        aspect = w / max(1, h)
        max_mon_w = avail_w * 0.48
        max_mon_h = avail_h * 0.48

        if aspect >= 1.0:
            mon_w = max_mon_w
            mon_h = max(40, min(max_mon_h, mon_w / aspect))
        else:
            mon_h = max_mon_h
            mon_w = max(40, min(max_mon_w, mon_h * aspect))

        cx = c_w / 2.0
        cy = c_h / 2.0

        mx0 = cx - mon_w / 2.0
        my0 = cy - mon_h / 2.0
        mx1 = cx + mon_w / 2.0
        my1 = cy + mon_h / 2.0

        rom_gap = 4 if getattr(self, "compact_rom", True) else 14
        side_rom_w = max(60, min(140, (mx0 - margin - rom_gap)))
        vert_rom_h = max(40, min(90, (my0 - margin - rom_gap)))

        # 1. Merkez Monitör Çizimi
        is_p0_selected = (self.selected_part_idx == 0)
        mon_fill = "#141c2b" if is_p0_selected else "#0f131a"
        mon_outline = "#f39c12" if is_p0_selected else "#2c3e50"
        mon_width = 3 if is_p0_selected else 2

        # Monitör dikdörtgeni
        c.create_rectangle(mx0, my0, mx1, my1, fill=mon_fill, outline=mon_outline, width=mon_width)

        # Monitör Hitbox (Tıklandığında Parça 0 seçilir)
        self._slice_hitboxes.append({"part_idx": 0, "bbox": (mx0, my0, mx1, my1), "type": "monitor"})

        # Monitör İçi Yazılar
        c.create_text(
            cx, cy - 14,
            text=f"📺 MONİTÖR EKRANI",
            fill="#00d2ff" if is_p0_selected else "#7f8c8d",
            font=("Arial", 12, "bold")
        )
        c.create_text(
            cx, cy + 4,
            text=f"{w} x {h}  ({w * h:,} Lamba)",
            fill="#ecf0f1" if is_p0_selected else "#566573",
            font=("Arial", 10, "bold")
        )

        status_tag = "★ PARÇA 1 İLE BİRLİKTE SEÇİLİ" if is_p0_selected else "(Parça 1'e dahildir)"
        status_color = "#f39c12" if is_p0_selected else "#415b76"
        c.create_text(
            cx, cy + 22,
            text=status_tag,
            fill=status_color,
            font=("Arial", 9, "bold")
        )

        # 1.1. Monitör Sol Üst Trafoları ve Hizalama Çapası Çizimi
        # Ana Trafo ve hemen 2 kare yukarısındaki Hizalama Trafosu
        tf_w = 12
        tf_main_x0 = mx0 - tf_w - 4
        tf_main_y0 = my0 - tf_w / 2
        tf_main_x1 = mx0 - 4
        tf_main_y1 = my0 + tf_w / 2

        tf_align_x0 = tf_main_x0
        tf_align_y0 = tf_main_y0 - tf_w - 4
        tf_align_x1 = tf_main_x1
        tf_align_y1 = tf_main_y1 - tf_w - 4

        # Bakır kablo çizgisi
        c.create_line(
            (tf_main_x0 + tf_main_x1) / 2, (tf_main_y0 + tf_main_y1) / 2,
            (tf_align_x0 + tf_align_x1) / 2, (tf_align_y0 + tf_align_y1) / 2,
            fill="#d35400", width=2
        )
        # Ana Trafo
        c.create_rectangle(
            tf_main_x0, tf_main_y0, tf_main_x1, tf_main_y1,
            fill="#16a085", outline="#1abc9c", width=1.5
        )
        # Hizalama Trafosu (2 kare yukarısı)
        c.create_rectangle(
            tf_align_x0, tf_align_y0, tf_align_x1, tf_align_y1,
            fill="#e67e22", outline="#f39c12", width=1.5
        )
        # Hizalama etiketi
        c.create_text(
            tf_align_x0 - 2, (tf_main_y0 + tf_align_y1) / 2,
            text="⚓", fill="#f39c12", font=("Arial", 9), anchor="e"
        )

        # 2. 4 Kenardaki ROM Bloklarının Çizimi
        rom_boxes = {
            "top": (mx0, my0 - rom_gap - vert_rom_h, mx1, my0 - rom_gap),
            "bottom": (mx0, my1 + rom_gap, mx1, my1 + rom_gap + vert_rom_h),
            "left": (mx0 - rom_gap - side_rom_w, my0, mx0 - rom_gap, my1),
            "right": (mx1 + rom_gap, my0, mx1 + rom_gap + side_rom_w, my1)
        }

        labels = {
            "top": "ÜST ROM (Dikey)",
            "bottom": "ALT ROM (Dikey)",
            "left": "SOL ROM (Yatay)",
            "right": "SAĞ ROM (Yatay)"
        }

        total_f = max(1, self.total_frames_count)

        for side, (rx0, ry0, rx1, ry1) in rom_boxes.items():
            is_active = active_sides[side]

            if not is_active:
                # SÖNÜK KIRMIZI (Kullanılmayan / Boş ROM)
                c.create_rectangle(
                    rx0, ry0, rx1, ry1,
                    fill="#180b0b",
                    outline="#641e1e",
                    width=1,
                    dash=(3, 3)
                )
                scx = (rx0 + rx1) / 2.0
                scy = (ry0 + ry1) / 2.0
                c.create_text(
                    scx, scy - 6,
                    text=f"❌ {labels[side]}",
                    fill="#853636",
                    font=("Arial", 9, "bold")
                )
                c.create_text(
                    scx, scy + 8,
                    text="(Devre Dışı)",
                    fill="#5c2020",
                    font=("Arial", 8)
                )
            else:
                # AKTİF ROM: PARÇALARA / DİLİMLERE AYIR
                c.create_rectangle(
                    rx0, ry0, rx1, ry1,
                    fill="#101924",
                    outline="#1e88e5",
                    width=2
                )

                # Dilimleme Yönü: Yatay ROM'larda X boyunca, Dikey ROM'larda Y boyunca
                is_horiz_rom = (side in ("left", "right"))
                n_parts = self.num_parts

                for p in range(n_parts):
                    # Kare aralığı
                    f_s = (total_f * p) // n_parts
                    f_e = (total_f * (p + 1)) // n_parts
                    if f_s >= f_e:
                        f_s = min(p, total_f - 1)
                        f_e = min(p + 1, total_f)

                    if is_horiz_rom:
                        # X ekseninde dilim
                        if side == "right":
                            sx0 = rx0 + p * (rx1 - rx0) / n_parts
                            sx1 = rx0 + (p + 1) * (rx1 - rx0) / n_parts
                        else: # left (sol tarafta monitöre yakın olan ilk parçadır)
                            sx0 = rx1 - (p + 1) * (rx1 - rx0) / n_parts
                            sx1 = rx1 - p * (rx1 - rx0) / n_parts
                        sy0 = ry0
                        sy1 = ry1
                    else:
                        # Y ekseninde dilim
                        if side == "bottom":
                            sy0 = ry0 + p * (ry1 - ry0) / n_parts
                            sy1 = ry0 + (p + 1) * (ry1 - ry0) / n_parts
                        else: # top (üst tarafta monitöre yakın olan ilk parçadır)
                            sy0 = ry1 - (p + 1) * (ry1 - ry0) / n_parts
                            sy1 = ry1 - p * (ry1 - ry0) / n_parts
                        sx0 = rx0
                        sx1 = rx1

                    is_selected = (p == self.selected_part_idx)

                    # Dilim Arka Planı ve Çerçevesi
                    if is_selected:
                        slice_fill = "#2e1e0f" if p == 0 else "#1c2a1a"
                        slice_outline = "#f39c12" if p == 0 else "#2ecc71"
                        slice_width = 3
                    else:
                        slice_fill = "#131e2b"
                        slice_outline = "#244061"
                        slice_width = 1

                    c.create_rectangle(
                        sx0, sy0, sx1, sy1,
                        fill=slice_fill,
                        outline=slice_outline,
                        width=slice_width
                    )

                    # Tıklanabilir Hitbox Kaydı
                    self._slice_hitboxes.append({
                        "part_idx": p,
                        "bbox": (min(sx0, sx1), min(sy0, sy1), max(sx0, sx1), max(sy0, sy1)),
                        "type": "slice",
                        "side": side
                    })

                    # Dilim İçi Metinler
                    mid_x = (sx0 + sx1) / 2.0
                    mid_y = (sy0 + sy1) / 2.0

                    if is_horiz_rom:
                        p_title = f"P{p + 1}"
                        p_color = "#f39c12" if (is_selected and p == 0) else ("#2ecc71" if is_selected else "#ecf0f1")
                        c.create_text(
                            mid_x, mid_y - 10,
                            text=p_title,
                            fill=p_color,
                            font=("Arial", 11 if is_selected else 10, "bold")
                        )
                        c.create_text(
                            mid_x, mid_y + 4,
                            text=f"K:{f_s}..{f_e - 1}",
                            fill="#bdc3c7" if is_selected else "#7f8c8d",
                            font=("Arial", 8)
                        )
                        if p > 0 and self.copy_convenience:
                            c.create_text(
                                mid_x, mid_y + 16,
                                text="+1 Ortak",
                                fill="#3498db" if is_selected else "#2980b9",
                                font=("Arial", 7, "bold")
                            )
                    else: # Dikey ROM Dilimi
                        p_text = f"PARÇA {p + 1}  (Kare {f_s}..{f_e - 1})"
                        if p > 0 and self.copy_convenience:
                            p_text += "  [+1 Ortak Sütun]"
                        p_color = "#f39c12" if (is_selected and p == 0) else ("#2ecc71" if is_selected else "#ecf0f1")
                        c.create_text(
                            mid_x, mid_y,
                            text=p_text,
                            fill=p_color,
                            font=("Arial", 10 if is_selected else 9, "bold")
                        )

    def _on_canvas_click(self, event):
        """Kullanıcı canvas üzerinde bir dilime veya monitöre tıkladığında parçayı seçer."""
        for box in self._slice_hitboxes:
            x0, y0, x1, y1 = box["bbox"]
            if x0 <= event.x <= x1 and y0 <= event.y <= y1:
                p = box["part_idx"]
                if p != self.selected_part_idx:
                    self.selected_part_idx = p
                    self.lbl_active_part_nav.configure(text=f"Parça {p + 1} / {self.num_parts}")
                    self._render_schematic()
                    self._update_part_info_label()
                    self._trigger_auto_copy_if_ready()
                break

    def _on_canvas_motion(self, event):
        """Mouse hover durumunda imleci el işareti (hand2) yapar."""
        hovered = False
        for box in self._slice_hitboxes:
            x0, y0, x1, y1 = box["bbox"]
            if x0 <= event.x <= x1 and y0 <= event.y <= y1:
                hovered = True
                break
        self.schematic_canvas.configure(cursor="hand2" if hovered else "arrow")

    def _update_part_info_label(self):
        """Seçili parçanın ayrıntılarını ve üst rozetini günceller."""
        p = self.selected_part_idx
        n = self.num_parts
        total_f = max(1, self.total_frames_count)

        f_s = (total_f * p) // n
        f_e = (total_f * (p + 1)) // n
        if f_s >= f_e:
            f_s = min(p, total_f - 1)
            f_e = min(p + 1, total_f)

        f_count = f_e - f_s
        w, h = self._get_current_dimensions()

        compact_tag = "Kompakt" if getattr(self, "compact_rom", True) else "Standart"
        multi_row_tag = " | Çok Satırlı" if getattr(self, "fill_all_rows", False) else ""
        eng = getattr(self, 'selected_engine', 'v3')
        if eng == 'v3':
            eng_name = 'V3 (16 Kare/Sinyal)'
        elif eng == 'v2':
            eng_name = 'V2 (27-Bit)'
        else:
            eng_name = 'V1 (RGB24)'
        eng_tag = f"{eng_name} | {compact_tag}{multi_row_tag}"
        if p == 0:
            badge_text = f"★ SEÇİLİ: PARÇA 1 / {n} [{eng_tag}] (Monitör + ROM 1)"
            badge_color = "#f39c12"
            info_text = (
                f"Parça 1/{n} [{eng_tag}]: Monitör ({w}x{h} = {w*h:,} Lamba) + Saat Devresi + ROM (Kare {f_s}..{f_e - 1}, {f_count} kare)"
            )
        else:
            conv_note = f" | +1 Ortak Sütun (Kare {f_s - 1}) Dahil" if self.copy_convenience else ""
            badge_text = f"★ SEÇİLİ: PARÇA {p + 1} / {n} [{eng_tag}] (ROM Dilimi)"
            badge_color = "#2ecc71"
            info_text = (
                f"Parça {p + 1}/{n} [{eng_tag}]: ROM Kombinatör Dilimi (Kare {f_s}..{f_e - 1}, {f_count} kare){conv_note} | Monitör YOK"
            )

        self.lbl_part_badge.configure(text=badge_text, text_color=badge_color)
        self.lbl_part_info.configure(text=info_text)

    # =======================================================================
    # BLUEPRINT OLUŞTURMA VE ÖNBELLEK YÖNETİMİ
    # =======================================================================
    def _trigger_auto_copy_if_ready(self):
        """Eğer bu parça daha önce üretildiyse panoya otomatik kopyalar."""
        if self.selected_part_idx in self.part_blueprints:
            bp_str, _ = self.part_blueprints[self.selected_part_idx]
            if copy_to_clipboard(bp_str):
                self.btn_copy.configure(text=f"✓ Parça {self.selected_part_idx + 1} Kopyalandı!", fg_color="#27ae60")
                self.after(2000, lambda: self.btn_copy.configure(text="📋 Seçili Parçayı Kopyala", fg_color="#2980b9"))

    def _start_generation_thread(self):
        if not self.loaded_frames:
            messagebox.showwarning("Uyarı", "Lütfen önce bir video veya animasyon yükleyin!")
            return

        if self.is_compiling:
            return

        self.is_compiling = True
        self.btn_generate.configure(state="disabled", text="⏳ OLUŞTURULUYOR...")
        self.progress_bar.set(0)
        self.lbl_status.configure(text="Başlatılıyor...", text_color="#f39c12")

        thread = threading.Thread(target=self._run_generation, daemon=True)
        thread.start()

    def _run_generation(self):
        try:
            try:
                fps = int(self.entry_fps.get().strip())
            except Exception:
                fps = int(self.slider_fps.get())

            rom_mode = "horizontal_right"
            if hasattr(self, "opt_rom_mode") and hasattr(self, "rom_mode_map"):
                rom_mode = self.rom_mode_map.get(self.opt_rom_mode.get(), "horizontal_right")

            # UI'da seçili FPS ile hafızadaki karelerin FPS'i uyuşmuyorsa, tam senkronize yeniden çıkart
            if getattr(self, "_loaded_fps", None) != fps:
                w, h = self._get_current_dimensions()
                max_f = self._get_max_frames_val()
                if self.selected_file_path and os.path.exists(self.selected_file_path):
                    frames = extract_video_frames(
                        self.selected_file_path, width=w, height=h, target_fps=fps, max_frames=max_f, keep_aspect=False
                    )
                else:
                    frames = generate_procedural_demo(width=w, height=h, fps=fps, max_frames=max_f)
                self.loaded_frames = frames
                self.total_frames_count = len(frames)
                self._loaded_fps = fps
            else:
                frames = self.loaded_frames

            part = self.selected_part_idx
            n_parts = self.num_parts
            conv = self.copy_convenience

            def progress_cb(text: str, fraction: float):
                self.after(0, lambda t=text, f=fraction: self._update_progress_ui(t, f))

            eng = getattr(self, "selected_engine", "v3")
            if eng == "v3":
                compile_fn = compile_blueprint_v3
            elif eng == "v1":
                compile_fn = compile_blueprint_v1
            else:
                compile_fn = compile_blueprint_v2

            compile_kwargs = {
                "fps": fps,
                "rom_mode": rom_mode,
                "part_idx": part,
                "num_parts": n_parts,
                "copy_convenience": conv,
                "compact_rom": getattr(self, "compact_rom", True),
                "fill_all_rows": getattr(self, "fill_all_rows", False),
                "progress_callback": progress_cb
            }
            if eng == "v3":
                compile_kwargs["substation_quality"] = getattr(self, "substation_quality", "normal")

            bp_str, meta = compile_fn(frames, **compile_kwargs)
            # Uyumluluk: eski anahtarları taklit et
            if 'compile_f_start' not in meta:
                meta['compile_f_start'] = meta.get('compile_p_start', meta.get('f_start', 0)) * (3 if eng == "v2" else 1)
            if 'compile_f_end' not in meta:
                meta['compile_f_end'] = meta.get('compile_p_end', meta.get('f_end', 0)) * (3 if eng == "v2" else 1)

            self.part_blueprints[part] = (bp_str, meta)
            self.after(0, lambda p=part, m=meta: self._on_generation_success(p, m))
        except Exception as e:
            err_msg = str(e)
            import traceback
            traceback.print_exc()
            self.after(0, lambda msg=err_msg: self._on_generation_error(msg))
        finally:
            self.is_compiling = False

    def _update_progress_ui(self, text: str, fraction: float):
        self.progress_bar.set(fraction)
        self.lbl_status.configure(text=text)

    def _on_generation_success(self, part_idx: int, meta: Dict[str, Any]):
        self.btn_generate.configure(state="normal", text="⚡ SEÇİLİ PARÇAYI OLUŞTUR")
        self.lbl_status.configure(
            text=f"✓ Parça {part_idx + 1}/{self.num_parts} başarıyla oluşturuldu ve panoya kopyalandı!",
            text_color="#2ecc71"
        )

        bp_str, _ = self.part_blueprints[part_idx]
        copied = copy_to_clipboard(bp_str)
        if copied:
            self.btn_copy.configure(text=f"✓ Parça {part_idx + 1} Kopyalandı!", fg_color="#27ae60")
            self.after(3000, lambda: self.btn_copy.configure(text="📋 Seçili Parçayı Kopyala", fg_color="#2980b9"))

        # Bilgilendirme Kutusu
        part_desc = "Monitör + Saat + ROM Dilimi 1" if part_idx == 0 else f"ROM Kombinatör Dilimi {part_idx + 1}"
        conv_info = "Evet (+1 Ortak Sütun / Hizalama)" if (part_idx > 0 and self.copy_convenience) else "Hayır"
        eng = getattr(self, "selected_engine", "v3")
        if eng == "v3":
            eng_title = "Engine V3 (2-Bit Grayscale • 16 Kare/Sinyal)"
            range_info = f"• Kare Aralığı: Kare {meta.get('compile_f_start', meta.get('f_start', '?'))} .. {meta.get('compile_f_end', meta.get('f_end', '?')) - 1}\n"
            summary_info = f"• Toplam Kare: {meta.get('total_frames', '?')} kare (16 kare/sinyal)\n"
        elif eng == "v2":
            eng_title = "Engine V2 (27-Bit Zamansal Paketleme)"
            range_info = f"• Pack Aralığı: Pack {meta.get('compile_p_start', '?')} .. {meta.get('compile_p_end', '?') - 1} ({meta.get('frames_per_pack', 3)} kare/pack)\n"
            summary_info = f"• Toplam Paket: {meta.get('total_packs', '?')} pack = {meta.get('total_frames', '?')} kare\n"
        else:
            eng_title = "Engine V1 (Klasik RGB24)"
            range_info = f"• Kare Aralığı: Kare {meta.get('compile_f_start', meta.get('f_start', '?'))} .. {meta.get('compile_f_end', meta.get('f_end', '?')) - 1}\n"
            summary_info = f"• Toplam Kare: {meta.get('total_frames', '?')} kare (1 kombinatör/kare)\n"

        compact_str = "Kompakt (0'a 0 Boşluksuz)" if meta.get('compact_rom', getattr(self, "compact_rom", True)) else "Standart (Aralıklı)"
        if meta.get('fill_all_rows', getattr(self, "fill_all_rows", False)):
            compact_str += " + Tüm Satırlar Dolu (Çok Satırlı)"
        if meta.get('substation_quality') == 'none':
            sub_qual_str = "Trafo Yok (Harici Güç)"
        else:
            sub_qual_str = meta.get('substation_quality', getattr(self, 'substation_quality', 'legendary')).capitalize()
            if 'substation_step' in meta and meta['substation_step'] > 0:
                sub_qual_str += f" ({meta['substation_step']}x{meta['substation_step']} karo alan, {meta['substation_reach']} tel menzili)"
        messagebox.showinfo(
            "Başarılı!",
            f"Factorio 2.0 Blueprint Parçası Hazır! ({eng_title})\n\n"
            f"• Motor: {eng_title}\n"
            f"• ROM Düzeni: {compact_str}\n"
            f"• Trafo Niteliği: {sub_qual_str}\n"
            f"• Parça: {part_idx + 1} / {self.num_parts} ({part_desc})\n"
            f"{range_info}"
            f"• Kopyalama Kolaylığı: {conv_info}\n"
            f"• Toplam Varlık: {meta.get('num_entities', meta.get('total_entities', meta.get('entities_count', 0))):,} adet\n"
            f"• Toplam Tel: {meta.get('num_wires', meta.get('total_wires', 0)):,} adet\n"
            f"{summary_info}\n"
            f"Blueprint metni otomatik olarak panonuza (Ctrl + V) kopyalandı.\n"
            f"Oyunda bir önceki parçanın üzerine yapıştırabilirsiniz."
        )

    def _on_generation_error(self, err_msg: str):
        self.btn_generate.configure(state="normal", text="⚡ SEÇİLİ PARÇAYI OLUŞTUR")
        self.lbl_status.configure(text="Hata oluştu!", text_color="#e74c3c")
        messagebox.showerror("Hata", f"Blueprint oluşturulurken bir hata oluştu:\n{err_msg}")

    def _on_copy_clipboard(self):
        p = self.selected_part_idx
        if p not in self.part_blueprints:
            self._start_generation_thread()
            return

        bp_str, _ = self.part_blueprints[p]
        if copy_to_clipboard(bp_str):
            self.btn_copy.configure(text=f"✓ Parça {p + 1} Kopyalandı!", fg_color="#27ae60")
            self.after(2000, lambda: self.btn_copy.configure(text="📋 Seçili Parçayı Kopyala", fg_color="#2980b9"))

    def _on_save_file(self):
        p = self.selected_part_idx
        if p not in self.part_blueprints:
            messagebox.showwarning("Uyarı", "Lütfen önce 'Seçili Parçayı Oluştur' butonuna basın.")
            return

        bp_str, meta = self.part_blueprints[p]
        default_name = f"blueprint_part_{p + 1}_of_{self.num_parts}.txt"
        path = filedialog.asksaveasfilename(
            title=f"Parça {p + 1} Blueprint'ini Kaydet",
            initialfile=default_name,
            defaultextension=".txt",
            filetypes=[("Text Dosyası", "*.txt"), ("Tüm Dosyalar", "*.*")]
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(bp_str)
            messagebox.showinfo("Kaydedildi", f"Parça {p + 1} dosyaya kaydedildi:\n{path}")


def launch_gui():
    app = FactorioVideoApp()
    app.mainloop()


if __name__ == "__main__":
    launch_gui()
