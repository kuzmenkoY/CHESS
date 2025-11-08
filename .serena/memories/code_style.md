# Code Style & Conventions
- Language: Python 3 with `requests`, `psycopg2-binary`, `python-dotenv`.
- Structure: simple modules; prefer context managers for DB access (`get_db_connection`), environment-driven configuration, and sequential API calls honoring Chess.com rate limits.
- Style: module/docstring headers, descriptive function names, occasional type hints (e.g., return type annotations), lightweight logging via prints/emojis for scripts. Keep SQL in separate `.sql` files.
- Environment: secrets via `.env` (`DATABASE_URL` or Supabase components). Follow Chess.com API rules (custom User-Agent, serial requests, caching headers).
- Data handling: usernames stored lowercased, timestamps as Unix epoch seconds, results kept as literal API codes.