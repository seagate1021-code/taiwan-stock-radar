
from pathlib import Path
import yaml


CONFIG_PATH = Path(__file__).parent / "config" / "strategy.yaml"


def load_config():
    """讀取台股選股參數"""
    with open(CONFIG_PATH, "r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    if not isinstance(config, dict):
        raise ValueError("設定檔格式錯誤")

    return config


def validate_config(config):
    """檢查重要參數"""
    assert config["history"]["min_history_days"] >= 70
    assert config["basic"]["min_price"] > 0
    assert config["basic"]["min_avg_trade_value_20"] > 0
    assert config["selection"]["min_picks"] <= config["selection"]["max_picks"]


def main():
    print("=" * 50)
    print("Taiwan Stock Radar V1")
    print("台股自動選股系統")
    print("=" * 50)

    config = load_config()
    validate_config(config)

    print("\n選股參數載入成功！")

    print("\n基本篩選條件")
    print("歷史天數：", config["history"]["min_history_days"])
    print("最低股價：", config["basic"]["min_price"])
    print("最低成交值：", config["basic"]["min_avg_trade_value_20"])

    print("\n強勢股 FIRE")
    print("最低確認數：", config["fire"]["min_confirmations"])
    print("最低量比：", config["fire"]["min_volume_ratio"])

    print("\n拉回股 PULLBACK")
    print("RSI 下限：", config["pullback"]["rsi_min"])
    print("RSI 上限：", config["pullback"]["rsi_max"])

    print("\nTDCC 大戶趨勢")
    print("追蹤期數：", config["tdcc"]["target_period_count"])

    print("\n最終精選")
    print(
        config["selection"]["min_picks"],
        "至",
        config["selection"]["max_picks"],
        "檔"
    )

    print("\n系統初始化成功！")
    print("下一階段：串接台股行情與技術指標")


if __name__ == "__main__":
    main()
