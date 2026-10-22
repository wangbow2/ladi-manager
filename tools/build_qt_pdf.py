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
import calendar, datetime, io, json, os, re, sys, urllib.request, urllib.error

KST = datetime.timezone(datetime.timedelta(hours=9))
BASE = 'https://sum.su.or.kr:8888/Bible_Attach/QT2/J{ymd}-{slot}.jpg'
UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUALITY = 80          # 원본과 눈으로 구분이 안 되면서 용량은 1/3
MAX_MISSING = 2       # 중간에 이만큼까지 빠진 날은 봐준다


def fetch(ymd, slot):
    """지면 한 장. 아직 안 올라왔으면 None."""
    url = BASE.format(ymd=ymd, slot=slot)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
            data = r.read()
    except Exception as e:
        print(f'  ! {ymd}-{slot} 받기 실패: {e}')
        return None
    return data if data[:2] == b'\xff\xd8' else None     # JPEG가 아니면 '아직 없음'


def collect(ym):
    """그 달 지면을 날짜순으로 모은다. 다 안 올라왔으면 (None, 사유)."""
    y, m = (int(x) for x in ym.split('-'))
    last = calendar.monthrange(y, m)[1]
    pages, missing_days = [], []
    for day in range(1, last + 1):
        ymd = f'{y:04d}{m:02d}{day:02d}'
        first = fetch(ymd, 1)
        if first is None:            # 1면이 없으면 그 날은 아예 안 올라온 것 — 2면은 보지도 않는다
            missing_days.append(day)
            continue
        second = fetch(ymd, 2)
        pages += [p for p in (first, second) if p is not None]
    if last in missing_days:
        return None, f'{last}일이 아직 안 올라왔습니다(그 달 마지막 날)'
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
        pages, why = collect(ym)
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
