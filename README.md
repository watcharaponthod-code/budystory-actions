# budystory-actions

Automation ปักหมุด + คอมเมนต์ช่อง BudyStory บน GitHub Actions

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
