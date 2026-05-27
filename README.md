!! setup ini dulu wok, kalu gak gak bakal jalan ajg

1. Buat dan Aktifkan Virtual Environment (Gunakan Python 3.12 agar stabil)

   uv venv .venv --python 3.12

   .venv\Scripts\activate

(Pastikan sekarang sudah ada tulisan (.venv) di terminalmu).

2. Instalasi Pustaka Web dan AI (Termasuk fix untuk NumPy)

   uv pip install flask flask-socketio flask-cors opencv-python ultralytics "numpy<2"

3. Instalasi PyTorch (Versi CUDA / Akselerasi GPU)

   uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

Setelah proses instalasi selesai, silakan jalankan kembali kodemu:

python main.py

# 🚦 Dynamic Traffic Light AI

Sistem lampu lalu lintas adaptif berbasis YOLOv8 + Flask + Socket.IO.
Backend mendeteksi kepadatan kendaraan secara real-time via CCTV dan
menghitung durasi lampu hijau secara dinamis untuk tiap jalur persimpangan.

---

## Prasyarat

- Python 3.10+
- pip
- File video CCTV (`.mp4`) untuk 4 jalur
- File model YOLOv8 (`best.pt`) yang sudah dilatih mengenali kendaraan

---

## Instalasi

```bash
# 1. Clone / salin folder project
cd visualisasi_html

# 2. Install dependensi Python
pip install flask flask-socketio opencv-python ultralytics torch torchvision
```

---

## Struktur Folder

```
visualisasi_html/
├── models/
│   └── best.pt                ← model YOLOv8 (letakkan di sini)
├── videos/
│   ├── cctv_jalur1.mp4        ← video CCTV jalur 1
│   ├── cctv_jalur2.mp4
│   ├── cctv_jalur3.mp4
│   └── cctv_jalur4.mp4
├── templates/
│   └── dashboard.html         ← antarmuka web frontend
├── config.py
├── state.py
├── traffic_logic.py
├── vision_engine.py
├── routes.py
└── main.py
```

---

## Cara Menjalankan

```bash
cd visualisasi_html
python main.py
```

Buka browser dan akses:

```
http://localhost:5000
```

Klik tombol **▶ Mulai** di pojok kanan bawah dashboard untuk mengaktifkan siklus lampu.

---

## Cara Menghentikan

Tekan `Ctrl + C` di terminal.

---

## Konfigurasi Cepat

Semua parameter utama ada di `config.py`. Tidak perlu menyentuh file lain untuk penyesuaian dasar:

| Parameter           | Default     | Keterangan                      |
| ------------------- | ----------- | ------------------------------- |
| `W_MIN_DEFAULT`     | `10` detik  | Waktu hijau minimum             |
| `W_MAX_DEFAULT`     | `120` detik | Waktu hijau maksimum            |
| `DT_DEFAULT`        | `0.5`       | Faktor skala poin → detik       |
| `YELLOW_DURATION`   | `3` detik   | Durasi lampu kuning (tetap)     |
| `RED_MIN_DEFAULT`   | `30` detik  | Merah minimum                   |
| `JPEG_QUALITY`      | `85`        | Kualitas kompresi stream video  |
| `VISION_FPS_TARGET` | `30` FPS    | Target frame rate vision thread |
| `CONFIDENCE_THRESH` | `0.4`       | Threshold confidence deteksi AI |

---

## Algoritma Waktu Hijau Adaptif

```
W_hijau = clamp( W_min + Total_Poin × dt,  W_min,  W_max )
```

**Pembobotan kendaraan:**

| Kendaraan          | Poin |
| ------------------ | ---- |
| Motorcycle (motor) | 1    |
| Car (mobil)        | 2    |
| Truck (truk)       | 3    |
| Bus                | 3    |

Semakin padat jalur → semakin besar Total_Poin → semakin lama waktu hijau, hingga batas `W_max`.

---

## Arsitektur 3-Thread

```
┌──────────────────────────────────────────────────────┐
│  Thread 1 — Main Web Thread                          │
│  Flask + Socket.IO melayani HTTP request & WebSocket │
└──────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────┐
│  Thread 2 — Timer Thread  (traffic_logic.py)         │
│  Countdown 1 detik, siklus RED→GREEN→YELLOW,         │
│  broadcast `timer_update` ke semua client            │
└──────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────┐
│  Thread 3 — Vision Thread  (vision_engine.py)        │
│  Baca frame semua cap setiap ~33ms.                  │
│  Inferensi YOLOv8 HANYA pada tab yang sedang aktif.  │
│  3 jalur lain: cap.read() saja (video tetap loop).   │
│  Broadcast `data_update` setelah deteksi.            │
└──────────────────────────────────────────────────────┘
```

---

## Penjelasan Setiap File

### `config.py`

**Konfigurasi statis — satu-satunya file yang perlu diubah untuk tuning.**

Berisi semua konstanta: path file model & video, nama default jalur,
bobot kendaraan, parameter algoritma (W_min, W_max, dt), durasi tiap
fase lampu, kualitas JPEG, dan target FPS. Tidak mengimport modul
project lain sehingga bebas dari circular import.

---

### `state.py`

**Pusat data real-time — single source of truth.**

Mendefinisikan dua kelas:

- `LaneState` — menyimpan data satu jalur: nama, nama jalan, status lampu
  (`red`/`yellow`/`green`), timer countdown, dan hasil deteksi kendaraan.
  Menyediakan properti `total_kendaraan` dan `total_poin` (dihitung otomatis),
  serta method `to_dict()` yang menghasilkan payload JSON sesuai ekspektasi
  JavaScript di `dashboard.html`.

- `SystemState` — container untuk keempat `LaneState`, flag `running`,
  `active_lane` (jalur yang sedang hijau), `siklus`, `active_tab_view`
  (tab aktif frontend untuk on-demand AI), frame JPEG per jalur, dan
  parameter batas waktu. Method `to_payload()` menghasilkan dict lengkap
  yang langsung di-emit via Socket.IO.

Singleton `state` di-export dan diimport langsung oleh semua modul lain.
Semua akses tulis dibungkus `with state.lock` (threading.Lock).

---

### `traffic_logic.py`

**Logika siklus lampu adaptif — Timer Thread.**

Fungsi utama `traffic_cycle_thread(socketio)` berjalan selamanya di Thread-2.
Satu iterasi loop = satu giliran satu jalur:

1. **Hitung** `W_hijau` dengan rumus adaptif berdasarkan `total_poin` jalur aktif.
2. **Fase HIJAU** — countdown detik demi detik, emit `timer_update` tiap detik.
3. **Fase KUNING** — countdown `YELLOW_DURATION` detik, emit `timer_update`.
4. **Pindah** ke jalur berikutnya; naikkan `siklus` setiap kali kembali ke jalur 0.

Fungsi `_recalculate_red_timers()` menghitung estimasi sisa waktu merah
untuk setiap jalur non-aktif berdasarkan antrian siklus berikutnya.
`start_traffic_thread(socketio)` adalah factory function yang dipanggil dari `main.py`.

---

### `vision_engine.py`

**Deteksi kendaraan YOLOv8 + MJPEG streaming — Vision Thread.**

Alur kerja Thread-3:

1. Buka semua `cv2.VideoCapture` untuk 4 video.
2. Load model YOLOv8 dengan `torch.serialization.add_safe_globals()`
   agar `best.pt` aman dimuat tanpa peringatan serialisasi PyTorch.
3. Setiap ~33ms: iterasi semua capture, baca frame (`cap.read()`).
4. Untuk jalur `active_tab_view`: jalankan `model.predict()`, anotasi
   bounding box, update `state.lanes[i].counts`, emit `data_update`.
5. Untuk 3 jalur lain: hanya `cap.read()` — video tetap loop tanpa AI.
6. Encode semua frame ke JPEG dan simpan ke `state.frames[i]`.

Generator `generate_mjpeg(lane_id)` mengalirkan frame dari `state.frames`
sebagai multipart JPEG stream untuk endpoint `/video_feed/<id>`.

---

### `routes.py`

**Endpoint HTTP dan event handler Socket.IO.**

Fungsi `register_routes(app, socketio)` menerima instance Flask dan SocketIO
sebagai parameter (bukan mengimport langsung) untuk menghindari circular import.

**HTTP Endpoints:**

| Route                       | Keterangan                           |
| --------------------------- | ------------------------------------ |
| `GET /`                     | Sajikan `dashboard.html`             |
| `GET /video_feed/<lane_id>` | MJPEG stream jalur 0–3               |
| `GET /api/state`            | Snapshot state JSON (opsional/debug) |

**Socket.IO Events (server ← client):**

| Event              | Payload           | Aksi                                              |
| ------------------ | ----------------- | ------------------------------------------------- |
| `start_system`     | —                 | Set `state.running = True`, emit `status_update`  |
| `stop_system`      | —                 | Set `state.running = False`, emit `status_update` |
| `update_road_name` | `{lane_id, name}` | Ubah nama jalan, emit `road_updated`              |
| `change_tab`       | `{tab_index}`     | Update `state.active_tab_view` untuk on-demand AI |

**Socket.IO Events (server → client):**

| Event           | Kapan dikirim                                  |
| --------------- | ---------------------------------------------- |
| `status_update` | Saat connect, start, stop                      |
| `timer_update`  | Setiap detik dari Timer Thread                 |
| `data_update`   | Setelah setiap inferensi AI dari Vision Thread |
| `road_updated`  | Setelah nama jalan diubah                      |

---

### `main.py`

**Entry point — rakitan semua komponen.**

Urutan inisialisasi:

1. Buat instance `Flask` dan `SocketIO` (dengan `async_mode="threading"`).
2. Panggil `register_routes(app, socketio)` untuk mendaftarkan semua route.
3. Panggil `start_traffic_thread(socketio)` → jalankan Thread-2.
4. Panggil `start_vision_thread(socketio)` → jalankan Thread-3.
5. Jalankan server dengan `socketio.run()` (`debug=False`, `use_reloader=False`
   wajib agar threading stabil).

`app` dan `socketio` hanya dibuat di file ini dan tidak diimport oleh modul lain,
sehingga zero circular import.

---

### `templates/dashboard.html`

**Antarmuka web frontend.**

Single-page app berbasis vanilla JS + Socket.IO. Menampilkan:

- Tab CCTV per jalur dengan stream MJPEG live.
- Widget lampu lalu lintas (progress bar merah/kuning/hijau + countdown).
- Statistik poin kepadatan dan jumlah kendaraan per tipe.
- Kartu ringkasan 4 jalur + peta persimpangan berbasis Canvas.
- Panel kontrol batas waktu lampu + tombol Mulai/Jeda.

**Modifikasi wajib** — tambahkan satu baris di fungsi `switchTab(idx)` agar
frontend mengirim event `change_tab` ke backend (aktifkan on-demand AI):

```javascript
function switchTab(idx) {
  // ... kode existing ...
  streamImg.src = `/video_feed/${idx}`;
  socket.emit("change_tab", { tab_index: idx }); // ← TAMBAHKAN INI
  updateLeftPanel();
}
```

---

## Troubleshooting

**Video tidak muncul** — Pastikan path di `config.py` → `VIDEO_PATHS` sesuai
dan file `.mp4` ada di folder `videos/`.

**Model gagal dimuat** — Pastikan `best.pt` ada di `models/` dan dilatih
dengan Ultralytics YOLOv8 versi kompatibel. Cek versi: `pip show ultralytics`.

**Port sudah terpakai** — Ubah `PORT = 5000` di `config.py` ke port lain,
misalnya `8080`.

**Performa lambat** — Turunkan `VISION_FPS_TARGET` atau naikkan `CONFIDENCE_THRESH`
di `config.py`. Pastikan GPU tersedia jika dataset besar.
