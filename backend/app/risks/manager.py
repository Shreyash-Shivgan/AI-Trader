from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(slots=True)
class RiskMetrics:
    account_balance: float
    risk_percent: float
    risk_amount: float
    stop_loss_distance: float
    take_profit_distance: float
    lot_size: float
    position_size: float
    margin_requirement: float
    reward_amount: float
    rr_ratio: float

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["risk_amount"] = round(self.risk_amount, 2)
        payload["lot_size"] = round(self.lot_size, 4)
        payload["position_size"] = round(self.position_size, 4)
        payload["margin_requirement"] = round(self.margin_requirement, 2)
        payload["reward_amount"] = round(self.reward_amount, 2)
        payload["rr_ratio"] = round(self.rr_ratio, 2)
        return payload


class RiskManager:
    def __init__(
        self, pip_value_per_lot: float = 100000.0, leverage: float = 100.0
    ) -> None:
        self.pip_value_per_lot = pip_value_per_lot
        self.leverage = leverage

    def calculate(
        self,
        account_balance: float,
        risk_percent: float,
        stop_loss_distance: float,
        take_profit_distance: float,
        entry_price: float | None = None,
    ) -> RiskMetrics:
        risk_amount = account_balance * (risk_percent / 100.0)
        stop_loss_distance = max(stop_loss_distance, 1e-6)
        
        lot_size = risk_amount / (stop_loss_distance * self.pip_value_per_lot)
        
        # Fallback if computed lot size rounds to 0 (Task 7)
        if round(lot_size, 4) <= 0.0 and account_balance > 0:
            lot_size = risk_amount / stop_loss_distance
            lot_size = max(0.01, round(lot_size, 4))
            
        position_size = lot_size * 100000.0
        margin_requirement = (
            0.0
            if entry_price is None
            else (position_size * entry_price) / self.leverage
        )
        reward_amount = lot_size * take_profit_distance * self.pip_value_per_lot
        rr_ratio = (
            take_profit_distance / stop_loss_distance if stop_loss_distance else 0.0
        )
        return RiskMetrics(
            account_balance=account_balance,
            risk_percent=risk_percent,
            risk_amount=risk_amount,
            stop_loss_distance=stop_loss_distance,
            take_profit_distance=take_profit_distance,
            lot_size=lot_size,
            position_size=position_size,
            margin_requirement=margin_requirement,
            reward_amount=reward_amount,
            rr_ratio=rr_ratio,
        )
