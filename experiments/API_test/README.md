## API Experiments

- `simple_test.py`: basic fetch of stats + latest game for a single user.
- `stress_test.py`: multi-user stress run for `/stats` + latest archive game with CSV input and CSV logging.

Examples:
```bash
# Quick single-user probe (serial)
python experiments/API_test/stress_test.py yevgenchess --iterations 2 --sleep 1

# Multi-user run from CSV (column "username"), 4-way concurrency, log to file
python experiments/API_test/stress_test.py --users-csv users.csv --concurrency 4 --iterations 1 --output experiments/API_test/logs/run.csv
```

Notes:
- Concurrency above 1 may trigger `429`; use `--respect-retry-after` to back off automatically.
- Logs include status, latency, ETag/Last-Modified, hashes, and whether the payload changed. The freshest ratings usually come from the last game in the latest monthly archive.
