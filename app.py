"""한 개비만 늦게
실행: streamlit run app.py
GitHub 저장소에 app.py와 requirements.txt를 올리고 Streamlit Community Cloud에서 배포.
배포 후 사이드바에 공개 앱 주소를 입력하면 접속 QR 생성.
개인 기록은 서버 파일에 저장하지 않으며 현재 세션에서만 유지됨. JSON 백업 사용.
"""
import io
import json
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlparse

import pandas as pd
import qrcode
import streamlit as st

st.set_page_config(page_title='한 개비만 늦게', page_icon='🌿', layout='centered')
TZ = ZoneInfo('Asia/Seoul')
TAGS = ['선택 안 함', '식후', '커피', '운전·이동', '스트레스', '습관', '사람들과 함께']

def now():
    return datetime.now(TZ)

def stamp(t):
    return t.isoformat()

def parse(t):
    d = datetime.fromisoformat(t)
    if d.tzinfo is None:
        raise ValueError('시간대 정보가 없습니다.')
    return d.astimezone(TZ)

def initial():
    return {'version': 1, 'records': [], 'sessions': [], 'settings': {'price': 0, 'pack': 20}}

if 'data' not in st.session_state:
    st.session_state.data = initial()
if 'timer' not in st.session_state:
    st.session_state.timer = None
D = st.session_state.data

def add_record(t, count=1, tag='선택 안 함'):
    D['records'].append({'id': str(uuid.uuid4()), 'time': stamp(t), 'count': int(count), 'tag': tag})

def validate(payload):
    if not isinstance(payload, dict) or payload.get('version') != 1:
        raise ValueError('지원하지 않는 백업 형식입니다.')
    out = initial()
    for key in ['records', 'sessions']:
        rows = payload.get(key, [])
        if not isinstance(rows, list) or len(rows) > 50000:
            raise ValueError('기록 형식 또는 개수를 확인하세요.')
        seen = set()
        for r in rows:
            rid = str(r['id'])
            if not rid or len(rid) > 100 or rid in seen:
                raise ValueError('중복되거나 잘못된 기록 ID입니다.')
            seen.add(rid)
            t = parse(r['time'])
            if t > now() + timedelta(minutes=1):
                raise ValueError('미래 시각 기록은 복원할 수 없습니다.')
            if key == 'records':
                n = r['count']
                if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= 100:
                    raise ValueError('개비 수를 확인하세요.')
                tag = r.get('tag', '선택 안 함')
                if tag not in TAGS:
                    raise ValueError('지원하지 않는 상황 태그입니다.')
                out[key].append({'id': rid, 'time': stamp(t), 'count': n, 'tag': tag})
            else:
                mins = r['minutes']
                result = r['result']
                if mins not in [1, 3, 5] or result not in ['지금은 안 피울래요', '조금 더 기다릴래요', '피웠어요', '중단']:
                    raise ValueError('미루기 기록이 올바르지 않습니다.')
                out[key].append({'id': rid, 'time': stamp(t), 'minutes': mins, 'result': result})
    s = payload.get('settings', {})
    price, pack = s.get('price', 0), s.get('pack', 20)
    if type(price) is not int or not 0 <= price <= 1000000 or type(pack) is not int or not 1 <= pack <= 100:
        raise ValueError('가격 설정이 올바르지 않습니다.')
    out['settings'] = {'price': price, 'pack': pack}
    return out

st.markdown('''<style>
.stApp {background: #f5f8f5;}
.stButton > button, .stDownloadButton > button {min-height:52px; font-size:18px; border-radius:14px;}
[data-testid="stMetric"] {background:white; padding:18px; border-radius:16px;}
h1,h2,h3 {color:#254c3b;}
</style>''', unsafe_allow_html=True)
st.title('🌿 한 개비만 늦게')
st.caption('내 속도로 기록하고, 잠깐 기다려보는 시간')
st.info('기록은 현재 접속 세션에서만 유지됩니다. 접속 종료·새로고침·서버 재시작 시 사라질 수 있으니 JSON 백업을 내려받으세요. QR에는 기록이 담기지 않습니다.')

with st.sidebar:
    st.header('접속 QR · 설정')
    st.caption('앱을 배포한 후 실제 공개 주소를 입력하세요. QR을 찍으면 이 앱이 열립니다.')
    url = st.text_input('배포된 앱의 https 주소', placeholder='https://your-app.streamlit.app')
    if url:
        u = urlparse(url.strip())
        if u.scheme == 'https' and u.hostname and not u.username and not u.password:
            image = qrcode.make(url.strip())
            buf = io.BytesIO()
            image.save(buf, format='PNG')
            st.image(buf.getvalue(), caption='휴대폰 카메라로 스캔하세요', width=220)
            st.download_button('QR 이미지 받기', buf.getvalue(), 'app_qr.png', 'image/png')
        else:
            st.warning('정상적인 https 공개 주소를 입력하세요.')
    st.divider()
    st.caption('현재 개비 단위 제품만 지원합니다. 액상형 제품 사용량과 섞어 기록하지 마세요.')
    D['settings']['price'] = st.number_input('한 갑 가격 (원, 0이면 비용 숨김)', 0, 1000000, int(D['settings']['price']), step=100)
    D['settings']['pack'] = st.number_input('한 갑 개비 수', 1, 100, int(D['settings']['pack']))
    st.caption('시간 기준: 대한민국 (Asia/Seoul). 알림 권한, 위치, 가족 공유는 사용하지 않습니다.')

page = st.radio('화면', ['홈', '잠깐 미루기', '기록', '내 패턴', '백업·안내'], horizontal=True, label_visibility='collapsed')

if page == '홈':
    today = [r for r in D['records'] if parse(r['time']).date() == now().date()]
    total = sum(r['count'] for r in today)
    a, b = st.columns(2)
    a.metric('오늘 기록한 개비 수', f'{total}개비')
    latest = max(D['records'], key=lambda r: parse(r['time'])) if D['records'] else None
    if latest:
        elapsed = max(0, int((now() - parse(latest['time'])).total_seconds() // 60))
        b.metric('마지막 기록 후', f'{elapsed // 60}시간 {elapsed % 60}분')
    else:
        b.metric('마지막 기록 후', '기록 없음')
    if not today:
        st.caption('오늘 입력된 기록이 없습니다. 실제 흡연량이 0개비라는 뜻은 아닙니다.')
    st.caption('경과 시간은 화면을 새로 표시할 때 갱신됩니다.')
    if st.button('시간 새로 확인', use_container_width=True):
        st.rerun()
    if st.button('담배 피웠어요 · 1개비 기록', type='primary', use_container_width=True):
        add_record(now())
        st.rerun()
    st.caption('피우고 싶다면 상단의 ‘잠깐 미루기’에서 1·3·5분을 선택해보세요.')
    if latest:
        st.write('최근 기록:', parse(latest['time']).strftime('%m/%d %H:%M'), f"· {latest['count']}개비")
        if st.button('최근 기록 취소', use_container_width=True):
            D['records'] = [r for r in D['records'] if r['id'] != latest['id']]
            st.rerun()
        with st.form('quicktag'):
            tag = st.selectbox('최근 기록 상황 (선택)', TAGS, index=TAGS.index(latest['tag']))
            if st.form_submit_button('상황 저장'):
                latest['tag'] = tag
                st.rerun()
    completed = sum(1 for x in D['sessions'] if parse(x['time']).date() == now().date() and x['result'] != '중단')
    st.write(f'오늘 미루기 완료 {completed}회')
    st.caption('한 번의 기록부터 시작해도 괜찮아요. 기록은 평가가 아닙니다.')

elif page == '잠깐 미루기':
    st.subheader('지금, 잠깐만 기다려볼까요?')
    if st.session_state.timer is None:
        mins = st.radio('기다릴 시간', [1, 3, 5], index=1, horizontal=True, format_func=lambda x: f'{x}분')
        if st.button('기다리기 시작', type='primary', use_container_width=True):
            st.session_state.timer = {'id': str(uuid.uuid4()), 'minutes': mins, 'end': stamp(now() + timedelta(minutes=mins))}
            st.rerun()
    else:
        @st.fragment(run_every='1s')
        def countdown():
            timer = st.session_state.timer
            if not timer:
                return
            remaining = max(0, int((parse(timer['end']) - now()).total_seconds() + 0.999))
            st.metric('남은 시간', f'{remaining // 60:02d}:{remaining % 60:02d}')
            st.progress(min(1.0, max(0.0, 1 - remaining / (timer['minutes'] * 60))))
            st.write('💧 물 한 잔 마시기 · 자리에서 잠깐 움직이기 · 창밖 바라보기')
            if remaining:
                st.caption('다른 화면을 보고 돌아와도 종료 시각을 기준으로 계산합니다. 앱을 닫으면 알림은 오지 않습니다.')
                if st.button('기다리기 중단', use_container_width=True):
                    D['sessions'].append({'id': timer['id'], 'time': stamp(now()), 'minutes': timer['minutes'], 'result': '중단'})
                    st.session_state.timer = None
                    st.rerun()
            else:
                st.success('잠깐 기다리기가 끝났어요. 이제 선택해보세요.')
                for choice in ['지금은 안 피울래요', '조금 더 기다릴래요', '피웠어요']:
                    if st.button(choice, key='result_' + choice, use_container_width=True):
                        if not any(x['id'] == timer['id'] for x in D['sessions']):
                            D['sessions'].append({'id': timer['id'], 'time': stamp(now()), 'minutes': timer['minutes'], 'result': choice})
                            if choice == '피웠어요':
                                add_record(now())
                        st.session_state.timer = ({'id': str(uuid.uuid4()), 'minutes': timer['minutes'], 'end': stamp(now() + timedelta(minutes=timer['minutes']))} if choice == '조금 더 기다릴래요' else None)
                        st.rerun()
        countdown()
    st.caption('미루기는 줄인 담배 개비 수가 아닙니다. 중단해도 실패로 표시하지 않아요.')

elif page == '기록':
    st.subheader('내 기록')
    with st.expander('빠뜨린 기록 추가'):
        with st.form('add_past'):
            day = st.date_input('날짜', now().date(), max_value=now().date())
            clock = st.time_input('시각', now().time().replace(tzinfo=None, second=0, microsecond=0))
            count = st.number_input('개비 수', 1, 100, 1)
            tag = st.selectbox('상황', TAGS)
            if st.form_submit_button('기록 추가'):
                t = datetime.combine(day, clock, TZ)
                if t > now():
                    st.error('미래 시각은 입력할 수 없어요.')
                else:
                    add_record(t, count, tag)
                    st.rerun()
    a, b = st.columns(2)
    start = a.date_input('시작일', now().date() - timedelta(days=6))
    end = b.date_input('종료일', now().date())
    if start > end:
        st.warning('시작일을 종료일보다 앞서 선택하세요.')
    else:
        rows = sorted([r for r in D['records'] if start <= parse(r['time']).date() <= end], key=lambda r: parse(r['time']), reverse=True)
        if not rows:
            st.info('이 기간에 입력된 기록이 없어요.')
        for r in rows[:100]:
            t = parse(r['time'])
            with st.expander(f"{t:%m/%d %H:%M} · {r['count']}개비 · {r['tag']}"):
                with st.form('edit_' + r['id']):
                    day = st.date_input('날짜', t.date(), max_value=now().date(), key='d' + r['id'])
                    clock = st.time_input('시각', t.time().replace(tzinfo=None), key='t' + r['id'])
                    count = st.number_input('개비 수', 1, 100, r['count'], key='c' + r['id'])
                    tag = st.selectbox('상황', TAGS, index=TAGS.index(r['tag']), key='tag' + r['id'])
                    if st.form_submit_button('수정 저장'):
                        updated = datetime.combine(day, clock, TZ)
                        if updated > now():
                            st.error('미래 시각은 입력할 수 없어요.')
                        else:
                            r.update(time=stamp(updated), count=int(count), tag=tag)
                            st.rerun()
                confirm = st.checkbox('이 기록을 삭제할게요', key='confirm' + r['id'])
                if st.button('삭제', key='delete' + r['id'], disabled=not confirm):
                    D['records'] = [x for x in D['records'] if x['id'] != r['id']]
                    st.rerun()
        if len(rows) > 100:
            st.caption('최신 100건만 표시합니다. 기간을 좁혀주세요.')

elif page == '내 패턴':
    st.subheader('평가 대신, 내 습관 알아보기')
    period = st.selectbox('조회 기간', [7, 14, 30], format_func=lambda n: f'최근 {n}일')
    start = now().date() - timedelta(days=period - 1)
    rows = [r for r in D['records'] if start <= parse(r['time']).date() <= now().date()]
    if not rows:
        st.info('아직 이 기간에 기록이 없어요. 홈에서 한 번의 기록부터 시작해보세요.')
    else:
        df = pd.DataFrame([{'날짜': parse(r['time']).date().isoformat(), '시각': parse(r['time']).hour, '개비 수': r['count'], '상황': r['tag']} for r in rows])
        st.metric('기간 내 기록한 개비 수', int(df['개비 수'].sum()))
        daily = df.groupby('날짜')['개비 수'].sum().to_frame()
        st.write('날짜별 기록')
        st.bar_chart(daily, color='#3d8066')
        st.caption('입력 기록이 있는 날짜만 표시합니다. 빈 날짜는 0개비로 간주하지 않아요.')
        st.write('시간대별 기록')
        st.bar_chart(df.groupby('시각')['개비 수'].sum().to_frame(), color='#739d86')
        tagged = df[df['상황'] != '선택 안 함']
        if not tagged.empty:
            st.write('선택한 흡연 상황')
            st.dataframe(tagged.groupby('상황')['개비 수'].sum().sort_values(ascending=False).to_frame(), use_container_width=True)
        if df['날짜'].nunique() < 3:
            st.caption('기록한 날짜가 적어 습관을 판단하기에는 이릅니다.')
        if D['settings']['price']:
            cost = int(df['개비 수'].sum()) * D['settings']['price'] / D['settings']['pack']
            st.metric('기록 기준 예상 담배 비용', f'{cost:,.0f}원')
            st.caption('입력한 갑당 가격을 이용한 추정치이며 실제 구매 지출이나 절약액이 아닙니다.')
    sessions = [x for x in D['sessions'] if start <= parse(x['time']).date() <= now().date() and x['result'] != '중단']
    st.write(f'이 기간의 미루기 완료: {len(sessions)}회')
    st.caption('담배를 줄인 개비 수나 건강 개선 수치를 의미하지 않습니다.')

else:
    st.subheader('내 기록 백업 · 복원')
    st.warning('이 버전은 영구 저장이나 여러 기기 동기화를 제공하지 않습니다. 공용 GitHub 저장소에 개인 기록을 올리지 마세요.')
    backup = json.dumps(D, ensure_ascii=False, indent=2)
    st.download_button('JSON 백업 다운로드', backup.encode('utf-8'), f'smoking_backup_{now():%Y%m%d_%H%M}.json', 'application/json', use_container_width=True)
    if D['records']:
        export = pd.DataFrame([{'시각': r['time'], '개비 수': r['count'], '상황': r['tag']} for r in D['records']])
        st.download_button('흡연 기록 CSV 다운로드', export.to_csv(index=False).encode('utf-8-sig'), 'smoking_records.csv', 'text/csv', use_container_width=True)
    uploaded = st.file_uploader('이 앱에서 받은 JSON 백업', type=['json'])
    replace = st.checkbox('복원하면 현재 기록 전체가 백업 내용으로 교체되는 것을 이해했어요')
    if st.button('백업 복원', disabled=not uploaded or not replace):
        try:
            if uploaded.size > 5 * 1024 * 1024:
                raise ValueError('백업은 5MB 이하만 지원합니다.')
            restored = validate(json.loads(uploaded.getvalue().decode('utf-8')))
            st.session_state.data = restored
            st.session_state.timer = None
            st.rerun()
        except (ValueError, KeyError, TypeError, AttributeError, UnicodeDecodeError, OverflowError) as exc:
            st.error(f'복원하지 못했습니다. 백업 파일을 확인하세요. ({exc})')
    st.divider()
    delete = st.checkbox('전체 기록과 설정을 영구 삭제할게요')
    if st.button('전체 데이터 삭제', disabled=not delete):
        st.session_state.data = initial()
        st.session_state.timer = None
        st.rerun()
    st.subheader('사용 안내')
    st.write('① 홈에서 흡연 기록 → ② 원할 때 잠깐 미루기 → ③ 내 패턴 확인 → ④ 접속 종료 전 백업')
    st.write('배포: 두 파일을 GitHub 저장소 루트에 업로드 → Streamlit Community Cloud에서 해당 저장소와 app.py 선택 → Deploy → 생성된 공개 주소로 접속 → 사이드바에 주소를 넣어 QR 생성.')
    st.caption('Streamlit Community Cloud는 GitHub의 코드를 실행하는 서비스입니다. GitHub Pages만으로는 이 Python 앱을 실행할 수 없습니다.')
    st.caption('개인 기록은 앱 코드에서 서버 파일이나 데이터베이스로 저장하지 않습니다. 공개 앱에는 민감한 상세 정보 입력을 피하세요. 앱은 전문적인 금연 지원이나 진료를 대신하지 않으며 금연 효과를 보장하지 않습니다.')
