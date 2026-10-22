#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
청소년 매일성경 월별 큐티 지면 PDF 만들기.

매일성경은 PDF를 주지 않는다. 날짜별 JPEG 두 장(-1, -2)만 올라온다.
  https://sum.su.or.kr:8888/Bible_Attach/QT2/J{YYYYMMDD}-{1|2}.jpg
아직 안 올라온 날짜는 404가 아니라 '200 + HTML 안내 페이지'를 돌려주므로,
파일 앞 두 바이트가 JPEG인지(\xff\xd8)로만 판별한다.

한 달이 다 올라왔을 때만 묶어서 files/<YYYY-MM>/youth-qt-<YYYY-MM>.pdf 로 저장하고,
files/qt-index.json 을 디스크에 있는 PDF들로 다시 적는다.
연도를 박아 두지 않으므로 해가 바뀌어도 그대로 돈다.
"""
import calendar, datetime, io, json, os, re, sys, time, urllib.request, urllib.error

KST = datetime.timezone(datetime.timedelta(hours=9))
BASE = 'https://sum.su.or.kr:8888/Bible_Attach/QT2/J{ymd}-{slot}.jpg'
UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUALITY = 80          # 원본과 눈으로 구분이 안 되면서 용량은 1/3
MAX_MISSING = 2       # 중간에 이만큼까지 '아직 안 올라온 날'은 봐준다
TRIES = 4             # 연결이 끊겼을 때 다시 걸어 보는 횟수
PAUSE = 0.4           # 연달아 부르면 서버가 끊는다 — 한 장마다 조금 쉰다

MISSING = object()    # 서버가 '그런 날 없다'고 안내 페이지를 준 것 — 아직 안 올라옴


class FetchFailed(Exception):
    """안 올라온 것이 아니라 네트워크가 막힌 것. 이 달은 아예 만들지 않는다."""


def fetch(ymd, slot):
    """지면 한 장. 아직 안 올라왔으면 MISSING, 통신이 막히면 FetchFailed.

    매일성경은 없는 날짜에도 404가 아니라 '200 + HTML 안내'를 준다. 그래서
    '없는 것'과 '못 받은 것'은 응답 내용으로만 갈린다 — JPEG 매직넘버로 가른다.
    이 둘을 섞으면 쪽이 빠진 PDF가 조용히 만들어지므로 반드시 나눠서 다룬다.
    """
    url = BASE.format(ymd=ymd, slot=slot)
    last = None
    for i in range(TRIES):
        time.sleep(PAUSE)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                data = r.read()
            return data if data[:2] == b'\xff\xd8' else MISSING
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return MISSING
            last = e
        except Exception as e:
            last = e
        time.sleep(1.5 * (i + 1))      # 끊겼으면 점점 더 쉬었다가 다시
    raise FetchFailed(f'{ymd}-{slot}: {last}')


def collect(ym):
    """그 달 지면을 날짜순으로 모은다. 아직이면 (None, 사유).

    마지막 날이 떠야 비로소 묶는다 — 매일성경은 달 단위로 한 번에 올리기 때문에
    그 전에 묶으면 반쪽짜리 PDF가 된다.
    """
    y, m = (int(x) for x in ym.split('-'))
    last = calendar.monthrange(y, m)[1]

    # 마지막 날부터 본다. 아직이면 나머지 60번을 부를 까닭이 없다.
    if fetch(f'{y:04d}{m:02d}{last:02d}', 1) is MISSING:
        return None, f'{last}일(그 달 마지막 날)이 아직 안 올라왔습니다'

    pages, missing_days = [], []
    for day in range(1, last + 1):
        ymd = f'{y:04d}{m:02d}{day:02d}'
        first = fetch(ymd, 1)
        if first is MISSING:         # 1면이 없으면 그 날은 아예 없는 것 — 2면은 보지도 않는다
            missing_days.append(day)
            continue
        second = fetch(ymd, 2)
        pages.append(first)
        if second is not MISSING:
            pages.append(second)
    if len(missing_days) > MAX_MISSING:
        return None, f'{len(missing_days)}일치가 비었습니다 — 아직 올라오는 중'
    if missing_days:
        print(f'  · 빠진 날: {missing_days} (그대로 진행)')
    return pages, None


def build_pdf(pages, out_path):
    from PIL import Image
    imgs = [Image.open(io.BytesIO(p)).convert('RGB') for p in pages]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    imgs[0].save(out_path, 'PDF', save_all=True, append_images=imgs[1:],
                 quality=QUALITY, resolution=96.0)


def human(n):
    return f'{n/1024/1024:.0f}MB' if n >= 1024 * 1024 else f'{n/1024:.0f}KB'


def write_index():
    """files/ 안에 실제로 있는 PDF만 보고 목록을 다시 적는다. 손으로 올린 것도 같이 잡힌다."""
    months = {}
    files_dir = os.path.join(ROOT, 'files')
    for ym in sorted(os.listdir(files_dir)) if os.path.isdir(files_dir) else []:
        if not re.fullmatch(r'\d{4}-\d{2}', ym):
            continue
        rel = f'files/{ym}/youth-qt-{ym}.pdf'
        full = os.path.join(ROOT, rel)
        if not os.path.exists(full):
            continue
        months[ym] = {'label': f'{int(ym[5:7])}월 청소년 큐티 PDF',
                      'href': rel,
                      'size': human(os.path.getsize(full))}
    out = os.path.join(files_dir, 'qt-index.json')
    json.dump({'updatedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
               'months': months},
              open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'목록 갱신: {len(months)}개월 — {", ".join(months) or "없음"}')


def targets_from_today():
    """이번 달과 다음 달. 12월엔 다음 달이 내년 1월이 되므로 해가 바뀌어도 그냥 돈다."""
    t = datetime.datetime.now(KST).date()
    nxt = (t.replace(day=1) + datetime.timedelta(days=32)).replace(day=1)
    return [f'{t.year:04d}-{t.month:02d}', f'{nxt.year:04d}-{nxt.month:02d}']


def main(argv):
    asked = [a.strip() for a in ' '.join(argv).replace(',', ' ').split() if a.strip()]
    for a in asked:
        if not re.fullmatch(r'\d{4}-\d{2}', a):
            sys.exit(f'달 이름은 YYYY-MM 으로 주세요: {a}')
    months = asked or targets_from_today()
    made = []
    for ym in months:
        out = os.path.join(ROOT, 'files', ym, f'youth-qt-{ym}.pdf')
        if os.path.exists(out) and not asked:
            print(f'{ym}: 이미 있음 — 건너뜀')
            continue
        print(f'{ym}: 매일성경에서 지면 받는 중…')
        try:
            pages, why = collect(ym)
        except FetchFailed as e:
            # 반쪽짜리 PDF를 만드느니 아무것도 안 만들고 다음 차례에 다시 본다.
            print(f'{ym}: 매일성경 서버와 통신이 막혔습니다 ({e}) — 이번엔 건너뜁니다')
            continue
        if pages is None:
            print(f'{ym}: 아직 — {why}')
            continue
        build_pdf(pages, out)
        print(f'{ym}: {len(pages)}쪽 · {human(os.path.getsize(out))} → {os.path.relpath(out, ROOT)}')
        made.append(ym)
    write_index()
    print('만든 달: ' + (', '.join(made) if made else '없음'))


if __name__ == '__main__':
    main(sys.argv[1:])
