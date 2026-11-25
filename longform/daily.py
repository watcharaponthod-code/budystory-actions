"""คลิปยาวอวกาศวันละคลิป ลงช่อง VDstudio เอง (รันบนเครื่องนี้ด้วย Task Scheduler — NotebookLM ต้องใช้ Chrome ที่ล็อกอินไว้ พอร์ต 9334)
ขั้น: เลือกหัวข้อที่ยังไม่เคยทำ → เนื้อหา Wikipedia → NotebookLM เจนเสียงพิธีกร → ภาพ NASA + เสียงบรรยากาศ (make.py) → อัปผ่าน Maton
ใช้: python longform/daily.py            (ทำจริง+ลง public)
     python longform/daily.py --no-upload (ทำถึงเรนเดอร์ ไม่ลง)
"""
import datetime, json, os, subprocess, sys, time, urllib.parse, urllib.request, uuid
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
ENV = {**(dict(l.split('=', 1) for l in (ROOT / '.env').read_text(encoding='utf-8').splitlines() if '=' in l and not l.startswith('#')) if (ROOT / '.env').exists() else {}), **os.environ}
# 11-25 ผู้ใช้สั่ง: รันบน cloud (GitHub ubuntu) ไม่ใช่เครื่องผู้ใช้ → มี NB_STATE (cookie Google gzip+base64) = เปิด Chromium เองด้วย cookie · ไม่มี = Chrome บนเครื่อง พอร์ต 9334 แบบเดิม
NB_STATE = os.environ.get('NB_STATE')
CDP, PROFILE = 'http://127.0.0.1:9334', Path(os.environ.get('LOCALAPPDATA', '.')) / 'ChromeProfiles' / 'vdstudio'
USED, LOG = HERE / 'used.json', HERE / 'daily.log'
if os.name == 'nt' and not os.environ.get('FFMPEG_DIR'):   # ffmpeg จาก WinGet ไม่อยู่ใน PATH ของงานตั้งเวลา และโฟลเดอร์เปลี่ยนชื่อตามเวอร์ชัน
    found = sorted((Path(os.environ['LOCALAPPDATA']) / 'Microsoft/WinGet/Packages').glob('Gyan.FFmpeg_*/ffmpeg-*/bin'))
    if found:
        os.environ['FFMPEG_DIR'] = str(found[-1])
MAX_SEC = 15 * 60 - 5   # ช่องยังไม่ยืนยันเบอร์ YouTube รับไม่เกิน 15 นาที
PROMPT = ('พูดเป็นภาษาไทยทั้งหมด น้ำเสียงนุ่ม ช้า สงบ ผ่อนคลาย เหมาะกับคนฟังก่อนนอน ไม่ตื่นเต้น ไม่หัวเราะดัง '
          'เล่าเรื่องต่อเนื่องเรียงตามลำดับเนื้อหาในแหล่งข้อมูล ให้ยาวและละเอียดที่สุด ใช้ข้อเท็จจริงจากแหล่งข้อมูลเท่านั้น ไม่พูดถึงคำว่าแหล่งข้อมูลหรือเอกสาร')


def log(msg):
    line = f'{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {msg}'
    print(line, flush=True)
    with LOG.open('a', encoding='utf-8') as f:
        f.write(line + '\n')


def wiki_text(title):
    url = 'https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&redirects=1&format=json&titles=' + urllib.parse.quote(title)
    req = urllib.request.Request(url, headers={'User-Agent': 'longform-video/1.0'})
    page = next(iter(json.load(urllib.request.urlopen(req, timeout=60))['query']['pages'].values()))
    text = page.get('extract', '')
    assert len(text) > 3000, f'Wikipedia {title} สั้นเกิน ({len(text)})'
    return page['title'], text.split('\n== See also')[0].split('\n== References')[0][:60000]


def chrome():
    try:
        urllib.request.urlopen(CDP + '/json/version', timeout=3)
    except Exception:
        exe = next(p for p in (Path(os.environ.get('ProgramFiles', '')) / 'Google/Chrome/Application/chrome.exe',
                               Path(os.environ.get('ProgramFiles(x86)', '')) / 'Google/Chrome/Application/chrome.exe',
                               Path(os.environ['LOCALAPPDATA']) / 'Google/Chrome/Application/chrome.exe') if p.exists())
        subprocess.Popen([str(exe), f'--user-data-dir={PROFILE}', '--remote-debugging-port=9334', '--no-first-run', '--no-default-browser-check', 'about:blank'])
        time.sleep(8)


def notebook_audio(name, text, dest):
    """สร้าง notebook ใหม่ วางเนื้อหา สั่งภาพรวมแบบเสียงภาษาไทย รอ แล้วดาวน์โหลด → (ไฟล์ m4a, ชื่อที่ NotebookLM ตั้ง)"""
    from playwright.sync_api import sync_playwright
    if not NB_STATE:
        chrome()
    dest.mkdir(parents=True, exist_ok=True)
    for f in dest.glob('*'):
        f.unlink()
    with sync_playwright() as p:
        if NB_STATE:
            import base64, gzip
            saved = json.loads(gzip.decompress(base64.b64decode(NB_STATE)))
            b = p.chromium.launch(headless=True)
            ctx = b.new_context(storage_state=saved['state'], user_agent=saved['ua'], locale='th-TH', timezone_id='Asia/Bangkok', accept_downloads=True)
        else:
            b = p.chromium.connect_over_cdp(CDP, timeout=120000)
            ctx = b.contexts[0]
        page = ctx.new_page()
        page.set_default_timeout(60000)
        page.set_viewport_size({'width': 930, 'height': 920})   # จอแคบ = หน้าแบบแท็บ Sources/แชท/Studio ที่สคริปต์นี้รู้จัก (จอกว้างเป็น 3 คอลัมน์ ปุ่มคนละแบบ)
        page.goto('https://notebooklm.google.com/', wait_until='domcontentloaded')
        page.wait_for_timeout(6000)
        assert 'accounts.google.com' not in page.url, 'หลุดล็อกอิน Google — cookie หมดอายุ/Google ตัด ต้องส่ง NB_STATE ใหม่' if NB_STATE else 'Chrome ช่องใหม่หลุดล็อกอิน Google — ต้องล็อกอินใหม่ในหน้าต่างพอร์ต 9334'
        page.get_by_text('Notebook ใหม่').first.click()
        page.wait_for_url('**/notebook/**')
        page.wait_for_timeout(5000)
        page.get_by_text('Sources', exact=True).first.click(); page.wait_for_timeout(2500)
        page.get_by_text('เพิ่มแหล่งข้อมูล').first.click(); page.wait_for_timeout(3500)
        page.get_by_text('ข้อความที่คัดลอก').first.click(); page.wait_for_timeout(2500)
        page.locator('textarea:visible').last.fill(name + '\n\n' + text); page.wait_for_timeout(1500)
        page.get_by_role('button', name='แทรก').click(); page.wait_for_timeout(15000)
        try:
            page.get_by_role('button', name='ปิดโน้ต').click(timeout=8000); page.wait_for_timeout(2000)
        except Exception:
            pass
        page.get_by_text('Studio', exact=True).first.click(); page.wait_for_timeout(3000)
        page.get_by_role('button', name='ภาพรวมแบบเสียง').first.click(); page.wait_for_timeout(5000)
        d = page.locator('mat-dialog-container').first
        if 'ไทย' not in d.inner_text():
            d.get_by_text('English', exact=True).first.click(); page.wait_for_timeout(1500)
            page.locator('[role=option]:visible', has_text='ไทย').first.click(); page.wait_for_timeout(1500)
        d.get_by_text('ค่าเริ่มต้น', exact=True).first.click(); page.wait_for_timeout(800)
        d.locator('textarea:visible').last.fill(PROMPT); page.wait_for_timeout(1000)
        d.get_by_role('button', name='สร้างเลย').click(); page.wait_for_timeout(10000)
        t = time.time()
        while 'กำลังสร้าง' in page.evaluate('document.body.innerText'):
            assert time.time() - t < 40 * 60, 'NotebookLM เจนเสียงเกิน 40 นาที'
            page.wait_for_timeout(20000)
        body = page.evaluate('document.body.innerText')
        assert 'เจาะลึกข้อมูล' in body or 'พร้อมใช้งาน' in body, 'NotebookLM ไม่ได้เสียงออกมา (โควตาหมด?): ' + body[-300:].replace('\n', ' ')
        if not NB_STATE:   # Chrome บนเครื่อง: expect_download ทำ Chrome หลุด
            ctx.new_cdp_session(page).send('Browser.setDownloadBehavior', {'behavior': 'allow', 'downloadPath': str(dest)})
        page.keyboard.press('Escape'); page.wait_for_timeout(800)
        page.locator('button:visible', has_text='more_vert').nth(1).click(); page.wait_for_timeout(1500)
        item = page.locator('[role=menuitem]:visible').filter(has_text='ดาวน์โหลด').first
        if NB_STATE:
            with page.expect_download(timeout=180000) as dl:
                item.click()
            dl.value.save_as(dest / dl.value.suggested_filename)
        else:
            item.click()
        t = time.time()
        while not [f for f in dest.glob('*') if f.suffix != '.crdownload']:
            assert time.time() - t < 180, 'ดาวน์โหลดเสียงไม่สำเร็จ'
            page.wait_for_timeout(2000)
        page.close()
    src = next(f for f in dest.glob('*') if f.suffix != '.crdownload')
    return src, src.stem.replace('_', ' ').strip()


def upload(path, title, description, tags):
    meta = {'snippet': {'title': title[:95], 'description': description, 'tags': tags, 'categoryId': '28', 'defaultLanguage': 'th', 'defaultAudioLanguage': 'th'},
            'status': {'privacyStatus': 'public', 'selfDeclaredMadeForKids': False, 'containsSyntheticMedia': True}}
    bd = '====' + uuid.uuid4().hex
    head = ('--%s\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n%s\r\n--%s\r\nContent-Type: video/mp4\r\n\r\n' % (bd, json.dumps(meta, ensure_ascii=False), bd)).encode('utf-8')
    body = head + Path(path).read_bytes() + ('\r\n--%s--\r\n' % bd).encode('utf-8')
    req = urllib.request.Request('https://api.maton.ai/youtube/upload/youtube/v3/videos?uploadType=multipart&part=snippet,status', data=body,
                                 headers={'Authorization': 'Bearer ' + ENV['MATON_API_KEY'].strip(), 'Maton-Connection': ENV['MATON_VD_CONNECTION'].strip(),
                                          'Content-Type': 'multipart/related; boundary=' + bd})
    d = json.loads(urllib.request.urlopen(req, timeout=1800).read().decode('utf-8'))
    # กันลงผิดช่อง: คำตอบต้องเป็นช่อง VDstudio เท่านั้น
    assert d['snippet']['channelId'] == 'UCovwtNBSLDVNAhOVuRduTew', f"ลงผิดช่อง! {d['snippet']['channelId']} video {d.get('id')}"
    return d['id']


def main(do_upload=True, skip=()):
    import make
    topics = json.loads((HERE / 'topics.json').read_text(encoding='utf-8'))
    used = json.loads(USED.read_text(encoding='utf-8')) if USED.exists() else []
    left = [t for t in topics if t['wiki'] not in used and t['wiki'] not in skip]
    assert left, 'หัวข้อใน topics.json หมดแล้ว ต้องเพิ่มหัวข้อใหม่'
    topic = left[0]
    main.topic = topic['wiki']
    day = datetime.date.today().isoformat()
    log(f'เริ่ม {topic["wiki"]}')
    name, text = wiki_text(topic['wiki'])
    src, title = notebook_audio(name, text, HERE / 'out' / 'nb' / day)
    audio = HERE / 'out' / 'nb' / f'{day}.m4a'
    total = make.duration(src)
    log(f'ได้เสียง {total / 60:.1f} นาที ชื่อ "{title}"')
    if total > MAX_SEC:   # shortcut: ตัดท้ายทิ้งถ้าเกิน 15 นาที, ยืนยันเบอร์ช่องแล้วให้ลบ MAX_SEC
        make.run(make.ff('ffmpeg'), '-y', '-i', src, '-t', MAX_SEC, '-af', f'afade=out:st={MAX_SEC - 4}:d=4', '-c:a', 'aac', '-b:a', '160k', audio)
        total = MAX_SEC
    else:
        src.replace(audio)
    # shortcut: ภาพไล่ตามลำดับคำค้นของหัวข้อ แบ่งเวลาเท่ากัน (พิธีกรเล่าตามลำดับเนื้อหา) — ถ้าภาพไม่ตรงช่วงให้เปลี่ยนเป็นถอดเสียงแล้วจับคำ
    step = total / len(topic['q'])
    make.from_audio(audio, [[i * step, q] for i, q in enumerate(topic['q'])])
    video = HERE / 'out' / f'{day}.mp4'
    credits = (HERE / 'out' / f'{day}.credits.txt').read_text(encoding='utf-8')
    if do_upload:
        desc = (f'{title}\n\nฟังเรื่องราวจากอวกาศแบบสบายๆ ก่อนนอน ภาพจริงจากคลังภาพของ NASA\n\n'
                f'เสียงบรรยายและบทสร้างด้วย AI จากข้อมูลสารานุกรม · ภาพ: NASA (public domain)\n{make.MUSIC_CREDIT if make.MUSIC.exists() else ""}\n\n#อวกาศ #ดาราศาสตร์ #ฟังก่อนนอน #จักรวาล #space\n\n{credits[:3000]}')
        vid = upload(video, f'{title} | เล่าเรื่องอวกาศฟังก่อนนอน', desc, ['อวกาศ', 'ดาราศาสตร์', 'จักรวาล', 'ฟังก่อนนอน', 'เล่าเรื่องอวกาศ', 'ผ่อนคลาย', 'สารคดีอวกาศ', 'พอดแคสต์อวกาศ', 'เรื่องเล่าก่อนนอน',
                      'นอนหลับ', 'ระบบสุริยะ', 'นาซา', 'NASA', 'space', 'astronomy', 'space documentary', 'sleep podcast', name] + topic['q'][:6])   # แท็กรวมต้องไม่เกิน 500 ตัวอักษร
        log(f'ลงแล้ว https://youtu.be/{vid}')
        video.unlink()
    USED.write_text(json.dumps(used + [topic['wiki']], ensure_ascii=False, indent=1), encoding='utf-8')
    log('จบ')


def run_all():
    """ลงต่อเนื่องจนโควตา NotebookLM หมด: หัวข้อที่ล้มถูกข้ามในรอบนี้ · ล้ม 2 เรื่องติดกัน = หยุด (โควตาหมดหรือระบบเสีย)"""
    skip, fails, done = set(), 0, 0
    while fails < 2 and done < 5:   # ผู้ใช้กำหนดวันละ 5 คลิป
        main.topic = None
        try:
            main(True, skip)
            fails, done = 0, done + 1
        except Exception as e:
            log(f'ล้ม: {type(e).__name__} {str(e)[:500]}')
            if main.topic is None:   # หัวข้อหมด/อ่านรายการไม่ได้ วนต่อไม่มีประโยชน์
                break
            fails += 1
            skip.add(main.topic)
    log(f'จบรอบวัน ลงได้ {done} คลิป')
    return done


if __name__ == '__main__':
    if '--all' in sys.argv:
        sys.exit(0 if run_all() else 1)
    try:
        main('--no-upload' not in sys.argv)
    except BaseException as e:
        log(f'ล้ม: {type(e).__name__} {str(e)[:500]}')
        raise
