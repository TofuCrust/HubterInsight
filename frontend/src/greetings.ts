/**
 * Sapaan acak untuk halaman sambutan: berganti tiap sesi baru, refresh, atau buka halaman.
 * Pemilihan memakai "kantong acak": semua sapaan di pool dipakai sekali dulu sebelum ada yang
 * diulang, dan riwayatnya diingat di browser sehingga refresh pun tidak mengulang kalimat yang sama.
 */

const GENERAL = [
  'Apa yang ingin Anda ketahui?',
  'Mau tanya apa hari ini?',
  'Ada yang bisa dibantu? Gas! 🚀',
  'Jangan lupa minum air putih 🚰',
  'Easy come, easy go ✌️',
  'Santai dulu, tanya belakangan ☕',
  'Satu pertanyaan, sejuta pasal 📚',
  'Tenang, pasalnya kita cari bareng 🔍',
  'Pasal mana yang bikin penasaran?',
  'Hari ini mau bongkar aturan yang mana?',
  'Tanya dulu, panik belakangan 😄',
  'Sudah ngopi belum? ☕',
  'Regangkan badan dulu, baru baca pasal 🧘',
  'Teliti itu kunci, tanyanya jangan ditunda 🔑',
  'Punggung tegak, bahu rileks, pasal siap 🪑',
  'Pelan-pelan, yang penting paham 🐌',
  'Tarik napas dulu, lalu tanya 🌬️',
  'Bingung? Wajar. Tanya saja 🤝',
  'Tak ada pertanyaan yang terlalu receh 🪙',
  'Ayo kupas aturannya lapis demi lapis 🧅',
  'Ada pasal yang bikin kening berkerut? 🤔',
  'Mari bedah peraturan, tanpa drama 🔬',
  'Baca sendiri capek? Tanya saja 😎',
  'Dokumennya banyak, pertanyaannya silakan 📂',
  'Cari jarum di tumpukan pasal? Serahkan ke sini 🧵',
  'Siap membantu, tanpa antre 🎟️',
  'Satu pertanyaan, satu langkah lebih paham 👣',
  'Kalau ragu, cek ulang ke dokumen sumber ✅',
  'Hari yang baik untuk bertanya 🌱',
  'Rileks, kita telusuri bersama 🧭',
  'Mau mulai dari mana? 🏁',
  'Tanya sekarang, pusing nanti 😌',
  'Kopi sudah, pasal berikutnya 🥤',
  'Sedia payung sebelum rapat ☔',
  'Rapat jam berapa? Tanya dulu biar siap 📝',
  'Ketik saja, nanti kita cari jawabannya ⌨️',
  'Mari bikin urusan peraturan jadi ringan 🪶',
  'Lagi cari dasar hukum? Sini 🏛️',
  'Jangan lupa berkedip dan minum 💧',
  'Istirahatkan mata sejenak, 20 detik saja 👀',
  'Ada yang mengganjal di pasal? Ceritakan 🗣️',
  'Teliti hari ini, tenang besok 🌤️',
  'Ide bagus mulai dari pertanyaan bagus 💡',
  'Hukum itu ribet? Kita sederhanakan 🧩',
  'Tanya apa saja, kecuali resep rendang 🍲',
  'Mode serius, tapi tetap santai 🕶️',
  'Pasal boleh panjang, jawabannya kita ringkas ✂️',
  'Sambil nunggu loading hidup, tanya saja ⏳',
  'Halo! Siap diskusi soal aturan? 👋',
  'Tidak ada pertanyaan bodoh, yang ada pasal rumit 📖',
  'Semangat, sedikit lagi paham! 🔥',
  'Yuk, kita kejar pasalnya 🏃',
  'Dari ayat ke ayat, kita susuri 🧗',
  'Jangan lupa makan, otak butuh bahan bakar 🍚',
  'Pelan tapi pasti, pasal demi pasal 🐢',
  'Take it easy, kita cari jawabannya 🍃',
  'Keep calm and tanya pasal 🧘‍♂️',
  'Kerja cerdas, tanya yang tepat 🎯',
  'Mulai dari pertanyaan kecil juga boleh 🐣',
]

const BY_DAY: Record<number, string[]> = {
  0: [
    'Minggu: waktunya istirahat, tapi pasal tetap menunggu 😌',
    'Sunday is a “Slow Day” 🛋️',
    'Minggu masih kepikiran kerjaan? Sini cerita 🫶',
    'Libur itu perlu, tapi rasa penasaran boleh 😄',
    'Sunday vibes: santai, tapi tetap teliti 🍃',
  ],
  1: [
    'Monday is a “Happy Day” 🌞',
    'Senin semangat, pasal jangan sampai lepas 💪',
    'Senin: mulai minggu dengan kepala dingin ❄️',
    'Monday, tapi kita tetap tersenyum 😁',
    'Awal pekan, awal yang rapi 📌',
  ],
  2: [
    'Tuesday is a Day 😅',
    'Selasa: baru mulai, belum capek kok',
    'Selasa tenang, pasal pun tenang 🌿',
    'Tuesday: sudah lewat Senin, aman 🎉',
    'Selasa produktif, tanya yang perlu 📈',
  ],
  3: [
    'Rabu: setengah jalan, tetap semangat 🐢',
    'Wednesday is a “Halfway Day” ⛰️',
    'Rabu: puncak pekan, turunnya tinggal sebentar 🏔️',
    'Midweek check: sudah minum air putih? 🚰',
    'Rabu: kerjaan setengah beres, pasal setengah paham 😆',
  ],
  4: [
    'Kamis: satu hari lagi menuju Jumat 🤞',
    'Thursday is an “Almost There Day” 🏃',
    'Kamis: sedikit lagi akhir pekan 🏖️',
    'Kamis sibuk? Pertanyaannya biar kami yang cari 🔎',
    'Thursday: tinggal selangkah lagi ke Friday 👟',
  ],
  5: [
    'Jumat berkah, pertanyaan pun lancar ✨',
    'Friday is a “Finish Strong Day” 🎯',
    'Jumat: tutup pekan dengan rapi 🗂️',
    'Hari Jumat, tanya yang penting dulu 🕌',
    'Friday feeling: tinggal beresin satu-dua pasal 🎶',
  ],
  6: [
    'Sabtu masih kerja? Salut 🫡',
    'Saturday is a “Bonus Day” 🎁',
    'Sabtu: lembur tipis-tipis, ya? 🌤️',
    'Akhir pekan, tapi semangat tetap on 🔋',
    'Saturday: pelan-pelan saja, tidak ada yang mengejar 🚶',
  ],
}

const BY_TIME = {
  pagi: [
    'Selamat pagi! Sarapan dulu? 🍳',
    'Pagi cerah, pasal pun terang ☀️',
    'Pagi! Semoga kopinya cukup kuat ☕',
    'Good morning, mari mulai dengan satu pertanyaan 🌅',
    'Pagi segar, otak segar, pasal segar 🍃',
  ],
  siang: [
    'Selamat siang! Jangan lupa makan siang 🍛',
    'Siang-siang enaknya tanya yang ringan dulu 😎',
    'Siang! Jangan sampai lupa istirahat 🕛',
    'Matahari lagi tinggi, semangat jangan turun 🌞',
    'Habis makan siang, saatnya tanya lagi 🍽️',
  ],
  sore: [
    'Selamat sore! Sedikit lagi pulang 🌇',
    'Sore-sore, waktunya rapikan pertanyaan 📝',
    'Sore tenang, pasal pun tenang 🌆',
    'Sore begini cocok untuk teh hangat 🍵',
    'Sebentar lagi senja, yuk selesaikan satu pertanyaan 🌅',
  ],
  malam: [
    'Sesi hukum malam? Gas! 🌙',
    'Malam begini masih semangat, mantap 🦉',
    'Malam tenang, waktunya mendalami pasal 🌃',
    'Jangan begadang, tanya yang penting saja 😴',
    'Lembur? Tenang, ditemani di sini 🌠',
  ],
}

const timeOfDay = (hour: number) =>
  hour < 4 ? 'malam' : hour < 11 ? 'pagi' : hour < 15 ? 'siang' : hour < 18 ? 'sore' : 'malam'

const KEY = 'hubter-greetings-seen'
const MAX_SEEN = 400

const loadSeen = (): string[] => {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? '[]')
    return Array.isArray(raw) ? raw.filter((x): x is string => typeof x === 'string') : []
  } catch {
    return []
  }
}

const saveSeen = (seen: string[]) => {
  try {
    localStorage.setItem(KEY, JSON.stringify(seen.slice(-MAX_SEEN)))
  } catch {
    /* penyimpanan tidak tersedia */
  }
}

let last = ''

/** Pilih satu sapaan acak yang belum dipakai pada putaran ini; putaran baru dimulai bila semuanya sudah tampil. */
export function pickGreeting(now: Date = new Date()): string {
  const pool = [...GENERAL, ...BY_DAY[now.getDay()], ...BY_TIME[timeOfDay(now.getHours())]]
  let seen = loadSeen()

  let fresh = pool.filter((g) => !seen.includes(g))
  if (fresh.length === 0) {
    // Putaran selesai: mulai lagi, tapi jangan langsung mengulang yang paling akhir
    seen = seen.filter((g) => !pool.includes(g))
    fresh = pool.filter((g) => g !== last)
  }

  const choice = fresh[Math.floor(Math.random() * fresh.length)] ?? pool[0]
  last = choice
  saveSeen([...seen.filter((g) => g !== choice), choice])
  return choice
}
