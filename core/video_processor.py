import io
import os
from typing import List, Tuple, Optional
from PIL import Image

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

# ---------------------------------------------------------------------------
# Tip alias: kare verisi artık bytes (JPEG) olarak saklanır.
# Bu sayede 480p × 3600 kare = ~4 GB yerine ~200 MB bellekte tutulur.
# ---------------------------------------------------------------------------
FrameBytes = bytes


def _pil_to_jpeg_bytes(img: Image.Image, quality: int = 80) -> FrameBytes:
    """PIL Image → JPEG bytes (sıkıştırılmış, düşük bellek)."""
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=quality, optimize=False)
    return buf.getvalue()


def frame_bytes_to_image(fb: FrameBytes) -> Image.Image:
    """JPEG bytes → PIL Image (görüntüleme / blueprint üretimi için)."""
    return Image.open(io.BytesIO(fb)).convert("RGB")


def extract_video_frames(
    video_path: str,
    width: int,
    height: int,
    target_fps: int = 5,
    max_frames: Optional[int] = None,
    keep_aspect: bool = False,
    progress_callback=None
) -> List[FrameBytes]:
    """
    Video veya GIF dosyasından belirtilen çözünürlük ve FPS'e göre kareleri ayıklar.
    max_frames None veya <= 0 ise sınır olmaksızın tüm video karelerini alır.

    Dönen liste: her eleman bir JPEG bytes nesnesidir (PIL Image değil).
    frame_bytes_to_image() ile PIL Image'e dönüştürülebilir.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Dosya bulunamadı: {video_path}")

    ext = os.path.splitext(video_path)[1].lower()
    frames: List[FrameBytes] = []

    def resize_frame(img: Image.Image) -> Image.Image:
        if keep_aspect:
            img_ratio = img.width / img.height
            target_ratio = width / height
            if img_ratio > target_ratio:
                new_w = width
                new_h = max(1, int(round(width / img_ratio)))
            else:
                new_h = height
                new_w = max(1, int(round(height * img_ratio)))
            resized = img.resize((new_w, new_h), Image.Resampling.BILINEAR)
            canvas = Image.new("RGB", (width, height), (0, 0, 0))
            canvas.paste(resized, ((width - new_w) // 2, (height - new_h) // 2))
            return canvas
        else:
            return img.resize((width, height), Image.Resampling.BILINEAR)

    safe_target_fps = max(1, min(60, int(round(target_fps))))
    factorio_fps = float(safe_target_fps)

    if ext == ".gif":
        with Image.open(video_path) as im:
            total_available = getattr(im, "n_frames", 1)
            duration_ms = im.info.get("duration", 0)
            if not duration_ms or duration_ms <= 0:
                try:
                    im.seek(0)
                    duration_ms = im.info.get("duration", 100)
                except Exception:
                    duration_ms = 100
            if not duration_ms or duration_ms <= 0:
                duration_ms = 100
            gif_fps = 1000.0 / duration_ms if duration_ms > 0 else 10.0

            k = 0
            curr_src_idx = -1
            cached_frame = None
            est_total = min(max_frames, int(total_available * factorio_fps / gif_fps)) if max_frames else int(total_available * factorio_fps / gif_fps)

            while max_frames is None or max_frames <= 0 or len(frames) < max_frames:
                target_src_idx = int(round(k * (gif_fps / factorio_fps)))
                if target_src_idx >= total_available:
                    break
                if target_src_idx == curr_src_idx and cached_frame is not None:
                    frames.append(cached_frame)
                else:
                    im.seek(target_src_idx)
                    frame = resize_frame(im.convert("RGB"))
                    cached_frame = _pil_to_jpeg_bytes(frame)
                    frames.append(cached_frame)
                    curr_src_idx = target_src_idx
                if progress_callback:
                    progress_callback(len(frames), max(1, est_total))
                k += 1
    elif HAS_CV2:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"OpenCV dosyayı açamadı: {video_path}")

        orig_fps = cap.get(cv2.CAP_PROP_FPS)
        if orig_fps <= 0 or orig_fps > 240:
            orig_fps = 30.0

        total_cap_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        est_total = min(max_frames, int(total_cap_frames * factorio_fps / orig_fps)) if max_frames else int(total_cap_frames * factorio_fps / orig_fps)

        k = 0
        curr_src_idx = -1
        cached_frame = None

        while cap.isOpened() and (max_frames is None or max_frames <= 0 or len(frames) < max_frames):
            target_src_idx = int(round(k * (orig_fps / factorio_fps)))
            if total_cap_frames > 0 and target_src_idx >= total_cap_frames:
                break

            if target_src_idx == curr_src_idx and cached_frame is not None:
                frames.append(cached_frame)
            else:
                while curr_src_idx < target_src_idx:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    curr_src_idx += 1
                    if curr_src_idx == target_src_idx:
                        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        pil_img = resize_frame(Image.fromarray(rgb_frame))
                        cached_frame = _pil_to_jpeg_bytes(pil_img)
                        break
                if curr_src_idx != target_src_idx or cached_frame is None:
                    break
                frames.append(cached_frame)

            if progress_callback:
                progress_callback(len(frames), max(1, est_total))
            k += 1

        cap.release()
    else:
        with Image.open(video_path) as im:
            frame = resize_frame(im.convert("RGB"))
            frames.append(_pil_to_jpeg_bytes(frame))
            if progress_callback:
                progress_callback(1, 1)

    if not frames:
        raise ValueError("Videodan hiçbir kare okunamadı!")

    return frames


def generate_procedural_demo(
    width: int = 16,
    height: int = 16,
    num_frames: Optional[int] = None,
    fps: int = 5,
    duration: float = 3.2,
    max_frames: Optional[int] = None
) -> List[FrameBytes]:
    """Dönen parlak nokta ve dinamik renk dalgalarından oluşan test animasyonu üretir.
    FPS değiştiğinde animasyon hızını sabit (süreye bağlı) tutar, ağır çekime geçmez.
    """
    import math
    safe_fps = max(1, min(60, int(round(fps))))
    factorio_fps = float(safe_fps)

    if num_frames is not None and num_frames > 0:
        total_f = num_frames
    else:
        total_f = max(1, int(round(duration * factorio_fps)))
        if max_frames and max_frames > 0:
            total_f = min(total_f, max_frames)

    frames = []
    cx, cy = width / 2.0, height / 2.0
    radius = min(width, height) / 3.2

    for f in range(total_f):
        img = Image.new("RGB", (width, height), (10, 10, 20))
        pixels = img.load()
        t_sec = f / factorio_fps
        angle = (2 * math.pi * t_sec) / duration

        bx = cx + radius * math.cos(angle)
        by = cy + radius * math.sin(angle)

        for y in range(height):
            for x in range(width):
                dist = math.sqrt((x - bx) ** 2 + (y - by) ** 2)
                if dist < 2.0:
                    pixels[x, y] = (255, int(220 * (1 - dist / 2.0)), 30)
                else:
                    r = int(40 + 35 * math.sin(x * 0.4 + angle))
                    g = int(40 + 35 * math.sin(y * 0.4 + angle * 1.5))
                    b = int(100 + 50 * math.cos(angle))
                    pixels[x, y] = (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))
        frames.append(_pil_to_jpeg_bytes(img))
    return frames


def get_media_info(file_path: str) -> dict:
    """Video veya GIF dosyasının çözünürlük, FPS, toplam kare ve süre bilgilerini ayıklar."""
    default_info = {
        "width": 16,
        "height": 16,
        "orig_w": 16,
        "orig_h": 16,
        "fps": 30.0,
        "total_frames": 1,
        "duration": 0.0,
        "format": "UNKNOWN"
    }
    if not os.path.exists(file_path):
        return default_info

    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".gif":
        try:
            with Image.open(file_path) as im:
                w, h = im.width, im.height
                n_frames = getattr(im, "n_frames", 1)
                dur_ms = im.info.get("duration", 100)
                fps = round(1000.0 / dur_ms, 2) if dur_ms > 0 else 10.0
                dur = round(n_frames / fps, 2) if fps > 0 else 0.0
                return {
                    "width": w,
                    "height": h,
                    "orig_w": w,
                    "orig_h": h,
                    "fps": fps,
                    "total_frames": n_frames,
                    "duration": dur,
                    "format": "GIF"
                }
        except Exception:
            pass

    if HAS_CV2:
        try:
            cap = cv2.VideoCapture(file_path)
            if cap.isOpened():
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps_val = cap.get(cv2.CAP_PROP_FPS)
                if fps_val <= 0 or fps_val > 240:
                    fps_val = 30.0
                fps = round(fps_val, 2)
                count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                dur = round(count / fps, 2) if fps > 0 else 0.0
                cap.release()
                if w > 0 and h > 0:
                    return {
                        "width": w,
                        "height": h,
                        "orig_w": w,
                        "orig_h": h,
                        "fps": fps,
                        "total_frames": count,
                        "duration": dur,
                        "format": ext.upper().lstrip(".")
                    }
        except Exception:
            pass

    try:
        with Image.open(file_path) as im:
            return {
                "width": im.width,
                "height": im.height,
                "orig_w": im.width,
                "orig_h": im.height,
                "fps": 30.0,
                "total_frames": 1,
                "duration": 0.0,
                "format": ext.upper().lstrip(".")
            }
    except Exception:
        return default_info


def get_media_dimensions(file_path: str) -> Tuple[int, int]:
    """Video veya GIF dosyasının orijinal çözünürlüğünü (genişlik, yükseklik) döndürür."""
    info = get_media_info(file_path)
    return info["width"], info["height"]
