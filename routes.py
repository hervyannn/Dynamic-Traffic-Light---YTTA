"""
routes.py
=========
Semua endpoint HTTP dan event handler Socket.IO.
Tidak mengimport `app` atau `socketio` — keduanya diterima sebagai
parameter fungsi `register_routes()` untuk menghindari circular import.

JANGAN gunakan jsonify() di dalam thread latar belakang.
Di sini jsonify hanya dipakai di endpoint HTTP (dalam request context).
"""

from flask          import Response, render_template, jsonify
from flask_socketio import SocketIO

from state          import state
from vision_engine  import generate_mjpeg
from traffic_logic  import calculate_w_hijau


def register_routes(app, socketio: SocketIO):
    """
    Daftarkan semua route HTTP dan event SocketIO ke instance Flask & SocketIO
    yang diberikan.
    """

    # ── HTTP Routes ───────────────────────────────────────────────────────────

    @app.route("/")
    def index():
        """Halaman utama — sajikan dashboard.html dari folder templates."""
        return render_template("dashboard.html")

    @app.route("/video_feed/<int:lane_id>")
    def video_feed(lane_id: int):
        """
        MJPEG stream untuk satu jalur.
        URL: /video_feed/0  /video_feed/1  /video_feed/2  /video_feed/3
        Dipanggil oleh tag <img src="/video_feed/{idx}"> di frontend.
        """
        if lane_id < 0 or lane_id >= len(state.frames):
            return Response("Lane not found", status=404)

        return Response(
            generate_mjpeg(lane_id),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )

    @app.route("/api/state")
    def api_state():
        """REST endpoint opsional — kembalikan snapshot state saat ini."""
        return jsonify(state.to_payload())

    # ── Socket.IO Events ──────────────────────────────────────────────────────

    @socketio.on("connect")
    def on_connect():
        """
        Client baru tersambung — kirim snapshot state terkini agar UI
        langsung terupdate tanpa menunggu event berikutnya.
        """
        payload = state.to_payload()
        socketio.emit("status_update", payload)

    @socketio.on("disconnect")
    def on_disconnect():
        print("[SocketIO] Client terputus.")

    @socketio.on("start_system")
    def on_start_system():
        """
        Frontend mengirim event ini ketika tombol '▶ Mulai' diklik.
        Mengaktifkan flag state.running sehingga traffic_cycle_thread
        mulai berjalan.
        """
        with state.lock:
            state.running = True
        print("[Routes] Sistem DIMULAI.")
        socketio.emit("status_update", state.to_payload())

    @socketio.on("stop_system")
    def on_stop_system():
        """
        Frontend mengirim event ini ketika tombol '⏸ Jeda' diklik.
        Menghentikan loop siklus lampu.
        """
        with state.lock:
            state.running = False
        print("[Routes] Sistem DIJEDA.")
        socketio.emit("status_update", state.to_payload())

    @socketio.on("update_road_name")
    def on_update_road_name(data: dict):
        """
        Frontend mengirim: { lane_id: int, name: str }
        Perbarui nama jalan jalur tersebut dan broadcast kembali.

        Frontend mendengarkan event 'road_updated' dengan payload
        { lane_id, name } untuk memperbarui UI secara parsial.
        """
        lane_id = data.get("lane_id")
        name    = data.get("name", "").strip()

        if lane_id is None or not (0 <= lane_id < len(state.lanes)):
            return
        if not name:
            return

        with state.lock:
            state.lanes[lane_id].road = name

        print(f"[Routes] Nama jalan jalur {lane_id} diubah ke '{name}'.")

        # Broadcast ke semua client (sesuai listener 'road_updated' di JS)
        socketio.emit("road_updated", {"lane_id": lane_id, "name": name})

    @socketio.on("change_tab")
    def on_change_tab(data: dict):
        """
        *** EVENT BARU — On-Demand AI Inference ***

        Frontend mengirim: { tab_index: int }  ketika user klik tab jalur.
        Backend memperbarui state.active_tab_view sehingga Vision Thread
        hanya menjalankan inferensi AI pada jalur tab yang aktif.

        Instruksi penyisipan ke dashboard.html:
        ┌─────────────────────────────────────────────────────────────────┐
        │  Tambahkan SATU BARIS ini di dalam fungsi switchTab(idx)        │
        │  tepat setelah baris  streamImg.src = `/video_feed/${idx}`;     │
        │                                                                 │
        │    socket.emit('change_tab', { tab_index: idx });               │
        └─────────────────────────────────────────────────────────────────┘
        """
        tab_index = data.get("tab_index", 0)

        if not isinstance(tab_index, int):
            return
        if not (0 <= tab_index < len(state.lanes)):
            return

        state.active_tab_view = tab_index
        print(f"[Routes] Active tab view → Jalur {tab_index}.")
