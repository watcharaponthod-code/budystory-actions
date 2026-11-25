// ปักตะกร้าสินค้าใน YouTube Studio บนเครื่องของ GitHub (ผู้ใช้สั่ง 2026-11-24: ไม่รันบนเครื่องตัวเอง)
// Cloudflare Worker บอกว่าคลิปรีวิวไหนยังไม่ปัก + คำค้น (/tagtodo) และจดผล (/tagdone) · เบราว์เซอร์ล็อกอินด้วย cookie Google ใน secret YT_STORAGE_STATE
// choose + tagOne คัดลอกจาก scripts/tag_products.mjs ของโปรเจกต์ (ตัวที่เคยรันบนเครื่อง) แก้ที่นั่น = แก้ที่นี่ด้วย
import { gunzipSync } from 'node:zlib';
import { chromium } from 'playwright';

const W = process.env.WORKER_URL, K = process.env.CF_RUN_KEY, dry = process.env.DRY === 'true', PER_CLIP = 1;
const CHANNEL = 'UCJ5qIG4kQvvMlN8BR98gjeA';
const api = async path => { const r = await fetch(`${W}${path}&key=${K}`); if (!r.ok) throw new Error(`${path.split('?')[0]} ${r.status}`); return r.text(); };

function choose(results, must, min, max = Infinity) {
  return results.map((r, i) => ({ ...r, i, pct: +(r.text.match(/([0-9.]+) *%/)?.[1] ?? 0), price: +(r.text.match(/฿ *([0-9,.]+)/)?.[1].replace(/,/g, '') ?? 0) }))
    .filter(r => must.every(m => r.title.toLowerCase().includes(m)) && r.price >= min && r.price <= max).sort((a, b) => b.price * b.pct - a.price * a.pct)[0];
}

// 11-25 คำค้นของฮิตรายสัปดาห์เป็นชื่อร้านยาวโดนตัด ('กระเป๋าโท้ตเก็บอาหาร 6 12Lกระเป๋าใส่อาหา') Studio ค้นไม่เจอ → ข้อสองค้นด้วยชื่อสั้น cat ช่วงราคากว้างขึ้น
// รันใน Chrome: คืน {status, products}. คลิกด้วย JS เพราะ Studio รายงาน element เป็น hidden กับ Playwright
const tagOne = (id, queries, dry, retag) => `async (page) => {
  const sleep = ms => page.waitForTimeout(ms);
  await page.goto('https://studio.youtube.com/video/${id}/edit', { timeout: 45000, waitUntil: 'commit' }).catch(() => {});
  try { await page.waitForSelector('#shopping-toolbar-edit', { state: 'attached', timeout: 30000 }); } catch { return { status: 'no-toolbar' }; }   // ยังไม่เผยแพร่/ติดแท็กไม่ได้
  await sleep(3000);
  const has = () => page.evaluate(() => !document.querySelector('.ytcpShoppingProductTaggingToolbarNoProductsMessage'));
  if (!${retag} && await has()) return { status: 'already' };
  await page.evaluate(() => document.querySelector('#shopping-toolbar-edit').click());
  await page.waitForSelector('ytcp-dialog#main-dialog #search-input', { state: 'attached', timeout: 20000 });
  await sleep(1500);
  if (${retag} && !${dry}) { await page.evaluate(() => document.querySelector('ytcp-dialog#main-dialog .ytshoppingProductPickerSelectedProductClearAll button')?.click()); await sleep(1500); }   // --retag: ล้างของเดิมก่อน
  const products = [];
  for (const P of ${JSON.stringify(queries)}) {
    const q = P.q;
    if (products.length >= ${PER_CLIP}) break;
    await page.evaluate(q => { const i = document.querySelector('ytcp-dialog#main-dialog #search-input'); i.focus(); i.value = q; i.dispatchEvent(new Event('input', { bubbles: true })); }, q);
    await page.keyboard.press('Enter').catch(() => {});
    const choose = ${choose.toString()}; let p;
    for (let t = 0; t < 10; t++) {   // รอจนผลค้นเปลี่ยนจากคำค้นก่อนหน้าและนิ่ง
      await sleep(1500);
      const r = await page.evaluate(() => document.querySelector('ytcp-dialog#main-dialog tp-yt-paper-progress')?.hasAttribute('active') ? [] : [...document.querySelectorAll('ytcp-dialog#main-dialog ytshopping-product-picker-search-result')].map(e => ({ title: e.querySelector('.ytcpYtshoppingProductProductTitle')?.innerText.trim() || '', text: e.innerText })));
      if ((p = choose(r, P.must, P.min, P.max ?? Infinity))) break;   // รอจนผลค้นมีรุ่นที่ค้นจริง (ผลค้างจากคำค้นก่อน/รายการแนะนำเริ่มต้นไม่ผ่าน)
    }
    if (!p || products.some(x => x.startsWith(p.title.slice(0, 50)))) continue;
    products.push(p.title.slice(0, 50) + ' ฿' + p.price + ' ' + p.pct + '%');
    if (!${dry}) { await page.evaluate(i => document.querySelectorAll('ytcp-dialog#main-dialog ytshopping-product-picker-search-result')[i].querySelector('.tag-product-button').click(), p.i); await sleep(1200); }
  }
  if (!products.length) return { status: 'no-results' };
  if (${dry}) return { status: 'dry', products };
  const header = await page.evaluate(() => document.querySelector('ytcp-dialog#main-dialog .ytshoppingProductPickerHeaderTitle')?.innerText || '');
  await page.evaluate(() => [...document.querySelectorAll('ytcp-dialog#main-dialog .footer button')].find(b => b.innerText.trim() === 'เสร็จ').click());
  await sleep(2500);
  // บางเวอร์ชัน "เสร็จ" บันทึกเลย บางเวอร์ชันต้องกด "บันทึก" ของหน้า
  await page.evaluate(() => { const b = document.querySelector('ytcp-button#save button, #save button'); if (b && !b.disabled && b.getAttribute('aria-disabled') !== 'true') b.click(); });
  await sleep(5000);
  // พิสูจน์: โหลดหน้าใหม่แล้วต้องยังเห็นสินค้า
  await page.goto('https://studio.youtube.com/video/${id}/edit', { timeout: 45000, waitUntil: 'commit' }).catch(() => {});
  await page.waitForSelector('#shopping-toolbar-edit', { state: 'attached', timeout: 30000 }).catch(() => {});
  await sleep(3500);
  return { status: (await has()) ? 'tagged' : 'not-saved', header, products };
}`;

const todo = JSON.parse(await api(`/tagtodo?days=${+process.env.DAYS || 3}`)).slice(0, +process.env.LIMIT || 5);
console.log('ต้องปัก', todo.length, 'คลิป');
if (!todo.length) process.exit(0);   // ไม่มีคลิปรีวิวค้าง = ไม่เปิดเบราว์เซอร์ ไม่แตะบัญชี Google

const saved = process.env.YT_STORAGE_STATE ? JSON.parse(gunzipSync(Buffer.from(process.env.YT_STORAGE_STATE, 'base64')).toString()) : {};   // gzip: cookie ดิบเกินเพดาน secret 48 KB
if (!saved.state) throw new Error('ไม่มี secret YT_STORAGE_STATE');
const browser = await chromium.launch({ channel: 'chrome', headless: true });
let fail = 0;
try {
  const page = await (await browser.newContext({ storageState: saved.state, userAgent: saved.ua, locale: 'th-TH', timezoneId: 'Asia/Bangkok', viewport: { width: 1440, height: 900 } })).newPage();
  const run = code => (0, eval)(`(${code})`)(page);
  // Chrome มีหลายบัญชี: ไล่หา authuser ที่เข้า Studio ของ BudyStory ได้ ไม่เจอ = cookie หมดอายุ/Google ไม่รับเครื่องนี้ → ล้มดังๆ
  let acct = -1;
  for (let n = 0; n < 6 && acct < 0; n++) {
    await page.goto(`https://studio.youtube.com/channel/${CHANNEL}?authuser=${n}`, { timeout: 45000, waitUntil: 'commit' }).catch(() => {});
    await page.waitForTimeout(7000);
    if (await page.evaluate(() => !!document.querySelector('ytcp-navigation-drawer')).catch(() => false)) acct = n;
  }
  if (acct < 0) throw new Error('เข้า Studio ของ BudyStory ไม่ได้ (หน้า ' + new URL(page.url()).hostname + ') — cookie หมดอายุหรือ Google ขอยืนยันตัวตน ต้องส่ง cookie ใหม่');
  for (const c of todo) {
    let r; try { r = await run(tagOne(c.id, [{ q: c.q, must: c.must, min: c.min, max: c.max ?? undefined }, { q: c.cat, must: [c.cat.toLowerCase()], min: Math.floor(c.min / 2), max: c.max ? c.max * 2 : undefined }], dry, false)); } catch (e) { r = { status: 'error', msg: String(e.message).slice(0, 300) }; }
    console.log(c.id, c.cat, JSON.stringify(r));
    if (!dry) await api(`/tagdone?id=${c.id}&status=${r.status}`);
    if (!['tagged', 'already', 'dry', 'no-toolbar'].includes(r.status)) fail++;
  }
} finally { await browser.close(); }
process.exitCode = fail ? 1 : 0;
