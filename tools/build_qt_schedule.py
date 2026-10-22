#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
매일성경 묵상 일정표(날짜 → 본문)를 받아 files/qt-schedule.json 으로 적는다.

index.html 안의 QT_SCHEDULE은 2026-12-31에서 끝난다. 그대로 두면 1월 1일에
큐티 화면이 '큐티 일정이 없습니다'가 된다. 앱은 이 파일을 런타임에 읽어
QT_SCHEDULE에 덧붙이므로, 해가 바뀌어도 사람이 손으로 채워 넣을 일이 없다.

출처: 성서유니온 '오늘의 묵상' 달력이 쓰는 그 주소.
  POST https://sum.su.or.kr:8888/Ajax/Bible/Calendar
  {"qt_ty": "QT2", "Base_de": "YYYY-MM-01"}      QT2 = 청소년(지면 이미지와 같은 코드)
앱에 이미 들어 있는 2026-06~12 214일과 한 글자도 틀리지 않음을 확인하고 만들었다.
"""
import datetime, json, os, re, sys, time, urllib.request

API = 'https://sum.su.or.kr:8888/Ajax/Bible/Calendar'
HEAD = {'Content-Type': 'application/json; charset=utf-8',
        'Referer': 'https://sum.su.or.kr:8888/bible/today',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
START = '2026-06'     # index.html의 QT_SCHEDULE이 시작하는 달. 그 앞은 만들지 않는다.
KST = datetime.timezone(datetime.timedelta(hours=9))
TRIES = 3


def month_rows(ym):
    """그 달의 {날짜: '본문'}. 한 번 실패하면 쉬었다가 다시 건다."""
    body = json.dumps({'qt_ty': 'QT2', 'Base_de': ym + '-01'}).encode()
    last = None
    for i in range(TRIES):
        try:
            with urllib.request.urlopen(urllib.request.Request(API, data=body, headers=HEAD), timeout=40) as r:
                rows = json.loads(r.read().decode('utf-8'))
            break
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    else:
        raise RuntimeError(f'{ym} 일정표를 못 받았습니다: {last}')

    out = {}
    for r in rows:
        day = str(r.get('Day') or '').strip()
        name = (r.get('Bible_name') or '').strip()
        ch = (r.get('Bible_chapter') or '').strip()
        if not (day and name and ch):
            continue
        ds = f"{int(r['Year']):04d}-{int(r['Month']):02d}-{int(day):02d}"
        out[ds] = f'{name} {tidy(ch)}'
    return out


def tidy(ch):
    """'4:13 - 5:6' → '4:13-5:6', '1:1 - 1:9' → '1:1-9'.

    같은 장 안에서 끝나면 뒷장을 생략한다 — 앱에 이미 적혀 있는 214일이 그 꼴이라,
    여기서 맞춰 두지 않으면 같은 날이 두 가지로 보이게 된다.
    """
    c = ch.replace(' ', '')
    m = re.fullmatch(r'(\d+):(\d+)-(\d+):(\d+)', c)
    if m and m.group(1) == m.group(3):
        return f'{m.group(1)}:{m.group(2)}-{m.group(4)}'
    return c


def months_wanted():
    """START부터 '내년 12월'까지. 해가 바뀌면 끝이 저절로 한 해 밀린다."""
    sy, sm = (int(x) for x in START.split('-'))
    end_y = datetime.datetime.now(KST).year + 1
    out, y, m = [], sy, sm
    while (y, m) <= (end_y, 12):
        out.append(f'{y:04d}-{m:02d}')
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def main():
    days = {}
    for ym in months_wanted():
        got = month_rows(ym)
        if not got:
            print(f'{ym}: 아직 없음 — 건너뜀')
            continue
        days.update(got)
        print(f'{ym}: {len(got)}일')
    if not days:
        sys.exit('일정표를 하나도 못 받았습니다 — 파일은 그대로 둡니다')

    out = os.path.join(ROOT, 'files', 'qt-schedule.json')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    # 내용이 그대로면 손대지 않는다(시각만 바뀐 빈 커밋 방지)
    if os.path.exists(out):
        try:
            if json.load(open(out, encoding='utf-8')).get('days') == days:
                print(f'일정 그대로: {len(days)}일')
                return
        except Exception:
            pass
    json.dump({'updatedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
               'source': '성서유니온 매일성경 청소년(QT2) 묵상 일정표',
               'days': dict(sorted(days.items()))},
              open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(f'일정 갱신: {len(days)}일 ({min(days)} ~ {max(days)})')


if __name__ == '__main__':
    main()
