# Database Design

The proposed schema is defined in `schema.json`. Part 5 documents and validates the design only; database runtime code begins after approval in Part 6.

## Initialization and migrations

The backend will use Python's standard `sqlite3` module. At startup it will create `data/pm.db` when absent, enable foreign keys for every connection, set WAL mode and a five-second busy timeout, then apply pending numbered migrations in one transaction. Applied versions are recorded in `schema_migrations`; existing migrations are immutable and future changes add a new version.

After migrations, one idempotent seed transaction will create the fixed `user`, that user's board, and all five columns only when absent. Column identity comes from `column_key`; titles are editable, while keys and positions remain fixed. The application will not expose column create, delete, or reorder operations.

## Ownership and ordering

`boards.owner_user_id` is unique, allowing at most one board per user. Cards carry `board_id` and `column_id`; their composite foreign key must match one `board_columns` row, preventing a card from referencing a column on another board. Every board query and mutation is scoped through the authenticated user's board.

Column positions are unique from 0 through 4 per board. Card positions are unique and contiguous from 0 within each column. A card move uses `BEGIN IMMEDIATE`, validates source and target ownership, temporarily shifts affected positions above both current list ranges, writes both ordered lists back contiguously, and commits as one unit. A failure rolls back the complete move.

## Sessions

The browser keeps an opaque token only in its HTTP-only cookie. SQLite stores the token's SHA-256 hash, never the usable token. A session belongs to one user and has creation and expiry timestamps. Lookup requires both a matching hash and a future expiry; logout deletes the row, and expired rows are removed during login or startup.

## Local data and backups

The host database is `data/pm.db`, bind-mounted to `/data/pm.db` in the container. The entire `data/` directory is ignored by Git and is the persistence and backup boundary.

For a consistent backup while the application is running, use SQLite's backup API or stop the Compose service before copying `data/`. WAL mode may create `pm.db-wal` and `pm.db-shm`, so copying only `pm.db` from a running application is not sufficient.

To reset all local application state, stop the service, delete the ignored `data/` directory, and start the service again. Startup initialization will create and seed a new database.