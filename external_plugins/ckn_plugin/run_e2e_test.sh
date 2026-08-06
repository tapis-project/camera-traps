#!/usr/bin/env bash
#
# Runs a full camera-traps experiment end-to-end against the real ckn_plugin
# in this branch, streaming oracle events + a power summary through cknbroker
# into patradb. Automates the runbook in PR #65
# (https://github.com/tapis-project/camera-traps/pull/65).
#
# Requirements: Docker + Compose v2 on a Linux host (x86_64 or arm64), ~25 GB
# free disk, outbound HTTPS. The user/model below must already be registered
# in patradb (users.username / models.id) or the ingest trigger will reject
# every event. The device does not: an unseen device_id auto-registers in
# edge_devices on first event.
#
# Usage:
#   ./run_e2e_test.sh                 # real powerjoular (0 W readings on most VMs)
#   SYNTHETIC_POWER=1 ./run_e2e_test.sh   # swap in a fake powerjoular with nonzero wattage
#
# Override identities/version if needed:
#   USER_ID=example_user DEVICE_ID=example_device MODEL_ID=2 TRAPS_REL=0.6.0 ./run_e2e_test.sh

set -euo pipefail

TRAPS_REL="${TRAPS_REL:-0.6.0}"
USER_ID="${USER_ID:-example_user}"
DEVICE_ID="${DEVICE_ID:-example_device}"
MODEL_ID="${MODEL_ID:-2}"
EXPERIMENT_ID="${EXPERIMENT_ID:-$(python3 -c 'import uuid; print(uuid.uuid4())')}"
SYNTHETIC_POWER="${SYNTHETIC_POWER:-0}"
WORKDIR="${WORKDIR:-$HOME/ct-e2e}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "=== camera-traps CKN e2e test ==="
echo "Experiment ID: $EXPERIMENT_ID"
echo "Identity: user=$USER_ID device=$DEVICE_ID model=$MODEL_ID"
echo "Synthetic power: $SYNTHETIC_POWER"
echo "Work dir: $WORKDIR"
echo

mkdir -p "$WORKDIR"

echo "--- 1. Building ckn_plugin image from this branch ---"
docker build -t "tapis/ckn_plugin:${TRAPS_REL}" --build-arg REL="${TRAPS_REL}" \
  "$REPO_ROOT/external_plugins/ckn_plugin"

echo "--- 2. Building installer image from this branch ---"
docker build -t tapis/camera-traps-installer:local "$REPO_ROOT/installer"

echo "--- 3. Writing input.yml ---"
cat > "$WORKDIR/input.yml" <<EOF
install_dir: e2e_test
use_gpu_in_scoring: false
inference_server: false
use_ultralytics: true
local_model_path: ./md_v5a.0.0.pt
user_id: ${USER_ID}
device_id: ${DEVICE_ID}
model_id: "${MODEL_ID}"
experiment_id: ${EXPERIMENT_ID}
EOF

echo "--- 4. Rendering install ---"
# The installer refuses to render into an existing install_dir; if a previous
# run left one, preserve the model weights and clear it first.
if [ -f "$WORKDIR/e2e_test/md_v5a.0.0.pt" ]; then
  mv "$WORKDIR/e2e_test/md_v5a.0.0.pt" "$WORKDIR/md_v5a.0.0.pt"
fi
rm -rf "$WORKDIR/e2e_test"

docker run --rm --user "$(id -u):$(id -g)" \
  -v "$WORKDIR:/host" \
  -e INSTALL_HOST_PATH="$WORKDIR" \
  -e INPUT_FILE=input.yml \
  tapis/camera-traps-installer:local

echo "--- 5. Providing model weights ---"
# Extract the weights baked into the ultralytics scoring image so no download
# from the (retired) legacy Patra model endpoint is needed.
if [ -f "$WORKDIR/md_v5a.0.0.pt" ]; then
  mv "$WORKDIR/md_v5a.0.0.pt" "$WORKDIR/e2e_test/md_v5a.0.0.pt"
else
  docker pull "tapis/image_scoring_plugin_ultralytics_py_3.13:${TRAPS_REL}"
  cid=$(docker create "tapis/image_scoring_plugin_ultralytics_py_3.13:${TRAPS_REL}")
  docker cp "$cid:/md_v5a.0.0.pt" "$WORKDIR/e2e_test/md_v5a.0.0.pt"
  docker rm "$cid" >/dev/null
fi

if [ "$SYNTHETIC_POWER" = "1" ]; then
  echo "--- 5b. Wiring in synthetic power readings (no RAPL on this host) ---"
  FPJ_DIR="$WORKDIR/fake-powerjoular"
  mkdir -p "$FPJ_DIR"
  cat > "$FPJ_DIR/fake_powerjoular.py" <<'PYEOF'
#!/usr/bin/env python3
"""
Test-only stand-in for powerjoular, for hosts without Intel RAPL (cloud VMs).

Accepts the same CLI the camera-traps powerjoular backend uses
(`-tp <pid> -f <output_path>`) and appends one CSV row per second in the
5-column format `convert_powerjoular_csv_to_json` expects, with synthetic
nonzero CPU/GPU wattage. Runs until the backend force-removes the container.
"""
import random
import sys
import time
from datetime import datetime

args = sys.argv[1:]
pid = args[args.index("-tp") + 1]
out = args[args.index("-f") + 1]

print(f"fake-powerjoular: monitoring pid {pid}, writing {out}", flush=True)

with open(out, "w") as f:
    f.write("Date,CPU Utilization,Total Power,CPU Power,GPU Power\n")

while True:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    util = random.uniform(0.05, 0.95)
    cpu_w = random.uniform(2.0, 6.0)
    gpu_w = random.uniform(0.05, 0.3)
    total_w = cpu_w + gpu_w
    with open(out, "a") as f:
        f.write(f"{ts},{util:.14f},{total_w:.14f},{cpu_w:.14f},{gpu_w:.14f}\n")
    time.sleep(1)
PYEOF
  cat > "$FPJ_DIR/Dockerfile" <<'DOCKEOF'
FROM python:3.12-alpine
COPY fake_powerjoular.py /fake_powerjoular.py
ENTRYPOINT ["python", "-u", "/fake_powerjoular.py"]
DOCKEOF

  # the power backend always `docker pull`s POWER_JOULAR_IMAGE before running,
  # so a local-only tag needs to come from somewhere pullable: a throwaway
  # local registry (localhost is exempt from Docker's TLS requirement).
  docker rm -f e2e-registry >/dev/null 2>&1 || true
  docker run -d -p 5000:5000 --name e2e-registry registry:2 >/dev/null
  sleep 2
  docker build -t localhost:5000/fake-powerjoular:latest "$FPJ_DIR"
  docker push localhost:5000/fake-powerjoular:latest

  sed -i '/TRAPS_TEST_POWER_FUNCTION=1/a\      - POWER_JOULAR_IMAGE=localhost:5000/fake-powerjoular:latest' \
    "$WORKDIR/e2e_test/docker-compose.yml"
fi

echo "--- 6. Running the experiment ---"
cd "$WORKDIR/e2e_test"
docker compose up -d

echo "Waiting for ckn_plugin to process all images and exit..."
while true; do
  status=$(docker inspect -f '{{.State.Status}}' ckn_plugin 2>/dev/null || echo "gone")
  if [ "$status" = "exited" ] || [ "$status" = "gone" ]; then
    break
  fi
  sleep 5
done

echo
echo "=== ckn_plugin log tail ==="
docker logs ckn_plugin 2>&1 | tail -40

streamed=$(docker logs ckn_plugin 2>&1 | grep -c "Successfully streamed event" || true)
power=$(docker logs ckn_plugin 2>&1 | grep -c "Power summary successfully streamed" || true)
errs=$(docker logs ckn_plugin 2>&1 | grep -ci "error streaming\|failed to connect\|traceback" || true)

echo
echo "=== Summary ==="
echo "Oracle events streamed: $streamed"
echo "Power summary streamed: $power"
echo "Errors detected in log: $errs"

if [ "$SYNTHETIC_POWER" = "1" ]; then
  docker rm -f e2e-registry >/dev/null 2>&1 || true
fi

echo
echo "--- 7. Teardown ---"
docker compose down

echo
echo "=== Verify in patradb ==="
echo "export PGPASSWORD=<patradb password>"
cat <<EOF
CONN="host=patradb.pods.icicleai.tapis.io port=443 dbname=patradb user=patradb sslmode=require"
psql "\$CONN" -c "SELECT count(*) FROM events WHERE experiment_id='${EXPERIMENT_ID}';"
psql "\$CONN" -x -c "SELECT * FROM power_summary WHERE experiment_id='${EXPERIMENT_ID}';"
psql "\$CONN" -x -c "SELECT experiment_uid, user_id, edge_device_id, model_id, total_images, total_predictions, precision, recall, f1_score, total_cpu_power_w, total_gpu_power_w FROM experiments WHERE experiment_uid='${EXPERIMENT_ID}';"
EOF
echo
echo "Expected: 12 events rows, 1 power_summary row, 1 experiments row with total_images=12."
if [ "$streamed" != "12" ] || [ "$power" != "1" ] || [ "$errs" != "0" ]; then
  echo
  echo "WARNING: counts above are not the expected 12/1/0 -- check the ckn_plugin log for details."
fi
