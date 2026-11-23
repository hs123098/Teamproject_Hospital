"""
실시간 병원·응급실·약국 조회 시스템 (Streamlit + Supabase PostgreSQL)
- 응급실 현황 / 병원 검색·상세 / 약국 검색 / 병상 관리(데모)
"""
import html
import re
from datetime import datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

KST = ZoneInfo("Asia/Seoul")
STALE_MIN = 60  # 이 시간(분) 넘게 갱신 안 된 병상 정보는 경고 표시

st.set_page_config(page_title="응급·병원·약국 찾기", page_icon="🚑", layout="wide")

CSS = """
<style>
.block-container{padding-top:1.2rem;max-width:1200px;}
.emg{background:#d92d20;color:#fff;border-radius:14px;padding:12px 18px;display:flex;flex-wrap:wrap;
     gap:6px 20px;align-items:center;justify-content:space-between;margin-bottom:12px}
.emg .big{font-size:1.15rem;font-weight:800}
.emg a{color:#fff;font-weight:700;text-decoration:underline}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:12px;margin:8px 0 16px}
.card{border:1px solid rgba(128,128,128,.3);background:rgba(128,128,128,.07);border-radius:14px;
      padding:14px 16px;border-left:6px solid #98a2b3}
.card.ok{border-left-color:#12b76a}.card.full{border-left-color:#f04438}.card.none{border-left-color:#98a2b3}
.card h4{margin:0 0 6px;font-size:1.05rem}
.badge{display:inline-block;padding:2px 9px;border-radius:999px;font-size:.75rem;font-weight:700;
       color:#fff;margin:0 4px 4px 0}
.b-ok{background:#12b76a}.b-full{background:#f04438}.b-gray{background:#667085}
.b-blue{background:#2e90fa}.b-amber{background:#f79009}
.beds{font-size:2rem;font-weight:800;line-height:1}
.muted{opacity:.7;font-size:.82rem}
.row{margin:4px 0;font-size:.9rem}
.card a{text-decoration:none}
</style>
"""

# ---------------------------------------------------------------------
# DB 연결 / 쿼리
# ---------------------------------------------------------------------
@st.cache_resource
def get_engine():
    return create_engine(st.secrets["DATABASE_URL"], pool_pre_ping=True, pool_size=3, max_overflow=2)


@st.cache_data(ttl=30, show_spinner=False)
def q(sql: str, params: dict | None = None) -> pd.DataFrame:
    """SELECT 실행 (30초 캐시 → 병상 정보가 거의 실시간으로 반영됨)"""
    with get_engine().connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


def execute(sql: str, params: dict) -> None:
    with get_engine().begin() as conn:
        conn.execute(text(sql), params)
    st.cache_data.clear()


# [INNER JOIN] 응급실 운영 병원만
ER_SQL = """
SELECT h.hospital_id, h.hospital_name, h.region, h.address, h.phone, h.hospital_type,
       h.funeral_hall, e.status, e.available_beds, e.er_phone, e.update_time
FROM hospital h
INNER JOIN emergencyroom e ON h.hospital_id = e.hospital_id
"""

# [LEFT JOIN + 서브쿼리] 응급실 없는 병원 포함 + 진료과목 문자열 집계
HOSPITAL_SQL = """
SELECT h.hospital_id, h.hospital_name, h.region, h.address, h.phone, h.hospital_type,
       h.open_time, h.close_time, h.holiday_open, h.funeral_hall,
       e.er_id,
       COALESCE(e.status, '응급실 미운영') AS er_status,
       COALESCE(e.available_beds, 0)       AS available_beds,
       e.er_phone, e.update_time,
       (SELECT string_agg(d.dept_name, ', ' ORDER BY d.dept_id)
          FROM hospital_department hd
          JOIN department d ON d.dept_id = hd.dept_id
         WHERE hd.hospital_id = h.hospital_id) AS departments
FROM hospital h
LEFT JOIN emergencyroom e ON h.hospital_id = e.hospital_id
"""

PHARMACY_SQL = """
SELECT p.pharmacy_id, p.pharmacy_name, p.region, p.address, p.phone,
       p.open_time, p.close_time, p.holiday_open
FROM pharmacy p
"""


# ---------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------
def esc(v) -> str:
    return "" if v is None or pd.isna(v) else html.escape(str(v))


def tel(phone) -> str:
    if phone is None or pd.isna(phone) or not str(phone).strip():
        return "-"
    digits = re.sub(r"[^0-9+]", "", str(phone))
    return f'<a href="tel:{digits}">📞 {esc(phone)}</a>'


def map_url(address: str) -> str:
    return "https://map.naver.com/p/search/" + quote(str(address))


def hhmm(t) -> str:
    return "-" if t is None or pd.isna(t) else t.strftime("%H:%M")


def ago(ts, now):
    """(표시문구, 오래됐는지) 반환"""
    if ts is None or pd.isna(ts):
        return "-", False
    ts = pd.Timestamp(ts)
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert(KST)
    mins = max(int((now - ts).total_seconds() // 60), 0)
    if mins < 1:
        label = "방금 전"
    elif mins < 60:
        label = f"{mins}분 전"
    elif mins < 1440:
        label = f"{mins // 60}시간 전"
    else:
        label = f"{mins // 1440}일 전"
    return label, mins >= STALE_MIN


def is_open(open_t, close_t, holiday_open, now, is_holiday) -> bool:
    if open_t is None or close_t is None or pd.isna(open_t) or pd.isna(close_t):
        return False
    if is_holiday and holiday_open != "Y":
        return False
    return open_t <= now.time() < close_t


def grid(cards: list[str]) -> None:
    if not cards:
        st.info("조건에 맞는 결과가 없습니다. 필터를 조정해 보세요.")
        return
    st.markdown('<div class="grid">' + "".join(cards) + "</div>", unsafe_allow_html=True)


def region_filter(table: str, key: str):
    regs = q(f"SELECT DISTINCT region FROM {table} ORDER BY region")["region"].tolist()
    cities = sorted({r.split()[0] for r in regs})
    c1, c2 = st.columns(2)
    city = c1.selectbox("시·도", ["전체"] + cities, key=f"{key}_city")
    dists = [r for r in regs if city == "전체" or r.split()[0] == city]
    dist = c2.selectbox("시·군·구", ["전체"] + dists, key=f"{key}_dist")
    return city, dist


def region_where(alias: str, city: str, dist: str, where: list, params: dict) -> None:
    if dist != "전체":
        where.append(f"{alias}.region = :region")
        params["region"] = dist
    elif city != "전체":
        where.append(f"split_part({alias}.region, ' ', 1) = :city")
        params["city"] = city


def with_where(sql: str, where: list) -> str:
    return sql + (" WHERE " + " AND ".join(where) if where else "")


# ---------------------------------------------------------------------
# 카드 렌더링
# ---------------------------------------------------------------------
def er_card(r: dict, now) -> str:
    beds = int(r["available_beds"])
    ok = r["status"] == "운영중" and beds > 0
    cls, badge = ("ok", '<span class="badge b-ok">수용 가능</span>') if ok else (
        "full", '<span class="badge b-full">포화</span>')
    when, stale = ago(r["update_time"], now)
    stale_badge = '<span class="badge b-amber">⚠ 정보 오래됨</span>' if stale else ""
    funeral = '<span class="badge b-gray">장례식장</span>' if r.get("funeral_hall") == "Y" else ""
    return (
        f'<div class="card {cls}">'
        f'<h4>{esc(r["hospital_name"])}</h4>'
        f'{badge}<span class="badge b-blue">{esc(r["hospital_type"])}</span>{funeral}{stale_badge}'
        f'<div class="row"><span class="beds">{beds}</span> <span class="muted">가용 병상</span></div>'
        f'<div class="row">🚑 응급실 {tel(r["er_phone"])}</div>'
        f'<div class="row">📍 {esc(r["address"])} · <a href="{map_url(r["address"])}" target="_blank">지도</a></div>'
        f'<div class="muted">갱신 {when}</div>'
        f'</div>'
    )


def hospital_card(r: dict, now, is_holiday: bool) -> str:
    has_er = r["er_id"] is not None and not pd.isna(r["er_id"])
    beds = int(r["available_beds"])
    if not has_er:
        cls, er_badge = "none", '<span class="badge b-gray">응급실 미운영</span>'
    elif r["er_status"] == "운영중" and beds > 0:
        cls, er_badge = "ok", f'<span class="badge b-ok">응급실 {beds}병상</span>'
    else:
        cls, er_badge = "full", '<span class="badge b-full">응급실 포화</span>'
    opened = is_open(r["open_time"], r["close_time"], r["holiday_open"], now, is_holiday)
    out_badge = ('<span class="badge b-blue">외래 진료중</span>' if opened
                 else '<span class="badge b-gray">외래 종료</span>')
    hol = '<span class="badge b-blue">휴일 외래</span>' if r["holiday_open"] == "Y" else ""
    funeral = '<span class="badge b-gray">장례식장</span>' if r["funeral_hall"] == "Y" else ""
    return (
        f'<div class="card {cls}">'
        f'<h4>{esc(r["hospital_name"])}</h4>'
        f'{er_badge}{out_badge}{hol}{funeral}'
        f'<div class="row muted">{esc(r["hospital_type"])} · {esc(r["region"])}</div>'
        f'<div class="row">🩺 {esc(r["departments"])}</div>'
        f'<div class="row">🕘 외래 {hhmm(r["open_time"])}~{hhmm(r["close_time"])}</div>'
        f'<div class="row">{tel(r["phone"])}</div>'
        f'</div>'
    )


def pharmacy_card(r: dict, now, is_holiday: bool) -> str:
    opened = is_open(r["open_time"], r["close_time"], r["holiday_open"], now, is_holiday)
    cls = "ok" if opened else "none"
    state = ('<span class="badge b-ok">지금 영업중</span>' if opened
             else '<span class="badge b-gray">영업 종료</span>')
    hol = ('<span class="badge b-blue">휴일 운영</span>' if r["holiday_open"] == "Y"
           else '<span class="badge b-gray">휴일 휴무</span>')
    night = '<span class="badge b-amber">야간 운영</span>' if (
        r["close_time"] is not None and r["close_time"].strftime("%H:%M") >= "22:00") else ""
    return (
        f'<div class="card {cls}">'
        f'<h4>{esc(r["pharmacy_name"])}</h4>'
        f'{state}{hol}{night}'
        f'<div class="row">🕘 {hhmm(r["open_time"])} ~ {hhmm(r["close_time"])}</div>'
        f'<div class="row">{tel(r["phone"])}</div>'
        f'<div class="row">📍 {esc(r["address"])} · <a href="{map_url(r["address"])}" target="_blank">지도</a></div>'
        f'<div class="muted">{esc(r["region"])}</div>'
        f'</div>'
    )


# ---------------------------------------------------------------------
# 탭 1: 응급실
# ---------------------------------------------------------------------
def tab_er(now):
    city, dist = region_filter("hospital", "er")
    c1, c2 = st.columns(2)
    only_ok = c1.toggle("수용 가능한 응급실만", value=True, key="er_ok")
    sort = c2.selectbox("정렬", ["가용 병상 많은 순", "최근 갱신 순", "병원명 순"], key="er_sort")

    where, params = [], {}
    region_where("h", city, dist, where, params)
    if only_ok:
        where.append("e.status = '운영중' AND e.available_beds > 0")
    order = {
        "가용 병상 많은 순": " ORDER BY e.available_beds DESC, e.update_time DESC",
        "최근 갱신 순": " ORDER BY e.update_time DESC",
        "병원명 순": " ORDER BY h.hospital_name",
    }[sort]
    df = q(with_where(ER_SQL, where) + order, params)

    m1, m2, m3 = st.columns(3)
    m1.metric("조회된 응급실", f"{len(df)}곳")
    m2.metric("수용 가능", f"{int(((df['status'] == '운영중') & (df['available_beds'] > 0)).sum())}곳")
    m3.metric("가용 병상 합계", f"{int(df['available_beds'].sum())}개")

    grid([er_card(r, now) for r in df.to_dict("records")])
    st.caption("병상 수는 실시간 변동될 수 있으니 방문 전 응급실 직통 전화로 꼭 확인하세요.")


# ---------------------------------------------------------------------
# 탭 2: 병원 검색 + 상세
# ---------------------------------------------------------------------
def tab_hospital(now, is_holiday):
    city, dist = region_filter("hospital", "hos")
    depts = q("SELECT dept_name FROM department ORDER BY dept_id")["dept_name"].tolist()

    c1, c2 = st.columns([2, 1])
    kw = c1.text_input("병원명 검색", placeholder="예: 서울대, 성모", key="hos_kw")
    sel_depts = c2.multiselect("진료과목 (선택한 과목을 모두 진료)", depts, key="hos_dept")

    f1, f2, f3, f4 = st.columns(4)
    night = f1.checkbox("🌙 야간·휴일 진료 (응급실 또는 휴일 외래)", key="hos_night")
    open_now = f2.checkbox("지금 외래 진료중", key="hos_open")
    er_only = f3.checkbox("응급실 있는 곳만", key="hos_er")
    funeral = f4.checkbox("장례식장 보유", key="hos_fun")

    where, params = [], {}
    region_where("h", city, dist, where, params)
    if kw.strip():
        where.append("h.hospital_name ILIKE :kw")
        params["kw"] = f"%{kw.strip()}%"
    if sel_depts:  # N:M 다중 JOIN: 선택 과목을 모두 가진 병원
        where.append(
            "h.hospital_id IN (SELECT hd.hospital_id FROM hospital_department hd "
            "JOIN department d ON d.dept_id = hd.dept_id "
            "WHERE d.dept_name IN :depts GROUP BY hd.hospital_id "
            "HAVING COUNT(DISTINCT d.dept_name) = :n)"
        )
        params["depts"] = tuple(sel_depts)
        params["n"] = len(sel_depts)
    if night:
        where.append("(e.er_id IS NOT NULL OR h.holiday_open = 'Y')")
    if er_only:
        where.append("e.er_id IS NOT NULL")
    if funeral:
        where.append("h.funeral_hall = 'Y'")
    if open_now:
        where.append("h.open_time <= :now_t AND h.close_time > :now_t")
        params["now_t"] = now.time()
        if is_holiday:
            where.append("h.holiday_open = 'Y'")

    df = q(with_where(HOSPITAL_SQL, where) + " ORDER BY h.region, h.hospital_name", params)
    st.markdown(f"**검색 결과 {len(df)}곳**")
    records = df.to_dict("records")
    grid([hospital_card(r, now, is_holiday) for r in records])

    if records:
        st.divider()
        st.subheader("🏥 병원 상세 정보")
        pick = st.selectbox("병원 선택", records, format_func=lambda r: f'{r["hospital_name"]} ({r["region"]})',
                            key="hos_pick")
        hospital_detail(pick, now)


def hospital_detail(r: dict, now):
    has_er = r["er_id"] is not None and not pd.isna(r["er_id"])
    left, right = st.columns(2)
    with left:
        st.markdown(f"### {r['hospital_name']}")
        st.markdown(
            f"- **분류**: {r['hospital_type']}\n"
            f"- **지역**: {r['region']}\n"
            f"- **주소**: {r['address']}\n"
            f"- **대표전화**: {tel(r['phone'])}\n"
            f"- **평일 외래**: {hhmm(r['open_time'])} ~ {hhmm(r['close_time'])}\n"
            f"- **휴일 외래**: {'진료' if r['holiday_open'] == 'Y' else '휴진'}\n"
            f"- **장례식장**: {'있음' if r['funeral_hall'] == 'Y' else '없음'}\n"
            f"- **진료과목**: {r['departments'] or '-'}",
            unsafe_allow_html=True,
        )
        st.link_button("🗺️ 네이버 지도에서 보기", map_url(r["address"]))
    with right:
        st.markdown("### 🚑 응급실 현황")
        if not has_er:
            st.info("이 병원은 응급실을 운영하지 않습니다. 야간·휴일에는 응급실 운영 병원을 이용하세요.")
        else:
            when, stale = ago(r["update_time"], now)
            c1, c2 = st.columns(2)
            c1.metric("운영 상태", r["er_status"])
            c2.metric("가용 병상", f"{int(r['available_beds'])}개")
            st.markdown(f"응급실 직통: {tel(r['er_phone'])}", unsafe_allow_html=True)
            st.caption(f"최종 갱신 {when}" + (" ⚠ 오래된 정보입니다. 전화로 확인하세요." if stale else ""))


# ---------------------------------------------------------------------
# 탭 3: 약국
# ---------------------------------------------------------------------
def tab_pharmacy(now, is_holiday):
    city, dist = region_filter("pharmacy", "ph")
    kw = st.text_input("약국명 검색", key="ph_kw")
    f1, f2, f3 = st.columns(3)
    open_now = f1.checkbox("지금 영업중", key="ph_open")
    night = f2.checkbox("🌙 야간 운영 (22시 이후)", key="ph_night")
    hol = f3.checkbox("휴일 운영", value=is_holiday, key="ph_hol")

    where, params = [], {}
    region_where("p", city, dist, where, params)
    if kw.strip():
        where.append("p.pharmacy_name ILIKE :kw")
        params["kw"] = f"%{kw.strip()}%"
    if night:
        where.append("p.close_time >= '22:00:00'")
    if hol:
        where.append("p.holiday_open = 'Y'")
    if open_now:
        where.append("p.open_time <= :now_t AND p.close_time > :now_t")
        params["now_t"] = now.time()
        if is_holiday:
            where.append("p.holiday_open = 'Y'")

    df = q(with_where(PHARMACY_SQL, where) + " ORDER BY p.close_time DESC, p.pharmacy_name", params)
    st.markdown(f"**검색 결과 {len(df)}곳**")
    records = df.to_dict("records")
    records.sort(key=lambda r: not is_open(r["open_time"], r["close_time"], r["holiday_open"], now, is_holiday))
    grid([pharmacy_card(r, now, is_holiday) for r in records])
    st.caption("영업시간은 변동될 수 있으니 방문 전 전화로 확인하세요. (영업중 약국이 먼저 표시됩니다)")


# ---------------------------------------------------------------------
# 탭 4: 병상 관리 (실시간 UPDATE / UPSERT 시연)
# ---------------------------------------------------------------------
def tab_admin():
    pw = st.secrets.get("ADMIN_PASSWORD")
    if not pw:
        st.info("secrets에 ADMIN_PASSWORD를 설정하면 병상 수를 직접 갱신하는 관리 기능을 쓸 수 있습니다.")
        return
    if st.text_input("관리자 비밀번호", type="password", key="adm_pw") != pw:
        st.caption("비밀번호를 입력하세요.")
        return

    df = q(ER_SQL + " ORDER BY h.hospital_id")
    pick = st.selectbox("응급실 선택", df.to_dict("records"),
                        format_func=lambda r: f'{r["hospital_name"]} (현재 {int(r["available_beds"])}병상, {r["status"]})')
    hid = int(pick["hospital_id"])

    status_case = ("status = CASE WHEN GREATEST(available_beds + :d, 0) = 0 THEN '포화' ELSE '운영중' END")
    c1, c2, c3 = st.columns(3)
    if c1.button("➖ 환자 1명 입실 (병상 -1)", use_container_width=True):
        execute(f"UPDATE emergencyroom SET {status_case}, available_beds = GREATEST(available_beds + :d, 0), "
                "update_time = NOW() WHERE hospital_id = :hid", {"d": -1, "hid": hid})
        st.rerun()
    if c2.button("➕ 환자 1명 퇴실 (병상 +1)", use_container_width=True):
        execute(f"UPDATE emergencyroom SET {status_case}, available_beds = GREATEST(available_beds + :d, 0), "
                "update_time = NOW() WHERE hospital_id = :hid", {"d": 1, "hid": hid})
        st.rerun()
    with c3:
        beds = st.number_input("병상 수 직접 입력", min_value=0, max_value=200,
                               value=int(pick["available_beds"]), step=1)
        if st.button("💾 저장", use_container_width=True):
            execute("UPDATE emergencyroom SET available_beds = :b, "
                    "status = CASE WHEN :b = 0 THEN '포화' ELSE '운영중' END, "
                    "update_time = NOW() WHERE hospital_id = :hid", {"b": int(beds), "hid": hid})
            st.rerun()
    st.caption("저장 즉시 DB에 반영되며, 응급실 탭에서 확인할 수 있습니다.")


# ---------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------
def main():
    st.markdown(CSS, unsafe_allow_html=True)
    now = datetime.now(KST)

    st.markdown(
        '<div class="emg"><span class="big">🚨 응급상황이면 지금 바로 119</span>'
        '<span>📞 <a href="tel:119">119 신고</a> · <a href="tel:1339">1339 응급의료정보센터</a> · '
        '<a href="tel:109">109 자살예방상담</a></span></div>',
        unsafe_allow_html=True,
    )

    h1, h2, h3 = st.columns([3, 2, 1])
    h1.title("🏥 병원·응급실·약국 찾기")
    is_holiday = h2.toggle("오늘은 휴일(공휴일 포함)", value=now.weekday() >= 5)
    h2.caption(f"현재 {now:%Y-%m-%d %H:%M} (KST)")
    if h3.button("🔄 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    try:
        q("SELECT 1 AS ok")
    except Exception as e:  # noqa: BLE001
        st.error("데이터베이스에 연결하지 못했습니다. Streamlit secrets의 DATABASE_URL을 확인하세요.")
        st.code(str(e)[:500])
        st.stop()

    t1, t2, t3, t4 = st.tabs(["🚑 응급실", "🏥 병원 검색", "💊 약국", "🔧 병상 관리"])
    with t1:
        tab_er(now)
    with t2:
        tab_hospital(now, is_holiday)
    with t3:
        tab_pharmacy(now, is_holiday)
    with t4:
        tab_admin()

    st.divider()
    st.caption("※ 본 서비스는 학습(PBL)용 샘플 데이터 기반이며 실제 의료 판단을 대체하지 않습니다. "
               "실제 응급실 정보는 응급의료포털(e-gen.or.kr)과 119를 이용하세요.")


main()
