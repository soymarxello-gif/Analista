\
from .moving_averages import add_moving_averages
from .rsi import add_rsi
from .macd import add_macd
from .atr import add_atr
from .obv import add_obv
from .volume import add_volume_features

def add_all_indicators(df, config):
    out = add_moving_averages(df, config.get("indicators", {}).get("moving_averages", [20, 50, 200]))
    out = add_rsi(out, config.get("indicators", {}).get("rsi", {}).get("period", 14))
    macd_cfg = config.get("indicators", {}).get("macd", {})
    out = add_macd(out, macd_cfg.get("fast", 12), macd_cfg.get("slow", 26), macd_cfg.get("signal", 9))
    out = add_atr(out, config.get("indicators", {}).get("atr", {}).get("period", 14))
    out = add_obv(out, config.get("indicators", {}).get("obv", {}).get("slope_period", 20))
    out = add_volume_features(out, config.get("indicators", {}).get("volume", {}).get("avg_period", 20))
    return out
