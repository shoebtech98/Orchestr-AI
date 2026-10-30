# OrchestrAI Review 2: PDF semantic retrieval

This prototype extracts text from local research PDFs, creates overlapping text
chunks, embeds them with `sentence-transformers/all-MiniLM-L6-v2`, and stores
the vectors and source metadata in Qdrant. It does not create, replace, or delete
an existing collection.

## Requirements

- Python 3.10 or later
- A running Qdrant instance (default URL: `http://localhost:6333`)
- Internet access on first use to download the embedding model, unless it is
  already cached locally

From the `backend` directory, activate the existing virtual environment in the
project root and install dependencies:

```powershell
..\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

The model is loaded locally. Its first load can take time and requires enough
memory to run sentence-transformers and PyTorch.

## API configuration

Copy `.env.example` to `.env` in the `backend` directory and replace the
database and signing-key placeholders. The Qdrant defaults preserve the
existing URL and collection:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

| Variable | Default | Description |
| --- | --- | --- |
| `APP_NAME` | `OrchestrAI` | FastAPI application name |
| `API_PREFIX` | `/api/v1` | Versioned API route prefix |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant HTTP endpoint |
| `QDRANT_COLLECTION` | `orchestrai_papers` | Existing retrieval collection |
| `MAX_UPLOAD_BYTES` | `20971520` | Maximum PDF upload size (20 MiB) |
| `DATABASE_URL` | required | PostgreSQL SQLAlchemy URL using the `psycopg` driver |
| `JWT_SECRET_KEY` | required | Random signing key (at least 32 bytes) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access-token lifetime, at most 1440 minutes |

The CLI continues to accept `QDRANT_URL` and `QDRANT_COLLECTION` and retains
its existing command-line overrides.

Generate a signing key locally and set it in `.env`; do not commit `.env` or use
the placeholder value:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

The API refuses to start if `DATABASE_URL` is empty or is not PostgreSQL, or if
the JWT signing key is a placeholder or has fewer than 32 bytes / eight
distinct bytes. Never put production credentials in `.env.example`.

## Database migrations

Create the PostgreSQL database and set `DATABASE_URL`, then run migrations from
the `backend` directory:

```powershell
python -m alembic upgrade head
```

The initial migration creates only the `users` table; it does not reset or
modify Qdrant or other database data. The normalized email has a unique
constraint (and corresponding index), and a check constraint prevents
non-normalized values. `created_at` is stored as a timezone-aware timestamp.
The initial migration is intentionally irreversible to avoid deleting accounts.

## Run the API

From the `backend` directory:

```powershell
python -m uvicorn orchestrai_review2.api:app --reload
```

### Health

```http
GET /api/v1/health
```

When Qdrant is reachable, the response is HTTP 200:

```json
{
  "status": "healthy",
  "application": { "name": "OrchestrAI", "status": "healthy" },
  "dependencies": { "qdrant": { "status": "healthy" } }
}
```

If Qdrant is unavailable, the endpoint responds with HTTP 503 and reports the
application as healthy but its Qdrant dependency as unavailable. This check
only queries Qdrant connectivity; it does not create, clear, or modify a
collection.

### Register and log in

Registration requires a valid email and a password of 12–128 characters:

```powershell
curl.exe -X POST http://localhost:8000/api/v1/auth/register `
  -H "Content-Type: application/json" `
  -d '{ "email": "researcher@example.com", "password": "a-long-unique-password" }'
```

It returns HTTP 201 with the user UUID and normalized email (never the password
or password hash). A duplicate email returns HTTP 409.

Login uses JSON credentials:

```powershell
curl.exe -X POST http://localhost:8000/api/v1/auth/login `
  -H "Content-Type: application/json" `
  -d '{ "email": "researcher@example.com", "password": "a-long-unique-password" }'
```

Successful login returns an HS256 JWT with explicit `sub`, `iat`, `exp`, `iss`,
and `aud` claims. Invalid email/password combinations share the same HTTP 401
response. Send the access token in the standard HTTP Authorization bearer
header to both
`POST /api/v1/documents` and `POST /api/v1/search`. Missing, malformed, expired,
or invalid-signature tokens are rejected with HTTP 401.

API-indexed Qdrant chunks are tagged with the authenticated user's UUID and
point IDs are user-scoped; API search filters on that owner ID. Existing
unowned Qdrant points are left untouched and are not returned by authenticated
API search. The CLI retains its existing unfiltered collection behavior.
Ownership metadata is held in Qdrant; this phase does not add a separate
relational document catalog.

### Index an uploaded PDF

```powershell
curl.exe -X POST http://localhost:8000/api/v1/documents `
  -H "Authorization: Bearer <access_token>" `
  -F "file=@.\data\papers\sample_paper.pdf"
```

Successful requests return HTTP 201 and document metadata:

```json
{
  "document_id": "stable-document-id",
  "filename": "sample_paper.pdf",
  "chunks_indexed": 12
}
```

Only `.pdf` uploads are accepted. Empty, unreadable, or text-free PDFs receive
HTTP 422; files over `MAX_UPLOAD_BYTES` receive HTTP 413. Indexing uses the
existing extraction, chunking, embedding, and Qdrant pipeline.

### Search indexed content

```powershell
curl.exe -X POST http://localhost:8000/api/v1/search `
  -H "Authorization: Bearer <access_token>" `
  -H "Content-Type: application/json" `
  -d '{ "query": "How does the paper evaluate its method?" }'
```

Search returns up to five results with cosine scores and source page references:

```json
{
  "query": "How does the paper evaluate its method?",
  "results": [
    {
      "score": 0.82,
      "document_id": "stable-document-id",
      "filename": "sample_paper.pdf",
      "page_number": 3,
      "chunk_index": 4,
      "chunk_text": "..."
    }
  ]
}
```

Invalid search requests receive HTTP 422. Embedding and Qdrant failures return
HTTP 503 with a structured error code and message.

## Index a PDF

```powershell
python -m orchestrai_review2 index .\data\papers\research-paper.pdf
```

Optional chunk sizing is measured in words:

```powershell
python -m orchestrai_review2 index .\data\papers\research-paper.pdf --chunk-size 200 --overlap 40
```

Qdrant URL and collection can be configured with `QDRANT_URL` and
`QDRANT_COLLECTION`; defaults are `http://localhost:6333` and
`orchestrai_papers`. CLI options can override these settings. Put global options
before the subcommand:

```powershell
$env:QDRANT_URL = "http://localhost:6333"
$env:QDRANT_COLLECTION = "orchestrai_papers"
python -m orchestrai_review2 --qdrant-url http://localhost:6333 index .\data\papers\research-paper.pdf
```

Each stored point includes `chunk_text`, `document_id`, `filename`,
`page_number` (1-based), and `chunk_index` payload fields. Existing collections
are reused only when their vector size and cosine distance match this model.
Incompatible collections are left untouched and result in an error. Re-indexing
the same PDF updates its existing points; indexing a changed PDF adds a new
document ID and does not remove older points.

## Search

```powershell
python -m orchestrai_review2 search "How does the paper evaluate its method?"
```

Search returns up to five results as JSON, including cosine similarity scores
and their source metadata.

## Tests

From `backend`:

```powershell
python -m pytest
```

API tests use mocked retrieval services; the ordinary test suite does not
require a live Qdrant server.

## Scope and limitations

The API supports registration, login, authenticated PDF indexing and semantic
search, and health reporting. It does not include OCR, LLM-generated answers/
RAG, refresh tokens, password reset, OAuth, roles, or frontend functionality.
The embedding model may need to download on its first index or search request.
The health endpoint checks Qdrant connectivity, not whether the embedding model
or PostgreSQL is available. Existing unowned Qdrant content has no API owner
association and is intentionally excluded from authenticated API search.

## Troubleshooting

- **PDF not found:** verify the path exists; relative paths are resolved from
  the current directory.
- **Empty PDF / no extractable text:** scanned PDFs need OCR before indexing;
  OCR is not included in this prototype.
- **Encrypted or unreadable PDF:** provide an unencrypted, readable PDF.
- **Embedding model load/encode error:** check memory and network access for
  the initial model download, and retry after the model is cached.
- **Qdrant connection error:** verify Qdrant is running and that
  `QDRANT_URL` points to its reachable HTTP endpoint.
- **Collection dimension/distance mismatch:** choose another collection name
  or use a compatible collection. This tool deliberately does not modify or
  delete incompatible collections.
- **No collection on search:** index at least one PDF into the selected
  collection before searching.
