#!/usr/bin/env bash
# Refresh both registers and rebuild khoj.html.
#   ./refresh.sh          rescue portal only (fast, ~2 min) — the flood data
#   ./refresh.sh --full   also re-copy the police register (~40 min, slow server)
set -euo pipefail
cd "$(dirname "$0")"

# On a clean runner there is no records.json; recover the police register from
# the page we published last time so a failed fetch cannot drop people.
python3 seed.py

# The rescue portal carries the flood data. Without it there is nothing worth
# publishing, so let a failure here stop us.
python3 fetch_rescue.py

# The police register is slow and drops connections under load, and adds only a
# small share of flood-window records. If it fails, keep the copy we already have
# rather than throwing away a good rescue-portal fetch.
if [ "${1:-}" = "--full" ]; then
  if ! python3 fetch.py; then
    if [ -f records.json ]; then
      echo "police register unavailable; reusing the previous copy"
    else
      echo "police register unavailable and no previous copy; continuing without it"
      echo '{"source":"","fetched":"","count":0,"records":[]}' > records.json
    fi
  fi
fi
python3 prepare.py
python3 build.py combined.json index.html
echo "rebuilt index.html — republish it to https://claude.ai/code/artifact/c2040a45-b45d-4d08-904a-b41a051ccfc8"
