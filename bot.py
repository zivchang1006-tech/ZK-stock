import requests
import json
from datetime import datetime, timedelta, timezone

def get_val(lst, idx, default=None):
    try:
        return lst[idx]
    except Exception:
        return default

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
    today_str = now_tw.strftime("%Y%m%d")
    display_date = now_tw.strftime("%Y-%m-%d")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    record = {
        "date": display_date,
        "update_time": now_tw.strftime("%Y-%m-%d %H:%M"),
        "index": 0, "vol": 0, "margin": 0, "usd": 0,
        "foreign": 0, "trust": 0, "dealer": 0,
        "f_oi": 0, "top5": 0, "top10": 0,
        "pc_ratio": 0, "f_opt": 0,
        "mtx_retail": 0, "tmf_retail": 0,
        "tsm_adr": 0, "tsm_chg": 0
    }

    # 1. 三大法人
    try:
        r = requests.get(f"https://twse.com.tw{today_str}&type=day", headers=headers, timeout=15).json()
        if r.get("stat") == "OK":
            rows = r.get("data", [])
            d_self = clean_num(get_val(get_val(rows, 0, []), 3))
            d_hedge = clean_num(get_val(get_val(rows, 1, []), 3))
            record["dealer"] = round((d_self + d_hedge) / 1e8, 2)
            record["trust"] = round(clean_num(get_val(get_val(rows, 2, []), 3)) / 1e8, 2)
            record["foreign"] = round(clean_num(get_val(get_val(rows, 3, []), 3)) / 1e8, 2)
    except Exception as e:
        print("三大法人錯誤:", e)

    # 2. 大盤指數與成交量
    try:
        r = requests.get(f"https://twse.com.tw{today_str}", headers=headers, timeout=15).json()
        if r.get("stat") == "OK" and r.get("data"):
            last_day = r["data"][-1]
            record["vol"] = round(clean_num(get_val(last_day, 2)) / 1e8, 1)
            record["index"] = round(clean_num(get_val(last_day, 4)), 0)
    except Exception as e:
        print("大盤指數錯誤:", e)

    # 3. 融資餘額
    try:
        r = requests.get(f"https://twse.com.tw{today_str}&selectType=MS", headers=headers, timeout=15).json()
        if r.get("stat") == "OK" and r.get("tables"):
            mar_rows = get_val(r["tables"], 0, {}).get("data", [])
            record["margin"] = round(clean_num(get_val(get_val(mar_rows, 2, []), 5)) / 1e5, 2)
    except Exception as e:
        print("融資餘額錯誤:", e)

    # 4. 美元匯率
    try:
        r = requests.get("https://er-api.com", timeout=15).json()
        if r.get("rates"):
            record["usd"] = round(float(r["rates"].get("TWD", 0)), 3)
    except Exception as e:
        print("匯率錯誤:", e)

    # 5. 期交所三大法人與散戶比
    try:
        r_fut = requests.get("https://taifex.com.tw", headers=headers, timeout=15).json()
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

        r_daily = requests.get("https://taifex.com.tw", headers=headers, timeout=15).json()
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
    except Exception as e:
        print("期貨籌碼錯誤:", e)

    # 6. 五大與十大交易人
    try:
        r_top = requests.get("https://taifex.com.tw", headers=headers, timeout=15).json()
        for item in r_top:
            if item.get("ContractCode") == "TX" and "所有" in item.get("ContractMonth", ""):
                record["top5"] = int(clean_num(item.get("Top5BuyOpenInterest")) - clean_num(item.get("Top5SellOpenInterest")))
                record["top10"] = int(clean_num(item.get("Top10BuyOpenInterest")) - clean_num(item.get("Top10SellOpenInterest")))
                break
    except Exception as e:
        print("大額交易人錯誤:", e)

    # 7. P/C Ratio
    try:
        r_pc = requests.get("https://taifex.com.tw", headers=headers, timeout=15).json()
        if r_pc:
            record["pc_ratio"] = round(clean_num(r_pc[-1].get("PutCallRatio")), 2)
    except Exception as e:
        print("PC比錯誤:", e)

    # 8. 外資選擇權
    try:
        r_opt = requests.get("https://taifex.com.tw", headers=headers, timeout=15).json()
        opt_val = 0.0
        for item in r_opt:
            if item.get("ContractCode") == "TXO" and "外資" in item.get("Item", ""):
                val = clean_num(item.get("OpenInterestNetValue"))
                if item.get("CallPut") == "買權":
                    opt_val += val
                elif item.get("CallPut") == "賣權":
                    opt_val -= val
        record["f_opt"] = round(opt_val / 10, 1)
    except Exception as e:
        print("選擇權錯誤:", e)

    # 9. 台積電 ADR
    try:
        r_tsm = requests.get("https://yahoo.com", headers=headers, timeout=15).json()
        meta = r_tsm["chart"]["result"][0]["meta"]
        price = float(meta["regularMarketPrice"])
        prev = float(meta["chartPreviousClose"])
        record["tsm_adr"] = round(price, 2)
        record["tsm_chg"] = round(price - prev, 2)
    except Exception as e:
        print("TSM ADR錯誤:", e)

    try:
        with open("data.json", "r", encoding="utf-8") as f:
            history = json.load(f)
    except Exception:
        history = []

    history = [h for h in history if h.get("date") != display_date]
    history.insert(0, record)

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print("更新完成:", record)

if __name__ == "__main__":
    get_stock_data()
