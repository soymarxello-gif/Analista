\
from setups.breakout import detect_breakout
from setups.pullback import detect_pullback
from setups.reclaim import detect_reclaim
from setups.volatility_contraction import detect_volatility_contraction

def score_structure(df, config):
    b = detect_breakout(df, config)
    p = detect_pullback(df, config)
    r = detect_reclaim(df, config)
    v = detect_volatility_contraction(df, config)

    if b.get("is_breakout"):
        return {"structure_score": 1.0, "setup_type": "BREAKOUT", "trigger_confirmed": True, "trigger_level": b.get("breakout_level")}
    if p.get("is_pullback"):
        return {"structure_score": 0.82, "setup_type": "PULLBACK", "trigger_confirmed": True, "trigger_level": p.get("pullback_level")}
    if r.get("is_reclaim"):
        return {"structure_score": 0.78, "setup_type": "RECLAIM", "trigger_confirmed": True, "trigger_level": r.get("reclaim_level")}
    if v.get("is_vcp"):
        return {"structure_score": 0.70, "setup_type": "VOLATILITY_CONTRACTION", "trigger_confirmed": False, "trigger_level": None}
    return {"structure_score": 0.25, "setup_type": "NO_VALID_SETUP", "trigger_confirmed": False, "trigger_level": None}
