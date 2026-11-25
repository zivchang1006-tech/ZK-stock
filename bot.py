
    if used_rows == 0:
        raise ValueError(
            "TAIFEX外資選擇權資料找不到可辨識的買權/賣權淨未平倉金額欄位。"
            f"實際欄位：{list(foreign_rows[0].keys())}"
        )

    # 若來源為千元，除以 10 轉萬元；若來源為百萬元，乘 100 轉萬元。
    sample_row = foreign_rows[0]
    value_key = next((k for k in sample_row if norm_key(k) in {norm_key(x) for x in value_candidates}), "")
    if "millions" in value_key.lower():
        return round(total_thousand * 100, 1)
    return round(total_thousand / 10, 1)


def get_tsm_adr() -> tuple[float, float]:
    """取得台積電 ADR 最新價格及相較前收盤的價差。"""
    payload = request_json(YAHOO_CHART_API, params={"range": "5d", "interval": "1d"})
    chart = payload.get("chart", {})
    results = chart.get("result") or []
    if not results:
        raise ValueError(f"Yahoo Finance沒有TSM報價：{chart.get('error')}")

    result = results[0]
    meta = result.get("meta", {})
    price = meta.get("regularMarketPrice")
    previous = meta.get("chartPreviousClose") or meta.get("previousClose")

    if price is None or previous is None:
        quote = (result.get("indicators", {}).get("quote") or [{}])[0]
        closes = [v for v in quote.get("close", []) if v is not None]
        if len(closes) >= 2:
            price = closes[-1]
            previous = closes[-2]

    if price is None or previous is None or float(price) <= 0 or float(previous) <= 0:
        raise ValueError("Yahoo Finance TSM報價缺少最新價或前收盤價")

    return round(float(price), 2), round(float(price) - float(previous), 2)


def load_history() -> list[dict]:
    if not DATA_FILE.exists():
        return []
    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            history = json.load(file)
    except json.JSONDecodeError as exc:
        # 不要因為 JSON 壞掉就把舊歷史資料清空。
        raise ValueError(f"{DATA_FILE.name} 不是有效JSON，為避免覆蓋歷史資料，停止更新") from exc
    if not isinstance(history, list):
        raise ValueError("data.json 格式錯誤：最外層必須是陣列 []")
    return history


def save_history(history: list[dict]) -> None:
    temp_file = DATA_FILE.with_suffix(".json.tmp")
    with temp_file.open("w", encoding="utf-8") as file:
        json.dump(history, file, ensure_ascii=False, indent=2)
    temp_file.replace(DATA_FILE)


def get_stock_data() -> None:
    now_tw = datetime.now(TW_TZ)
    print(f"開始更新台股盤後資料：{now_tw:%Y-%m-%d %H:%M:%S} (台灣時間)")

    # 先取得實際最新交易日，再用該日期查詢證交所日報。
    trading_date, index_value, volume = get_twse_index_and_volume()
    print(f"1. 大盤量價：日期={trading_date}，指數={index_value}，成交金額={volume} 億")

    foreign, trust, dealer = get_twse_institutional_amounts(trading_date)
    print(f"2. 三大法人現貨：外資={foreign} 億，投信={trust} 億，自營商={dealer} 億")

    margin = get_twse_margin(trading_date)
    print(f"3. 融資餘額：{margin} 億")

    usd = get_usd_twd()
    print(f"4. 美元兌台幣：{usd}")

    f_oi, mtx_retail, tmf_retail = get_taifex_futures_positions()
    print(f"5. 期貨籌碼：外資台指期淨未平倉={f_oi} 口，小台推估={mtx_retail}%，微台推估={tmf_retail}%")

    top5, top10 = get_taifex_top_traders()
    print(f"6. 五大/十大淨額：{top5} 口 / {top10} 口")

    pc_ratio = get_taifex_pc_ratio()
    print(f"7. P/C未平倉比：{pc_ratio}%")

    f_opt = get_taifex_foreign_options_value()
    print(f"8. 外資選擇權淨值差：{f_opt} 萬元")

    tsm_adr, tsm_chg = get_tsm_adr()
    print(f"9. 台積電ADR：{tsm_adr} 美元，漲跌={tsm_chg} 美元")

    record = {
        "date": trading_date,
        "update_time": now_tw.strftime("%Y-%m-%d %H:%M"),
        "index": index_value,
        "vol": volume,
        "margin": margin,
        "usd": usd,
        "foreign": foreign,
        "trust": trust,
        "dealer": dealer,
        "f_oi": f_oi,
        "top5": top5,
        "top10": top10,
        "pc_ratio": pc_ratio,
        "f_opt": f_opt,
        "mtx_retail": mtx_retail,
        "tmf_retail": tmf_retail,
        "tsm_adr": tsm_adr,
        "tsm_chg": tsm_chg,
    }

    history = load_history()
    history = [item for item in history if item.get("date") != trading_date]
    history.insert(0, record)
    save_history(history)
    print(f"✅ 更新完成：{trading_date}；共保存 {len(history)} 筆資料至 {DATA_FILE}")


if __name__ == "__main__":
    try:
        get_stock_data()
    except Exception as exc:
        print(f"❌ 更新失敗，未覆蓋 data.json：{exc}", file=sys.stderr)
        raise
