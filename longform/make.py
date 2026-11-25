"""คลิปยาวเล่าเรื่องอวกาศ (ช่อง VDstudio): ภาพ NASA เลื่อนช้า + เสียงพากย์ edge-tts + เสียงบรรยากาศ 250Hz
ใช้: python longform/make.py longform/stories/<ชื่อ>.json  →  longform/out/<ชื่อ>.mp4 (+ .credits.txt)
story json: {"title": str, "scenes": [{"text": คำพากย์, "q": คำค้นภาพ NASA ภาษาอังกฤษ}]}
ต้องมี ffmpeg/ffprobe ใน PATH หรือ env FFMPEG_DIR · pip install edge-tts
"""
import asyncio, json, os, subprocess, sys, urllib.parse, urllib.request
from pathlib import Path

import edge_tts

VOICE, RATE = 'th-TH-NiwatNeural', '-12%'   # ช้าลงให้ฟังสงบ
MUSIC = Path(__file__).parent / 'music' / 'bg.mp3'
MUSIC_DB = -12                                # ระดับดนตรีพื้นหลัง (dB) ปรับตรงนี้
MUSIC_CREDIT = 'Music: "Dreamy Soundscape for Meditation", "Relaxing Ambient Soundscape", "Weightless Soundscape for Sleep" by AmbiNet (Pixabay) — Pixabay Content License'
BED_DB = -6                                 # ระดับเสียงบรรยากาศ (dB) ปรับตรงนี้ที่เดียว
W, H, FPS, PAD = 1920, 1080, 25, 1.5        # PAD = เงียบหลังจบแต่ละฉาก (วินาที)
FF = os.environ.get('FFMPEG_DIR', '')
ff = lambda name: str(Path(FF) / name) if FF else name
# ภาพงานแถลงข่าว/คนในห้อง ไม่ใช่ภาพอวกาศ
SKIP = ('chart', 'map', 'diagram', 'instruments', 'model', 'graph', 'spectrum', 'trajectory', 'skylab', 'untangled', 'break in', 'infographic', 'briefing', 'conference', 'ceremony', 'visit', 'meeting', 'employee', 'administrator', 'light-day', 'patch', 'ground track', 'flight profile', 'logo', 'poster')


def bed_filter(total, voice):
    """เสียงพื้นหลัง: ถ้ามี longform/music/bg.mp3 ใช้ดนตรีนั้นวนตลอดคลิป (11-19 ผู้ใช้: โทนสังเคราะห์ฟังไม่เป็นดนตรี)
    ไฟล์ปัจจุบัน (ผู้ใช้เลือก 11-19) = เพลง Pixabay 3 เพลงของ AmbiNet (id 315271, 315364, 315426) ต่อกัน 17 นาที · Pixabay Content License ใช้เชิงพาณิชย์ได้ ไม่บังคับเครดิต (ใส่ MUSIC_CREDIT ไว้เป็นหลักฐาน)
    ไม่มีไฟล์ = ถอยไปใช้โทน 250Hz + เสียงลมต่ำที่สร้างเอง"""
    t = f'{total:.2f}'
    tail = f"aformat=channel_layouts=stereo,afade=in:0:d=4,afade=out:st={total - 5:.2f}:d=5"
    if MUSIC.exists():
        p = MUSIC.as_posix().replace(':', '\\:')
        bed = f"amovie='{p}':loop=0,asetpts=N/SR/TB,atrim=0:{t},aresample=48000,{tail},volume={MUSIC_DB}dB[bed]"
    else:
        bed = (f"sine=f=250:d={t}[a];sine=f=125:d={t}[b];sine=f=375:d={t}[c];sine=f=500:d={t}[e];anoisesrc=c=brown:d={t}:a=0.8,lowpass=f=900[n];"
               f"[a][b][c][e][n]amix=5:weights='0.5 0.3 0.18 0.1 0.6':normalize=0,tremolo=f=0.1:d=0.4,{tail},volume={BED_DB}dB[bed]")
    return f"{bed};{voice}aresample=48000,aformat=channel_layouts=stereo[v];[v][bed]amix=2:normalize=0[mix]"


def run(*a):
    subprocess.run([str(x) for x in a], check=True, capture_output=True)


def duration(p):
    return float(subprocess.run([ff('ffprobe'), '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(p)], check=True, capture_output=True, text=True).stdout)


def width(p):
    try:
        return int(subprocess.run([ff('ffprobe'), '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width', '-of', 'csv=p=0', str(p)], check=True, capture_output=True, text=True).stdout.strip() or 0)
    except Exception:
        return 0


# 11-19 รอบ 3 ยังหลุด: แผนภูมิสีมีป้าย, แผนที่เส้นทางรถสำรวจ, คนถือของ, ภาพช่างในโรงงาน, ภาพดำเกือบทั้งจอ → กรองจากคำอธิบายภาพ + ความสว่าง
SKIP_DESC = ('annotated', 'labeled', 'labelled', 'diagram', 'graphic', 'schematic', 'chart', 'plot ', 'route', 'traverse', 'false-color', 'false color',
             'radio occultation', 'holds ', 'holding ', 'poses', 'speaks', 'technician', 'engineers', 'clean room', 'cleanroom', 'photographed at', 'news conference', 'team members')


def luma(p):
    """ความสว่างเฉลี่ย 0-255 ของภาพ"""
    try:
        r = subprocess.run([ff('ffmpeg'), '-v', 'error', '-i', str(p), '-vf', 'scale=64:36,format=gray', '-frames:v', '1', '-f', 'rawvideo', '-'], check=True, capture_output=True).stdout
        return sum(r) / max(len(r), 1)
    except Exception:
        return 255


def nasa_image(q, used, dst):
    """ภาพแรกจากคลัง NASA ที่ยังไม่ใช้ในคลิปนี้ · คืน (nasa_id, title)"""
    words = q.split()
    items = []
    while words and not items:   # คำค้นยาวไปมักได้ 0 ภาพ → ตัดคำท้ายออกทีละคำ
        url = 'https://images-api.nasa.gov/search?media_type=image&page_size=40&q=' + urllib.parse.quote(' '.join(words))
        try:
            items = [it for it in json.load(urllib.request.urlopen(url, timeout=60))['collection']['items'] if it['data'][0]['nasa_id'] not in used]
        except OSError:   # คลัง NASA ตอบ 404/หลุดเป็นบางคำค้น (11-19 ล้มทั้งคลิปเพราะเหตุนี้) → ถือว่าไม่มีภาพ ไปคำค้นถัดไป
            pass
        words.pop()
    for it in items:
        d = it['data'][0]
        desc = (d['title'] + ' ' + d.get('description', '')).lower()
        if d['nasa_id'].upper().startswith('NHQ') or any(w in d['title'].lower() for w in SKIP) or any(w in desc for w in SKIP_DESC):
            continue
        hrefs = {l['href'].rsplit('~', 1)[-1].split('.')[0]: l['href'] for l in it.get('links', []) if l['href'].lower().endswith('.jpg')}
        for size in ('large', 'orig', 'medium'):   # ใช้ลิงก์ที่ API ให้มา บางภาพไม่มีขนาด large
            if size in hrefs:
                try:
                    urllib.request.urlretrieve(urllib.parse.quote(hrefs[size], safe=':/~'), dst)
                    if width(dst) < 1600 or luma(dst) < 28:   # เล็ก = เบลอ · มืดเกือบดำ = จอว่าง
                        continue
                    used.add(d['nasa_id'])
                    return d['nasa_id'], d['title']
                except Exception:
                    continue
    raise SystemExit(f'ไม่มีภาพ NASA สำหรับ "{q}"')


def main(story_path):
    story = json.loads(Path(story_path).read_text(encoding='utf-8'))
    name = Path(story_path).stem
    out = Path(__file__).parent / 'out'
    tmp = out / name
    tmp.mkdir(parents=True, exist_ok=True)
    used, credits, parts = set(), [], []
    for i, sc in enumerate(story['scenes']):
        mp3, jpg, mp4 = tmp / f'{i:03}.mp3', tmp / f'{i:03}.jpg', tmp / f'{i:03}.mp4'
        asyncio.run(edge_tts.Communicate(sc['text'], VOICE, rate=RATE).save(str(mp3)))
        credits.append('%s — %s' % nasa_image(sc['q'], used, jpg))
        d = duration(mp3) + PAD
        # ภาพใหญ่กว่าจอ 20% แล้วเลื่อนช้าๆ ตลอดฉาก สลับซ้าย-ขวา
        x = f'(iw-{W})*t/{d:.2f}' if i % 2 == 0 else f'(iw-{W})*(1-t/{d:.2f})'
        vf = f"scale={int(W * 1.2)}:{int(H * 1.2)}:force_original_aspect_ratio=increase,crop={int(W * 1.2)}:{int(H * 1.2)},crop={W}:{H}:x='{x}':y='(ih-{H})/2',fade=in:0:{FPS},fade=out:st={d - 1:.2f}:d=1,format=yuv420p"
        run(ff('ffmpeg'), '-y', '-loop', '1', '-framerate', FPS, '-i', jpg, '-i', mp3, '-vf', vf, '-af', f'apad=pad_dur={PAD}', '-t', f'{d:.2f}',
            '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-c:a', 'aac', '-ar', '48000', '-ac', '2', mp4)
        parts.append(mp4)
        print(f'ฉาก {i + 1}/{len(story["scenes"])} {d:.1f}s', flush=True)
    lst = tmp / 'list.txt'
    lst.write_text(''.join(f"file '{p.as_posix()}'\n" for p in parts), encoding='utf-8')
    total = sum(duration(p) for p in parts)
    bed = bed_filter(total, '[0:a]')
    final = out / f'{name}.mp4'
    run(ff('ffmpeg'), '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-filter_complex', bed, '-map', '0:v', '-map', '[mix]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', final)
    (out / f'{name}.credits.txt').write_text('ภาพ: NASA\n' + '\n'.join(credits), encoding='utf-8')
    print(f'เสร็จ {final} {total / 60:.1f} นาที', flush=True)


def from_audio(audio, cues, every=20):
    """เสียงเล่าสำเร็จรูป (NotebookLM) + ภาพ NASA ตามเรื่องที่เล่า + เสียงบรรยากาศ → out/<ชื่อไฟล์เสียง>.mp4
    cues = [[วินาทีเริ่ม, "คำค้นภาพ"], ...] เรียงตามเวลา (ได้จากการถอดเสียง) · ในแต่ละช่วงเปลี่ยนภาพทุก `every` วินาที"""
    audio = Path(audio)
    out = Path(__file__).parent / 'out'
    tmp = out / audio.stem
    tmp.mkdir(parents=True, exist_ok=True)
    total = duration(audio)
    shots = []
    for k, (t0, q) in enumerate(cues):
        t1 = cues[k + 1][0] if k + 1 < len(cues) else total
        n = max(1, round((t1 - t0) / every))
        shots += [(q, (t1 - t0) / n)] * n
    used, credits, parts = set(), [], []
    for i, (q, d) in enumerate(shots):
        jpg, mp4 = tmp / f'{i:03}.jpg', tmp / f'{i:03}.mp4'
        # คำค้นนี้ภาพหมด (ตัวกรองเข้ม) → ยืมภาพจากคำค้นอื่นของเรื่องเดียวกัน · หมดทุกคำค้น = ใช้ภาพก่อนหน้าซ้ำ ดีกว่าล้มทั้งคลิป
        for alt in [q] + [c[1] for c in cues if c[1] != q]:
            try:
                credits.append('%s — %s' % nasa_image(alt, used, jpg))
                break
            except SystemExit:
                continue
        else:
            assert i > 0, f'ไม่มีภาพ NASA เลยสำหรับ {q}'
            jpg = tmp / f'{i - 1:03}.jpg'
        x = f'(iw-{W})*t/{d:.2f}' if i % 2 == 0 else f'(iw-{W})*(1-t/{d:.2f})'
        vf = f"scale={int(W * 1.2)}:{int(H * 1.2)}:force_original_aspect_ratio=increase,crop={int(W * 1.2)}:{int(H * 1.2)},crop={W}:{H}:x='{x}':y='(ih-{H})/2',fade=in:0:{FPS},fade=out:st={max(d - 1, 0):.2f}:d=1,format=yuv420p"
        run(ff('ffmpeg'), '-y', '-loop', '1', '-framerate', FPS, '-i', jpg, '-vf', vf, '-t', f'{d:.2f}', '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', mp4)
        parts.append(mp4)
        print(f'ภาพ {i + 1}/{len(shots)} {q}', flush=True)
    lst = tmp / 'list.txt'
    lst.write_text(''.join(f"file '{p.as_posix()}'\n" for p in parts), encoding='utf-8')
    final = out / f'{audio.stem}.mp4'
    run(ff('ffmpeg'), '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-i', audio, '-filter_complex', bed_filter(total, '[1:a]'), '-map', '0:v', '-map', '[mix]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', final)
    (out / f'{audio.stem}.credits.txt').write_text('ภาพ: NASA' + '\n' + '\n'.join(credits), encoding='utf-8')
    print(f'เสร็จ {final} {total / 60:.1f} นาที', flush=True)

if __name__ == '__main__':
    # make.py story.json   |   make.py --audio เสียง.m4a cues.json
    from_audio(sys.argv[2], json.loads(Path(sys.argv[3]).read_text(encoding='utf-8'))) if sys.argv[1] == '--audio' else main(sys.argv[1])
