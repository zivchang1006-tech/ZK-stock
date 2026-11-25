import requests
import json
from datetime import datetime

# 1. 設定今天日期 (格式: 20261125)
today_str = datetime.now().strftime("%Y%m%d")
display_date = datetime.now().strftime("%Y-%m-%d")

# 2. 去台灣證交所抓「三大法人買賣金額統計表」
url = f"https://twse.com.tw{today_str}&type=day"

try:
    res = requests.get(url, timeout=10).json()
    
    # 如果今天有開盤，資料狀態會是 OK
    if res.get("stat") == "OK":
        data_rows = res["data"]
        # 抓取三大法人買賣超差額 (單位：元 -> 換算成「億」)
        dealer = round(float(data_rows[0][3].replace(",", "")) / 100000000, 2) # 自營商
        trust = round(float(data_rows[2][3].replace(",", "")) / 100000000, 2)  # 投信
        foreign = round(float(data_rows[3][3].replace(",", "")) / 100000000, 2)# 外資
        
        new_record = {
            "date": display_date,
            "foreign": foreign,
            "trust": trust,
            "dealer": dealer,
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M")
        }

        # 3. 讀取舊的 data.json 歷史紀錄，把今天的加在最前面
        try:
            with open("data.json", "r", encoding="utf-8") as f:
                history = json.load(f)
        except:
            history = []

        # 避免同一天重複紀錄
        history = [item for item in history if item["date"] != display_date]
        history.insert(0, new_record)

        # 4. 存回 data.json
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        print("✅ 成功更新今日數據！", new_record)
    else:
        print("😴 今天可能是假日或尚未收盤，沒有新資料。")

except Exception as e:
    print("❌ 抓取失敗：", e)
