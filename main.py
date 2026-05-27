"""
main.py
=======
Entry point — inisialisasi Flask + SocketIO, daftarkan routes, dan
jalankan kedua background thread sebelum server dimulai.

Arsitektur 3-Thread:
  [1] Main Web Thread   — Flask + SocketIO request handler (di sini)
  [2] Timer Thread      — countdown lampu & broadcast timer_update
  [3] Vision Thread     — baca frame video + inferensi YOLOv8 on-demand

Anti-circular import:
  app & socketio dibuat DI SINI lalu diteruskan ke register_routes(),
  start_traffic_thread(), dan start_vision_thread(). Tidak ada modul
  lain yang mengimport `app` atau `socketio` secara langsung.
"""

from flask          import Flask
from flask_socketio import SocketIO

from config         import HOST, PORT, SECRET_KEY
from routes         import register_routes
from traffic_logic  import start_traffic_thread
from vision_engine  import start_vision_thread


# ── Buat instance Flask & SocketIO ────────────────────────────────────────────

app = Flask(__name__, template_folder="templates")
app.config["SECRET_KEY"] = SECRET_KEY

# async_mode='threading' — wajib agar background thread bisa emit event
socketio = SocketIO(
    app,
    async_mode="threading",
    cors_allowed_origins="*",
    logger=False,
    engineio_logger=False,
)


# ── Daftarkan routes & event handler ─────────────────────────────────────────

register_routes(app, socketio)


# ── Jalankan background threads ───────────────────────────────────────────────

start_traffic_thread(socketio)   # Thread-2: Timer countdown
start_vision_thread(socketio)    # Thread-3: Vision + AI inference


# ── Run server ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"[Main] Server berjalan di http://{HOST}:{PORT}")
    print("[Main] Tekan Ctrl+C untuk menghentikan.")
    socketio.run(
        app,
        host=HOST,
        port=PORT,
        debug=False,       # HARUS False agar threading stabil
        use_reloader=False,
        allow_unsafe_werkzeug=True,
    )
