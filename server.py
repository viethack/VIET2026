from flask import Flask, request, jsonify
import threading, time, uuid, random, string, re, requests
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

# ================== CONFIG ==================
URL = "https://zefame-free.com/api_free.php"
PROXY = "http://user-p3g4pnl3oagz:7UxliLrcZgO3t@pr.lunaproxy.com:32233"

VIEW_PER_REQ = 200
THREADS = 20
MAX_CONCURRENT_JOBS = 2   # giống file mẫu bạn gửi

headers = {
    "accept": "application/json, text/javascript, */*; q=0.01",
    "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
    "origin": "https://zefame.com",
    "referer": "https://zefame.com/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/143.0.0.0",
}

# ================== QUEUE & STATE ==================
task_queue = []
active_jobs = []
lock = threading.Lock()

# ================== TOOL FUNCTIONS ==================
def random_username(n=12):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))

def random_video_id():
    return str(random.randint(10**18, 10**19 - 1))

def random_tiktok_link(link):
    m = re.search(r"/video/(\d+)", link)
    return f"https://www.tiktok.com/@{random_username()}/video/{m.group(1)}"

# ================== CORE RUNNER ==================
def run_job(video_link, target_view):
    total_view = 0
    stop_event = threading.Event()
    view_lock = threading.Lock()

    def worker():
        nonlocal total_view
        while not stop_event.is_set():
            data = {
                "service": "229",
                "link": random_tiktok_link(video_link),
                "uuid": str(uuid.uuid4()),
                "videoId": random_video_id(),
            }

            try:
                r = requests.post(
                    URL,
                    params={"action": "order"},
                    headers=headers,
                    data=data,
                    proxies={"http": PROXY, "https": PROXY},
                    timeout=20
                ).json()

                if r.get("success") is True:
                    with view_lock:
                        if total_view >= target_view:
                            stop_event.set()
                            return

                        total_view += VIEW_PER_REQ
                        if total_view >= target_view:
                            total_view = target_view
                            print(f"✅ +200 view ({total_view}/{target_view})")
                            stop_event.set()
                            return

                        print(f"✅ +200 view ({total_view}/{target_view})")

            except:
                pass

            time.sleep(0.15)

    with ThreadPoolExecutor(max_workers=THREADS) as exe:
        for _ in range(THREADS):
            exe.submit(worker)

    print("🎯 DONE – ĐÃ ĐỦ VIEW")

# ================== WORKER LOOP ==================
def worker_loop(worker_id):
    while True:
        with lock:
            if not task_queue:
                time.sleep(1)
                continue
            video_link, views = task_queue.pop(0)
            active_jobs.append((video_link, views))

        print(f"[▶️ Worker-{worker_id}] Bắt đầu: {video_link} ({views} view)")
        try:
            run_job(video_link, views)
        finally:
            with lock:
                active_jobs.remove((video_link, views))
            print(f"[✅ Worker-{worker_id}] Hoàn tất")

# ================== START WORKERS ==================
def start_workers():
    for i in range(MAX_CONCURRENT_JOBS):
        threading.Thread(target=worker_loop, args=(i+1,), daemon=True).start()

start_workers()

# ================== API ==================
@app.route("/run", methods=["POST"])
def run_api():
    data = request.get_json()
    if not data or "url" not in data or "views" not in data:
        return jsonify({"error": "Thiếu url hoặc views"}), 400

    with lock:
        task_queue.append((data["url"], int(data["views"])))
        pos = len(task_queue)
        running = len(active_jobs)

    return jsonify({
        "status": "started" if running < MAX_CONCURRENT_JOBS else "queued",
        "queue_position": pos,
        "url": data["url"],
        "views": data["views"]
    })

@app.route("/status", methods=["GET"])
def status():
    with lock:
        return jsonify({
            "running_jobs": active_jobs,
            "queue_length": len(task_queue)
        })

# ================== MAIN ==================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=2540)
