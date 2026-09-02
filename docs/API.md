# Backend API

All board routes require the signed `pm_session` cookie. Unknown identifiers and identifiers owned by another user both return `404` so ownership is not disclosed.

## Board response

Board operations return the complete current board:

```json
{
  "id": "board-id",
  "title": "Kanban Studio",
  "columns": [
    { "id": "column-id", "title": "Backlog", "cardIds": ["card-id"] }
  ],
  "cards": {
    "card-id": { "id": "card-id", "title": "Title", "details": "Details" }
  }
}
```

Columns and `cardIds` are returned in persisted position order.

## Operations

| Method | Route | Body | Result |
| --- | --- | --- | --- |
| `GET` | `/api/board` | None | Read the signed-in user's board. |
| `PATCH` | `/api/columns/{column_id}` | `{"title":"Ideas"}` | Rename an owned column. |
| `POST` | `/api/cards` | `{"columnId":"...","title":"...","details":"..."}` | Append a card and return `201`. |
| `PATCH` | `/api/cards/{card_id}` | `{"title":"...","details":"..."}` | Edit an owned card. |
| `DELETE` | `/api/cards/{card_id}` | None | Delete a card and close its ordering gap. |
| `POST` | `/api/cards/{card_id}/move` | `{"columnId":"...","position":0}` | Reorder or move a card transactionally. |

Titles are trimmed and must not be blank. Column titles are limited to 80 characters and card titles to 200. Positions are zero-based and may range from zero through the current target-column length after removing the moving card. Invalid request shapes return `422`; invalid operations return `400`.

## AI diagnostic

`POST /api/ai/diagnostic` requires the signed `pm_session` cookie and asks the
configured KodeKloud `gpt-oss-120b` model `2+2`. A successful response is:

```json
{"answer": "4"}
```

Missing server configuration returns `503`, provider failures return `502`, and
provider timeouts return `504`. Error responses do not include provider details,
credentials, or configuration values.