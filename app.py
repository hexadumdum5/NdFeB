import streamlit as st
import requests
from bs4 import BeautifulSoup
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.naver.com/" # 네이버 검색을 위해 레퍼러 변경
}

@st.cache_data(ttl=600)
def fetch_market_data():
    data = {"nd": None, "dy": None, "exchange": None, "exchange_source": "수동 입력", "errors": []}

    # 1. Nd 시세 (Trading Economics)
    try:
        url_nd = "https://ko.tradingeconomics.com/sremndm:com"
        res_nd = requests.get(url_nd, headers=HEADERS, timeout=10)
        
        if "Cloudflare" in res_nd.text or "Just a moment" in res_nd.text or "보안 인증" in res_nd.text:
            data["errors"].append("Nd 시세 (보안 차단됨)")
        else:
            soup_nd = BeautifulSoup(res_nd.text, 'html.parser')
            price_found = None
            
            price_tag = soup_nd.find(id="market_last_price")
            if price_tag:
                price_found = float(price_tag.text.strip().replace(',', ''))
                
            if not price_found:
                for tr in soup_nd.find_all('tr'):
                    if 'Neodymium' in tr.text or '네오디뮴' in tr.text:
                        for td in tr.find_all('td'):
                            clean_val = re.sub(r'[^0-9.]', '', td.text.strip())
                            if clean_val and float(clean_val) > 100000:
                                price_found = float(clean_val)
                                break
                    if price_found: break
                        
            if not price_found:
                text_nd = soup_nd.get_text(separator=' ')
                match_nd = re.search(r'(?:실제|Actual)\s*([0-9]{2,},[0-9]{3}\.?[0-9]*|[0-9]{5,}\.?[0-9]*)', text_nd)
                if match_nd:
                    price_found = float(match_nd.group(1).replace(',', ''))
                    
            if price_found:
                data["nd"] = price_found
            else:
                data["errors"].append("Nd 시세 (구조 변경)")
                
    except Exception:
        data["errors"].append("Nd 시세 (통신 실패)")

    # 2. Dy 시세 (SunSirs)
    try:
        url_dy = "https://www.sunsirs.com/m-kr/page/commodity-price-detail/commodity-price-detail-113.html"
        res_dy = requests.get(url_dy, headers=HEADERS, timeout=10)
        soup_dy = BeautifulSoup(res_dy.text, 'html.parser')
        text_dy = soup_dy.get_text(separator=' ')
        
        match_dy = re.search(r'비철금속\s*([0-9,.]+)\s*RMB', text_dy)
        if not match_dy:
            match_dy = re.search(r'금속디스프로슘\s+([0-9]{6,8}\.[0-9]{2})', text_dy)

        if match_dy:
            data["dy"] = float(match_dy.group(1).replace(',', ''))
        else:
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
         data["errors"].append("Dy 시세 (통신 실패)")

    # 3. 환율 (네이버 통합검색 1순위 -> 구글 파이낸스 2순위 백업)
    try:
        # 1차 시도: 네이버 통합검색창 우회 (차단 회피율이 가장 높음)
        url_naver_search = "https://search.naver.com/search.naver?query=위안화+환율"
        res_naver = requests.get(url_naver_search, headers=HEADERS, timeout=10)
        soup_naver = BeautifulSoup(res_naver.text, 'html.parser')
        
        # 네이버 검색 결과의 환율 숫자 영역 파싱
        spt_con = soup_naver.find('div', class_='spt_con')
        if spt_con and spt_con.find('strong'):
            data["exchange"] = float(spt_con.find('strong').text.replace(',', ''))
            data["exchange_source"] = "네이버 (하나은행 매매기준율)"
        else:
            # 보조 탐색 (정규식)
            match = re.search(r'([1-9][0-9]{2}\.[0-9]{2})\s*원', soup_naver.get_text())
            if match:
                data["exchange"] = float(match.group(1))
                data["exchange_source"] = "네이버 (하나은행 매매기준율)"
            else:
                raise Exception("Naver Search Parsing Failed")
    except Exception:
        try:
            # 2차 시도: 구글 파이낸스 (네이버 완전히 막혔을 때)
            url_google = "https://www.google.com/finance/quote/CNY-KRW"
            res_google = requests.get(url_google, headers=HEADERS, timeout=10)
            soup_google = BeautifulSoup(res_google.text, 'html.parser')
            price_div = soup_google.find(class_='YMlKec fxKbKc')
            if price_div:
                data["exchange"] = float(price_div.text.strip().replace(',', ''))
                data["exchange_source"] = "구글 (국제 외환 기준 - 네이버 차단됨)"
            else:
                 data["errors"].append("환율 (데이터 없음)")
        except Exception:
            data["errors"].append("환율 (통신 실패)")

    return data

# --- 앱 화면 구성 ---
st.set_page_config(page_title="희토류 가치 계산기", layout="centered")

st.title("NdFeB 폐자석 가치 계산기")
st.markdown("Nd, Dy 시세 및 환율 자동 연동")

if st.button("🔄 실시간 데이터 갱신 (새로고침)"):
    st.cache_data.clear()
    st.rerun()

market_data = fetch_market_data()

if market_data["errors"]:
    error_msgs = ", ".join(market_data["errors"])
    st.warning(f"⚠️ 일부 데이터를 자동으로 불러오지 못했습니다. (실패 항목: {error_msgs})")
else:
    st.success("✅ 모든 실시간 시세 및 환율을 성공적으로 불러왔습니다.")

default_nd = market_data["nd"] if market_data["nd"] else 975000.0
default_dy = market_data["dy"] if market_data["dy"] else 1920000.0
default_ex = market_data["exchange"] if market_data["exchange"] else 190.0

with st.expander("⚙️ 여기를 눌러 자석 정보 및 시세를 입력하세요", expanded=True):
    st.subheader("1. 자석 정보 입력")
    total_weight = st.number_input("총 투입 중량 (kg)", value=1.0)
    nd_content = st.number_input("Nd 함량 (%)", value=25.0)
    dy_content = st.number_input("Dy 함량 (%)", value=0.0)
    recovery_rate = st.number_input("예상 회수 수율 (%)", min_value=0.0, max_value=100.0, value=80.0, step=0.1)
    
    st.markdown("---")
    st.subheader("2. 실시간 시세 및 환율 수정")
    # 환율 출처를 사용자에게 투명하게 보여줌
    st.caption(f"💡 현재 환율 출처: **{market_data.get('exchange_source')}**")
    
    nd_price_cny = st.number_input("Nd 시세 (CNY/Ton)", value=default_nd, step=1000.0)
    dy_price_cny = st.number_input("Dy 시세 (CNY/Ton)", value=default_dy, step=10000.0)
    exchange_rate = st.number_input("환율 (KRW/CNY)", value=default_ex, step=1.0)
    
    st.info("👆 입력을 마치셨다면 위쪽의 '⚙️ 여기를 눌러...' 영역을 다시 눌러 창을 접어주세요.")

nd_price_krw_per_kg = (nd_price_cny * exchange_rate) / 1000
dy_price_krw_per_kg = (dy_price_cny * exchange_rate) / 1000

nd_value = total_weight * (nd_content / 100) * nd_price_krw_per_kg * (recovery_rate / 100)
dy_value = total_weight * (dy_content / 100) * dy_price_krw_per_kg * (recovery_rate / 100)
total_value = nd_value + dy_value

st.subheader("📊 예상 가치 산출 결과")
st.write(f"**Nd (네오디뮴) 회수 가치:** {nd_value:,.0f} 원")
st.write(f"**Dy (디스프로슘) 회수 가치:** {dy_value:,.0f} 원")
st.markdown("---")
st.write(f"### **총 예상 가치: {total_value:,.0f} 원**")
