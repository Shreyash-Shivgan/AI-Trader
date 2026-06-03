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
    grade: str,  # "A+", "A", "B", "C", "Speculative"
    atr: float,
    support: float,
    resistance: float,
) -> str:
    symbol_header = symbol.replace("/", "").replace("_", "")
    direction_str = direction.upper()
    
    current_price_str = format_price(current_price)
    
    if grade == "Speculative":
        support_str = format_price(support)
        resistance_str = format_price(resistance)
        expected_dir = "Bullish" if direction_str == "BUY" else "Bearish"
        
        message = [
            f"⚠️ {symbol_header}",
            "",
            f"Price: {current_price_str}",
            "",
            f"Buy Above: {resistance_str}",
            f"Sell Below: {support_str}",
            "",
            f"Expected: {expected_dir}",
            "",
            "Action: Wait"
        ]
    else:
        # Quality setup
        # Determine if market order (entry ≈ current_price)
        is_market = abs(entry_price - current_price) <= atr * 0.15
        
        # Order type header label
        if is_market:
            order_type = f"{direction_str} NOW"
            action_label = "Enter Now"
        else:
            if direction_str == "SELL":
                order_type = "SELL LIMIT"
            else:
                order_type = "BUY LIMIT"
            action_label = "Wait for Entry"
            
        entry_str = format_price(entry_price)
        stop_loss_str = format_price(stop_loss)
        tp1_str = format_price(tp1)
        tp2_str = format_price(tp2)
        tp3_str = format_price(tp3)
        
        rr_str = f"1:{rr:.1f}" if rr else "1:0.0"
        lot_size_str = "N/A" if lot_size <= 0 else f"{lot_size:.2f}"
        
        # Strength
        strength_label = "Strong" if grade in {"A+", "A"} else "Medium"
        
        if is_market:
            message = [
                f"🚨 {symbol_header} | {order_type}",
                "",
                f"Price: {current_price_str}",
                f"SL: {stop_loss_str}",
                "",
                f"TP1: {tp1_str}",
                f"TP2: {tp2_str}",
                f"TP3: {tp3_str}",
                "",
                f"RR: {rr_str} | Lot: {lot_size_str}",
                f"Strength: {strength_label}",
                "",
                f"Action: {action_label}"
            ]
        else:
            message = [
                f"🚨 {symbol_header} | {order_type}",
                "",
                f"Price: {current_price_str}",
                f"Entry: {entry_str}",
                f"SL: {stop_loss_str}",
                "",
                f"TP1: {tp1_str}",
                f"TP2: {tp2_str}",
                f"TP3: {tp3_str}",
                "",
                f"RR: {rr_str} | Lot: {lot_size_str}",
                f"Strength: {strength_label}",
                "",
                f"Action: {action_label}"
            ]
            
    return "\n".join(message)
