import streamlit as st
import requests
from bs4 import BeautifulSoup
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
}

@st.cache_data(ttl=3600)
def get_nd_price():
    url = "https://ko.tradingeconomics.com/commodity/neodymium"
    try:
        response = requests.get(url, headers=HEADERS, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        tables = soup.find_all('table')
        for table in tables:
            if '실제' in table.text and '이전' in table.text:
                rows = table.find_all('tr')
                for row in rows:
                    tds = row.find_all('td')
                    if len(tds) >= 1:
                        price_str = tds[0].text.strip()
                        price_clean = re.sub(r'[^0-9.]', '', price_str)
                        if price_clean:
                            return float(price_clean)
                            
        return 1060000.0 
    except Exception:
        return 1060000.0 

@st.cache_data(ttl=3600)
def get_dy_price():
    url = "https://www.sunsirs.com/m-kr/page/commodity-price-detail/commodity-price-detail-113.html"
    try:
        response = requests.get(url, headers=HEADERS, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table') 
        if table:
            tds = table.find_all('td')
            if len(tds) > 1:
                price_str = tds[1].text.strip()
                return float(re.sub(r'[^0-9.]', '', price_str))
        return 2075000.0
    except Exception:
        return 2075000.0

@st.cache_data(ttl=3600)
def get_exchange_rate():
    url = "https://m.stock.naver.com/marketindex/exchange/FX_CNYKRW"
    try:
        response = requests.get(url, headers=HEADERS, timeout=5)
        match = re.search(r'"closePrice"\s*:\s*"([0-9,.]+)"', response.text)
        if match:
            return float(match.group(1).replace(',', ''))
            
        soup = BeautifulSoup(response.text, 'html.parser')
        text = soup.get_text()
        numbers = re.findall(r'1[89][0-9]\.[0-9]{2}|20[0-9]\.[0-9]{2}', text)
        if numbers:
            return float(numbers[0])
            
        return 190.0
    except Exception:
        return 190.0

# --- 앱 화면 및 UI 구성 ---
st.title("NdFeB 폐자석 희토류 가치 계산기")
st.markdown("Nd, Dy 시세 및 실시간 네이버 CNY 환율 자동 연동")

# 1. 백그라운드에서 시세 및 환율 데이터 불러오기
raw_nd_price = get_nd_price()
raw_dy_price = get_dy_price()
raw_exchange_rate = get_exchange_rate()

# 2. 사이드바: 입력 및 시세 보정 UI
st.sidebar.header("1. 실시간 시세 및 환율")
st.sidebar.caption("자동으로 불러온 값이 부정확할 경우 직접 클릭하여 수정 가능합니다.")
nd_price_cny = st.sidebar.number_input("Nd 시세 (CNY/Ton)", value=float(raw_nd_price), step=1000.0)
dy_price_cny = st.sidebar.number_input("Dy 시세 (CNY/Ton)", value=float(raw_dy_price), step=10000.0)
exchange_rate = st.sidebar.number_input("환율 (KRW/CNY)", value=float(raw_exchange_rate), step=1.0)

st.sidebar.markdown("---")
st.sidebar.header("2. 자석 정보 입력")
total_weight = st.sidebar.number_input("총 투입 중량 (kg)", value=1000.0)
nd_content = st.sidebar.number_input("Nd 함량 (%)", value=25.0)
dy_content = st.sidebar.number_input("Dy 함량 (%)", value=3.0)

# 슬라이더에서 직접 입력(number_input) 방식으로 변경
recovery_rate = st.sidebar.number_input("예상 회수 수율 (%)", min_value=0.0, max_value=100.0, value=90.0, step=0.1)

# 3. 가치 계산
# 톤당 위안화 가격을 원화 기준 kg당 가격으로 환산
nd_price_krw_per_kg = (nd_price_cny * exchange_rate) / 1000
dy_price_krw_per_kg = (dy_price_cny * exchange_rate) / 1000

nd_value = total_weight * (nd_content / 100) * nd_price_krw_per_kg * (recovery_rate / 100)
dy_value = total_weight * (dy_content / 100) * dy_price_krw_per_kg * (recovery_rate / 100)
total_value = nd_value + dy_value

# 4. 결과 출력
st.subheader("예상 가치 산출 결과 (KRW)")
st.write(f"**Nd (네오디뮴) 회수 가치:** {nd_value:,.0f} 원")
st.write(f"**Dy (디스프로슘) 회수 가치:** {dy_value:,.0f} 원")
st.markdown("---")
st.write(f"### **총 예상 가치: {total_value:,.0f} 원**")
