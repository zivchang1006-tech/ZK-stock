import requests
import urllib3
import json
from datetime import datetime, timedelta, timezone

# 關閉 SSL 憑證警告，確保台灣官方 OpenAPI 連線順暢
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def clean_num(val):
    if val is None:
        return 0.0
    try:
        return float(str(val).replace(",", "").strip())
    except Exception:
        return 0.0

def get_stock_data():
    tw_tz = timezone(timedelta(hours=8))
    now_tw = datetime.now(tw_tz)
    display_date = now_tw.strftime("%Y-%m-%d")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }

    record = {
        "date": display_date,
        "update_time": now_tw.strftime("%Y-%m-%d %H:%M"),
        "index": 0,          # 01 台指收盤(加權指數)
        "vol": 0,            # 02 現貨量(億)
        "margin": 0,         # 03 融資餘額(億)
        "usd": 0,            # 04 美元兌台幣
        "foreign": 0,        # 05 外資現貨(億)
        "trust": 0,          # 06 投信現貨(億)
        "dealer": 0,         # 07 自營商現貨(億)
        "f_oi": 0,           # 08 外資台指期未平倉
        "top5": 0,           # 09 五大淨額(口)
        "top10": 0,          # 10 十大淨額(口)
        "pc_ratio": 0,       # 11 P/C未平倉比(%)
        "f_opt": 0,          # 12 外資選擇權未平倉淨額(萬)
        "mtx_retail": 0,     # 13 小台散戶多空比(%)
        "tmf_retail": 0,     # 14 微台散戶多空比(%)
        "tsm_adr": 0,        # 15 台積電美股ADR指數
        "tsm_chg": 0         # 台積電ADR漲跌
    }

    # 1. 證交所 OpenAPI：大盤收盤指數與成交金額(億)
    try:
        r_idx = requests.get("https://twse.com.tw", headers=headers, verify=False, timeout=15).json()
        if r_idx:
            last_day = r_idx[-1]
            # 轉為億元 (原始單位為元)
            record["vol"] = round(clean_num(last_day.get("TradeValue")) / 1e8, 1)
            record["index"] = round(clean_num(last_day.get("TAIEX")), 0)
            # 若官方資料有日期，同步轉換民國年為西元年 (例如 1151125 -> 2026-11-25)
            roc_date = str(last_day.get("Date", "")).strip()
            if len(roc_date) == 7:
                yyyy = int(roc_date[:3]) + 1911
                mm = roc_date[3:5]
                dd = roc_date[5:7]
                record["date"] = f"{yyyy}-{mm}-{dd}"
                display_date = record["date"]
        print("1. 大盤量價抓取:", record["index"], record["vol"])
    except Exception as e:
        print("❌ 大盤指數抓取失敗:", e)

    # 2. 證交所 OpenAPI：三大法人買賣超(億)
    try:
        r_inst = requests.get("https://twse.com.tw", headers=headers, verify=False, timeout=15).json()
        dealer_sum = 0.0
        for row in r_inst:
            name = row.get("Item", "")
            diff = clean_num(row.get("Difference"))
            if "自營商" in name:
                dealer_sum += diff
            elif "投信" in name:
                record["trust"] = round(diff / 1e8, 2)
            elif "外資及陸資" in name and "不含" in name:
                record["foreign"] = round(diff / 1e8, 2)
        record["dealer"] = round(dealer_sum / 1e8, 2)
        print("2. 三大法人抓取:", record["foreign"], record["trust"], record["dealer"])
    except Exception as e:
        print("❌ 三大法人抓取失敗:", e)

    # 3. 證交所 OpenAPI：融資餘額(億)
    try:
        r_mar = requests.get("https://twse.com.tw", headers=headers, verify=False, timeout=15).json()
        for row in r_mar:
            if "融資金額" in row.get("Item", ""):
                # 原始單位為仟元，轉億元除以 100000
                record["margin"] = round(clean_num(row.get("TodayBalance")) / 1e5, 2)
                break
        print("3. 融資餘額抓取:", record["margin"])
    except Exception as e:
        print("❌ 融資餘額抓取失敗:", e)

    # 4. 美元兌台幣匯率
    try:
        r_usd = requests.get("https://er-api.com", verify=False, timeout=15).json()
        if r_usd.get("rates"):
            record["usd"] = round(float(r_usd["rates"].get("TWD", 0)), 3)
        print("4. 美元匯率抓取:", record["usd"])
    except Exception as e:
        print("❌ 匯率抓取失敗:", e)

    # 5. 期交所 OpenAPI：三大法人期貨未平倉 & 小台/微台散戶多空比
    try:
        r_fut = requests.get("https://taifex.com.tw", headers=headers, verify=False, timeout=15).json()
        mtx_inst, tmf_inst = 0, 0
        for item in r_fut:
            code = item.get("ContractCode", "")
            who = item.get("Item", "")
            net_oi = int(clean_num(item.get("OpenInterestNetVolume")))
            if code == "TX" and "外資" in who:
                record["f_oi"] = net_oi
            elif code == "MTX":
                mtx_inst += net_oi
            elif code == "TMF":
                tmf_inst += net_oi

        r_daily = requests.get("https://taifex.com.tw", headers=headers, verify=False, timeout=15).json()
        mtx_tot, tmf_tot = 0, 0
        for d in r_daily:
            if d.get("TradingSession") == "一般":
                if d.get("Contract") == "MTX":
                    mtx_tot += int(clean_num(d.get("OpenInterest")))
                elif d.get("Contract") == "TMF":
                    tmf_tot += int(clean_num(d.get("OpenInterest")))

        if mtx_tot > 0:
            record["mtx_retail"] = round((-mtx_inst / mtx_tot) * 100, 2)
        if tmf_tot > 0:
            record["tmf_retail"] = round((-tmf_inst / tmf_tot) * 100, 2)
        print("5. 期貨與散戶比抓取:", record["f_oi"], record["mtx_retail"], record["tmf_retail"])
    except Exception as e:
        print("❌ 期貨籌碼抓取失敗:", e)

    # 6. 期交所 OpenAPI：五大/十大交易人淨額
    try:
        r_top = requests.get("https://taifex.com.tw", headers=headers, verify=False, timeout=15).json()
        for item in r_top:
            if item.get("ContractCode") == "TX" and "所有" in item.get("ContractMonth", ""):
                record["top5"] = int(clean_num(item.get("Top5BuyOpenInterest")) - clean_num(item.get("Top5SellOpenInterest")))
                record["top10"] = int(clean_num(item.get("Top10BuyOpenInterest")) - clean_num(item.get("Top10SellOpenInterest")))
                break
        print("6. 五大十大淨額抓取:", record["top5"], record["top10"])
    except Exception as e:
        print("❌ 五大/十大交易人抓取失敗:", e)

    # 7. 期交所 OpenAPI：P/C Ratio (%)
    try:
        r_pc = requests.get("https://taifex.com.tw", headers=headers, verify=False, timeout=15).json()
        if r_pc:
            record["pc_ratio"] = round(clean_num(r_pc[-1].get("PutCallRatio")), 2)
        print("7. P/C比抓取:", record["pc_ratio"])
    except Exception as e:
        print("❌ P/C比抓取失敗:", e)

    # 8. 期交所 OpenAPI：外資選擇權未平倉淨金額(萬)
    try:
        r_opt = requests.get("https://taifex.com.tw", headers=headers, verify=False, timeout=15).json()
        opt_val = 0.0
        for item in r_opt:
            if item.get("ContractCode") == "TXO" and "外資" in item.get("Item", ""):
                val = clean_num(item.get("OpenInterestNetValue"))
                if item.get("CallPut") == "買權":
                    opt_val += val
                elif item.get("CallPut") == "賣權":
                    opt_val -= val
        record["f_opt"] = round(opt_val / 10, 1)
        print("8. 外資選擇權抓取:", record["f_opt"])
    except Exception as e:
        print("❌ 外資選擇權抓取失敗:", e)

    # 9. 台積電 ADR (Yahoo Finance API)
    try:
        r_tsm = requests.get("https://yahoo.com", headers=headers, verify=False, timeout=15).json()
        result_list = r_tsm.get("chart", {}).get("result", [])
        if result_list:
            meta = result_list[0].get("meta", {})
            price = float(meta.get("regularMarketPrice", 0))
            prev = float(meta.get("chartPreviousClose", 0))
            record["tsm_adr"] = round(price, 2)
            record["tsm_chg"] = round(price - prev, 2)
        print("9. 台積電ADR抓取:", record["tsm_adr"], record["tsm_chg"])
    except Exception as e:
        print("❌ 台積電ADR抓取失敗:", e)

    # 讀取舊紀錄並寫入 data.json
    try:
        with open("data.json", "r", encoding="utf-8") as f:
            history = json.load(f)
    except Exception:
        history = []

    history = [h for h in history if h.get("date") != display_date]
    history.insert(0, record)

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print("✅ 全部寫入 data.json 完成！")

if __name__ == "__main__":
    get_stock_data()
