"""
vision_engine.py
================
Thread-3: Vision Thread — membaca frame video, menjalankan inferensi
YOLOv8 hanya pada jalur yang tab-nya aktif di frontend, dan menyimpan
frame JPEG ter-encode ke state.frames[i].

Optimasi On-Demand:
  - model.predict() hanya dijalankan untuk state.active_tab_view.
  - Untuk jalur lain: cap.read() tetap dipanggil agar video loop tidak
    macet, namun frame tidak diproses AI.
"""

import time
import threading
import cv2
import numpy as np

from config import (
    MODEL_PATH,
    VIDEO_PATHS,
    JPEG_QUALITY,
    VISION_FPS_TARGET,
    CONFIDENCE_THRESH,
    VEHICLE_WEIGHTS,
)
from state import state


# ─────────────────────────────────────────────────────────────────────────────
#  LOAD MODEL (aman dari circular import — hanya dijalankan saat modul diimport)
# ─────────────────────────────────────────────────────────────────────────────

def _load_model():
    """
    Muat model YOLOv8 dengan safe globals PyTorch agar best.pt bisa dimuat
    tanpa peringatan/error serialisasi.
    """
    import torch
    import ultralytics
    import ultralytics.nn.tasks

    torch.serialization.add_safe_globals(
        [ultralytics.nn.tasks.DetectionModel]
    )

    from ultralytics import YOLO
    model = YOLO(MODEL_PATH)
    return model


# ─────────────────────────────────────────────────────────────────────────────
#  HELPER: anotasi frame dengan bounding box hasil deteksi
# ─────────────────────────────────────────────────────────────────────────────

_COLOR_MAP = {
    "motorcycle": (0,  165, 255),   # oranye
    "car":        (255, 87,  34),   # biru-tua
    "truck":      ( 76,  17, 235),  # merah
    "bus":        (170,  0, 255),   # ungu
}

def _annotate_frame(frame: np.ndarray, results) -> tuple[np.ndarray, dict]:
    """
    Gambar bounding box + label pada frame, hitung counts kendaraan.

    Returns:
        annotated_frame, counts_dict
    """
    counts = {k: 0 for k in VEHICLE_WEIGHTS}

    for result in results:
        for box in result.boxes:
            conf = float(box.conf[0])
            if conf < CONFIDENCE_THRESH:
                continue

            cls_name = result.names[int(box.cls[0])].lower()
            if cls_name not in VEHICLE_WEIGHTS:
                continue

            counts[cls_name] += 1

            x1, y1, x2, y2 = map(int, box.xyxy[0])
            color = _COLOR_MAP.get(cls_name, (200, 200, 200))
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            label = f"{cls_name} {conf:.2f}"
            cv2.putText(
                frame, label, (x1, max(y1 - 6, 12)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA
            )

    return frame, counts


# ─────────────────────────────────────────────────────────────────────────────
#  FALLBACK FRAME: frame gelap dengan teks "Tidak ada video"
# ─────────────────────────────────────────────────────────────────────────────

def _make_blank_frame(lane_id: int) -> bytes:
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(
        img,
        f"Jalur {lane_id + 1} — Video tidak tersedia",
        (60, 240),
        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (80, 80, 80), 2,
    )
    _, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
    return buf.tobytes()


# ─────────────────────────────────────────────────────────────────────────────
#  VISION THREAD UTAMA
# ─────────────────────────────────────────────────────────────────────────────

def vision_thread_func(socketio):
    """
    Thread-3: Berjalan terus (daemon). Membuka semua capture, lalu loop
    membaca frame. Inferensi AI hanya dijalankan pada active_tab_view.

    socketio dipakai untuk emit 'data_update' setelah selesai inference.
    """
    frame_delay = 1.0 / VISION_FPS_TARGET

    # ── Buka semua VideoCapture ──────────────────────────────────────────────
    caps: list[cv2.VideoCapture | None] = []
    for path in VIDEO_PATHS:
        cap = cv2.VideoCapture(path)
        if cap.isOpened():
            caps.append(cap)
        else:
            print(f"[VisionEngine] Peringatan: tidak bisa membuka {path}")
            caps.append(None)

    # ── Set blank frame awal untuk semua jalur ───────────────────────────────
    for i in range(len(VIDEO_PATHS)):
        state.frames[i] = _make_blank_frame(i)

    # ── Load model ───────────────────────────────────────────────────────────
    model = None
    try:
        model = _load_model()
        print("[VisionEngine] Model YOLOv8 berhasil dimuat.")
    except Exception as e:
        print(f"[VisionEngine] Gagal memuat model: {e}. Berjalan tanpa AI.")

    # ── Loop utama ───────────────────────────────────────────────────────────
    while True:
        t_start = time.time()

        active_tab = state.active_tab_view   # tidak perlu lock (int, atomic)

        for i, cap in enumerate(caps):
            if cap is None:
                continue

            ret, frame = cap.read()
            if not ret:
                # Looping video: reset ke frame awal
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = cap.read()
                if not ret:
                    state.frames[i] = _make_blank_frame(i)
                    continue

            # ── On-demand inference: hanya jalur yang tab-nya aktif ──────────
            if i == active_tab and model is not None:
                try:
                    results = model.predict(
                        frame,
                        verbose=False,
                        conf=CONFIDENCE_THRESH,
                    )
                    frame, counts = _annotate_frame(frame, results)

                    # Update state (thread-safe)
                    with state.lock:
                        state.lanes[i].counts = counts

                    # Broadcast data update ke semua client
                    socketio.emit("data_update", state.to_payload())

                except Exception as e:
                    print(f"[VisionEngine] Error inferensi jalur {i}: {e}")

            # ── Encode JPEG dan simpan ke state.frames ───────────────────────
            try:
                _, buf = cv2.imencode(
                    ".jpg", frame,
                    [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
                )
                state.frames[i] = buf.tobytes()
            except Exception as e:
                print(f"[VisionEngine] Error encode JPEG jalur {i}: {e}")

        # ── Jaga target FPS ──────────────────────────────────────────────────
        elapsed = time.time() - t_start
        sleep_t = frame_delay - elapsed
        if sleep_t > 0:
            time.sleep(sleep_t)


# ─────────────────────────────────────────────────────────────────────────────
#  GENERATOR MJPEG untuk /video_feed/<lane_id>
# ─────────────────────────────────────────────────────────────────────────────

def generate_mjpeg(lane_id: int):
    """
    Generator yang menghasilkan multipart JPEG stream untuk route
    /video_feed/<lane_id>. Dipanggil dari routes.py (HTTP Response).
    """
    while True:
        frame_bytes = state.frames[lane_id]
        if frame_bytes is None:
            frame_bytes = _make_blank_frame(lane_id)

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + frame_bytes
            + b"\r\n"
        )
        time.sleep(1.0 / VISION_FPS_TARGET)


# ─────────────────────────────────────────────────────────────────────────────
#  LAUNCHER
# ─────────────────────────────────────────────────────────────────────────────

def start_vision_thread(socketio) -> threading.Thread:
    """Buat dan jalankan Vision Thread. Dipanggil dari main.py."""
    t = threading.Thread(
        target=vision_thread_func,
        args=(socketio,),
        daemon=True,
        name="VisionThread",
    )
    t.start()
    return t
