import heapq

def calculate_route_distance(route_parcelids, parcel_dict, dist_matrix):
    "This calculates total round-trip distance (HUB -> drops -> HUB) for a list of parcel IDs."
    if not route_parcelids:
        return 0.0
    locs = [parcel_dict[pid]["delivery_location_id"] for pid in route_parcelids]
    dist = dist_matrix["HUB"][locs[0]]
    for i in range(len(locs) - 1):
        dist += dist_matrix[locs[i]][locs[i+1]]
    dist += dist_matrix[locs[-1]]["HUB"]
    return dist

def is_route_feasible(route_parcelids, parcel_dict, dist_matrix, max_capacity, max_distance, departure_time, return_cutoff):
    "This validates capacity, trip range, and 18:00 vehicle return cutoff hard constraints."
    if not route_parcelids:
        return True
    # 1. Vehicle Capacity Check (Maximum is 30 units)
    total_size = sum(parcel_dict[pid]["size"] for pid in route_parcelids)
    if total_size > max_capacity:
        return False
    # 2. Maximum Trip Distance Check (Maximum is 320 km)
    dist = calculate_route_distance(route_parcelids, parcel_dict, dist_matrix)
    if dist > max_distance:
        return False
    # 3. Return Cutoff Check
    est_return_time = departure_time + dist
    if est_return_time > return_cutoff:
        return False
    return True

def insert_cheapest(current_route, new_parcelid, parcel_dict, dist_matrix):
    "Use a Greedy insertion (Cheapest Insertion Heuristic) to add parcels with minimal detour."
    if not current_route:
        return [new_parcelid]
    best_route = None
    best_dist = float('inf')
    for pos in range(len(current_route) + 1):
        cand = current_route[:pos] + [new_parcelid] + current_route[pos:]
        d = calculate_route_distance(cand, parcel_dict, dist_matrix)
        if d < best_dist:
            best_dist = d
            best_route = cand
    return best_route

def two_opt_optimize(route_parcelids, parcel_dict, dist_matrix, max_iter=50):
    "2-Opt Local Search Operator, which iteratively swaps edge pairs to eliminate route crossings and minimize distance."
    if len(route_parcelids) <= 2:
        return list(route_parcelids)
    best_route = list(route_parcelids)
    best_dist = calculate_route_distance(best_route, parcel_dict, dist_matrix)
    improved = True
    count = 0
    while improved and count < max_iter:
        improved = False
        count += 1
        n = len(best_route)
        for i in range(n - 1):
            for j in range(i + 1, n):
                # Reverse sub-path between index i and j
                new_route = best_route[:i] + best_route[i:j+1][::-1] + best_route[j+1:]
                new_dist = calculate_route_distance(new_route, parcel_dict, dist_matrix)
                if new_dist < best_dist - 1e-5:
                    best_route = new_route
                    best_dist = new_dist
                    improved = True
                    break
            if improved:
                break
    return best_route