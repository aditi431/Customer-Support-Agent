# Customer Care Frontend

React + Vite customer-facing starter using JavaScript, JSX, and custom CSS.

## Run

```powershell
npm install
npm run dev
```

Start FastAPI in another terminal from the project root:

```powershell
.\venv\Scripts\Activate.ps1
uvicorn app.api:app --reload --port 8000
```

Then start Vite from `frontend`. It proxies `/api` requests to
`http://127.0.0.1:8000` and injects `API_ACCESS_TOKEN` from the project-root
`.env` on the server side. The token is never sent to browser JavaScript.
Keep Vite bound to localhost; this development proxy is not a production
customer-authentication system.

To use another local backend, set `VITE_SUPPORT_API_PROXY` in the environment
before starting Vite:

```powershell
$env:VITE_SUPPORT_API_PROXY = "http://127.0.0.1:8001"
npm run dev
```

## Backend integration status

`src/services/supportApi.js` calls the existing `POST /api/chat` endpoint and
sends its request fields and required `Idempotency-Key`. The Vite development
proxy supplies the server-side `X-API-Key`; do not add `API_ACCESS_TOKEN` as a
`VITE_` variable or place it in browser storage. Restart both servers after
changing `.env`.

The backend has per-case status but no customer case-list or order-history
endpoints. My Cases therefore shows successful submissions from this browser
only; My Orders explains that live order history is not connected.
