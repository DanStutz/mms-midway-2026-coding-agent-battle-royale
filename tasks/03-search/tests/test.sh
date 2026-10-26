#!/usr/bin/env bash
set -euo pipefail
node /tests/verify.cjs /app /logs/verifier
