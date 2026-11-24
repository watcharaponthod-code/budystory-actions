# budystory-actions

Automation ปักหมุด + คอมเมนต์ช่อง + **ปักตะกร้าสินค้า (YouTube Shopping)** บน GitHub Actions

## ปักตะกร้าสินค้า (tag-products) — รันบนเครื่องของ GitHub (ตั้งแต่ 24 พ.ย. 2026)

- ผู้ใช้สั่ง 24 พ.ย. 2026: ไม่รันบนเครื่องตัวเอง Scheduled Task `BudyStory-TagProducts` ถูกลบ และ self-hosted runner
  `C:ctions-runner` ถูกปิด (โฟลเดอร์ยังอยู่ ไม่เปิดเองตอนล็อกอินแล้ว)
- **Data API ไม่มี endpoint ปักสินค้า** ต้องทำผ่านหน้า YouTube Studio: `scripts/tag_cloud.mjs` เปิด Chrome บน `ubuntu-latest`
  ล็อกอินด้วย cookie Google ของช่องใน secret `YT_STORAGE_STATE` (gzip + base64 ของ Playwright storageState + user agent)
- Cloudflare Worker `budystory-upload` บอกคลิปรีวิวที่ยังไม่ปักพร้อมคำค้น (`/tagtodo`) และจดผลใน KV `tag:<id>` (`/tagdone`)
  ไม่มีคลิปค้าง = ไม่เปิดเบราว์เซอร์ · คลิปที่หาสินค้าไม่เจอ 3 รอบจะเลิกลอง
- ตาราง: ทุก 15 นาที 10:05-14:50 และ 15:05 เวลาไทย + ยิงมือได้ (days / limit / dry)
- Secrets: `YT_STORAGE_STATE`, `CF_RUN_KEY`, `WORKER_URL`
- **ถ้า run ล้มด้วย "เข้า Studio ของ BudyStory ไม่ได้"** = cookie หมดอายุหรือ Google ขอยืนยันตัวตน: ส่งออก cookie ใหม่จาก Chrome
  ที่ล็อกอินช่อง (เฉพาะโดเมน google.com / youtube.com) แล้วตั้ง secret ใหม่
- ความเสี่ยงที่รับไว้: Google เห็นการเข้าใช้จาก IP ดาต้าเซ็นเตอร์ อาจตัด session หรือขอยืนยันตัวตน
- ห้ามอัป screenshot / trace เป็น artifact: repo นี้ public
- `choose` + `tagOne` ใน `tag_cloud.mjs` คัดลอกจาก `scripts/tag_products.mjs` ของโปรเจกต์ แก้กฎเลือกสินค้าต้องแก้ทั้งสองที่

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
