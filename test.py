# test.py 맨 위에 추가
import sys
sys.path.insert(0, '/home/administrator/kiwoom-rest-api/src')


# test.py - 차트 조회 부분 수정
import os
from dotenv import load_dotenv
from kiwoom_rest_api import KiwoomAPI

load_dotenv()

api = KiwoomAPI(
    app_key=os.getenv("APP_KEY"),
    app_secret=os.getenv("APP_SECRET"),
    is_mock=True,
)

try:
    # 1. 삼성전자 기본 정보
    print("=== 삼성전자 기본 정보 ===")
    info = api.stock_info.basic_stock_info(stk_cd="005930")
    print(f"종목명: {info.get('stk_nm')}")
    print(f"현재가: {info.get('cur_prc')}")
    print()

    # 2. 내 계좌 평가 현황
    print("=== 내 계좌 평가 현황 ===")
    evaluation = api.account.account_evaluation(
        qry_tp="0",
        dmst_stex_tp="01"
    )
    print(evaluation)
    print()

    # 3. 삼성전자 일봉 차트 (수정됨!)
    print("=== 삼성전자 일봉 차트 (최근 5일) ===")
    chart = api.chart.stock_daily_chart(
        stk_cd="005930",
        base_dt="20260901",
        upd_stkpc_tp="0"  # ← 여기에 파라미터 추가! (0: 수정주가, 1: 원주가)
    )
    data_list = chart.get('data', [])
    for item in data_list[:5]:
        print(item)

except Exception as e:
    print(f"에러 발생: {e}")

finally:
    api.close()