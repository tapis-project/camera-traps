# Testing notes: `device_id=skylake` / "Quality Metrics show 0" investigation

Context: Samuel Khuvis reported not seeing experiments for `device_id=skylake` in the Patra
web app, and later that Quality Metrics showed all zeros once experiments did appear. His OSC
deployment runs `cyberinfrastructure-knowledge-network`'s `plugins/oracle_ckn_daemon/oracle_daemon.py`
(the plugin this PR replaces) — the label-matching logic tested below
(`_update_experiment_metrics` / `has_correct_prediction`) is the same logic now in this PR's
`ckn_plugin.py` (lines ~429-473), so the findings and test approach carry over directly.

No live DB/broker access was reachable from the sandbox's network (`psql` to
`patradb.pods.icicleai.tapis.io:5432` times out) — every check below instead went through the
Tapis Pods `exec_pod_commands` API (execs `psql` inside the live `patradb` pod) or by publishing
real Kafka messages to the live CKN broker.

## Tools used

- **DB queries**: `tapipy`'s `t.pods.exec_pod_commands(pod_id="patradb", commands=["psql", "-U", "patradb", "-d", "patradb", "-c", sql])`,
  run from `~/.venvs/tapis` with `plale_lab/tapis/.env` sourced (`set -a; source .env; set +a`).
  This runs `psql` *inside* the running Postgres container, sidestepping the fact that the
  external hostname's port 5432 isn't reachable from here.
- **Synthetic Kafka events**: `confluent_kafka.Producer` targeting
  `cknbroker.pods.icicleai.tapis.io:443` with `security.protocol: SSL`. Messages to
  `oracle-events` and `cameratraps-power-summary` both require the Kafka Connect JSON envelope
  `{"schema": {...}, "payload": {...}}` — both live connectors have
  `value.converter.schemas.enable=true`, confirmed via
  `GET https://cknkafkaconnect.pods.icicleai.tapis.io/connectors/<name>/config`. (This is the
  gap the "Wrap CKN Kafka events in Connect schema envelopes" commit on this branch addresses —
  the old `oracle_daemon.py`/pre-fix `ckn_plugin.py` producer sent bare JSON with no envelope.)
- **Live API checks**: plain `curl` against `patrabackend.pods.icicleai.tapis.io` /
  `patrabackenddemo.pods.icicleai.tapis.io`.

## Step 1 — confirm the device auto-register fix is actually live

```sql
SELECT prosrc LIKE '%ON CONFLICT (device_id) DO NOTHING%' AS has_autoregister_fix
FROM pg_proc WHERE proname = 'fn_ingest_camera_trap_event';
-- -> t
```

Then proved it end-to-end with a synthetic event for a **brand-new, never-seen** `device_id`
(`verify-autoregister-<random>`), published with a currently-valid `model_id`
(`ea991e85-feaa-4781-a297-4d7bec1a69b1`, MegaDetector 6b-yolov9c) and a registered `user_id`
(`skhuvis`). Confirmed via:
- `GET /experiments/animal-ecology/users/skhuvis/summary` includes the new experiment_id
- `SELECT device_id FROM edge_devices WHERE device_id = '...'` shows the row was auto-created

Repeated with a second random device_id and again with the literal `device_id=skylake` to rule
out anything specific to that name. All three auto-registered correctly. **Conclusion: device
auto-registration is not the problem** — matches this PR's `run_e2e_test.sh` note that "an
unseen device_id auto-registers in edge_devices on first event."

## Step 2 — find why `skylake`'s real events weren't landing

```sql
SELECT device_id FROM edge_devices WHERE device_id = 'skylake';        -- 0 rows (not yet registered)
SELECT * FROM events WHERE device_id = 'skylake' ORDER BY ingested_at DESC LIMIT 10;  -- nothing since Feb
SELECT id FROM models WHERE id::text = '<his old model uuid>';         -- 0 rows
SELECT m.id FROM models m JOIN model_cards mc ON mc.id = m.model_card_id
  WHERE mc.uuid::text = '<his old model uuid>';                        -- 0 rows
```

His device's `model_id` had been deleted from the catalog. Unlike an unregistered device
(auto-heals), an unresolvable model still `RAISE EXCEPTION`s by design (models carry real
identity that shouldn't be fabricated), which — since it's an `AFTER` trigger — rolls back the
*entire* raw insert. Nothing lands anywhere, no error visible to the person running it.

**Conclusion: not a device problem, a stale-model-reference problem specific to his deployment.**

## Step 3 — power-events pipeline sanity check

Same synthetic-event approach, but publishing a second message to
`cameratraps-power-summary` (topic used by `PgSinkConnectorPowerSummary`) keyed by the same
`experiment_id`, matching the shape `power_processor.py` builds. Confirmed
`GET /experiments/{domain}/{experiment_id}/power` returns the submitted wattage fields, and
that the ingest trigger for power correctly no-ops (`RAISE NOTICE`, not exception) if the
oracle-event side hasn't landed yet rather than failing loudly.

## Step 4 — "Quality Metrics show 0" — reproducing the real scoring logic

Once his device *did* land a real event (`5a3ba227-...`, `TP=0, FP=80, FN=6`), the question was
whether Patra was computing precision/recall wrong, or just storing what arrived. Answer:
Patra only derives `precision/recall/f1` from the `true_positives/false_positives/false_negatives`
fields already present in each event — it does no independent scoring. So the question became:
why is *his* `true_positives` always 0?

Verified two ways against `cyberinfrastructure-knowledge-network`'s `oracle_daemon.py`
(`_update_experiment_metrics`, added in commit `d2e46d9`, 2025-08-31 — same logic as this PR's
`ckn_plugin.py`):

**a) Isolated function test** — extracted just the relevant methods via `ast.parse` (avoids
needing to import the whole module, which pulls in `watchdog`/`confluent_kafka` module-level
config), bound them onto a minimal stand-in class, and called
`_update_experiment_metrics(ground_truth, scores, None)` directly with his exact
`ground_truth`/`flattened_scores` values pulled from Postgres for the `baby-red-fox.jpg` image.
Result: `true_positives=1` — correct, given `ground_truth="animal"` and one of the predicted
labels is also `"animal"`.

**b) Full pipeline replay** — the CKN repo ships the actual example dataset
(`plugins/oracle_ckn_daemon/events/image_mapping_final.json`, the literal default
`ORACLE_EVENTS_FILE`) that Samuel confirmed he's using ("it's just the example images in the
repo"). Instantiated the real `OracleEventHandler` class unmodified, pointed at that file, with
a `FakeProducer` stub (just collects `produce()` calls instead of hitting Kafka) standing in for
the real `confluent_kafka.Producer`, then called `handler.read_json_events()` — the actual
method the daemon runs on file-watch events. Final cumulative metrics:
`TP=6, FP=74, FN=0, precision=0.075, recall=1.0, f1=0.1395` — this exactly matches two of
Samuel's own earlier *good* runs (`09fa7519-...`, `70619b0d-...` from `2026-07-16`), not his
recent `TP=0` runs.

One wrinkle found along the way: the fixture file's own embedded `model_id`
(`9103066540bd614e...-model`) is itself a stale placeholder that doesn't resolve to any real
model — publishing the replayed events with that literal value produced zero rows anywhere
(same failure class as Step 2). Had to override `model_id` to a real one
(`ea991e85-feaa-4781-a297-4d7bec1a69b1-model`) before it would land.

**Conclusion**: current code, run against Samuel's exact dataset, computes the right answer.
Since his real deployment produces `TP=0` on the same data, his running container must be
serving older/different code than what's in the repo — a rebuild/redeploy problem, not a logic
bug. (Separately confirmed his `git log` was *not* stale — `main` hadn't moved since his last
pull — which narrowed it from "pull latest" to "rebuild and redeploy the container." Once he's
on this PR's `ckn_plugin` instead, that's moot.)

## Step 5 — live end-to-end confirmation (not just a local dry run)

Republished the 12-image replay (from step 4b) to the real broker with the proper schema
envelope, this time as `user_id=neelk` to avoid mixing test data into Samuel's own experiment
history. Confirmed via direct DB query:

```sql
SELECT true_positives, false_positives, false_negatives, precision, recall, f1_score
FROM experiments WHERE experiment_uid = 'experiment-repro-neelk-...';
-- 6 | 74 | 0 | 0.07500 | 1.00000 | 0.13953
```

Matches step 4b exactly, this time verified through the real Kafka → Kafka Connect → Postgres
→ REST API path, not just in-process.

## Gotchas hit along the way (not bugs, just confusing while debugging)

- **`patradb` vs `patradb_demo`**: same Postgres instance, two databases. The demo Kafka Connect
  sink connector (`PgSinkConnectorCameraTrapsDemo`) mirrors *all* `oracle-events` traffic into
  `patradb_demo`, but that database has a much smaller model/device catalog — a message can
  succeed on `patradb` and silently vanish on `patradb_demo` if the model it references isn't in
  that catalog too. Always check the frontend URL (`patra.` vs `patrademo.`) before assuming data
  is missing.
- **Timestamp choice matters for visibility, not correctness**: the first `neelk` replay reused
  the fixture file's original `2025-09-25` timestamps verbatim, which is legitimate data but
  sorted the experiment to page 8 of 11 in the UI's `start_at DESC` ordering — looked "missing"
  but wasn't. Substituting current timestamps on the second replay put it at the top.
- **Refreshing the page resets the user selection.** The frontend doesn't restore
  `selectedUserId` after a hard reload — you have to re-pick the user from the dropdown before
  `userSummary`/`experimentList` repopulate.
