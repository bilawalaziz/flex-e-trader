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
  - charge_efficiency (η_ch), discharge_efficiency (η_dis)
  - initial_soc (kWh)
  - time_step Δt (hours, e.g., 0.25)

Objective:
  Maximise Σ_t (discharge[t] * price_sell[t] - charge[t] * price_buy[t]) * Δt

Subject to (for all t):
  soc[t] = soc[t-1] + (charge[t] * η_ch - discharge[t] / η_dis) * Δt
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


def compute_battery_schedule(prices, battery_spec):
    """
    Args:
        prices (pd.DataFrame): columns ['timestamp', 'buy_price', 'sell_price']
        battery_spec (dict): {max_charge, max_discharge, soc_min, soc_max, charge_eff, discharge_eff, initial_soc}
    Returns:
        pd.DataFrame with columns ['timestamp', 'power_mw', 'soc_kwh']
    """
    # this is just will do it later,
    # for now just holding sample algo flow built with help of ai agent,
    # after other basic thing
    raise NotImplementedError("Optimisation engine not yet implemented.")
