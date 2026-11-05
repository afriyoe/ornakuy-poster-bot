# Ornakuy Poster Bot

Mengambil pesanan dari channel Discord (kode + foto depan + foto belakang), membuat poster chrome dengan OpenAI, menyimpannya di repo, menampilkannya di dashboard, dan mengirim posternya kembali ke Discord.

## Format pesan di Discord
Satu pesan berisi:
- kode 6 karakter, misalnya `F3E7D7`
- 2 gambar: **gambar pertama = depan**, **gambar kedua = belakang**

## Secrets (Settings → Secrets and variables → Actions → Secrets)
| Nama | Isi |
|---|---|
| `DISCORD_BOT_TOKEN` | token bot Discord |
| `DISCORD_CHANNEL_ID` | ID channel sumber (mis. #side-job-avatar) |
| `OPENAI_API_KEY` | API key OpenAI |
| `DISCORD_RESULT_CHANNEL_ID` | (opsional) channel tujuan poster |

## Variables opsional (tab Variables)
| Nama | Default | Keterangan |
|---|---|---|
| `IMAGE_QUALITY` | `high` | `low` / `medium` / `high` |
| `TEXT_MODE` | `script` | `script` = kode ditempel script (selalu benar), `ai` = kode ditulis AI |
| `MAX_PER_RUN` | `3` | batas poster per sekali jalan |
| `POST_BACK` | `true` | kirim poster ke Discord |
| `IMAGE_MODEL` | `gpt-image-2` | model gambar OpenAI |

## Tes manual
Tab **Actions → Generate poster dari Discord → Run workflow**. Isi `only_code` untuk mengetes satu kode tertentu.

Jalan pertama hanya memproses 1 pesanan terbaru supaya saldo aman.

Font: Inter Display (SIL Open Font License).
