# KVR Go

A simple Python REST API server that acts as a central hub for the KingdomVR world. It stores user data (username, PIN, KVRCoin balance, chess points) and exposes it through a secured API so that other games (chess, etc.) have a way to store data centrally. Includes an admin page and a dashboard for users to manage their accounts. (coming soon)
Can easily be modified for other use cases.

## Requirements

- Python 3.8+
- Dependencies listed in `requirements.txt`

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure the environment:**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and set a strong, random value for `API_KEY`.

3. **Run the server:**
   ```bash
   python app.py
   ```
   The server starts on `http://localhost:5000` by default.

## Authentication

Every request must include the shared secret in the `X-API-Key` header:

```
X-API-Key: your_secret_api_key_here
```

## API Endpoints

All endpoints return JSON. HTTP `401` is returned when the API key is missing or wrong. HTTP `404` is returned when a user is not found.

### Create a user
```
POST /users
Content-Type: application/json

{
  "username": "alice",
  "pin": 1234,
  "kvrcoin": 0,
  "chess_points": 0
}
```
`username` and `pin` are required; `kvrcoin` and `chess_points` default to `0`.

### Get user by username
```
GET /users/<username>
```

### Get user by PIN
```
GET /users/pin/<pin>
```

### Update user fields
```
PATCH /users/<username>
Content-Type: application/json

{
  "kvrcoin": 150,
  "chess_points": 42
}
```

### Delete a user
```
DELETE /users/<username>
```

## Adding New Fields

1. In `app.py`, add the new column to the `CREATE TABLE` statement inside `init_db()` (e.g. `new_field REAL NOT NULL DEFAULT 0`).
2. In `user_to_dict()`, add the new field to the returned dict (e.g. `"new_field": row["new_field"]`).
3. If you want the field to be updatable via `PATCH`, add its name to the `allowed_fields` set in `update_user()`.
4. Delete `kvr_database.db` so the table is recreated with the new column, then restart the server.
