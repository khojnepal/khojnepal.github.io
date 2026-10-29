#!/usr/bin/env bash
# Refresh both registers and rebuild khoj.html.
#   ./refresh.sh          rescue portal only (fast, ~2 min) — the flood data
#   ./refresh.sh --full   also re-copy the police register (~40 min, slow server)
set -euo pipefail
cd "$(dirname "$0")"

# On a clean runner there is no records.json or rescue.json; recover both from
# the page we published last time so a failed fetch cannot drop people.
python3 seed.py

# Neither register gates the other. The rescue portal carries the flood data and
# the police register carries ~9,400 missing-person records; when one server is
# unreachable, publish the other half rather than nothing. Going down together
# is what the record-count guard in build.py is for.
if ! python3 fetch_rescue.py; then
  if [ -f rescue.json ]; then
    echo "rescue portal unavailable; reusing the previous copy"
  else
    echo "rescue portal unavailable and no previous copy; continuing without it"
    echo '{"source":"","fetched":"","count":0,"records":[]}' > rescue.json
  fi
fi

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
