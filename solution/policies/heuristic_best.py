"""
Recommended policy: Spatio-Temporal Hybrid Dispatcher.

Algorithm Logic:
  1. Min-Heap Urgency Queue  - Pops the single most urgent parcel to seed the trip.
  2. Dynamic Batch Threshold - Delays dispatch if no parcel is urgent (>120 min slack) 
                               and load is small (<15 units) before 16:30.
  3. Spatial Fill (Cheapest) - Fills remaining vehicle capacity by selecting whichever 
                               waiting parcel adds the minimal detour distance.
  4. 2-Opt Local Search      - Refines the final route to eliminate edge crossings.
"""
import heapq
from solution.policies.helpers import (
    calculate_route_distance,
    is_route_feasible,
    insert_cheapest,
    two_opt_optimize
)

WAIT_SLACK = 120.0   # minutes to earliest deadline above which we may wait
WAIT_LOAD = 15.0     # total waiting size below which we may wait
WAIT_UNTIL = 990.0   # 16:30 cutoff (minutes after midnight)


def dispatch(parcel, context):
    distance_matrix = context["travel_distance"]
    capacity = context["capacity"] #vehicle capacity once again
    max_distance = context["max_trip_distance_km"]
    current_time = context["current_time"]
    departure_delay = context["departure_delay"]
    return_cutoff = context["return_cutoff"]
    dep_time = current_time + departure_delay

    # 1. Gather unassigned parcels
    unassigned = [
        pid for pid, info in parcel.items()
        if info.get("vehicle_assigned") is None and info.get("delivery_time") is None
    ]
    if not unassigned:
        return []

    # 2. Build Min-Heap Priority Queue by Urgency (delivery_window_end)
    pq = []
    for pid in unassigned:
        info = parcel[pid]
        heapq.heappush(pq, (info["delivery_window_end"], info["arrival_time"], pid))

    # Dynamic Batching Threshold
    most_urgent_deadline = pq[0][0]
    slack = most_urgent_deadline - current_time
    total_available_size = sum(parcel[pid]["size"] for pid in unassigned)

    if slack > WAIT_SLACK and total_available_size < WAIT_LOAD and current_time < WAIT_UNTIL:
        return []  # Delay dispatch to accumulate denser clusters

    # 3. Seed Selection: Pick the most urgent parcel that forms a feasible solo trip
    route = []
    current_size = 0.0

    while pq:
        _, _, pid = heapq.heappop(pq)
        if is_route_feasible([pid], parcel, distance_matrix, capacity, max_distance, dep_time, return_cutoff):
            route = [pid]
            current_size = parcel[pid]["size"]
            break

    if not route:
        return []

    # 4. Spatial Fill: Cheapest insertion over all remaining waiting parcels
    waiting = set(unassigned)
    waiting.discard(route[0])

    while waiting:
        best_pid = None
        best_route = None
        best_dist = float('inf')

        for pid in waiting:
            psize = parcel[pid]["size"]
            if current_size + psize > capacity:
                continue

            candidate_route = insert_cheapest(route, pid, parcel, distance_matrix)
            if is_route_feasible(candidate_route, parcel, distance_matrix, capacity, max_distance, dep_time, return_cutoff):
                d = calculate_route_distance(candidate_route, parcel, distance_matrix)
                if d < best_dist:
                    best_dist = d
                    best_route = candidate_route
                    best_pid = pid

        if best_pid is None:
            break

        route = best_route
        current_size += parcel[best_pid]["size"]
        waiting.discard(best_pid)

    # 5. 2-Opt Local Search Optimization
    route = two_opt_optimize(route, parcel, distance_matrix)
    return route