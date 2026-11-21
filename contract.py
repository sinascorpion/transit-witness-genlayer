# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
import hashlib
import json
import re


def identifier(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,48}", value)


def minute(value):
    return type(value) is int and 0 <= value < 2880


def parse_schedule(body):
    assert len(body) <= 32768, "Schedule too large"
    data = json.loads(body)
    assert isinstance(data, dict) and set(data) == {"schema", "legs"}, "Invalid schedule"
    assert data["schema"] == "transit-witness/v1", "Unsupported schema"
    rows = data["legs"]
    assert isinstance(rows, list) and 1 <= len(rows) <= 256, "Invalid leg count"
    ids = set()
    for row in rows:
        assert isinstance(row, list) and len(row) == 5, "Invalid leg"
        leg, origin, destination, depart, arrive = row
        assert identifier(leg) and identifier(origin) and identifier(destination), "Invalid identifier"
        assert leg not in ids and origin != destination, "Duplicate or circular leg"
        assert minute(depart) and minute(arrive) and depart < arrive, "Invalid times"
        ids.add(leg)
    return sorted(rows)


def solve(rows, origin, destination, start, deadline, buffer, max_legs):
    # Within a fixed leg count, the earliest arrival at a stop dominates later arrivals.
    reachable = {origin: (start, ())}
    best = None
    for depth in range(max_legs):
        following = {}
        for leg, source, target, depart, arrive in rows:
            previous = reachable.get(source)
            if previous is None or depart < previous[0] + (buffer if depth else 0) or arrive > deadline:
                continue
            candidate = (arrive, previous[1] + (leg,))
            if target not in following or candidate < following[target]:
                following[target] = candidate
        result = following.get(destination)
        if result is not None:
            candidate = (result[0], depth + 1, result[1])
            if best is None or candidate < best:
                best = candidate
        reachable = following
        if not reachable:
            break
    if best is None:
        return {"status": "NO_ROUTE_IN_SNAPSHOT", "arrival": None, "legs": []}
    return {"status": "ROUTE_FOUND", "arrival": best[0], "legs": list(best[2])}


class TransitWitness(gl.Contract):
    count: u64
    records: TreeMap[str, str]
    query_ids: TreeMap[str, u64]

    def __init__(self):
        self.count = 0

    @gl.public.write
    def attest(self, owner: str, repo: str, commit: str, digest: str,
               origin: str, destination: str, start: u64, deadline: u64,
               transfer_buffer: u64, max_legs: u64) -> u64:
        assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", owner), "Invalid GitHub owner"
        assert re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", repo) and repo not in (".", ".."), "Invalid repo"
        assert re.fullmatch(r"[0-9a-f]{40}", commit), "Expected pinned commit"
        assert re.fullmatch(r"[0-9a-f]{64}", digest), "Expected SHA-256 hex"
        assert identifier(origin) and identifier(destination) and origin != destination, "Invalid stops"
        assert 0 <= start < deadline < 2880 and 0 <= transfer_buffer <= 180, "Invalid time window"
        assert 1 <= max_legs <= 6, "Invalid leg limit"
        url = f"https://raw.githubusercontent.com/{owner}/{repo}/{commit}/schedule.json"
        query = [url, digest, origin, destination, int(start), int(deadline), int(transfer_buffer), int(max_legs)]
        key = hashlib.sha256(json.dumps(query).encode()).hexdigest()
        existing = self.query_ids.get(key, 0)
        if existing:
            return existing

        def observe():
            response = gl.nondet.web.request(url, method="GET")
            if response.status != 200 or response.body is None:
                raise gl.UserError("Schedule unavailable")
            body = response.body
            if len(body) > 32768 or hashlib.sha256(body).hexdigest() != digest:
                raise gl.UserError("Schedule size or digest mismatch")
            return json.dumps(parse_schedule(body), separators=(",", ":"))

        rows = json.loads(gl.eq_principle.strict_eq(observe))
        result = solve(rows, origin, destination, start, deadline, transfer_buffer, max_legs)
        self.count += 1
        self.records[str(self.count)] = json.dumps({
            "id": int(self.count), "source": url, "sha256": digest, "origin": origin,
            "destination": destination, "start": int(start), "deadline": int(deadline),
            "transfer_buffer": int(transfer_buffer), "max_legs": int(max_legs),
            "leg_count": len(rows), "result": result,
        }, sort_keys=True)
        self.query_ids[key] = self.count
        return self.count

    @gl.public.view
    def get_attestation(self, record_id: u64) -> str:
        return self.records.get(str(record_id), "")
