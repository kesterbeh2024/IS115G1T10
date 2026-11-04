"""Calculate performance metrics from one simulation run's event log."""

import argparse
import csv
import json
from pathlib import Path
from turtle import distance
from typing import Any, Dict, List, Optional
import simulator
from simulator.loaders import day_input_paths
import sys
import json
print(sys.path)


def calculate_metrics(
    parcels: List[Dict[str, str]],
    distances: List[Dict[str, str]],
    config: Dict[str, Any],
    events: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Return a JSON-serializable dictionary for the chosen performance metric.

    parcels and distances are the rows of the day's CSV files, config is the
    contents of config.json, and events are the records from the run's log.
    CSV values are strings, so convert them before calculating. In particular,
    parcel times are "HH:MM" strings while event times are minutes after
    midnight: "17:00" is 17 * 60 = 1020.
    """

    # Illustration only: replace or extend this with your chosen metric.
    
    """ Calculates operational metrics and the Total Service & Operational Penalty (TSOP). Parameters: parcels (list): Row dicts from day demand CSV. distances (list): Row dicts from dist.csv. config (dict): Fleet configuration from config.json. events (list): Event dicts from simulation log.txt in chronological order. Returns: dict: Metric names mapped to JSON-serializable numeric values. """

    # 1. Build distance graph matrix
    dist_map = {}
    for row in distances:
        u = row['location_1']
        v = row['location_2']
        w = float(row['dist'])
        if u not in dist_map:
            dist_map[u] = {}
        dist_map[u][v] = w

    # 2. Build parcel lookup dictionary
    parcel_info = {}
    for p in parcels:
        pid = p['parcel_id']
        parcel_info[pid] = {
            'dest': p['delivery_location_id'],
            'window_end': parse_hhmm(p['delivery_window_end'])
        }

    total_parcels = len(parcels)
    delivered_times = {}
    trip_deliveries = {} # (vehicle_id, trip_id) -> list of (delivery_time, location_id)
    hub_departures = 0

    # 3. Parse events log
    for ev in events:
        etype = ev.get('event_type')
        if etype == 'hub_departure':
            hub_departures += 1
        elif etype == 'delivery':
            pid = ev['parcel_id']
            t = float(ev['time'])
            delivered_times[pid] = t
            v_id = ev['vehicle_id']
            tr_id = ev['trip_id']
            key = (v_id, tr_id)
            if key not in trip_deliveries:
                trip_deliveries[key] = []
            dest = parcel_info[pid]['dest']
            trip_deliveries[key].append((t, dest))

    # 4. Reconstruct actual vehicle trip distances
    total_distance_km = 0.0
    for key, drops in trip_deliveries.items():
        # Sort drops chronologically by delivery timestamp to track exact route
        drops.sort(key=lambda x: x[0])
        route_locs = [d[1] for d in drops]
        
        curr = "HUB"
        for loc in route_locs:
            if curr in dist_map and loc in dist_map[curr]:
                total_distance_km += dist_map[curr][loc]
            curr = loc
        # Return trip to HUB
        if curr in dist_map and "HUB" in dist_map[curr]:
            total_distance_km += dist_map[curr]["HUB"]

    # 5. Calculate Lateness and Non-Delivery Penalties
    total_lateness_min = 0.0
    delivered_count = len(delivered_times)
    undelivered_count = total_parcels - delivered_count

    for pid, del_time in delivered_times.items():
        w_end = parcel_info[pid]['window_end']
        lateness = max(0.0, del_time - w_end)
        total_lateness_min += lateness

    # Cost parameters
    c_dist = 1.0       # $1.00 per km
    c_late = 0.50      # $0.50 per min of lateness
    c_undel = 100.0    # $100.00 fixed penalty per undelivered parcel

    tsop = (c_dist * total_distance_km) + (c_late * total_lateness_min) + (c_undel * undelivered_count)

    return {
        "tsop": round(tsop, 2),
        "total_distance_km": round(total_distance_km, 2),
        "total_lateness_min": round(total_lateness_min, 2),
        "undelivered_parcels": undelivered_count,
        "delivered_parcels": delivered_count,
        "total_trips": hub_departures
    }

    
    
def parse_hhmm(t_str):
    """Converts 'HH:MM' string to float minutes after midnight."""
    if not t_str:
        return 0.0
    h, m = map(int, t_str.split(':'))
    return float(h * 60 + m)

def main(argv: Optional[List[str]] = None) -> int:
    """Load one day's inputs and event log, then write the metrics report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data"),
                        help="directory containing dist.csv, config.json and demand/")
    parser.add_argument("--day", required=True, help="day identifier, for example day_001")
    parser.add_argument("--log", type=Path, required=True,
                        help="event log from a simulator run")
    parser.add_argument("--output", type=Path,
                        help="JSON report (default: metrics.json beside the selected log)")
    args = parser.parse_args(argv)
    try:
        parcel_path, distance_path, config_path = day_input_paths(args.data, args.day)
        output = args.output if args.output is not None else args.log.with_name("metrics.json")
        # The input files all live in the data directory, so this also protects them.
        if output.resolve() == args.data.resolve() or args.data.resolve() in output.resolve().parents:
            raise ValueError("report output must be outside the input data directory")
        if output.resolve() == args.log.resolve():
            raise ValueError("report output must not overwrite the log")
        with parcel_path.open(newline="", encoding="utf-8-sig") as stream:
            parcels = list(csv.DictReader(stream))
        with distance_path.open(newline="", encoding="utf-8-sig") as stream:
            distances = list(csv.DictReader(stream))
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        with args.log.open(encoding="utf-8") as stream:
            events = [json.loads(line) for line in stream if line.strip()]
        metrics = calculate_metrics(parcels, distances, config, events)
        report = json.dumps(metrics, indent=2, allow_nan=False) + "\n"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")
    except (OSError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(f"Metrics report: {output}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """Load one day's inputs and event log, then write the metrics report."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data"),
                        help="directory containing dist.csv, config.json and demand/")
    parser.add_argument("--day", required=True, help="day identifier, for example day_001")
    parser.add_argument("--log", type=Path, required=True,
                        help="event log from a simulator run")
    parser.add_argument("--output", type=Path,
                        help="JSON report (default: metrics.json beside the selected log)")
    args = parser.parse_args(argv)
    try:
        parcel_path, distance_path, config_path = day_input_paths(args.data, args.day)
        output = args.output if args.output is not None else args.log.with_name("metrics.json")
        # The input files all live in the data directory, so this also protects them.
        if output.resolve() == args.data.resolve() or args.data.resolve() in output.resolve().parents:
            raise ValueError("report output must be outside the input data directory")
        if output.resolve() == args.log.resolve():
            raise ValueError("report output must not overwrite the log")
        with parcel_path.open(newline="", encoding="utf-8-sig") as stream:
            parcels = list(csv.DictReader(stream))
        with distance_path.open(newline="", encoding="utf-8-sig") as stream:
            distances = list(csv.DictReader(stream))
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        with args.log.open(encoding="utf-8") as stream:
            events = [json.loads(line) for line in stream if line.strip()]
        metrics = calculate_metrics(parcels, distances, config, events)
        report = json.dumps(metrics, indent=2, allow_nan=False) + "\n"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")
    except (OSError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(f"Metrics report: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
