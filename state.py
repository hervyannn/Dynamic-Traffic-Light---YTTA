"""
state.py
========
Pusat data real-time sistem. Satu instance SystemState dipakai bersama
oleh semua modul (vision, traffic logic, routes) — tidak ada import
siklik karena modul lain hanya mengimport INSTANCE `state` dari sini.
"""

import threading
from config import (
    NUM_LANES,
    DEFAULT_LANE_NAMES,
    DEFAULT_ROAD_NAMES,
    W_MIN_DEFAULT,
    W_MAX_DEFAULT,
    DT_DEFAULT,
    RED_MIN_DEFAULT,
    RED_MAX_DEFAULT,
    YELLOW_DURATION,
    VEHICLE_WEIGHTS,
)


class LaneState:
    """Data real-time untuk satu jalur."""

    def __init__(self, lane_id: int):
        self.lane_id    = lane_id
        self.name       = DEFAULT_LANE_NAMES[lane_id]
        self.road       = DEFAULT_ROAD_NAMES[lane_id]

        # State lampu: 'red' | 'yellow' | 'green'
        self.light_state = "red"

        # Timer countdown (detik) — nilai yang ditampilkan di UI
        self.timer_red    = RED_MIN_DEFAULT
        self.timer_green  = W_MIN_DEFAULT
        self.timer_yellow = YELLOW_DURATION

        # Waktu hijau yang telah dikalkulasi (hasil algoritma adaptif)
        self.w_hijau_calculated = W_MIN_DEFAULT

        # Deteksi kendaraan
        self.counts: dict[str, int] = {k: 0 for k in VEHICLE_WEIGHTS}

    # ── Properti turunan ────────────────────────────────────────────────────

    @property
    def total_kendaraan(self) -> int:
        return sum(self.counts.values())

    @property
    def total_poin(self) -> int:
        return sum(self.counts[v] * w for v, w in VEHICLE_WEIGHTS.items())

    # ── Serialisasi ke dict (payload JSON untuk frontend) ───────────────────

    def to_dict(self) -> dict:
        return {
            "lane_id":       self.lane_id,
            "name":          self.name,
            "road":          self.road,
            "light_state":   self.light_state,
            "timer_red":     self.timer_red,
            "timer_green":   self.timer_green,
            "timer_yellow":  self.timer_yellow,
            "total_poin":    self.total_poin,
            "total_kendaraan": self.total_kendaraan,
            "w_hijau_calculated": self.w_hijau_calculated,
            "counts": dict(self.counts),
        }


class SystemState:
    """
    Satu-satunya sumber kebenaran (single source of truth) untuk
    seluruh data runtime sistem. Di-share lintas thread via lock.
    """

    def __init__(self):
        self.lock = threading.Lock()

        # Data per jalur
        self.lanes: list[LaneState] = [LaneState(i) for i in range(NUM_LANES)]

        # Jalur yang sedang aktif mendapat giliran hijau
        self.active_lane: int = 0

        # Siklus persimpangan (naik setiap jalur ke-4 selesai)
        self.siklus: int = 0

        # Apakah sistem sedang berjalan
        self.running: bool = False

        # Tab yang sedang aktif di frontend (untuk on-demand AI inference)
        self.active_tab_view: int = 0

        # Parameter batas waktu — bisa diubah via UI
        self.w_min      = W_MIN_DEFAULT
        self.w_max      = W_MAX_DEFAULT
        self.dt         = DT_DEFAULT
        self.red_min    = RED_MIN_DEFAULT
        self.red_max    = RED_MAX_DEFAULT
        self.yellow_dur = YELLOW_DURATION

        # Frame JPEG terakhir per jalur (untuk MJPEG stream)
        self.frames: list[bytes | None] = [None] * NUM_LANES

    # ── Serialisasi seluruh state ke payload JSON ────────────────────────────

    def to_payload(self) -> dict:
        """
        Menghasilkan dict yang kompatibel 100% dengan ekspektasi JavaScript
        di dashboard.html:
          stateData.lanes[i].{name, road, light_state, timer_red,
                               timer_green, timer_yellow, total_poin,
                               total_kendaraan, counts}
          stateData.siklus
        """
        with self.lock:
            return {
                "lanes":  [lane.to_dict() for lane in self.lanes],
                "siklus": self.siklus,
            }


# ── Singleton — diimport langsung oleh modul lain ───────────────────────────
state = SystemState()
