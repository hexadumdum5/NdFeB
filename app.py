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

    # 1. Nd 시세 (Trading Economics) - 3중 탐색 로직 적용
    try:
        url_nd = "https://ko.tradingeconomics.com/sremndm:com"
        # 로봇 차단 회피를 위해 브라우저인 척 대기 시간(timeout) 약간 증가
        res_nd = requests.get(url_nd, headers=HEADERS, timeout=10)
        
        # 보안 페이지에 걸렸는지 텍스트로 1차 확인
        if "Cloudflare" in res_nd.text or "Just a moment" in res_nd.text or "보안 인증" in res_nd.text:
            data["errors"].append("Nd 시세 (사이트 보안 시스템에 임시 차단됨)")
        else:
            soup_nd = BeautifulSoup(res_nd.text, 'html.parser')
            price_found = None
            
            # [탐색 1단계] 고유 ID로 정확히 찾기
            price_tag = soup_nd.find(id="market_last_price")
            if price_tag:
                price_found = float(price_tag.text.strip().replace(',', ''))
                
            # [탐색 2단계] 표(Table) 안에서 Neodymium 행을 뒤지기
            if not price_found:
                for tr in soup_nd.find_all('tr'):
                    if 'Neodymium' in tr.text or '네오디뮴' in tr.text:
                        for td in tr.find_all('td'):
                            clean_val = re.sub(r'[^0-9.]', '', td.text.strip())
                            # 희토류 시세가 10만 단위 이상이라는 점을 활용해 엉뚱한 숫자 필터링
                            if clean_val and float(clean_val) > 100000:
                                price_found = float(clean_val)
                                break
                    if price_found: break
                        
            # [탐색 3단계] 전체 텍스트에서 '실제' 글자 옆의 큰 숫자 찾기 (최후의 보루)
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
        data["errors"].append("Nd 시세 (서버 통신 실패)")

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
         data["errors"].append("Dy 시세 (서버 통신 실패)")

    # 3. 환율 (구글 파이낸스 -> 네이버 금융 2중 백업)
    try:
        url_google = "https://www.google.com/finance/quote/CNY-KRW"
        res_google = requests.get(url_google, headers=HEADERS, timeout=10)
        soup_google = BeautifulSoup(res_google.text, 'html.parser')
        price_div = soup_google.find(class_='YMlKec fxKbKc')
        if price_div:
            data["exchange"] = float(price_div.text.strip().replace(',', ''))
        else:
            raise Exception("Google failed")
    except Exception:
        try:
            url_naver = "https://finance.naver.com/marketindex/exchangeDetail.naver?marketindexCd=FX_CNYKRW"
            res_naver = requests.get(url_naver, headers=HEADERS, timeout=10)
            soup_naver = BeautifulSoup(res_naver.text, 'html.parser')
            today_price = soup_naver.find('p', class_='no_today')
            if today_price:
                price_str = today_price.find('span', class_='blind').text
                data["exchange"] = float(price_str.replace(',', ''))
            else:
                 data["errors"].append("환율 (데이터 없음)")
        except Exception:
            data["errors"].append("환율 (서버 통신 실패)")

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
    st.caption("자동 연동이 실패했거나 수치가 다를 경우 언제든 직접 수정하세요.")
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
    total_weight = st.number_input("총 투입 중량 (kg)", value=1.0)
    nd_content = st.number_input("Nd 함량 (%)", value=25.0)
    dy_content = st.number_input("Dy 함량 (%)", value=0.0)
    recovery_rate = st.number_input("예상 회수 수율 (%)", min_value=0.0, max_value=100.0, value=80.0, step=0.1)
    
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
