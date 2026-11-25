# HubTer Insight

Website chat AI berbasis RAG (OpenAI) untuk menjawab pertanyaan dari dokumen referensi hukum Indonesia.

**Status:** Nginx + SSL, backend, dan frontend chat sudah live. Ingest dokumen dan pencarian (BM25) sudah ada. `LLM_MODE=mock` hanya menampilkan bagian dokumen yang paling relevan; `LLM_MODE=openai` meminta model (default `gpt-5.4-mini`; petunjuknya ada di `backend/app/system_prompt.txt`) menyusun jawaban dari bagian dokumen itu, wajib dengan rujukan, dan menolak bila dokumen tidak memuatnya. Mode `openai` dibatasi per IP (`RATE_LIMIT_*` di `app/config.py`) untuk melindungi kredit.

## Struktur

```
compose.yaml                      Nginx, Certbot, backend, frontend
.env.example                      Contoh konfigurasi (salin ke .env)
backend/                          FastAPI: POST /api/chat (SSE), GET /api/config, /api/health
  app/rag.py                      Pencarian BM25 di memori atas corpus/corpus.jsonl
  app/providers.py                Penyedia jawaban (MockProvider; penyedia LLM menyusul)
  corpus/corpus.jsonl             Potongan dokumen hasil ingest (ikut masuk image)
  ingest/build_corpus.py          Membangun corpus dari folder "HubTer Insight Data"
frontend/                         React + Vite: UI chat, riwayat di localStorage
nginx/templates/                  Konfigurasi Nginx (dirender dengan ${DOMAIN})
nginx/snippets/app.conf           Routing: /api -> backend, / -> frontend (SSE tanpa buffering)
nginx/entrypoint.d/               Pemilih mode otomatis: bootstrap (HTTP) atau HTTPS
scripts/init-ssl.sh               Penerbitan sertifikat pertama kali
```

## Pengembangan lokal

```bash
# Backend (terminal 1)
cd backend && python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # Windows
.venv/Scripts/python -m uvicorn app.main:app --port 8000

# Frontend (terminal 2) - /api otomatis diteruskan ke port 8000
cd frontend && npm install && npm run dev      # http://localhost:5173
```

## Memperbarui korpus dokumen

Jalankan secara lokal setiap kali ada dokumen baru atau berubah di `HubTer Insight Data`:

```bash
python -m venv .venv-ingest && .venv-ingest/Scripts/pip install -r backend/ingest/requirements.txt   # sekali saja
.venv-ingest/Scripts/python backend/ingest/build_corpus.py --data "HubTer Insight Data" --out backend/corpus/corpus.jsonl
```

PDF hasil pindai di-OCR otomatis (hasilnya disimpan di `backend/ingest/.ocr-cache`, jadi tidak diulang). Peraturan dipotong per Pasal. Setelah itu bangun ulang image backend (lihat bawah). Judul kutipan diatur di `TITLES` pada skrip; berkas baru tanpa entri memakai nama berkasnya.

## Log evaluasi

Selama evaluasi, setiap pertanyaan, jawaban, sumber yang terambil, dan penilaian 👍/👎 beserta komentar penilai disimpan di SQLite (volume Docker `hubter-data`, berkas `/data/hubter.db`). Tidak ada IP atau identitas; hanya ID sesi acak per browser. Tidak ada halaman web untuk membacanya (situs tanpa login); bacalah lewat SSH:

```bash
docker compose exec -T backend python -m app.export_log --format stats          # ringkasan + perkiraan biaya
docker compose exec -T backend python -m app.export_log --format md > log.md    # dibaca manusia
docker compose exec -T backend python -m app.export_log --format csv > log.csv  # untuk spreadsheet
# opsi: --since 2026-11-24   --rated (hanya yang dinilai/dikomentari)   --bad (hanya 👎)
```

`APP_VERSION` (`app/config.py`, tampil di bilah kiri) tersimpan di tiap baris log. Naikkan (v2, v3, …) setiap mengubah pencarian, prompt, atau model supaya hasil antarversi bisa dibandingkan.

## Pencarian hybrid (embedding), opsional dan saat ini nonaktif

`SEARCH_MODE=hybrid` menggabungkan BM25 dengan kemiripan makna (`text-embedding-3-small`). Vektor dihitung sekali di VPS (`docker compose exec -T backend python -m app.embed_corpus`, sekitar 30 detik, kurang dari US$0,03) dan disimpan di volume data; bila korpus berubah, jalankan ulang. Bila berkas vektor tidak ada atau tidak cocok dengan korpus, pencarian otomatis kembali ke BM25.

Pada 22 pertanyaan uji (formal dan santai) hybrid **tidak lebih baik** dari BM25 (maksimal setara, dan bobot semantik tinggi menurunkan hasil), karena seluruh korpus bertopik sama sehingga kemiripan makna kurang membedakan. Karena itu default tetap `bm25`. Kaji ulang dengan pertanyaan nyata penilai dari log evaluasi sebelum mengaktifkannya (jika diaktifkan, naikkan `APP_VERSION`).

## Mode agentic, opsional dan saat ini nonaktif

`AGENTIC=1` (hanya `LLM_MODE=openai`) membuat model boleh memanggil alat `cari_dokumen` untuk mencari lagi dengan kata kunci lain setelah pencarian awal (`app/agent.py`, lewat Responses API karena gpt-5.4-mini tidak mendukung alat fungsi bersama `reasoning_effort` di Chat Completions; `store=False`). Prompt-nya memuat peta seluruh dokumen di korpus. `AGENTIC_FORCE_SEARCH=1` mewajibkan satu pencarian tambahan. Kata kunci yang dicari model tercatat di log (`[agentic] ...` pada kolom kata kunci).

Uji ujung-ke-ujung 22 pertanyaan di VPS (`backend/eval/arm_eval.py`, `ARM=bm25|hybrid|agentic|agentic_force`; "dikutip" = dokumen yang diharapkan ikut dikutip di jawaban):

| Lengan | Dokumen tepat dikutip | Biaya rata-rata | Median | Token masuk rata-rata |
|---|---|---|---|---|
| BM25 (v1) | 19/22 | $0,0060 | 2,1 dtk | 5.800 |
| Hybrid (embedding, bobot 0,3) | 19/22 | $0,0060 | 2,7 dtk | 5.600 |
| Agentic | 19/22 | $0,0080 | 2,7 dtk | 8.500 |
| Agentic, pencarian wajib | 18/22 | $0,0154 | 4,0 dtk | 17.900 |

Agentic biasa jarang mencari (2 dari 22 pertanyaan) karena kutipan awal tampak relevan bagi model; saat mencari, ia kadang menebak nomor pasal. Bila dipaksa mencari, satu pertanyaan sulit (batas waktu pernyataan sendiri) akhirnya menemukan PMK 131, tetapi dua pertanyaan lain (siapa yang menentukan hubter, pejabat pengawas wilayah) tidak lagi mengutip dokumen yang diharapkan, dan biaya naik sekitar 2,5 kali. Ukuran ini kasar: jawaban bisa benar dengan mengutip pasal lain. Tidak ada pendekatan yang menyelesaikan pertanyaan "pabrik kecil, SKT golongan 3". Karena itu default tetap BM25 (v1). Kaji ulang dengan pertanyaan nyata penilai; ide lanjutan yang lebih murah: memicu pencarian tambahan hanya bila skor pencarian awal lemah.

## Uji pencarian dengan pertanyaan sintetis

`backend/eval/synth_gen.py` membuat 2 pertanyaan (baku dan santai, pendek) per potongan korpus yang dipilih (672 pertanyaan dari 336 potongan, tersimpan di `backend/eval/synth_questions.json`; biaya sekitar US$0,5). `synth_eval.py` mengukur apakah potongan asal masuk 8 teratas tanpa memanggil model jawaban (gratis, bisa diulang tiap perubahan pencarian), dan `synth_judge.py` meminta model menilai kasus yang gagal: tidak mandiri, ada jawaban dari peraturan lain, atau benar-benar meleset.

Hasil BM25 v1: potongan asal masuk 8 teratas pada 71,7% pertanyaan (baku 81,5%, santai 61,9%; diskusi 44%). Namun dari 190 kasus gagal, 57 tidak mandiri ("mulainya kapan?"), 126 sebenarnya sudah punya jawaban dari peraturan lain di 8 teratas, dan hanya 7 benar-benar meleset. Hybrid (3 pengaturan) tidak lebih baik dari BM25. Artinya pencarian bukan hambatan utama untuk pertanyaan yang mandiri; kualitas bergantung pada pemilihan peraturan yang berlaku dan cara model merangkai jawaban.

## Login

Situs memakai halaman masuk sendiri (logo, nama pengguna, kata sandi, tombol Masuk) dengan satu akun bersama untuk pemakai internal, tanpa registrasi. Login diperiksa backend (`app/auth.py`): setelah masuk, browser menyimpan cookie sesi bertanda tangan (HttpOnly, SameSite=Lax, Secure di HTTPS, berlaku 30 hari). `/api/chat`, `/api/config`, dan `/api/feedback` menolak permintaan tanpa cookie (401); `/api/health` dan `/api/session` tetap terbuka. Nama pengguna tidak membedakan huruf besar kecil dan spasi di ujung diabaikan (kebiasaan keyboard HP). Percobaan masuk dibatasi 8 per menit per IP. Tombol "Keluar" ada di bawah bilah kiri.

Diatur lewat `.env` di VPS (lihat `.env.example`): `AUTH_USER`, `AUTH_PASSWORD`, `AUTH_SECRET`. `AUTH_PASSWORD` kosong berarti tanpa login (pengembangan lokal). Mengganti `AUTH_PASSWORD` atau `AUTH_SECRET` otomatis mengeluarkan semua sesi.

```bash
cat ~/hubter-login.txt                  # nama dan sandi saat ini (berkas hanya bisa dibaca pemilik)
nano ~/hubter-insight/.env              # ganti AUTH_PASSWORD (dan perbarui ~/hubter-login.txt)
cd ~/hubter-insight && docker compose up -d backend    # menerapkan sandi baru
```

Halaman statis (HTML dan JS) tetap terbuka karena tidak memuat isi sensitif; yang dilindungi adalah semua jawaban dan data lewat API.

## Status peraturan (v2, divalidasi ahli di v4.3)

**Pembaruan v4.3 (25 Nov 2026):** peta status kini divalidasi ahli; dokumen lengkap beserta dasar hukumnya ada di `docs/validasi-status-regulasi-2026-11-25.md`. Koreksi terpenting dari ahli: PER-10/BC/2023 MASIH BERLAKU sampai 31 Desember 2026 (PER-12/BC/2026 ditetapkan 25 September 2026 tetapi baru berlaku 1 Januari 2027, Pasal 13), SE-8/BC/2013 tidak mencantumkan PMK 200/2008, PMK 191/PMK.04/2010 hanya kehilangan dasar HubTer sejak 10 Juni 2013 (Pasal 21A dicabut PMK 78/2013), INS-2/BC/2013 dicabut INS-07/BC/2013, UU 1/2026 menyesuaikan pidana cukai sejak 2 Januari 2026, dan PMK 124/2024 diubah PMK 117/2025. Status kini punya tiga jenis (berlaku, dicabut, belum berlaku) dan beberapa bergantung tanggal (`doc_status.py`: PER-10 dan PER-12 berganti sendiri pada 1 Januari 2027). Peraturan berstatus belum berlaku ikut diturunkan peringkatnya dan diberi peringatan. Pemeriksaan: `backend/eval/validasi_check.py` (12 pertanyaan dengan harapan ahli).

Uraian awal (v2) di bawah tetap berlaku sebagai latar belakang cara kerja.

Karena banyak topik diatur beberapa peraturan sekaligus (mis. NPPBKC: PMK 200/2008, lalu PMK 66/2018 sebagaimana diubah PMK 68/2023), model bisa menjawab dari peraturan yang sudah dicabut. `app/doc_status.py` memuat peta status tiap peraturan, **disusun dari ketentuan penutup yang tertulis di dokumen korpus** (tiap entri menyebut pasalnya) dan tidak menelusuri peraturan di luar korpus: "BERLAKU" berarti "belum ditemukan pencabutan di dokumen referensi". Tinjau dan perbarui bila korpus bertambah. Cara kerjanya: (1) baris `Status:` pada tiap kutipan, (2) peringatan status tepat sebelum pertanyaan bila ada kutipan dari peraturan dicabut, (3) peraturan dicabut turun peringkat di pencarian (`REVOKED_WEIGHT`) kecuali pertanyaan menyebut nomornya, (4) aturan 17 di `system_prompt.txt`. Matikan dengan `DOC_STATUS=0`.

Uji (`backend/eval/status_run.py` dan `status_judge.py`, 20 pertanyaan rawan peraturan lama vs baru, dinilai model terhadap peta status): jawaban yang menyajikan peraturan dicabut sebagai berlaku turun dari 4/20 (v1) menjadi 0/20 (v2); pemakaian kutipan dari peraturan dicabut turun dari 8-9 menjadi 3 dari 20. Tanpa regresi berarti pada 22 pertanyaan lama; pada pertanyaan sintetis dengan kunci peraturan berlaku hit@8 naik 72,3% ke 74,1%, sedangkan pertanyaan yang kuncinya peraturan dicabut turun (sengaja).

## Halaman Dokumen (unggah berkas)

Di bilah kiri, di bawah "Percakapan baru", ada tautan **Dokumen** (alamat `https://hubterinsight.my.id/#/dokumen`): unggah berkas, daftar berkas di server, dan pencarian nama. Tanpa pratinjau; setiap berkas bisa diunduh (selalu sebagai lampiran, tidak pernah dibuka di browser). Hanya untuk yang sudah masuk (login).

- Tipe: `.md .pdf .xlsx .pptx .docx .png .jpg .jpeg`; maksimal 25 MB per berkas dan 1.000 MB total (`UPLOAD_MAX_MB`, `UPLOAD_QUOTA_MB` di `app/config.py`). Isi berkas dicocokkan dengan tipenya (tanda tangan PDF/PNG/JPEG, struktur ZIP untuk docx/xlsx/pptx, UTF-8 untuk md), nama dibersihkan (tanpa folder atau karakter aneh; nama kembar diberi akhiran `-2`), dan unggahan dibatasi 10 per menit per IP (`app/files.py`).
- Berkas disimpan di folder `~/hubter-insight/uploads` di VPS (bind mount ke `/uploads` di container) dan **tidak otomatis masuk korpus atau dibaca model**. Untuk memasukkannya: salin ke folder `HubTer Insight Data`, jalankan ingest, lalu deploy korpus baru (lihat "Memperbarui korpus dokumen").
- Tidak ada tombol hapus di halaman (agar tidak terhapus tidak sengaja); hapus lewat SSH: `rm ~/hubter-insight/uploads/<nama>`.

## Gaya jawaban tanpa penanda "dokumen" (v3)

Masukan penilai: jawaban tidak perlu memuat "berdasarkan dokumen..." atau "Konteks umum (di luar dokumen)". Di v3 (`system_prompt.txt` aturan 2, 10, 11, 14, 17, 18) model tidak lagi menulis kata "kutipan", "dokumen referensi", "di luar dokumen", atau "berdasarkan dokumen"; penanda sumber hanya nomor `[n]` (cocok dengan daftar "Sumber"), dan pernyataan tanpa `[n]` dipahami sebagai penjelasan umum. Penjelasan umum dibatasi dua kalimat konseptual dan tidak boleh memuat pasal, angka, atau klaim praktik. Label "analisis di riwayat diskusi" tetap dipakai karena itu analisis AI, bukan peraturan.

Uji (`backend/eval/phrase_stats.py`, `concept_run.py`): "di luar dokumen" 14% menjadi 0%, kata "kutipan" 23% menjadi 0%, jawaban menyesatkan soal peraturan dicabut tetap 0/20, 22 pertanyaan lama tetap 19/22 dikutip, pertanyaan di luar topik tetap ditolak. Penjelasan konseptual (mis. beda hubungan istimewa dan keterkaitan) kini masuk ke isi jawaban lengkap dengan `[n]`.

## Simulasi pemakaian dan v4

`backend/eval/conv_run.py` menjalankan percakapan simulasi berlapis (pertanyaan lanjutan ikut membawa riwayat) lewat alur sungguhan; masukannya `personas.json` yang dibuat dengan meminta subagen memerankan 10 pengguna (126 giliran). Dari simulasi atas v3 ditemukan pola: tarif "sekarang" dijawab dengan baris tahun lama, pertanyaan lanjutan kehilangan konteks (pencarian hanya digabung di 2 dari 44 lanjutan), skenario dijawab terlalu tegas atau salah sudut pandang, draf surat mengarang fakta, dan penolakan di luar topik bocor (kode, opini, tawaran bantuan).

v4 (`system_prompt.txt` aturan 9, 16, 19 sampai 23; `main.search_query`; `providers.build_messages`): tanggal hari ini disisipkan ke pesan pengguna; pertanyaan tarif "sekarang/terbaru" ditambah tahun berjalan pada pencarian; pencarian lanjutan digabung dengan pertanyaan substantif terdekat bila ada isyarat ("itu", "lebih sederhana", "contoh", "dasarnya", dst.) atau sedikit kata kunci; aturan prompt untuk pertanyaan lanjutan, skenario (sudut pandang peran, kesimpulan bersyarat, fakta belum diketahui), draf (placeholder, tanpa mengarang), penolakan satu kalimat, dan cakupan tetap. Peringatan status peraturan dicabut diperketat. Baris tarif terbaru kini ditulis "berlaku sejak 01-01-2026 (data ditelaah sampai 22-11-2026)" karena 22 November 2026 adalah batas telaah, bukan akhir masa berlaku (lihat `TELAAH_CUTOFF` di `build_corpus.py`; perbarui bila tabel tarif diperbarui).

Hasil (126 pertanyaan sama, v3 lalu v4): tarif "sekarang" yang menyebut periode 2025/2026 0/5 menjadi 4/5 sebelum penandaan batas telaah (kini konsisten); lanjutan yang disangkal "belum tersedia" 9 menjadi 2 dari 44; draf dengan placeholder 4/8 menjadi 7/8; penolakan di luar topik yang masih menempelkan "Bukan nasihat hukum" 10 menjadi 3, tanpa kode dan tanpa tawaran bantuan; pertanyaan identitas dijawab dengan cakupan tetap; jebakan dan injeksi tetap ditolak; 22 pertanyaan lama tetap 19/22; status menyesatkan 0/20. Biaya rata-rata per giliran naik sekitar 8% ($0,0074 menjadi $0,0080).

## v4.1: sapaan dan rantai pertanyaan lanjutan

Dari log penilai (sesi dengan 3 👎 pada v4): "halo" dijawab teks baku "tidak ditemukan... dokumen referensi", dan rantai lanjutan ("jelaskan mengenai rokok SKM" lalu "sederhananya gimana?" lalu "ya tolong jelaskan") kehilangan topik karena pencarian digabung dengan pesan lanjutan lain. Perbaikan: `providers.smalltalk_reply` menjawab sapaan dan ucapan terima kasih saja dengan teks tetap (tanpa memanggil model, biaya nol), teks "tidak ditemukan" ditulis ulang tanpa frasa "dokumen referensi", dan `main.search_query` memilih pertanyaan substantif terdekat sebelumnya, atau yang paling banyak kata kuncinya bila semuanya miskin kata kunci. Pesan seperti "halo, apa itu hubter?" tetap diperlakukan sebagai pertanyaan. Diuji offline pada 126 giliran simulasi (hanya 3 giliran yang dasar pencariannya berubah, semuanya lebih relevan) dan langsung pada 19 giliran (`PERSONAS=... OUT=... conv_run.py`).

## Batas pemakaian

Nilai bawaan untuk pemakaian internal oleh beberapa orang yang bisa berbagi satu jaringan (satu IP), dihitung per IP kecuali total harian. Aplikasi (`app/config.py`, dapat diubah lewat `.env` di VPS lalu `docker compose up -d backend`): `RATE_LIMIT_PER_MINUTE=30`, `RATE_LIMIT_PER_DAY=300`, `DAILY_REQUEST_CAP=600` (total semua pemakai per hari, pelindung kredit: sekitar US$5-6 pada gpt-5.4-mini), `LOGIN_RATE_PER_MINUTE=30`, `LOGIN_RATE_PER_DAY=500`. Unggahan 10 per menit per IP (`app/files.py`). Nginx (`nginx/templates/00-common.conf.template`): 120 permintaan per menit per IP, burst chat 20; mengubahnya butuh `docker compose restart nginx`. Sapaan dan ucapan terima kasih tidak memakai kredit tetapi tetap dihitung limiter. Hitungan limiter ada di memori dan kembali nol saat backend restart. Sebelum pelonggaran (24 Nov 2026): 6 per menit, 80 per hari, total 400, login 8 per menit, Nginx 30 per menit.

## v4.2: permintaan ubah bentuk ("jadi tabel", "lebih sederhana")

Dari tes pemilik proyek di v4.1: "hi" lalu "ya tolong jelaskan itu" lalu "tolong jadi tabel" dijawab "belum tersedia", karena pesan lanjutan nyaris tanpa kata kunci dan topiknya hanya ada di jawaban sistem. Perbaikan (`main.search_query`, `_answer_topic`): untuk pesan lanjutan dengan 3 kata kunci atau kurang, kueri pencarian ditambah 250 karakter pertama jawaban sistem sebelumnya (tanpa rujukan dan markup; untuk teks sapaan dipakai contoh pertanyaannya), supaya sumbernya sama dengan jawaban yang mau diubah bentuknya. Pesan lanjutan yang membawa topik sendiri tidak ditambah potongan itu (percobaan pertama menambahkannya ke semua lanjutan dan membuat "terus PMK 78 masih dipakai gak?" kehilangan sumber karena dibanjiri topik tarif; terdeteksi di uji dan diperbaiki sebelum rilis). Kata "tabel" ikut memicu penambahan tahun berjalan pada kueri tarif.

Uji: rantai sapaan, penjelasan, sederhana, tabel (dan SKM, tabel, 3 poin) dijawab benar; 79 giliran multi-giliran dari simulasi dibandingkan dengan v4: tidak ada giliran yang kehilangan rujukan, permintaan ubah-bentuk yang disangkal 0 dari 8, biaya per giliran sama ($0,0082).

## Memperbarui situs di VPS

Salin proyek ke `~/hubter-insight`, lalu:

```bash
docker compose up -d --build backend frontend
docker compose restart nginx     # hanya bila konfigurasi nginx berubah
```

Cara kerja mode Nginx: bila sertifikat belum ada, Nginx jalan HTTP saja (agar bisa menjawab tantangan Let's Encrypt). Begitu sertifikat ada, Nginx otomatis beralih ke HTTPS dan mengalihkan HTTP ke HTTPS.

## Deploy ke VPS

1. **Beli domain**, lalu buat record **A** (mis. `chat.contoh.id`) yang mengarah ke IP VPS. Tunggu propagasi (biasanya beberapa menit).
2. **Buka port 80 dan 443.** Firewall UFW di VPS saat ini hanya mengizinkan 22:
   ```bash
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   ```
   Bila penyedia VPS punya firewall di panel (cloud firewall), buka juga di sana.
3. **Salin proyek ke VPS**, lalu buat `.env`:
   ```bash
   cp .env.example .env
   nano .env        # isi DOMAIN dan LETSENCRYPT_EMAIL
   ```
4. **Terbitkan sertifikat:**
   ```bash
   ./scripts/init-ssl.sh --dry-run-only   # uji coba aman, tidak menerbitkan apa pun
   ./scripts/init-ssl.sh                  # terbitkan sungguhan + aktifkan HTTPS
   ```
   Pembaruan sertifikat berjalan otomatis lewat container `certbot`; Nginx memuat ulang tiap 6 jam.

## Pemecahan masalah

| Gejala | Penyebab umum |
|---|---|
| Skrip menolak karena DNS | Record A belum mengarah ke IP VPS / belum propagasi |
| Certbot gagal `Timeout during connect` | Port 80 belum dibuka di UFW atau firewall panel |
| Certbot gagal `too many failed authorizations` | Terlalu banyak percobaan; pakai `--dry-run-only` dulu dan tunggu 1 jam |
| Perlu lihat log | `docker compose logs nginx` / `docker compose logs certbot` |
