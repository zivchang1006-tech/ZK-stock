import requests
import json
from datetime import datetime, timedelta, timezone

def get_stock_data():
    # 強制使用台灣時間 (UTC+8)
    tw_tz = timezone(timedelta(hours=8))
    now_tw = datetime.now(tw_tz)
    today_str = now_tw.strftime("%Y%m%d")
    display_date = now_tw.strftime("%Y-%m-%d")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
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

    # 1. 證交所：三大法人買賣超 (15:00後公布)
    try:
        url_inst = f"https://twse.com.tw{today_str}&type=day"
        r_inst = requests.get(url_inst, headers=headers, timeout=15).json()
        if r_inst.get("stat") == "OK":
            rows = r_inst["data"]
            # 自營商(自行買賣+避險)
            dealer_val = float(rows[0][3].replace(",", "")) + float(rows[1][3].replace(",", ""))
            record["dealer"] = round(dealer_val / 1e8, 2)
            record["trust"] = round(float(rows[2][3].replace(",", "")) / 1e8, 2)
            record["foreign"] = round(float(rows[3][3].replace(",", "")) / 1e8, 2)
        else:
            print("⚠️ 三大法人尚未公布或今日休市")
    except Exception as e:
        print("❌ 三大法人抓取失敗:", e)

    # 2. 證交所：大盤收盤指數與成交金額(億)
    try:
        url_idx = f"https://twse.com.tw{today_str}"
        r_idx = requests.get(url_idx, headers=headers, timeout=15).json()
        if r_idx.get("stat") == "OK" and r_idx.get("data"):
            last_day = r_idx["data"][-1]
            record["vol"] = round(float(last_day[2].replace(",", "")) / 1e8, 1)
            record["index"] = round(float(last_day[4].replace(",", "")), 0)
    except Exception as e:
        print("❌ 大盤指數抓取失敗:", e)

    # 3. 證交所：融資餘額(億) (約16:00後公布)
    try:
        url_mar = f"https://twse.com.tw{today_str}&selectType=MS"
        r_mar = requests.get(url_mar, headers=headers, timeout=15).json()
        if r_mar.get("stat") == "OK" and r_mar.get("tables"):
            mar_data = r_mar["tables"][0]["data"]
            # 融資金額(仟元) -> 轉為億元除以 100000
            record["margin"] = round(float(mar_data[2][5].replace(",", "")) / 1e5, 2)
    except Exception as e:
        print("❌ 融資餘額抓取失敗:", e)

    # 4. 美元兌台幣匯率
    try:
        r_usd = requests.get("https://er-api.com", timeout=15).json()
        if r_usd.get("rates"):
            record["usd"] = round(r_usd["rates"]["TWD"], 3)
    except Exception as e:
        print("❌ 匯率抓取失敗:", e)

    # 5. 期交所 OpenAPI：三大法人期貨未平倉（含外資大台、小台、微台散戶比計算）
    try:
        url_fut = "https://taifex.com.tw"
        r_fut = requests.get(url_fut, headers=headers, timeout=15).json()
        
        mtx_inst_net = 0
        tmf_inst_net = 0
        for item in r_fut:
            code = item.get("ContractCode", "")
            who = item.get("Item", "")
            net_oi = int(float(item.get("OpenInterestNetVolume", 0)))
            if code == "TX" and "外資" in who:
                record["f_oi"] = net_oi
            elif code == "MTX":
                mtx_inst_net += net_oi
            elif code == "TMF":
                tmf_inst_net += net_oi

        # 抓取全市場未平倉量以計算小台/微台散戶多空比
        url_daily_fut = "https://taifex.com.tw"
        r_daily_fut = requests.get(url_daily_fut, headers=headers, timeout=15).json()
        mtx_total_oi = 0
        tmf_total_oi = 0
        for d in r_daily_fut:
            if d.get("Contract") == "MTX" and d.get("TradingSession") == "一般":
                mtx_total_oi += int(float(d.get("OpenInterest", 0) or 0))
            elif d.get("Contract") == "TMF" and d.get("TradingSession") == "一般":
                tmf_total_oi += int(float(d.get("OpenInterest", 0) or 0))

        # 散戶未平倉 = -法人未平倉；散戶多空比 = 散戶淨口數 / 全市場總未平倉 * 100
        if mtx_total_oi > 0:
            record["mtx_retail"] = round((-mtx_inst_net / mtx_total_oi) * 100, 2)
        if tmf_total_oi > 0:
            record["tmf_retail"] = round((-tmf_inst_net / tmf_total_oi) * 100, 2)
    except Exception as e:
        print("❌ 期貨籌碼抓取失敗:", e)

    # 6. 期交所 OpenAPI：五大/十大交易人淨額 (台指期所有契約)
    try:
        url_top = "https://taifex.com.tw"
        r_top = requests.get(url_top, headers=headers, timeout=15).json()
        for item in r_top:
            if item.get("ContractCode") == "TX" and "所有" in item.get("ContractMonth", ""):
                top5_buy = int(float(item.get("Top5BuyOpenInterest", 0) or 0))
                top5_sell = int(float(item.get("Top5SellOpenInterest", 0) or 0))
                top10_buy = int(float(item.get("Top10BuyOpenInterest", 0) or 0))
                top10_sell = int(float(item.get("Top10SellOpenInterest", 0) or 0))
                record["top5"] = top5_buy - top5_sell
                record["top10"] = top10_buy - top10_sell
                break
    except Exception as e:
        print("❌ 五大/十大交易人抓取失敗:", e)

    # 7. 期交所 OpenAPI：P/C Ratio (%)
    try:
        url_pc = "https://taifex.com.tw"
        r_pc = requests.get(url_pc, headers=headers, timeout=15).json()
        if r_pc:
            record["pc_ratio"] = round(float(r_pc[-1].get("PutCallRatio", 0)), 2)
    except Exception as e:
        print("❌ P/C比抓取失敗:", e)

    # 8. 期交所 OpenAPI：外資選擇權未平倉淨金額(萬)
    try:
        url_opt = "https://taifex.com.tw"
        r_opt = requests.get(url_opt, headers=headers, timeout=15).json()
        opt_net_val = 0
        for item in r_opt:
            if item.get("ContractCode") == "TXO" and "外資" in item.get("Item", ""):
                # 買權(Call)淨金額 - 賣權(Put)淨金額 (單位：千元 -> 轉萬元除以10)
                val = float(item.get("OpenInterestNetValue", 0) or 0)
                if item.get("CallPut") == "買權":
                    opt_net_val += val
                elif item.get("CallPut") == "賣權":
                    opt_net_val -= val
        record["f_opt"] = round(opt_net_val / 10, 1)
    except Exception as e:
        print("❌ 外資選擇權抓取失敗:", e)

    # 9. 台積電 ADR (Yahoo Finance API)
    try:
        url_tsm = "https://yahoo.com"
        r_tsm = requests.get(url_tsm, headers=headers, timeout=15).json()
        meta = r_tsm["chart"]["result"][0]["meta"]
        price = meta["regularMarketPrice"]
        prev = meta["chartPreviousClose"]
        record["tsm_adr"] = round(price, 2)
        record["tsm_chg"] = round(price - prev, 2)
    except Exception as e:
        print("❌ 台積電ADR抓取失敗:", e)

    # 讀取舊紀錄並寫入 data.json
    try:
        with open("data.json", "r", encoding="utf-8") as f:
            history = json.load(f)
    except Exception:
        history = []

    # 過濾掉同一天的舊資料，將最新資料插在最前面
    history = [h for h in history if h.get("date") != display_date]
    history.insert(0, record)

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    
    print("✅ 15項指標更新完成！", json.dumps(record, ensure_ascii=False))

if __name__ == "__main__":
    get_stock_data()
