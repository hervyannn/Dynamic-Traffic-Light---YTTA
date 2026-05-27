"""
config.py
=========
Konfigurasi statis dan path file untuk sistem Dynamic Traffic Light AI.
Semua konstanta dan parameter yang dapat disesuaikan terpusat di sini.
"""

import os

# ─────────────────────────────────────────────
#  PATH FILE
# ─────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "models", "best.pt")

VIDEO_PATHS = [
    os.path.join(BASE_DIR, "videos", "cctv_jalur1.mp4"),
    os.path.join(BASE_DIR, "videos", "cctv_jalur2.mp4"),
    os.path.join(BASE_DIR, "videos", "cctv_jalur3.mp4"),
    os.path.join(BASE_DIR, "videos", "cctv_jalur4.mp4"),
]

# ─────────────────────────────────────────────
#  KONFIGURASI SERVER
# ─────────────────────────────────────────────
HOST        = "0.0.0.0"
PORT        = 5000
DEBUG       = False          # Jangan True saat pakai threading + SocketIO
SECRET_KEY  = "traffic-ai-secret-2024"

# ─────────────────────────────────────────────
#  NAMA DEFAULT JALUR
# ─────────────────────────────────────────────
DEFAULT_LANE_NAMES = [
    "Jalur 1",
    "Jalur 2",
    "Jalur 3",
    "Jalur 4",
]

DEFAULT_ROAD_NAMES = [
    "Jl. Utama Barat",
    "Jl. Utama Timur",
    "Jl. Utama Selatan",
    "Jl. Utama Utara",
]

NUM_LANES = 4

# ─────────────────────────────────────────────
#  PEMBOBOTAN KENDARAAN
# ─────────────────────────────────────────────
VEHICLE_WEIGHTS = {
    "motorcycle": 1,
    "car":        2,
    "truck":      3,
    "bus":        3,
}

# ─────────────────────────────────────────────
#  PARAMETER ALGORITMA WAKTU HIJAU ADAPTIF
# ─────────────────────────────────────────────
W_MIN_DEFAULT    = 10     # detik — batas bawah waktu hijau
W_MAX_DEFAULT    = 120    # detik — batas atas waktu hijau
DT_DEFAULT       = 0.5    # detik per poin — faktor skala

# ─────────────────────────────────────────────
#  DURASI LAMPU MERAH & KUNING (detik)
# ─────────────────────────────────────────────
RED_MIN_DEFAULT    = 30
RED_MAX_DEFAULT    = 150
YELLOW_DURATION    = 3    # durasi tetap lampu kuning

# ─────────────────────────────────────────────
#  KONFIGURASI VISION ENGINE
# ─────────────────────────="────────────────────
JPEG_QUALITY       = 85   # kualitas kompresi JPEG untuk stream
VISION_FPS_TARGET  = 30   # target FPS vision thread
CONFIDENCE_THRESH  = 0.4  # confidence threshold inferensi YOLOv8

# ─────────────────────────────────────────────
#  INTERVAL BROADCAST (detik)
# ─────────────────────────────────────────────
TIMER_INTERVAL     = 1.0  # countdown broadcast setiap 1 detik
