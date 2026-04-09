import streamlit as st
import requests
from bs4 import BeautifulSoup
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
}

# 데이터를 10분(600초)만 기억하도록 시간을 짧게 줄였습니다.
@st.cache_data(ttl=600)
def fetch_market_data():
    data = {"nd": None, "dy": None, "exchange": None, "errors": []}

    # 1. Nd 시세 (Trading Economics)
    try:
        url_nd = "https://ko.tradingeconomics.com/sremndm:com"
        res_nd = requests.get(url_nd, headers=HEADERS, timeout=5)
        soup_nd = BeautifulSoup(res_nd.text, 'html.parser')
        text_nd = soup_nd.get_text(separator=' ')
        match_nd = re.search(r'실제\s+([0-9,]+)', text_nd)
        if match_nd:
            data["nd"] = float(match_nd.group(1).replace(',', ''))
        else:
            data["errors"].append("Nd 시세 (사이트 구조 변경 또는 차단됨)")
    except Exception:
        data["errors"].append("Nd 시세 (접속 지연 또는 차단)")

    # 2. Dy 시세 (SunSirs)
    try:
        url_dy = "https://www.sunsirs.com/m-kr/page/commodity-price-detail/commodity-price-detail-113.html"
        res_dy = requests.get(url_dy, headers=HEADERS, timeout=5)
        soup_dy = BeautifulSoup(res_dy.text, 'html.parser')
        table = soup_dy.find('table') 
        if table:
            tds = table.find_all('td')
            if len(tds) > 1:
                price_str = tds[1].text.strip()
                data["dy"] = float(re.sub(r'[^0-9.]', '', price_str))
        if data["dy"] is None:
            data["errors"].append("Dy 시세 (데이터 찾을 수 없음)")
    except Exception:
         data["errors"].append("Dy 시세 (접속 지연 또는 차단)")

    # 3. 환율 (네이버 모바일 직접 API 사용 - 가장 빠르고 정확함)
    try:
        url_ex = "https://m.stock.naver.com/front-api/v1/marketIndex/prices?category=exchange&reutersCode=FX_CNYKRW"
        res_ex = requests.get(url_ex, headers=HEADERS, timeout=5)
        json_ex = res_ex.json() # HTML이 아닌 순수 데이터(JSON)를 받아옵니다.
        price_str = json_ex['result'][0]['closePrice']
        data["exchange"] = float(price_str.replace(',', ''))
    except Exception:
        data["errors"].append("환율 (API 연동 실패)")

    return data

# --- 앱 화면 구성 ---
st.set_page_config(page_title="희토류 가치 계산기", layout="centered")

st.title("NdFeB 폐자석 가치 계산기")
st.markdown("Nd, Dy 시세 및 네이버 환율 자동 연동")

# 새로고침 버튼 (캐시 삭제 후 다시 불러오기)
if st.button("🔄 실시간 데이터 갱신 (새로고침)"):
    st.cache_data.clear()
    st.rerun()

# 백그라운드 데이터 불러오기
market_data = fetch_market_data()

# 에러가 발생한 경우 사용자에게 투명하게 알림
if market_data["errors"]:
    error_msgs = ", ".join(market_data["errors"])
    st.warning(f"⚠️ 일부 데이터를 자동으로 불러오지 못했습니다. 아래 숫자를 직접 수정해 주세요. (실패 항목: {error_msgs})")
else:
    st.success("✅ 모든 실시간 시세 및 환율을 성공적으로 불러왔습니다.")

# 크롤링 실패 시 적용할 기본값 설정
default_nd = market_data["nd"] if market_data["nd"] else 975000.0
default_dy = market_data["dy"] if market_data["dy"] else 2075000.0
default_ex = market_data["exchange"] if market_data["exchange"] else 190.0

with st.expander("⚙️ 여기를 눌러 자석 정보 및 시세를 입력하세요", expanded=True):
    st.subheader("1. 자석 정보 입력")
    total_weight = st.number_input("총 투입 중량 (kg)", value=1000.0)
    nd_content = st.number_input("Nd 함량 (%)", value=25.0)
    dy_content = st.number_input("Dy 함량 (%)", value=3.0)
    recovery_rate = st.number_input("예상 회수 수율 (%)", min_value=0.0, max_value=100.0, value=90.0, step=0.1)
    
    st.markdown("---")
    st.subheader("2. 실시간 시세 및 환율 수정")
    nd_price_cny = st.number_input("Nd 시세 (CNY/Ton)", value=default_nd, step=1000.0)
    dy_price_cny = st.number_input("Dy 시세 (CNY/Ton)", value=default_dy, step=10000.0)
    exchange_rate = st.number_input("환율 (KRW/CNY)", value=default_ex, step=1.0)
    
    st.info("👆 입력을 마치셨다면 위쪽의 '⚙️ 여기를 눌러...' 영역을 다시 눌러 창을 접어주세요.")

# 가치 계산
nd_price_krw_per_kg = (nd_price_cny * exchange_rate) / 1000
dy_price_krw_per_kg = (dy_price_cny * exchange_rate) / 1000

nd_value = total_weight * (nd_content / 100) * nd_price_krw_per_kg * (recovery_rate / 100)
dy_value = total_weight * (dy_content / 100) * dy_price_krw_per_kg * (recovery_rate / 100)
total_value = nd_value + dy_value

# 결과 출력
st.subheader("📊 예상 가치 산출 결과")
st.write(f"**Nd (네오디뮴) 회수 가치:** {nd_value:,.0f} 원")
st.write(f"**Dy (디스프로슘) 회수 가치:** {dy_value:,.0f} 원")
st.markdown("---")
st.write(f"### **총 예상 가치: {total_value:,.0f} 원**")
