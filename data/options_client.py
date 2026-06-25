from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from loguru import logger

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None


def _safe_float(value, default=None):
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _safe_sum(df: pd.DataFrame, col: str) -> float:
    if df is None or df.empty or col not in df.columns:
        return 0.0
    return float(pd.to_numeric(df[col], errors='coerce').fillna(0).sum())


def _base_metrics(
    ticker: str,
    *,
    available: bool,
    source: str,
    error: str = "",
    notes: str = "",
    warning: str = "",
) -> dict:
    message = warning or notes or error
    return {
        'ticker': ticker,
        'options_data_available': bool(available),
        'options_available': bool(available),
        'options_source': source,
        'options_error': error,
        'options_warning': message,
        'options_notes': notes or message,
    }


def _load_cache(ticker: str, ttl_minutes: int) -> dict | None:
    path = Path('cache/options') / f'{ticker}.json'
    if not path.exists():
        return None
    try:
        age_minutes = (datetime.now(timezone.utc).timestamp() - path.stat().st_mtime) / 60
        if age_minutes > ttl_minutes:
            return None
        with path.open('r', encoding='utf-8') as f:
            cached = json.load(f)
        cached['options_source'] = 'cache'
        cached.setdefault('options_available', bool(cached.get('options_data_available', False)))
        cached.setdefault('options_error', '')
        cached.setdefault('options_notes', cached.get('options_warning', ''))
        return cached
    except Exception:
        return None


def _save_cache(ticker: str, data: dict) -> None:
    path = Path('cache/options')
    path.mkdir(parents=True, exist_ok=True)
    with (path / f'{ticker}.json').open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def _normalize_chain(df: pd.DataFrame, expiration: str, spot: float) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    out['expiration'] = expiration
    out['strike'] = pd.to_numeric(out.get('strike'), errors='coerce')
    out['volume'] = pd.to_numeric(out.get('volume'), errors='coerce').fillna(0)
    out['openInterest'] = pd.to_numeric(out.get('openInterest'), errors='coerce').fillna(0)
    out['impliedVolatility'] = pd.to_numeric(out.get('impliedVolatility'), errors='coerce')
    out['bid'] = pd.to_numeric(out.get('bid'), errors='coerce')
    out['ask'] = pd.to_numeric(out.get('ask'), errors='coerce')
    out['lastPrice'] = pd.to_numeric(out.get('lastPrice'), errors='coerce')
    out['moneyness'] = (out['strike'] - spot) / spot if spot else None
    return out


def _select_expirations(expirations: tuple[str, ...] | list[str], config: dict) -> list[str]:
    cfg = config.get('options_flow', {})
    min_days = cfg.get('min_days_to_expiration', 3)
    max_days = cfg.get('max_days_to_expiration', 45)
    max_expirations = cfg.get('max_expirations', 3)
    now = datetime.now(timezone.utc).date()
    selected = []
    for exp in expirations or []:
        try:
            exp_date = pd.to_datetime(exp).date()
            dte = (exp_date - now).days
            if min_days <= dte <= max_days:
                selected.append((exp, dte))
        except Exception:
            continue
    return [x[0] for x in sorted(selected, key=lambda x: x[1])[:max_expirations]]


def _approx_max_pain(calls: pd.DataFrame, puts: pd.DataFrame) -> float | None:
    if calls.empty and puts.empty:
        return None
    strikes = sorted(set(calls.get('strike', pd.Series(dtype=float)).dropna().tolist()) |
                     set(puts.get('strike', pd.Series(dtype=float)).dropna().tolist()))
    if not strikes:
        return None
    call_data = calls[['strike', 'openInterest']].dropna() if not calls.empty else pd.DataFrame(columns=['strike', 'openInterest'])
    put_data = puts[['strike', 'openInterest']].dropna() if not puts.empty else pd.DataFrame(columns=['strike', 'openInterest'])
    best_strike = None
    best_payout = None
    for s in strikes:
        call_payout = ((s - call_data['strike']).clip(lower=0) * call_data['openInterest']).sum()
        put_payout = ((put_data['strike'] - s).clip(lower=0) * put_data['openInterest']).sum()
        payout = float(call_payout + put_payout)
        if best_payout is None or payout < best_payout:
            best_payout = payout
            best_strike = s
    return float(best_strike) if best_strike is not None else None


def fetch_options_metrics(ticker: str, spot: float, config: dict) -> dict:
    cfg = config.get('options_flow', {})
    if not cfg.get('enabled', False):
        return _base_metrics(
            ticker,
            available=False,
            source='disabled',
            error='options_flow_disabled',
            notes='options_flow desactivado; se informa como UNKNOWN_OPTIONS_FLOW',
        )

    ttl = config.get('data_sources', {}).get('cache_ttl_minutes', {}).get('options', cfg.get('cache_ttl_minutes', 30))
    cached = _load_cache(ticker, ttl)
    if cached is not None:
        return cached

    if yf is None:
        return _base_metrics(
            ticker,
            available=False,
            source='yfinance',
            error='yfinance_unavailable',
            notes='yfinance no disponible para consultar opciones',
        )

    warnings = []
    try:
        tk = yf.Ticker(ticker)
        raw_expirations = list(getattr(tk, 'options', []) or [])
        if not raw_expirations:
            data = _base_metrics(
                ticker,
                available=False,
                source='yfinance',
                error='no_options_listed',
                notes='Yahoo no devolvió vencimientos de opciones; posible activo sin opciones listadas',
            )
            _save_cache(ticker, data)
            return data

        selected_exps = _select_expirations(raw_expirations, config)
        if not selected_exps:
            data = _base_metrics(
                ticker,
                available=False,
                source='yfinance',
                error='no_expiration_in_config_window',
                notes='sin vencimientos dentro de la ventana configurada',
            )
            _save_cache(ticker, data)
            return data

        calls_list, puts_list = [], []
        for exp in selected_exps:
            try:
                chain = tk.option_chain(exp)
                calls_list.append(_normalize_chain(chain.calls, exp, spot))
                puts_list.append(_normalize_chain(chain.puts, exp, spot))
            except Exception as exc:
                warnings.append(f'falló option_chain {exp}: {exc}')

        calls = pd.concat(calls_list, ignore_index=True) if calls_list else pd.DataFrame()
        puts = pd.concat(puts_list, ignore_index=True) if puts_list else pd.DataFrame()
        if calls.empty and puts.empty:
            data = _base_metrics(
                ticker,
                available=False,
                source='yfinance',
                error='empty_option_chain',
                notes='option_chain vacío; ' + '; '.join(warnings),
            )
            data['options_expirations_used'] = ','.join(selected_exps)
            data['options_expiration_used'] = selected_exps[0] if selected_exps else ''
            _save_cache(ticker, data)
            return data

        near_pct = cfg.get('near_moneyness_pct', 0.08)
        near_calls = calls[(calls['strike'] >= spot) & (calls['strike'] <= spot * (1 + near_pct))] if not calls.empty else pd.DataFrame()
        near_puts = puts[(puts['strike'] <= spot) & (puts['strike'] >= spot * (1 - near_pct))] if not puts.empty else pd.DataFrame()

        total_call_volume = _safe_sum(calls, 'volume')
        total_put_volume = _safe_sum(puts, 'volume')
        total_call_oi = _safe_sum(calls, 'openInterest')
        total_put_oi = _safe_sum(puts, 'openInterest')
        near_call_volume = _safe_sum(near_calls, 'volume')
        near_put_volume = _safe_sum(near_puts, 'volume')
        near_call_oi = _safe_sum(near_calls, 'openInterest')
        near_put_oi = _safe_sum(near_puts, 'openInterest')

        max_call_oi_strike = max_put_oi_strike = max_call_oi = max_put_oi = None
        if not calls.empty and calls['openInterest'].fillna(0).sum() > 0:
            idx = calls['openInterest'].idxmax()
            max_call_oi_strike = _safe_float(calls.loc[idx, 'strike'])
            max_call_oi = _safe_float(calls.loc[idx, 'openInterest'])
        if not puts.empty and puts['openInterest'].fillna(0).sum() > 0:
            idx = puts['openInterest'].idxmax()
            max_put_oi_strike = _safe_float(puts.loc[idx, 'strike'])
            max_put_oi = _safe_float(puts.loc[idx, 'openInterest'])

        atm_ivs = []
        if not calls.empty:
            idx = (calls['strike'] - spot).abs().idxmin()
            atm_ivs.append(_safe_float(calls.loc[idx, 'impliedVolatility']))
        if not puts.empty:
            idx = (puts['strike'] - spot).abs().idxmin()
            atm_ivs.append(_safe_float(puts.loc[idx, 'impliedVolatility']))
        atm_ivs = [x for x in atm_ivs if x is not None]
        atm_iv = sum(atm_ivs) / len(atm_ivs) if atm_ivs else None

        total_option_volume = total_call_volume + total_put_volume
        total_option_oi = total_call_oi + total_put_oi
        data = {
            'ticker': ticker,
            'options_data_available': True,
            'options_available': True,
            'options_source': 'yfinance',
            'options_expirations_used': ','.join(selected_exps),
            'options_expiration_used': selected_exps[0] if selected_exps else '',
            'options_expiration_count': len(selected_exps),
            'call_volume': total_call_volume,
            'put_volume': total_put_volume,
            'call_open_interest': total_call_oi,
            'put_open_interest': total_put_oi,
            'options_total_call_oi': total_call_oi,
            'options_total_put_oi': total_put_oi,
            'put_call_volume_ratio': total_put_volume / total_call_volume if total_call_volume > 0 else None,
            'put_call_oi_ratio': total_put_oi / total_call_oi if total_call_oi > 0 else None,
            'options_put_call_oi_ratio': total_put_oi / total_call_oi if total_call_oi > 0 else None,
            'call_volume_share': total_call_volume / total_option_volume if total_option_volume > 0 else None,
            'call_oi_share': total_call_oi / total_option_oi if total_option_oi > 0 else None,
            'near_call_volume': near_call_volume,
            'near_put_volume': near_put_volume,
            'near_call_open_interest': near_call_oi,
            'near_put_open_interest': near_put_oi,
            'options_near_price_call_oi': near_call_oi,
            'options_near_price_put_oi': near_put_oi,
            'near_put_call_volume_ratio': near_put_volume / near_call_volume if near_call_volume > 0 else None,
            'near_put_call_oi_ratio': near_put_oi / near_call_oi if near_call_oi > 0 else None,
            'options_near_price_put_call_ratio': near_put_oi / near_call_oi if near_call_oi > 0 else None,
            'near_call_oi_share': near_call_oi / (near_call_oi + near_put_oi) if (near_call_oi + near_put_oi) > 0 else None,
            'max_call_oi_strike': max_call_oi_strike,
            'options_top_call_strike': max_call_oi_strike,
            'max_call_oi': max_call_oi,
            'max_put_oi_strike': max_put_oi_strike,
            'options_top_put_strike': max_put_oi_strike,
            'max_put_oi': max_put_oi,
            'max_pain_approx': _approx_max_pain(calls, puts),
            'atm_implied_volatility': atm_iv,
            'call_volume_to_oi': total_call_volume / total_call_oi if total_call_oi > 0 else None,
            'put_volume_to_oi': total_put_volume / total_put_oi if total_put_oi > 0 else None,
            'total_option_volume': total_option_volume,
            'total_option_open_interest': total_option_oi,
            'options_error': '',
            'options_warning': '; '.join(warnings),
            'options_notes': '; '.join(warnings),
        }
        _save_cache(ticker, data)
        return data
    except Exception as exc:
        logger.warning(f'Opciones fallaron para {ticker}: {exc}')
        return _base_metrics(
            ticker,
            available=False,
            source='yfinance',
            error='query_error',
            notes=str(exc),
        )
