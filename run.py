"""
Ornakuy Poster Bot - mode KUMPUL (v3)
Menarik SEMUA pesanan dari channel Discord (kode 6 karakter + foto depan + foto belakang)
dan menyimpannya ke repo. Tidak ada yang dibuang: kode yang pernah muncul tetap disimpan
dan ditandai "ulang", lalu dashboard yang memetakan mana yang baru / sudah pernah di-generate.

Secrets (GitHub > Settings > Secrets and variables > Actions):
  DISCORD_BOT_TOKEN   token bot Discord
  DISCORD_CHANNEL_ID  ID channel sumber (#side-job-avatar)
"""
import io, json, os, re, sys, time
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "state.json"
ORDERS = ROOT / "orders.json"
ODIR = ROOT / "orders"
STATE_KEY = "collect_v3_last_id"

API = "https://discord.com/api/v10"
TOKEN = os.environ["DISCORD_BOT_TOKEN"]
CHANNEL = os.environ["DISCORD_CHANNEL_ID"]
HDR = {"Authorization": f"Bot {TOKEN}", "User-Agent": "OrnakuyPosterBot (github-actions, 3.0)"}
CODE_RE = re.compile(r"\b([A-Z0-9]{6})\b")
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")


def load_json(p, default):
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def discord_get(path, **params):
    for _ in range(5):
        r = requests.get(API + path, headers=HDR, params=params, timeout=30)
        if r.status_code == 429:
            time.sleep(float(r.json().get("retry_after", 2)) + 0.5)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("Discord rate limit")


def fetch_new_messages(last_id):
    if not last_id:
        msgs = discord_get(f"/channels/{CHANNEL}/messages", limit=50)
        return sorted(msgs, key=lambda m: int(m["id"]))
    out, after = [], last_id
    while True:
        batch = discord_get(f"/channels/{CHANNEL}/messages", after=after, limit=100)
        if not batch:
            break
        batch = sorted(batch, key=lambda m: int(m["id"]))
        out += batch
        after = batch[-1]["id"]
        if len(batch) < 100:
            break
    return out


def parse_order(msg):
    m = CODE_RE.search((msg.get("content") or "").upper())
    imgs = [a for a in msg.get("attachments", [])
            if (a.get("content_type") or "").startswith("image/") or a["filename"].lower().endswith(IMG_EXT)]
    if not m or len(imgs) < 2:
        return None
    return {"code": m.group(1), "front_url": imgs[0]["url"], "back_url": imgs[1]["url"],
            "author": msg["author"].get("global_name") or msg["author"]["username"],
            "message_id": msg["id"], "time": msg["timestamp"]}


def save_img(url, path):
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    Image.open(io.BytesIO(r.content)).convert("RGB").save(path, "PNG", optimize=True)


def main():
    state = load_json(STATE, {})
    orders = load_json(ORDERS, [])
    known_ids = {x["message_id"] for x in orders}
    msgs = fetch_new_messages(state.get(STATE_KEY))
    print(f"{len(msgs)} pesan dibaca")

    last_ok = state.get(STATE_KEY)
    added = 0
    for m in msgs:
        o = parse_order(m)
        if o and o["message_id"] not in known_ids:
            folder = ODIR / o["message_id"]
            folder.mkdir(parents=True, exist_ok=True)
            try:
                save_img(o["front_url"], folder / "front.png")
                save_img(o["back_url"], folder / "back.png")
            except Exception as e:
                print("Gagal unduh foto", o["code"], ":", e)
                break  # coba lagi di jalan berikutnya
            repeat = any(x["code"] == o["code"] for x in orders)
            orders.append({"code": o["code"], "author": o["author"], "time": o["time"],
                           "message_id": o["message_id"], "repeat": repeat,
                           "front": f"orders/{o['message_id']}/front.png",
                           "back": f"orders/{o['message_id']}/back.png"})
            known_ids.add(o["message_id"])
            added += 1
            print("Pesanan", o["code"], "(kode ulang)" if repeat else "(baru)", "tersimpan")
        last_ok = m["id"]

    orders.sort(key=lambda x: x["time"], reverse=True)
    state[STATE_KEY] = last_ok
    state["last_run"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    state["last_added"] = added
    STATE.write_text(json.dumps(state, indent=2))
    ORDERS.write_text(json.dumps(orders, indent=2, ensure_ascii=False))
    print(f"Selesai: {added} pesanan baru ditambahkan")


if __name__ == "__main__":
    sys.exit(main())
