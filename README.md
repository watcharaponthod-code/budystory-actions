# budystory-actions

Automation ปักหมุด + คอมเมนต์ช่อง + **ปักตะกร้าสินค้า (YouTube Shopping)** บน GitHub Actions

## ปักตะกร้าสินค้า (tag-products) — รันบน self-hosted runner ของเครื่องนี้

- **Data API ไม่มี endpoint ปักสินค้า** (ยืนยันจาก docs 16 พ.ย. 2026 — videos.update มีแค่ snippet/status เท่านั้น)
  การติดแท็กจริงทำได้ทางเดียว = YouTube Studio UI โปรเจกต์จึงใช้ `scripts/tag_products.mjs`
  ขับ Chrome จริงผ่าน Playwright MCP bridge — ซึ่งต้องรันในเครื่องที่ล็อกอิน BudyStory
- ทางแก้ = **self-hosted runner** บนเครื่องเรา: นาทีรันฟรีไม่จำกัด (กติกาเดียวกับ public repo)
  ใช้ IP/Chrome/ล็อกอินจริง ไม่มีความเสี่ยง Google บล็อกบัญชีจากการล็อกอินผ่าน IP ดาต้าเซ็นเตอร์
- เงื่อนไขให้รอบรันสำเร็จ: เครื่องเปิด + runner ทำงานอยู่ + Chrome ล็อกอิน BudyStory และเปิด
  extension bridge (token ใน `.env`) ไว้ · คลิปที่ยังตั้งเวลาไม่ public จะถูกข้ามแล้วรอบหน้าติดเอง
- ตาราง: ทุกวัน **16:40 เวลาไทย** หลังคลิปขึ้นครบ + ยิงมือได้ที่ Actions > tag-products > Run
  workflow (ใส่ days / limit / dry / retag ได้)
- เลือกสินค้าให้คลิปอัตโนมัติจาก `REVIEW_PRODUCTS` ใน `cloudflare/picker.js` (กฎ highcom:
  ราคา×ค่าคอมสูงสุด + ชื่อต้องมีคำใน `must` + ราคา ≥ min) แก้รายการสินค้าที่เดียวกันนั้น

### ติดตั้ง runner บนเครื่องนี้ (ติดตั้งแล้วเมื่อ 16 พ.ย. 2026)

1. ติดตั้งไว้ที่ `C:\actions-runner` (runner v2.338.2, labels self-hosted/Windows/X64,
   ชื่อ LAPTOP-78Q10VL3, work dir `C:\actions-runner\_work`)
2. **สตาร์ตผ่าน `run-invariant.cmd` เท่านั้น** — wrapper ที่ตั้ง
   `DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1` เพราะ runner มี bug #4686:
   เครื่อง culture `th-TH` ทุก job ล้มก่อน step แรกใน SecretMasker
3. เปิดอัตโนมัติตอนล็อกอินผ่าน HKCU Run key → `run-hidden.vbs` (หน้าต่างซ่อน)
4. ทดสอบ: Actions > runner-smoke > Run workflow (ต้อง success) แล้ว
   tag-products > Run workflow ตั้ง `dry=true` > ดู log

### ทำไมไม่ยิง Studio จาก GitHub-hosted runner (ubuntu-latest) ตรง ๆ

ต้องฉีด cookies ล็อกอิน Studio ไปรันบน IP ดาต้าเซ็นเตอร์ = Google มองว่า session ผิดปกติ
เสี่ยงบัญชีช่องถูกล็อก/ต้องยืนยันตัวตนกลางคัน (ช่วงนี้กำลังจะยื่น YPP) — ไม่คุ้ม ห้ามใช้

## ทำอะไรทุกวัน (15:30 เวลาไทย หลัง Worker budystory-upload ลงคลิปเสร็จ)

1. หาคลิปใหม่ที่อัปภายใน 26 ชม. ผ่าน uploads playlist (ไม่ใช้โควตา search)
2. โพสต์คอมเมนต์ CTA จากช่องเป็น **คอมเมนต์แรก** ของคลิป (สุ่มจาก pool 8 ข้อความ กัน spam flag, ตรวจซ้ำไม่โพสต์ซ้ำ)
3. เลือกได้: ปักหมุดคลิปฮิตไว้หน้าแรกช่อง (featured video) — เปิดด้วย variable `FEATURED_ENABLED=true`
4. รันมือเป็นครั้งคราวได้: Actions > engage > Run workflow (ใส่ video_id เจาะจงได้)

## ข้อจำกัดจริงของ YouTube API (ยืนยันจาก docs 16 พ.ย. 2026)

- **ปักหมุดคอมเมนต์ (pin comment) ไม่มี endpoint ทางการ** — ต้องกดมือใน Studio (10 วิ)
  ทางเลือกที่เราทำแทน: โพสต์คอมเมนต์จากช่องทันทีหลังอัป = อยู่ท็อปโดยพฤตินัย
- **ปักหมุดคลิปหน้าช่อง ทำได้ทางการ** ผ่าน `brandingSettings.featuredVideoUrl` — workflow นี้รองรับแล้ว
- การใช้ internal API ของเว็บ YouTube เพื่อบังคับ pin คอมเมนต์ = ผิด ToS เสี่ยงช่อง — ห้าม

## ตั้งค่าครั้งเดียว (ผู้ใช้ต้องทำเอง — ห้ามส่ง token ผ่านแชต/ไฟล์ทุกกรณี)

1. เข้า https://console.cloud.google.com สร้าง project (หรือใช้เดิม) > เปิด **YouTube Data API v3**
2. APIs & Services > Credentials > สร้าง **OAuth client ID** ชนิด Web application
3. เข้า https://developers.google.com/oauthplayground (กดรูปเฟือง > ใช้ client credentials ของเรา)
   - Scope: `https://www.googleapis.com/auth/youtube.force-ssl`
   - ล็อกอินด้วย **บัญชี Google ของช่อง BudyStory** > Authorize > Exchange code for tokens
   - คัดลอก **refresh token**
4. ใน repo นี้: Settings > Secrets and variables > Actions
   - Secrets: `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`
   - Variables: `YT_CHANNEL_ID` = UC... ของช่อง, `FEATURED_ENABLED` = `true`/`false`
5. กด Run workflow ทดสอบ 1 รอบ > ดู log ว่า `comment posted on ...`
6. เสร็จแล้วระบบรันเองทุกวันตาม schedule

## ทำไม repo ต้องเป็น public

GitHub Actions ทางการ: **ฟรีไม่จำกัดนาทีสำหรับ standard runners บน public repo และ self-hosted runners**
(private = ฟรีแค่ 2,000 นาที/เดือน) โค้ดใน repo นี้ไม่มี secret ใด ๆ ทุก secret อยู่ใน Actions settings เท่านั้น

## โควตา YouTube ที่กินต่อรอบ

channels.list 1 + playlistItems 1 + ต่อคลิป: commentThreads.list 1 + insert 50
=> ~450-500 units/วัน จาก 10,000 ดีฟอลต์ (คอมเมนต์ 200 ตัว/วันยังไหว)

## แก้ข้อความคอมเมนต์

แก้ pool ใน `scripts/yt_engage.py` (ตัวแปร `COMMENTS`) — เขียนอีสานให้เข้าธีมตัวละคร
เลี่ยงคำหยาบระดับแรงในคอมเมนต์ (คอมเมนต์ช่องก็โดนเช็ค advertiser-friendly เหมือนกัน)
