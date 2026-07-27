"""Prometheus instrumentation.

Three things in this system can go quietly wrong, and each has a metric here:

1. The optimiser can return a schedule that is not optimal. The LP is solved
   without the charge/discharge exclusivity constraint, and any interval that
   comes back with both flows non-zero is repaired afterwards by zeroing the
   smaller one. That repair is invisible from the outside — the schedule still
   looks like a schedule — so the repair count and the profit it costs are
   exported per asset.
2. Price ingestion can fail per message, and the retry/DLQ path means a broken
   producer shows up as a slow leak into the dead-letter queue rather than as
   an error.
3. The websocket fan-out can drop clients silently, because a failed send just
   disconnects them.

Metric and label naming follows the Prometheus conventions: base units
(seconds, euros), `_total` on counters, and labels with bounded cardinality —
asset names are bounded, product codes and message ids are not.
"""

import os
import shutil

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, multiprocess
from prometheus_client import REGISTRY as DEFAULT_REGISTRY

MULTIPROC_ENV = "PROMETHEUS_MULTIPROC_DIR"

# --- Optimisation ---------------------------------------------------------

optimisation_cycles_total = Counter(
    "flexetrader_optimisation_cycles_total",
    "Optimisation cycles by outcome.",
    ["outcome"],  # success | no_prices | failed
)

optimisation_duration_seconds = Histogram(
    "flexetrader_optimisation_duration_seconds",
    "Wall time of a full optimisation cycle, across all assets.",
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

lp_solves_total = Counter(
    "flexetrader_lp_solves_total",
    "LP solves by solver status.",
    ["status"],  # optimal | infeasible | unbounded | iteration_limit | ...
)

lp_intervals_total = Counter(
    "flexetrader_lp_intervals_total",
    "Intervals in solved schedules. Denominator for the repair rate.",
    ["asset"],
)

lp_repaired_intervals_total = Counter(
    "flexetrader_lp_repaired_intervals_total",
    "Intervals where the LP charged and discharged at once and was repaired. "
    "Non-zero means the schedule is no longer provably optimal.",
    ["asset"],
)

lp_repair_cost_eur_total = Counter(
    "flexetrader_lp_repair_cost_eur_total",
    "Profit given up by the repair: LP objective minus the repaired schedule's "
    "profit. This is the price of relaxing the exclusivity constraint.",
    ["asset"],
)

schedule_profit_eur = Gauge(
    "flexetrader_schedule_profit_eur",
    "Expected profit of the most recently published schedule.",
    ["asset"],
)

schedule_slots_written_total = Counter(
    "flexetrader_schedule_slots_written_total",
    "Schedule slots upserted.",
    ["asset"],
)

# --- Price ingestion ------------------------------------------------------

price_messages_total = Counter(
    "flexetrader_price_messages_total",
    "Price messages by terminal outcome.",
    # inserted | deduplicated | validation_error | malformed_json |
    # retry_queued | dead_lettered
    ["outcome"],
)

price_message_duration_seconds = Histogram(
    "flexetrader_price_message_duration_seconds",
    "Time to handle one price message, from receipt to ack.",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

dead_letter_events_total = Counter(
    "flexetrader_dead_letter_events_total",
    "Messages that reached the dead-letter handler.",
    ["reason"],
)

# --- Websocket fan-out ----------------------------------------------------

websocket_connections = Gauge(
    "flexetrader_websocket_connections",
    "Currently connected schedule websocket clients.",
    multiprocess_mode="livesum",
)

websocket_broadcasts_total = Counter(
    "flexetrader_websocket_broadcasts_total",
    "Websocket sends by outcome.",
    ["outcome"],  # sent | dropped
)


def record_optimisation_result(asset_name: str, diagnostics: dict) -> None:
    """Record one asset's solve from the diagnostics the optimiser returns.

    The optimiser stays a pure function of prices and battery spec; it reports
    what happened and this decides what is worth exporting. That keeps asset
    names — the label — out of the maths.
    """
    status = diagnostics.get("solver_status", "unknown")
    lp_solves_total.labels(status=status).inc()

    intervals = diagnostics.get("intervals", 0)
    if intervals:
        lp_intervals_total.labels(asset=asset_name).inc(intervals)

    repaired = diagnostics.get("repaired_intervals", 0)
    if repaired:
        lp_repaired_intervals_total.labels(asset=asset_name).inc(repaired)

    lp_profit = diagnostics.get("lp_profit_eur")
    realised = diagnostics.get("realised_profit_eur")
    if lp_profit is not None and realised is not None:
        schedule_profit_eur.labels(asset=asset_name).set(realised)
        # Floor at zero: floating-point noise should not read as the repair
        # having improved on the LP optimum, which it cannot do.
        lp_repair_cost_eur_total.labels(asset=asset_name).inc(
            max(lp_profit - realised, 0.0)
        )


def build_registry() -> CollectorRegistry:
    """Return the registry to serve /metrics from.

    Celery runs tasks in forked children, so a counter incremented while
    optimising is incremented in a process that no HTTP server lives in.
    With PROMETHEUS_MULTIPROC_DIR set, prometheus_client writes values to
    shared mmap files and this collector sums them across processes. Without
    it — the API, which is a single process — the default registry is correct
    and cheaper.
    """
    if os.environ.get(MULTIPROC_ENV):
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        return registry
    return DEFAULT_REGISTRY


def reset_multiproc_dir() -> None:
    """Clear stale mmap files before a worker starts.

    Files left by a previous run belong to pids that no longer exist, and
    their counters would be summed into this run's totals forever.
    """
    path = os.environ.get(MULTIPROC_ENV)
    if not path:
        return
    shutil.rmtree(path, ignore_errors=True)
    os.makedirs(path, exist_ok=True)
