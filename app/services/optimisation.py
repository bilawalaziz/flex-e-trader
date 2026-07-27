"""
Battery dispatch optimisation engine.

Mathematical formulation (Linear Programming):
------------------------------------------------
We want to maximise profit over a horizon T (e.g., 96 15‑min intervals = 24h).

Decision variables (for each time step t):
  - charge[t]     : power used for charging (≥0)
  - discharge[t]  : power sent to grid (≥0)
  - soc[t]        : state of charge (kWh), bounded [SOC_min, SOC_max]

Parameters:
  - price_buy[t], price_sell[t]  (EUR/MWh)
  - max_charge, max_discharge     (MW)
  - charge_efficiency (n_ch), discharge_efficiency (n_dis)
  - initial_soc (kWh)
  - time_step Δt (hours, e.g., 0.25)

Objective:
  Maximise Σ_t (discharge[t] * price_sell[t] - charge[t] * price_buy[t]) * Δt

Subject to (for all t):
  soc[t] = soc[t-1] + (charge[t] * n_ch - discharge[t] / n_dis) * Δt
  SOC_min ≤ soc[t] ≤ SOC_max
  0 ≤ charge[t] ≤ max_charge
  0 ≤ discharge[t] ≤ max_discharge
  charge[t] * discharge[t] == 0   (cannot charge & discharge simultaneously, handled with binary or SOS1)
  soc[0] = initial_soc

For a single battery with perfect foresight, this is a standard LP (the exclusivity constraint can be relaxed or approximated for simplicity).
We will use scipy.optimize.linprog with the simplex method.

The function will:
  1. Fetch price forecasts as pandas DataFrame.
  2. Construct the constraint matrix and objective coefficients.
  3. Solve and return a schedule DataFrame with timestamp, power (negative for charge, positive for discharge), soc.
"""

import numpy as np
import pandas as pd
from scipy.optimize import linprog


def compute_battery_schedule(
    prices: pd.DataFrame,
    battery_spec: dict,
    delta_t: float = 0.25,  # hours (15 minutes)
) -> pd.DataFrame:
    """
    Compute optimal charge/discharge schedule for a single battery.

    Args:
        prices: DataFrame with columns ['timestamp', 'buy_price', 'sell_price'].
                Must be sorted by timestamp, one row per interval.
        battery_spec: dict with keys:
            max_charge_mw, max_discharge_mw,
            capacity_kwh, charge_eff, discharge_eff,
            min_soc (fraction 0..1), max_soc (fraction 0..1),
            initial_soc_kwh (optional, default 0.5*capacity).
        delta_t: length of each interval in hours (default 0.25 for 15 min).

    Returns:
        DataFrame with columns ['timestamp', 'power_mw', 'soc_kwh'].
        power_mw positive = discharge (export), negative = charge (import).
    """
    n = len(prices)
    if n == 0:
        empty = pd.DataFrame(columns=["timestamp", "power_mw", "soc_kwh"])
        empty.attrs["diagnostics"] = _diagnostics("no_prices", 0, 0, 0.0, 0.0)
        return empty

    # Battery parameters
    max_ch = battery_spec["max_charge_mw"]  # MW
    max_dis = battery_spec["max_discharge_mw"]  # MW
    cap_mwh = battery_spec["capacity_kwh"] / 1000.0  # MWh
    eta_ch = battery_spec["charge_eff"]
    eta_dis = battery_spec["discharge_eff"]
    soc_min = battery_spec["min_soc"] * cap_mwh  # MWh
    soc_max = battery_spec["max_soc"] * cap_mwh  # MWh
    initial_soc_kwh = battery_spec.get(
        "initial_soc_kwh", 0.5 * battery_spec["capacity_kwh"]
    )
    soc0 = initial_soc_kwh / 1000.0

    buy = prices["buy_price"].values
    sell = prices["sell_price"].values

    # Decision vector: [charge[0..n-1], discharge[0..n-1], soc[1..n]]
    c = np.zeros(3 * n)
    c[n : 2 * n] = -sell * delta_t
    c[0:n] = buy * delta_t  # charge cost, positive coefficient in min
    # Profit = sum over t of (discharge[t] * sell[t] - charge[t] * buy[t]) * delta_t

    # Constraints
    A_ub = []
    b_ub = []
    A_eq = []
    b_eq = []

    # 1. charge[t] <= max_ch
    for t in range(n):
        row = np.zeros(3 * n)
        row[t] = 1
        A_ub.append(row)
        b_ub.append(max_ch)

    # 2. discharge[t] <= max_dis
    for t in range(n):
        row = np.zeros(3 * n)
        row[n + t] = 1
        A_ub.append(row)
        b_ub.append(max_dis)

    # 3. soc[t] >= soc_min  →  -soc[t] <= -soc_min
    for t in range(n):
        row = np.zeros(3 * n)
        row[2 * n + t] = -1
        A_ub.append(row)
        b_ub.append(-soc_min)

    # 4. soc[t] <= soc_max
    for t in range(n):
        row = np.zeros(3 * n)
        row[2 * n + t] = 1
        A_ub.append(row)
        b_ub.append(soc_max)

    # 5. Equality: soc[t] = soc[t-1] + (charge[t]*eta_ch - discharge[t]/eta_dis)*delta_t
    # soc[0] is fixed initial, soc[1] is variable index 2n+0.
    # t=0: soc[1] - soc0 - (charge[0]*eta_ch - discharge[0]/eta_dis)*delta_t = 0
    for t in range(n):
        row = np.zeros(3 * n)
        if t == 0:
            row[2 * n + t] = 1
            row[t] = -eta_ch * delta_t  # charge[0]
            row[n + t] = (1.0 / eta_dis) * delta_t  # discharge[0] (note sign)
            b_eq.append(soc0)
        else:
            row[2 * n + t] = 1
            row[2 * n + t - 1] = -1
            row[t] = -eta_ch * delta_t
            row[n + t] = (1.0 / eta_dis) * delta_t
            b_eq.append(0)
        A_eq.append(row)

    # Bounds
    bounds = [(0, None)] * (3 * n)  # all variables ≥ 0

    # Solve
    result = linprog(
        c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs"
    )

    if not result.success:
        # Fallback: return all zeros
        power = np.zeros(n)
        soc = np.full(n, soc0)
        diagnostics = _diagnostics(_solver_status(result), n, 0, 0.0, 0.0)
    else:
        charge = result.x[0:n]
        discharge = result.x[n : 2 * n]
        soc = result.x[2 * n : 3 * n]

        # Profit the LP believes it achieved, before the repair below. The
        # objective is stated as a minimisation of negative profit.
        lp_profit = -float(result.fun)

        # Enforce mutual exclusivity: if both > 0, set the smaller to 0.
        # The LP is solved without this constraint because it is not linear;
        # repairing after the fact keeps the solve fast but means the result
        # is no longer provably optimal whenever this loop fires. Count it, so
        # "how often is that" has an answer instead of an opinion.
        repaired = 0
        for t in range(n):
            if charge[t] > 1e-6 and discharge[t] > 1e-6:
                repaired += 1
                if charge[t] < discharge[t]:
                    charge[t] = 0
                else:
                    discharge[t] = 0

        realised_profit = float(np.sum((discharge * sell - charge * buy) * delta_t))
        diagnostics = _diagnostics(
            _solver_status(result), n, repaired, lp_profit, realised_profit
        )

        # Recalculate SOC from the corrected flows
        soc_calc = np.zeros(n)
        prev = soc0
        for t in range(n):
            flow = charge[t] * eta_ch - discharge[t] / eta_dis
            soc_calc[t] = prev + flow * delta_t
            prev = soc_calc[t]
        # Clip to bounds
        soc = np.clip(soc_calc, soc_min, soc_max)
        power = discharge - charge  # positive = export

    schedule = pd.DataFrame(
        {
            "timestamp": prices["timestamp"],
            "power_mw": power,
            "soc_kwh": soc,
        }
    )
    schedule.attrs["diagnostics"] = diagnostics
    return schedule


# scipy reports the outcome as an integer; the string is what a metric label
# and a log line both want.
_SOLVER_STATUS = {
    0: "optimal",
    1: "iteration_limit",
    2: "infeasible",
    3: "unbounded",
    4: "numerical_failure",
}


def _solver_status(result) -> str:
    return _SOLVER_STATUS.get(getattr(result, "status", -1), "unknown")


def _diagnostics(
    solver_status: str,
    intervals: int,
    repaired_intervals: int,
    lp_profit_eur: float,
    realised_profit_eur: float,
) -> dict:
    """What the caller needs to know about a solve it did not watch.

    Returned on the DataFrame rather than emitted here so this module stays a
    pure function of prices and battery spec, with no metrics or logging
    dependency of its own.
    """
    return {
        "solver_status": solver_status,
        "intervals": intervals,
        "repaired_intervals": repaired_intervals,
        "lp_profit_eur": lp_profit_eur,
        "realised_profit_eur": realised_profit_eur,
    }
