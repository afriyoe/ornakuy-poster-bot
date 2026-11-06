"""Auto-crop Roblox screenshot ke avatar saja (portrait, ada ruang aman).

Cara deteksi:
1. Background Roblox baseplate = langit (gradasi biru per baris) + lantai abu-abu.
   Warna latar tiap baris ~ sama dari kiri ke kanan, jadi median baris = warna latar.
2. Piksel yang beda jauh dari median barisnya = calon avatar (setelah blur supaya
   tekstur lantai tidak ikut).
3. Ambil gumpalan yang menyentuh area tengah layar (avatar selalu di tengah),
   abaikan joystick kiri bawah & tombol UI.
4. Kotak avatar + margin lebar (atas 35%, bawah 15%, samping secukupnya),
   dipaksa rasio portrait 9:19.5 -> tidak mungkin kepala/kaki kepotong.
5. Kalau deteksi gagal/aneh -> fallback crop tengah tetap.
"""
import sys
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

ASPECT = 1179 / 2556  # lebar/tinggi seperti contoh
OUT_W = 1179


def detect_box(img):
    W, H = img.size
    a = np.asarray(img.convert('RGB').filter(ImageFilter.GaussianBlur(3)), dtype=np.int16)
    # warna latar per baris: median dari kolom kiri+kanan (bukan bagian tengah)
    side = np.concatenate([a[:, int(W * .15):int(W * .3)], a[:, int(W * .7):int(W * .9)]], axis=1)
    bg = np.median(side, axis=1)[:, None, :]
    diff = np.abs(a - bg).max(axis=2)
    # ambang adaptif: noise lantai per baris
    noise = np.percentile(np.abs(side - bg).max(axis=2), 95, axis=1)[:, None]
    mask = diff > np.maximum(45, noise * 1.8)
    # buang area UI: 15% kiri & 10% kanan
    mask[:, :int(W * .15)] = False
    mask[:, int(W * .9):] = False
    mask = ndimage.binary_opening(mask, iterations=2)
    mask = ndimage.binary_closing(mask, iterations=6)
    lab, n = ndimage.label(mask)
    if n == 0:
        return None
    cx0, cx1 = int(W * .35), int(W * .65)
    keep = []
    sizes = ndimage.sum(mask, lab, range(1, n + 1))
    for i, sl in enumerate(ndimage.find_objects(lab), 1):
        ys, xs = sl
        if sizes[i - 1] < W * H * 0.0005:
            continue
        if xs.stop > cx0 and xs.start < cx1:  # menyentuh area tengah
            keep.append(sl)
    if not keep:
        return None
    x0 = min(s[1].start for s in keep); x1 = max(s[1].stop for s in keep)
    y0 = min(s[0].start for s in keep); y1 = max(s[0].stop for s in keep)
    return x0, y0, x1, y1


def crop_image(img):
    img = img.convert('RGB')
    W, H = img.size
    box = detect_box(img)
    ok = box and (box[3] - box[1]) > H * 0.15 and (box[2] - box[0]) < W * 0.5
    if not ok:  # fallback: tengah layar
        box = (int(W * .42), int(H * .3), int(W * .58), int(H * .85))
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    # margin aman
    top = y0 - bh * .35; bot = y1 + bh * .15
    ch = bot - top
    cw = max(ch * ASPECT, bw * 1.3)
    ch = cw / ASPECT
    cx = (x0 + x1) / 2
    cy = (top + bot) / 2
    L, T = cx - cw / 2, cy - ch / 2
    # geser supaya tetap di dalam gambar (kalau kebesaran, kecilkan)
    if ch > H:
        ch = H; cw = ch * ASPECT; L = cx - cw / 2; T = 0
    T = min(max(T, 0), H - ch); L = min(max(L, 0), W - cw)
    c = img.crop((int(L), int(T), int(L + cw), int(T + ch)))
    return c.resize((OUT_W, round(OUT_W / ASPECT)), Image.LANCZOS)


def crop(path, out):
    crop_image(Image.open(path)).save(out)


if __name__ == '__main__':
    for p in sys.argv[1:]:
        crop(p, p.replace('.png', '_crop.png')); print('ok', p)
