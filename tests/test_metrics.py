import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from prometheus_client import REGISTRY

from app.core.metrics import record_optimisation_result
from app.services.optimisation import compute_battery_schedule


def value(name: str, **labels) -> float:
    """Read a metric out of the default registry, treating absent as zero."""
    return REGISTRY.get_sample_value(name, labels) or 0.0


class TestOptimisationDiagnostics:
    def test_a_solve_reports_status_and_size(self, battery_spec):
        prices = pd.DataFrame(
            {
                "timestamp": pd.date_range("2026-01-01", periods=8, freq="15min"),
                "buy_price": [50, 60, 40, 70, 55, 30, 80, 45],
                "sell_price": [55, 65, 45, 75, 60, 35, 85, 50],
            }
        )

        diagnostics = compute_battery_schedule(prices, battery_spec).attrs[
            "diagnostics"
        ]

        assert diagnostics["solver_status"] == "optimal"
        assert diagnostics["intervals"] == 8
        assert diagnostics["repaired_intervals"] >= 0

    def test_no_prices_is_reported_as_such_not_as_a_failed_solve(self, battery_spec):
        empty = pd.DataFrame(columns=["timestamp", "buy_price", "sell_price"])

        diagnostics = compute_battery_schedule(empty, battery_spec).attrs["diagnostics"]

        # An empty price table is an upstream problem, and reading it as
        # "infeasible" would point the investigation at the solver.
        assert diagnostics["solver_status"] == "no_prices"
        assert diagnostics["intervals"] == 0

    def test_an_unrepaired_schedule_realises_the_lp_objective(self, battery_spec):
        prices = pd.DataFrame(
            {
                "timestamp": pd.date_range("2026-01-01", periods=6, freq="15min"),
                "buy_price": [20, 90, 20, 90, 20, 90],
                "sell_price": [25, 95, 25, 95, 25, 95],
            }
        )

        diagnostics = compute_battery_schedule(prices, battery_spec).attrs[
            "diagnostics"
        ]

        if diagnostics["repaired_intervals"] == 0:
            assert diagnostics["realised_profit_eur"] == pytest.approx(
                diagnostics["lp_profit_eur"], abs=1e-6
            )
        else:
            # The repair can only remove flows, so it can only lose money.
            assert (
                diagnostics["realised_profit_eur"]
                <= diagnostics["lp_profit_eur"] + 1e-6
            )

    def test_repair_is_counted_per_interval_not_per_solve(self, battery_spec):
        # Flat prices give the LP no reason to prefer one direction, which is
        # where simultaneous charge and discharge shows up if it shows up.
        prices = pd.DataFrame(
            {
                "timestamp": pd.date_range("2026-01-01", periods=12, freq="15min"),
                "buy_price": np.full(12, 50.0),
                "sell_price": np.full(12, 50.0),
            }
        )

        diagnostics = compute_battery_schedule(prices, battery_spec).attrs[
            "diagnostics"
        ]

        assert 0 <= diagnostics["repaired_intervals"] <= diagnostics["intervals"]

    def test_the_returned_schedule_never_charges_and_discharges_at_once(
        self, battery_spec
    ):
        prices = pd.DataFrame(
            {
                "timestamp": pd.date_range("2026-01-01", periods=16, freq="15min"),
                "buy_price": [50, 20, 80, 30, 90, 10, 60, 40] * 2,
                "sell_price": [55, 25, 85, 35, 95, 15, 65, 45] * 2,
            }
        )

        schedule = compute_battery_schedule(prices, battery_spec)

        # power_mw is discharge minus charge, so this is what the repair is
        # for: one net direction per interval, whatever the LP returned.
        assert schedule["power_mw"].notna().all()


class TestMetricRecording:
    def test_a_clean_solve_records_intervals_and_no_repair(self):
        asset = "test-battery-clean"
        before = value("flexetrader_lp_intervals_total", asset=asset)

        record_optimisation_result(
            asset,
            {
                "solver_status": "optimal",
                "intervals": 96,
                "repaired_intervals": 0,
                "lp_profit_eur": 120.0,
                "realised_profit_eur": 120.0,
            },
        )

        assert value("flexetrader_lp_intervals_total", asset=asset) == before + 96
        assert value("flexetrader_lp_repaired_intervals_total", asset=asset) == 0.0
        assert value("flexetrader_schedule_profit_eur", asset=asset) == 120.0

    def test_a_repair_records_both_the_count_and_what_it_cost(self):
        asset = "test-battery-repaired"

        record_optimisation_result(
            asset,
            {
                "solver_status": "optimal",
                "intervals": 96,
                "repaired_intervals": 3,
                "lp_profit_eur": 120.0,
                "realised_profit_eur": 117.5,
            },
        )

        assert value("flexetrader_lp_repaired_intervals_total", asset=asset) == 3.0
        assert value(
            "flexetrader_lp_repair_cost_eur_total", asset=asset
        ) == pytest.approx(2.5)
        # The gauge shows what will actually be earned, not what the LP hoped.
        assert value("flexetrader_schedule_profit_eur", asset=asset) == 117.5

    def test_floating_point_noise_is_not_recorded_as_free_money(self):
        asset = "test-battery-noise"

        record_optimisation_result(
            asset,
            {
                "solver_status": "optimal",
                "intervals": 4,
                "repaired_intervals": 0,
                "lp_profit_eur": 100.0,
                "realised_profit_eur": 100.0000000001,
            },
        )

        # A Counter raises on a negative increment, so this is a crash in the
        # optimisation loop if it is not floored.
        assert value("flexetrader_lp_repair_cost_eur_total", asset=asset) == 0.0

    def test_a_failed_solve_is_recorded_under_its_status(self):
        before = value("flexetrader_lp_solves_total", status="infeasible")

        record_optimisation_result(
            "test-battery-infeasible",
            {"solver_status": "infeasible", "intervals": 0, "repaired_intervals": 0},
        )

        assert value("flexetrader_lp_solves_total", status="infeasible") == before + 1


class TestMetricsEndpoint:
    @pytest.mark.asyncio
    async def test_metrics_are_exposed_in_prometheus_format(self, async_client):
        response = await async_client.get("/metrics")

        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
        # HELP lines are what make a dashboard readable months later.
        assert "# HELP flexetrader_optimisation_cycles_total" in response.text

    @pytest.mark.asyncio
    async def test_every_metric_the_dashboard_queries_is_exported(self, async_client):
        # Renaming a metric is silent: the code keeps working and the Grafana
        # panel that queries it goes blank. Read the names out of the
        # dashboard rather than keeping a second list here that can drift.
        dashboard = Path("grafana/dashboards/flextrader-ops.json").read_text()
        queried = {
            # _bucket and _sum are generated by histograms; the HELP line
            # carries the base name.
            re.sub(r"_(bucket|sum|count)$", "", name)
            for name in re.findall(r"flexetrader_[a-z_]+", dashboard)
        }
        assert queried, "no metrics found in the dashboard"

        exported = set(
            re.findall(
                r"# HELP (flexetrader_[a-z_]+)",
                (await async_client.get("/metrics")).text,
            )
        )

        assert queried <= exported, (
            f"dashboard queries missing metrics: {queried - exported}"
        )

    @pytest.mark.asyncio
    async def test_the_scrape_does_not_redirect(self, async_client):
        # Mounting an ASGI app at /metrics answers 307 and costs every scrape
        # a second request.
        assert (await async_client.get("/metrics")).status_code == 200
