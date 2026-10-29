#!/usr/bin/env bash
# Daily: refetch both lists, rebuild the page, publish it.
# Pushing to the repo is what makes the live site update.
cd "$(dirname "$0")"
{
  echo "=== $(date -Is) ==="
  if ./refresh.sh --full; then
    size=$(stat -c%s index.html 2>/dev/null || echo 0)
    if [ "$size" -gt 5000000 ]; then
      git add index.html
      git -c user.name="Khoj" -c user.email="noreply@example.com" \
          commit -q -m "data refresh $(date -u +%Y-%m-%d)" --amend --no-edit
      git push --force origin main && echo "published"
    else
      echo "REFUSED to publish: index.html only ${size} bytes, data looks truncated"
    fi
  else
    echo "refresh failed; keeping the previous page live"
  fi
  echo "=== done $(date -Is) ==="
} >> refresh.log 2>&1
