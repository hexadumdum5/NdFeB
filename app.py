import streamlit as st
import requests
from bs4 import BeautifulSoup
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.google.com/"
}

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
            data["errors"].append("Nd 시세 (구조 변경)")
    except Exception:
        data["errors"].append("Nd 시세 (차단됨)")

    # 2. Dy 시세 (SunSirs) - 로직 대폭 강화
    try:
        url_dy = "https://www.sunsirs.com/m-kr/page/commodity-price-detail/commodity-price-detail-113.html"
        res_dy = requests.get(url_dy, headers=HEADERS, timeout=5)
        soup_dy = BeautifulSoup(res_dy.text, 'html.parser')
        text_dy = soup_dy.get_text(separator=' ')
        
        # 패턴 1: 상단 요약본에서 "비철금속 1920000.00 RMB" 형태 찾기
        match_dy = re.search(r'비철금속\s*([0-9,.]+)\s*RMB', text_dy)
        
        # 패턴 2: 아래쪽 표 영역에서 "금속디스프로슘 1920000.00" 형태 찾기
        if not match_dy:
            match_dy = re.search(r'금속디스프로슘\s+([0-9]{6,8}\.[0-9]{2})', text_dy)

        if match_dy:
            data["dy"] = float(match_dy.group(1).replace(',', ''))
        else:
            # 패턴 3: 진짜 데이터가 들어있는 테이블만 골라내서 추출
            tables = soup_dy.find_all('table')
            for t in tables:
                if '금속디스프로슘' in t.text and '날짜' in t.text:
                    tds = t.find_all('td')
                    if len(tds) >= 2:
                        price_clean = re.sub(r'[^0-9.]', '', tds[1].text.strip())
                        if price_clean:
                            data["dy"] = float(price_clean)
                            break
                            
        if data["dy"] is None:
            data["errors"].append("Dy 시세 (데이터 없음)")
    except Exception:
         data["errors"].append("Dy 시세 (차단됨)")

    # 3. 환율 (구글 파이낸스 -> 네이버 금융 2중 백업)
    try:
        url_google = "https://www.google.com/finance/quote/CNY-KRW"
        res_google = requests.get(url_google, headers=HEADERS, timeout=5)
        soup_google = BeautifulSoup(res_google.text, 'html.parser')
        price_div = soup_google.find(class_='YMlKec fxKbKc')
        if price_div:
            data["exchange"] = float(price_div.text.strip().replace(',', ''))
        else:
            raise Exception("Google failed")
    except Exception:
        try:
            url_naver = "https://finance.naver.com/marketindex/exchangeDetail.naver?marketindexCd=FX_CNYKRW"
            res_naver = requests.get(url_naver, headers=HEADERS, timeout=5)
            soup_naver = BeautifulSoup(res_naver.text, 'html.parser')
            today_price = soup_naver.find('p', class_='no_today')
            if today_price:
                price_str = today_price.find('span', class_='blind').text
                data["exchange"] = float(price_str.replace(',', ''))
            else:
                 data["errors"].append("환율 (데이터 연동 실패)")
        except Exception:
            data["errors"].append("환율 (모든 접속 차단됨)")

    return data

# --- 앱 화면 구성 ---
st.set_page_config(page_title="희토류 가치 계산기", layout="centered")

st.title("NdFeB 폐자석 가치 계산기")
st.markdown("Nd, Dy 시세 및 환율 자동 연동")

if st.button("🔄 실시간 데이터 갱신 (새로고침)"):
    st.cache_data.clear()
    st.rerun()

# 백그라운드 데이터 불러오기
market_data = fetch_market_data()

if market_data["errors"]:
    error_msgs = ", ".join(market_data["errors"])
    st.warning(f"⚠️ 일부 데이터를 자동으로 불러오지 못했습니다. (실패 항목: {error_msgs})")
else:
    st.success("✅ 모든 실시간 시세 및 환율을 성공적으로 불러왔습니다.")

# 크롤링 실패 시 적용할 임시 기본값 설정
default_nd = market_data["nd"] if market_data["nd"] else 975000.0
default_dy = market_data["dy"] if market_data["dy"] else 1920000.0
default_ex = market_data["exchange"] if market_data["exchange"] else 190.0

with st.expander("⚙️ 여기를 눌러 자석 정보 및 시세를 입력하세요", expanded=True):
    st.subheader("1. 자석 정보 입력")
    total_weight = st.number_input("총 투입 중량 (kg)", value=1000.0)
    nd_content = st.number_input("Nd 함량 (%)", value=25.0)
    dy_content = st.number_input("Dy 함량 (%)", value=3.0)
    recovery_rate = st.number_input("예상 회수 수율 (%)", min_value=0.0, max_value=100.0, value=90.0, step=0.1)
    
    st.markdown("---")
    st.subheader("2. 실시간 시세 및 환율 수정")
    st.caption("자동으로 불러온 값이 엉뚱할 경우, 클릭해서 언제든 직접 수정하세요.")
    nd_price_cny = st.number_input("Nd 시세 (CNY/Ton)", value=default_nd, step=1000.0)
    dy_price_cny = st.number_input("Dy 시세 (CNY/Ton)", value=default_dy, step=10000.0)
    exchange_rate = st.number_input("환율 (KRW/CNY)", value=default_ex, step=1.0)
    
    st.info("👆 입력을 마치셨다면 위쪽의 '⚙️ 여기를 눌러...' 영역을 다시 눌러 창을 접어주세요.")

# 가치 계산 로직
nd_price_krw_per_kg = (nd_price_cny * exchange_rate) / 1000
dy_price_krw_per_kg = (dy_price_cny * exchange_rate) / 1000

nd_value = total_weight * (nd_content / 100) * nd_price_krw_per_kg * (recovery_rate / 100)
dy_value = total_weight * (dy_content / 100) * dy_price_krw_per_kg * (recovery_rate / 100)
total_value = nd_value + dy_value

# 결과 출력 영역
st.subheader("📊 예상 가치 산출 결과")
st.write(f"**Nd (네오디뮴) 회수 가치:** {nd_value:,.0f} 원")
st.write(f"**Dy (디스프로슘) 회수 가치:** {dy_value:,.0f} 원")
st.markdown("---")
st.write(f"### **총 예상 가치: {total_value:,.0f} 원**")
