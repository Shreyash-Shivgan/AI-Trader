from __future__ import annotations

import math
from typing import Any

def format_price(val: Any) -> str:
    try:
        f_val = float(val)
        if math.isnan(f_val) or math.isinf(f_val):
            return "XXXX"
        if f_val.is_integer():
            return f"{int(f_val)}"
        return f"{f_val:.2f}"
    except (ValueError, TypeError):
        return str(val) if val is not None else "XXXX"

def determine_reason(direction: str, entry_price: float, support: float, resistance: float, atr: float) -> str:
    direction_upper = direction.upper()
    if "BUY" in direction_upper or "BULL" in direction_upper:
        if abs(entry_price - support) <= atr * 1.5:
            return "Support bounce"
        else:
            return "Bullish breakout setup"
    else:
        if abs(entry_price - resistance) <= atr * 1.5:
            return "Sell resistance retest"
        else:
            return "Bearish breakout setup"

def generate_telegram_message(
    symbol: str,
    current_price: float,
    entry_price: float,
    direction: str,  # "BUY" or "SELL"
    stop_loss: float,
    tp1: float,
    tp2: float,
    tp3: float,
    rr: float,
    lot_size: float,
    grade: str,  # "A+", "A", "B", "C"
    atr: float,
    support: float,
    resistance: float,
    reason: str,
) -> str:
    symbol_header = symbol.replace("/", "").replace("_", "")
    direction_str = direction.upper()
    
    current_price_str = format_price(current_price)
    entry_str = format_price(entry_price)
    stop_loss_str = format_price(stop_loss)
    tp1_str = format_price(tp1)
    tp2_str = format_price(tp2)
    tp3_str = format_price(tp3)
    
    rr_str = f"1:{rr:.1f}" if rr else "1:0.0"
    lot_size_str = "N/A" if lot_size <= 0 else f"{lot_size:.2f}"
    
    is_market = abs(entry_price - current_price) <= atr * 0.15
    if is_market:
        if grade == "C":
            order_type = f"{direction_str} NOW"
        else:
            order_type = direction_str
        action_label = "ENTER NOW"
    else:
        if direction_str == "SELL":
            order_type = "SELL LIMIT"
        else:
            order_type = "BUY LIMIT"
        action_label = "WAIT FOR ENTRY"
        
    if grade == "C":
        action_label = "WAIT FOR CONFIRMATION"
        emoji = "🚨"
    else:
        emoji = "🚀"
        
    message = [
        f"{emoji} {symbol_header} | {order_type}",
        "",
        f"Price: {current_price_str}",
        "",
        f"Entry: {entry_str}",
        f"SL: {stop_loss_str}",
        "",
        f"TP1: {tp1_str}",
        f"TP2: {tp2_str}",
        f"TP3: {tp3_str}",
        "",
        f"RR: {rr_str}",
        f"Lot: {lot_size_str}",
        "",
        f"Grade: {grade}",
    ]
    
    if grade == "C":
        message.append("Risk: High")
        
    message.extend([
        "",
        "Action:",
        action_label,
        "",
        "Reason:",
        reason
    ])
    
    return "\n".join(message)
