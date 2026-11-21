# TransitWitness

TransitWitness records whether a published timetable snapshot supports a journey within an agreed time window. A mobility app, accessibility group, or service auditor can cite one immutable record when comparing schedules or checking a service commitment.

A caller supplies a GitHub owner, repository, full commit SHA, SHA-256 of the raw `schedule.json` bytes, and journey constraints. GenLayer validators independently fetch the pinned file, verify its digest, validate the schema and agree on the complete normalized leg list with `strict_eq`. After agreement, deterministic code computes the earliest reachable arrival and stores a witness containing the source, query and leg IDs. Fetch failures, mismatches and invalid data abort without writing a finding. Repeating the same query returns its existing record ID.

The solver keeps the earliest arrival at each stop for each exact leg count. With a uniform transfer buffer and permission to wait, arriving earlier at the same stop with the same leg count cannot eliminate a connection available to a later arrival. The solver takes at most six passes over 256 legs. Ties prefer fewer legs and are resolved deterministically.

## Try it

Deploy `contract.py` in GenLayer Studio. Publish `schedule.json` at the root of a public GitHub repository and obtain its full commit SHA and the digest of the published raw bytes. Call `attest(owner, repo, commit, digest, "Library", "Airport", 1370, 1470, 5, 2)`. Read the returned record ID with `get_attestation(id)`.

The included synthetic fixture yields T1 → T3, arriving at minute 1460. T2 departs only three minutes after T1 arrives, and T4 misses the deadline. With a three-minute buffer the solver instead finds T1 → T2 at minute 1450. With a one-leg limit there is no route within the selected deadline.

Each row is `[leg_id, origin, destination, departure_minute, arrival_minute]`. Times are minutes since the same schedule-day origin and can cross midnight. Publishers must supply a single resolved service day, unique leg IDs and a consistent stop namespace.

The input is a small JSON projection, not a GTFS feed. It models waiting at the same stop and a uniform transfer buffer. It does not model walking links, fares, cancellations, continuous vehicle boarding or real-time delays. A finding applies only to the supplied snapshot. Consensus verifies the bytes and computation, while the caller must choose a publisher they trust for timetable provenance.

Run `python -m unittest -v` from this directory. Tests use a mock GenLayer runtime. No network deployment or funded account is required.
