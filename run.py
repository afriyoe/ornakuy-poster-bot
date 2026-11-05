"""
Ornakuy Poster Bot
Discord channel (kode + foto depan + foto belakang) -> OpenAI gpt-image -> poster chrome -> repo + Discord.

Secrets / env (diatur di GitHub > Settings > Secrets and variables > Actions):
  DISCORD_BOT_TOKEN        (secret)  token bot Discord
  DISCORD_CHANNEL_ID       (secret)  ID channel sumber, mis. #side-job-avatar
  OPENAI_API_KEY           (secret)  API key OpenAI
  DISCORD_RESULT_CHANNEL_ID (opsional) channel tujuan poster; kosong = balas di channel sumber
Variables opsional:
  IMAGE_MODEL   default gpt-image-2
  IMAGE_QUALITY default high   (low / medium / high)
  TEXT_MODE     default script (script = kode ditempel script, ai = kode ditulis AI)
  MAX_PER_RUN   default 3      (batas poster per sekali jalan, supaya saldo aman)
  POST_BACK     default true   (kirim poster ke Discord)
"""
import base64, io, json, os, re, sys, time
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont
from openai import OpenAI

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "state.json"
OUT = ROOT / "output"
DOCS_DATA = ROOT / "data.json"
REF = ROOT / "reference.jpg"
FONT = ROOT / "InterDisplay-Black.otf"

API = "https://discord.com/api/v10"
TOKEN = os.environ["DISCORD_BOT_TOKEN"]
CHANNEL = os.environ["DISCORD_CHANNEL_ID"]
RESULT_CHANNEL = os.environ.get("DISCORD_RESULT_CHANNEL_ID") or CHANNEL
MODEL = os.environ.get("IMAGE_MODEL") or "gpt-image-2"
QUALITY = os.environ.get("IMAGE_QUALITY") or "high"
TEXT_MODE = (os.environ.get("TEXT_MODE") or "script").lower()
MAX_PER_RUN = int(os.environ.get("MAX_PER_RUN") or 3)
POST_BACK = (os.environ.get("POST_BACK") or "true").lower() == "true"
ONLY_CODE = (os.environ.get("ONLY_CODE") or "").strip().upper()  # untuk tes manual satu kode

HDR = {"Authorization": f"Bot {TOKEN}", "User-Agent": "OrnakuyPosterBot (github-actions, 1.0)"}
CODE_RE = re.compile(r"\b([A-Z0-9]{6})\b")
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")

BASE_PROMPT = """Image 1 = FRONT view and Image 2 = BACK view of the same Roblox avatar outfit (the product).
Image 3 = STYLE REFERENCE ONLY (background, lighting, layout, typography).

Create a vertical 2:3 promotional poster in the exact style of Image 3:
- Liquid silver chrome swirl background on a light grey studio backdrop, glossy reflective dark floor, soft studio lighting, high detail render.
- The avatar from Images 1 and 2 shown twice side by side: FRONT view on the left, BACK view on the right, full body head to shoes, same size, standing on the floor with reflections.
- STRICT OUTFIT LOCK: reproduce the outfit EXACTLY as in Images 1 and 2 — identical colors, color shades, patterns, graphics, rips, cut-outs, shapes, layers, accessories, shoes, hair and skin tone. Do not recolor, simplify, redesign or add anything.
- NEVER use the character, outfit, hair or colors of Image 3. Only copy its style.
"""
PROMPT_SCRIPT_TEXT = BASE_PROMPT + """- Keep the top 22% of the poster as clean light background with no objects (a title will be added later).
- Do NOT write any text, letters, numbers or logos anywhere.
"""
PROMPT_AI_TEXT = BASE_PROMPT + """- At the top center, exactly like Image 3: a small four-point star, the word "CODE" in small heavy black sans-serif, below it the code "{code}" in very large heavy black sans-serif, then a small four-point star.
- Spell the code exactly: {spelled}. No other text anywhere.
"""


def load_json(p, default):
    return json.loads(p.read_text()) if p.exists() else default


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
    if last_id:
        msgs = discord_get(f"/channels/{CHANNEL}/messages", after=last_id, limit=50)
    else:
        # jalan pertama: hanya ambil pesan terbaru, jangan proses seluruh riwayat
        msgs = discord_get(f"/channels/{CHANNEL}/messages", limit=10)
    return sorted(msgs, key=lambda m: int(m["id"]))


def parse_order(msg):
    m = CODE_RE.search((msg.get("content") or "").upper())
    imgs = [a for a in msg.get("attachments", [])
            if (a.get("content_type") or "").startswith("image/") or a["filename"].lower().endswith(IMG_EXT)]
    if not m or len(imgs) < 2:
        return None
    return {"code": m.group(1), "front": imgs[0]["url"], "back": imgs[1]["url"],
            "author": msg["author"].get("global_name") or msg["author"]["username"],
            "message_id": msg["id"], "time": msg["timestamp"]}


def download(url):
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    im = Image.open(io.BytesIO(r.content)).convert("RGB")
    buf = io.BytesIO(); im.save(buf, "PNG"); buf.seek(0)
    return buf


def as_file(buf, name):
    buf.seek(0); buf.name = name
    return buf


def generate(order, client):
    front = as_file(download(order["front"]), "front.png")
    back = as_file(download(order["back"]), "back.png")
    ref = as_file(io.BytesIO(REF.read_bytes()), "reference.jpg")
    if TEXT_MODE == "ai":
        prompt = PROMPT_AI_TEXT.format(code=order["code"], spelled="-".join(order["code"]))
    else:
        prompt = PROMPT_SCRIPT_TEXT
    res = client.images.edit(model=MODEL, image=[front, back, ref], prompt=prompt,
                             size="1024x1536", quality=QUALITY)
    img = Image.open(io.BytesIO(base64.b64decode(res.data[0].b64_json))).convert("RGB")
    if TEXT_MODE != "ai":
        img = add_code_text(img, order["code"])
    return img


def star(d, cx, cy, R, ink):
    r = R * 0.16
    pts = []
    for i in range(8):
        import math
        a = math.pi / 4 * i - math.pi / 2
        rad = R if i % 2 == 0 else r
        pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
    d.polygon(pts, fill=ink)


def add_code_text(img, code):
    W, H = img.size
    s = W / 1024
    d = ImageDraw.Draw(img)
    ink = (24, 24, 28)
    f_small = ImageFont.truetype(str(FONT), int(40 * s))
    f_big = ImageFont.truetype(str(FONT), int(104 * s))
    cx = W // 2
    star(d, cx, 70 * s, 38 * s, ink)
    d.text((cx, 150 * s), "CODE", font=f_small, fill=ink, anchor="mm")
    d.text((cx, 232 * s), code, font=f_big, fill=ink, anchor="mm")
    star(d, cx, 305 * s, 24 * s, ink)
    return img


def post_to_discord(path, order):
    payload = {"content": f"Poster **CODE {order['code']}** siap ✨",
               "message_reference": {"message_id": order["message_id"], "fail_if_not_exists": False}}
    if RESULT_CHANNEL != CHANNEL:
        payload.pop("message_reference")
    with open(path, "rb") as f:
        r = requests.post(f"{API}/channels/{RESULT_CHANNEL}/messages", headers=HDR,
                          data={"payload_json": json.dumps(payload)},
                          files={"files[0]": (path.name, f, "image/png")}, timeout=60)
    if r.status_code >= 300:
        print("Gagal kirim ke Discord:", r.status_code, r.text[:300])


def main():
    OUT.mkdir(exist_ok=True)
    state = load_json(STATE, {"last_message_id": None})
    data = load_json(DOCS_DATA, [])
    done_codes = {x["code"] for x in data}

    msgs = fetch_new_messages(state["last_message_id"])
    orders = [o for o in (parse_order(m) for m in msgs) if o]
    if ONLY_CODE:
        orders = [o for o in orders if o["code"] == ONLY_CODE] or orders[-1:]
    elif not state["last_message_id"]:
        orders = orders[-1:]  # jalan pertama: tes 1 poster saja
    print(f"{len(msgs)} pesan baru, {len(orders)} pesanan valid")

    client = OpenAI()
    made = 0
    for o in orders:
        if made >= MAX_PER_RUN:
            print("Batas MAX_PER_RUN tercapai, sisanya di jalan berikutnya")
            break
        if o["code"] in done_codes and not ONLY_CODE:
            state["last_message_id"] = o["message_id"]
            continue
        print("Generate", o["code"], "...")
        try:
            img = generate(o, client)
        except Exception as e:
            print("Gagal generate", o["code"], ":", e)
            break  # berhenti, coba lagi di jalan berikutnya (pesan ini belum ditandai selesai)
        path = OUT / f"{o['code']}.png"
        img.save(path, "PNG", optimize=True)
        data = [x for x in data if x["code"] != o["code"]]
        data.insert(0, {"code": o["code"], "file": f"output/{path.name}", "author": o["author"],
                        "time": o["time"], "front": o["front"], "back": o["back"]})
        if POST_BACK:
            post_to_discord(path, o)
        state["last_message_id"] = o["message_id"]
        made += 1

    if msgs and made < MAX_PER_RUN and not ONLY_CODE:
        # semua pesan sudah dilihat (yang bukan pesanan dilewati)
        failed = any(o["code"] not in {x["code"] for x in data} for o in orders)
        if not failed:
            state["last_message_id"] = msgs[-1]["id"]

    STATE.write_text(json.dumps(state, indent=2))
    DOCS_DATA.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"Selesai: {made} poster dibuat")


if __name__ == "__main__":
    sys.exit(main())
