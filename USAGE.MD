# KVR Database Server — Usage

This document explains how to run the server, call the HTTP API, and add new fields to the `users` table.

**Prerequisites**
- Python 3.8+ and dependencies from `requirements.txt`.
- A working SQLite database file (default: `kvr_database.db`).

**Configuration**
- Create a `.env` file in the project root or set environment variables in your shell:

```
API_KEY=supersecret
DATABASE=kvr_database.db
```

Make sure there are no accidental leading/trailing spaces in values.

**Start the server**
- Windows CMD:

```cmd
set API_KEY=supersecret && python app.py
```

- PowerShell:

```powershell
$env:API_KEY = "supersecret"; python app.py
```

The server will listen on http://127.0.0.1:5000 by default.

--------------------------------------------------
API Endpoints (require `X-API-Key` header)
--------------------------------------------------

All endpoints require the header `X-API-Key: <your key>`.

- Create user — POST /users

  CMD (curl):

  ```cmd
  curl -X POST http://127.0.0.1:5000/users -H "Content-Type: application/json" -H "X-API-Key: supersecret" -d "{\"username\":\"alice\",\"pin\":1234}"
  ```

  PowerShell (Invoke-RestMethod):

  ```powershell
  $h=@{"X-API-Key"="supersecret"; "Content-Type"="application/json"}
  Invoke-RestMethod -Uri http://127.0.0.1:5000/users -Method POST -Headers $h -Body '{"username":"alice","pin":1234}'
  ```

- Get user by username — GET /users/<username>

  ```cmd
  curl http://127.0.0.1:5000/users/alice -H "X-API-Key: supersecret"
  ```

- Get user by PIN — GET /users/pin/<pin>

  ```cmd
  curl http://127.0.0.1:5000/users/pin/1234 -H "X-API-Key: supersecret"
  ```

- Update user — PATCH /users/<username>

  Only known mutable fields are accepted by the server (e.g. `pin`, `kvrcoin`, `chess_points`).

  ```cmd
  curl -X PATCH http://127.0.0.1:5000/users/alice -H "Content-Type: application/json" -H "X-API-Key: supersecret" -d "{\"kvrcoin\":250}"
  ```

- Delete user — DELETE /users/<username>

  ```cmd
  curl -X DELETE http://127.0.0.1:5000/users/alice -H "X-API-Key: supersecret"
  ```

--------------------------------------------------
Adding a new field to `users` (script)
--------------------------------------------------

Use the helper script `scripts/add_field.py` to add a new column safely and initialize existing rows.

Examples:

- Add a text field `role` defaulting to `player`:

```cmd
python scripts/add_field.py --name role --default player --type TEXT --db kvr_database.db
```

- Add an integer field `age` defaulting to `0`:

```cmd
python scripts/add_field.py --name age --default 0 --type INTEGER --db kvr_database.db
```

What the script does:
- Validates the column name.
- Infers or uses the provided type (`INTEGER`, `REAL`, `TEXT`).
- Runs `ALTER TABLE users ADD COLUMN ... DEFAULT ...`.
- Updates existing rows where the new column is NULL to the provided default.

Notes about API compatibility
- The server's response serializer now returns all columns (except the internal `id`) from the `users` table. That means newly added fields will automatically appear in `GET` responses for existing users.
--------------------------------------------------
Leaderboard
--------------------------------------------------

The server includes a leaderboard endpoint for `chess_points`.

- Get chess leaderboard — GET /leaderboard/chess

  Query parameters:
  - `limit` (int, optional): maximum rows to return
  - `order` (`asc`|`desc`, default `desc`): sort order by `chess_points`

  Examples:

  ```cmd
  # Top 10 players (descending)
  curl "http://127.0.0.1:5000/leaderboard/chess?limit=10" -H "X-API-Key: supersecret"

  # Lowest scores first (ascending)
  curl "http://127.0.0.1:5000/leaderboard/chess?order=asc" -H "X-API-Key: supersecret"
  ```

  Response: a JSON array of objects with `username` and `chess_points`.

--------------------------------------------------
Testing
--------------------------------------------------

- Run the test suite with:

```cmd
python -m pytest -q
```

--------------------------------------------------
Cleanup and security notes
--------------------------------------------------
- The temporary diagnostic route and auth logging used during troubleshooting have been removed. The codebase no longer exposes `/debug-headers`.
- Never commit your real `API_KEY` to version control.

If you'd like, I can add automated tests for the leaderboard endpoint.
