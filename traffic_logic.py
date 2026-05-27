"""
traffic_logic.py
================
Logika timer lampu hijau adaptif dan siklus persimpangan.
Berjalan di Thread-2 (Timer Thread) — countdown 1 detik.

Algoritma:
  W_hijau = clamp(W_min + Total_Poin * dt,  W_min,  W_max)

Siklus per jalur:
  RED  →  GREEN  →  YELLOW  →  (pindah ke jalur berikutnya)
"""

import time
import threading

from config import TIMER_INTERVAL
from state  import state   # singleton


# ── Kalkulasi Waktu Hijau Adaptif ─────────────────────────────────────────────

def calculate_w_hijau(total_poin: int) -> int:
    """
    Hitung durasi lampu hijau (detik) berdasarkan poin kepadatan.

    W_hijau = clamp(W_min + total_poin * dt,  W_min,  W_max)
    """
    raw = state.w_min + total_poin * state.dt
    return int(max(state.w_min, min(state.w_max, raw)))


# ── Recalculate timers for all non-active (RED) lanes ────────────────────────

# def _recalculate_red_timers():
#     """
#     Hitung ulang timer merah untuk semua jalur yang tidak sedang hijau.
#     Timer merah = sum(w_hijau + w_kuning) untuk semua jalur setelah mereka,
#     sampai giliran mereka tiba kembali.

#     Implementasi sederhana: total waktu satu siklus dikurangi giliran aktif.
#     """
#     # Kumpulkan estimasi w_hijau semua jalur
#     w_list = []
#     for lane in state.lanes:
#         w_list.append(calculate_w_hijau(lane.total_poin))

#     # Hitung merah untuk setiap jalur non-aktif
#     num = len(state.lanes)
#     active = state.active_lane

#     for i, lane in enumerate(state.lanes):
#         if i == active:
#             continue  # jalur aktif diatur di loop utama

#         # Hitung berapa detik sampai giliran jalur i
#         wait = 0
#         # Dari jalur aktif, iterasi ke depan hingga mencapai jalur i
#         j = active
#         while True:
#             wait += w_list[j] + state.yellow_dur
#             j = (j + 1) % num
#             if j == i:
#                 break

#         lane.timer_red = max(state.red_min, min(state.red_max, wait))

def _recalculate_red_timers():
    # Kumpulkan estimasi prediksi waktu hijau secara REAL-TIME berdasarkan poin AI
    w_list = []
    for lane in state.lanes:
        w = calculate_w_hijau(lane.total_poin)
        lane.w_hijau_calculated = w  # Simpan hasil prediksi untuk dikirim ke HTML
        w_list.append(w)

    num = len(state.lanes)
    active = state.active_lane

    for i, lane in enumerate(state.lanes):
        # [REVISI 3] Jika jalur sedang aktif (hijau/kuning), lampu merah PASTI 0
        if i == active:
            lane.timer_red = 0
            continue

        # [REVISI 3] Jika jalur tidak aktif (merah), lampu hijau PASTI 0
        lane.timer_green = 0

        # [REVISI 2] Kalkulasi sisa waktu merah secara berantai
        wait = 0
        j = active
        while True:
            if j == active:
                # Sisa waktu PASTI dari jalur yang sedang menyala
                wait += state.lanes[active].timer_green + state.lanes[active].timer_yellow
            else:
                # Waktu PREDIKSI dari jalur antrean di depannya
                wait += w_list[j] + state.yellow_dur

            j = (j + 1) % num
            if j == i:
                break

        lane.timer_red = wait


# ── Thread utama siklus lampu ─────────────────────────────────────────────────

def traffic_cycle_thread(socketio):
    """
    Thread-2: Berjalan selamanya (selama state.running True).
    Setiap detik melakukan countdown dan broadcast ke frontend via SocketIO.

    Parameter:
        socketio — instance Flask-SocketIO (dikirim dari main.py)
    """

    def broadcast():
        payload = state.to_payload()
        socketio.emit("timer_update", payload)

    while True:
        # Tunggu sampai sistem dijalankan
        while not state.running:
            time.sleep(0.2)

        # ── Inisialisasi giliran jalur aktif ─────────────────────────────
        with state.lock:
            active = state.active_lane
            lane   = state.lanes[active]

            # Hitung w_hijau untuk jalur ini berdasarkan deteksi terkini
            w_green = calculate_w_hijau(lane.total_poin)
            lane.w_hijau_calculated = w_green

            # Set state semua lampu
            for i, l in enumerate(state.lanes):
                l.light_state = "green" if i == active else "red"

            lane.timer_green  = w_green
            lane.timer_yellow = state.yellow_dur
            _recalculate_red_timers()

        broadcast()

        # ── FASE HIJAU: countdown detik demi detik ───────────────────────
        for _ in range(w_green):
            if not state.running:
                break
            time.sleep(TIMER_INTERVAL)

            with state.lock:
                lane = state.lanes[state.active_lane]
                lane.timer_green = max(0, lane.timer_green - 1)

                _recalculate_red_timers()

                # Countdown merah jalur lainnya
                # for i, l in enumerate(state.lanes):
                #     if i != state.active_lane:
                #         l.timer_red = max(0, l.timer_red - 1)

            broadcast()

        if not state.running:
            continue
        
        # ── FASE KUNING ──────────────────────────────────────────────────
        with state.lock:
            lane = state.lanes[state.active_lane]
            lane.light_state  = "yellow"
            lane.timer_yellow = state.yellow_dur
            lane.timer_green  = 0
            
        broadcast()

        for _ in range(state.yellow_dur):
            if not state.running:
                break
            time.sleep(TIMER_INTERVAL)

            with state.lock:
                lane = state.lanes[state.active_lane]
                lane.timer_yellow = max(0, lane.timer_yellow - 1)

                # [REVISI] Kalkulasi prediksi waktu merah & hijau secara real-time
                _recalculate_red_timers()

            broadcast()

        # ── FASE KUNING ──────────────────────────────────────────────────
        # with state.lock:
        #     lane = state.lanes[state.active_lane]
        #     lane.light_state  = "yellow"
        #     lane.timer_yellow = state.yellow_dur
        #     lane.timer_green  = 0

        # broadcast()

        # for _ in range(state.yellow_dur):
        #     if not state.running:
        #         break
        #     time.sleep(TIMER_INTERVAL)

        #     with state.lock:
        #         lane = state.lanes[state.active_lane]
        #         lane.timer_yellow = max(0, lane.timer_yellow - 1)

        #         for i, l in enumerate(state.lanes):
        #             if i != state.active_lane:
        #                 l.timer_red = max(0, l.timer_red - 1)

        #     broadcast()


        if not state.running:
            continue

        # ── PINDAH KE JALUR BERIKUTNYA ───────────────────────────────────
        with state.lock:
            old_active = state.active_lane
            state.lanes[old_active].light_state = "red"
            state.active_lane = (state.active_lane + 1) % len(state.lanes)

            # Naikkan siklus setiap kali kembali ke jalur 0
            if state.active_lane == 0:
                state.siklus += 1

        broadcast()


def start_traffic_thread(socketio) -> threading.Thread:
    """Buat dan jalankan Timer Thread. Dipanggil dari main.py."""
    t = threading.Thread(
        target=traffic_cycle_thread,
        args=(socketio,),
        daemon=True,
        name="TimerThread",
    )
    t.start()
    return t
