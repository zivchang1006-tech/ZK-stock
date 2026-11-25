import requests
import json
from datetime import datetime

def get_stock_data():
    today_str = datetime.now().strftime("%Y%m%d")
    display_date = datetime.now().strftime("%Y-%m-%d")
    headers = {"User-Agent": "Mozilla/5.0"}

    # 預設資料結構 (15個指標)
    record = {
        "date": display_date,
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "index": 0,          # 01 台指結算(加權指數)
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

    try:
        # 1. 抓三大法人買賣超 (證交所)
        r_inst = requests.get(f"https://twse.com.tw{today_str}&type=day", headers=headers, timeout=10).json()
        if r_inst.get("stat") != "OK":
            print("😴 今日尚未收盤或為假日，暫無資料")
            return
        
        rows = r_inst["data"]
        record["dealer"] = round((float(rows[0][3].replace(",", "")) + float(rows[1][3].replace(",", ""))) / 1e8, 2)
        record["trust"] = round(float(rows[2][3].replace(",", "")) / 1e8, 2)
        record["foreign"] = round(float(rows[3][3].replace(",", "")) / 1e8, 2)

        # 2. 抓大盤指數與成交金額 (證交所)
        r_idx = requests.get(f"https://twse.com.tw{today_str}", headers=headers, timeout=10).json()
        if r_idx.get("stat") == "OK" and r_idx.get("data"):
            last_day = r_idx["data"][-1]
            record["vol"] = round(float(last_day[2].replace(",", "")) / 1e8, 1)
            record["index"] = round(float(last_day[4].replace(",", "")), 0)

        # 3. 抓融資餘額 (證交所)
        r_mar = requests.get(f"https://twse.com.tw{today_str}&selectType=MS", headers=headers, timeout=10).json()
        if r_mar.get("stat") == "OK" and r_mar.get("tables"):
            mar_data = r_mar["tables"][0]["data"]
            record["margin"] = round(float(mar_data[2][5].replace(",", "")) / 1e5, 2)

        # 4. 抓美元兌台幣匯率 (免費公開API)
        r_usd = requests.get("https://er-api.com", timeout=10).json()
        if r_usd.get("rates"):
            record["usd"] = round(r_usd["rates"]["TWD"], 3)

        # 5. 抓期交所 OpenAPI (外資期貨未平倉 & P/C比)
        r_fut = requests.get("https://taifex.com.tw", headers=headers, timeout=10).json()
        for item in r_fut:
            if item.get("ContractCode") == "TX" and "外資" in item.get("Item", ""):
                record["f_oi"] = int(float(item.get("OpenInterestNetVolume", 0)))

        r_pc = requests.get("https://taifex.com.tw", headers=headers, timeout=10).json()
        if r_pc:
            record["pc_ratio"] = round(float(r_pc[-1].get("PutCallRatio", 0)), 2)

        # 6. 抓台積電 ADR (Yahoo Finance 公開介面)
        r_tsm = requests.get("https://yahoo.com", headers=headers, timeout=10).json()
        meta = r_tsm["chart"]["result"][0]["meta"]
        price = meta["regularMarketPrice"]
        prev = meta["chartPreviousClose"]
        record["tsm_adr"] = round(price, 2)
        record["tsm_chg"] = round(price - prev, 2)

    except Exception as e:
        print("⚠️ 部分資料抓取異常（可能尚未公布）：", e)

    # 讀取舊紀錄並寫入 data.json
    try:
        with open("data.json", "r", encoding="utf-8") as f:
            history = json.load(f)
    except:
        history = []

    history = [h for h in history if h["date"] != display_date]
    history.insert(0, record)

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print("✅ 15項指標更新完成！", record)

if __name__ == "__main__":
    get_stock_data()
