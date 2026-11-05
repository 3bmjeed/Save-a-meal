# Happy Meal

**Rescue Food. Save Money. Reduce Waste.**

A runnable full-stack MVP connecting customers with discounted surplus food and supporting restaurant approval, reservations, charity donations, and impact reporting. React/Vite frontend + Flask REST API + SQLAlchemy (SQLite by default). Database monetary fields use integer minor units (for the demo, 100 units = EGP 1.00).

## Architecture

- `frontend/`: React, Vite, React Router, Tailwind CSS, Lucide React, Recharts dependency.
- `backend/app.py`: Flask app, SQLAlchemy models, JWT authentication, role checks, and REST endpoints.
- `backend/seed.py`: development-only demo data.
- `backend/test_app.py`: starter API tests.

## Implemented in this MVP

- Registration, login, hashed passwords, JWT authentication, role-based protected endpoints.
- Public food listing browse/search/category filtering and listing detail.
- Restaurant listing creation/editing for approved restaurants.
- Reservation checkout with server-side pricing, pickup-time checks, inventory decrement, and eligible cancellation inventory restoration.
- Customer favorites, reviews gated to completed orders, and in-app notifications.
- Restaurant and charity account approval workflow; admin can approve restaurants.
- Donation creation, charity claiming, status tracking, and conflict prevention for already-claimed donations.
- Role-based dashboards and impact totals calculated from database records. Carbon savings are not claimed.
- Responsive landing page, browse, login/register, cart, dashboard, and impact pages.

## Prerequisites

- Python 3.10+ (3.11/3.12 recommended)
- Node.js 20+ and npm

## Run locally (Windows PowerShell)

### One-click Windows start

Install Python 3.10+ and Node.js 20+ (including npm), then double-click `start.bat` in the project folder. On first run it creates the backend virtual environment, installs required packages, copies `backend/.env.example` to `backend/.env` only if needed, seeds demo accounts and meals only for the default local SQLite database, and starts the API and frontend in separate terminal windows. It then opens `http://127.0.0.1:5173`.

The first run needs an internet connection to install Python and npm packages. Keep both terminal windows open while using the app. Existing environment settings, accounts, approvals, and meal inventory are preserved. When the database has no available meals, the seed script refreshes pickup deadlines only for active demo meals that still have stock; sold-out inventory is never replenished. If you have configured a non-default `DATABASE_URL`, the launcher skips seeding.

### 1. Backend

```powershell
cd save-a-meal\backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
py seed.py
py app.py
```

The API runs at `http://127.0.0.1:5000`. A health check is available at `http://127.0.0.1:5000/api/health`.

On macOS/Linux, use `python3 -m venv .venv`, `source .venv/bin/activate`, `cp .env.example .env`, and `python seed.py` / `python app.py`.

### 2. Frontend (in a second terminal)

```powershell
cd save-a-meal\frontend
npm install
npm run dev
```

Open the local URL printed by Vite (normally `http://127.0.0.1:5173`). To use another API host, create `frontend/.env` containing `VITE_API_URL=http://127.0.0.1:5000/api`.

### 3. Tests and production build

```powershell
cd save-a-meal\backend
py -m pytest -q
```

```powershell
cd save-a-meal\frontend
npm run build
```

## Demo accounts (development only)

All accounts use seeded data. Change these before any shared deployment.

| Role | Email | Password |
|---|---|---|
| Administrator | `admin@saveameal.local` | `Admin123!` |
| Customer | `customer@saveameal.local` | `Customer123!` |
| Restaurant | `restaurant@saveameal.local` | `Restaurant123!` |
| Charity partner | `charity@saveameal.local` | `Charity123!` |

The seed script preserves existing users, passwords, restaurant approvals, and meal inventory. It creates any missing demo accounts and, when there are no currently available meals, refreshes the pickup deadline of remaining active demo meals. It does not replenish sold-out inventory. To reset the local development database, stop the backend and delete `backend/instance/save_a_meal.db` if present, then rerun `py seed.py`.

## Main API routes

- `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`
- `GET /api/listings`, `GET /api/listings/:id`, `POST /api/listings`, `PATCH /api/listings/:id`
- `POST /api/orders`, `GET /api/orders`, `PATCH /api/orders/:id`
- `GET /api/favorites`, `POST /api/favorites/:listing_id`, `DELETE /api/favorites/:listing_id`
- `POST /api/reviews`
- `GET /api/notifications`, `PATCH /api/notifications/:id`
- `POST /api/donations`, `GET /api/donations`, `PATCH /api/donations/:id/claim`, `PATCH /api/donations/:id`
- `GET /api/impact`, `GET /api/dashboard`
- `GET /api/admin/restaurants`, `PATCH /api/admin/restaurants/:id`

Protected routes expect `Authorization: Bearer <access_token>`.

## Production notes and current limitations

This is a runnable starter/MVP, not a security-audited production deployment. Before public launch, add migrations (e.g. Flask-Migrate/Alembic), rate limiting, email verification/password reset, stricter state-transition policies, CSRF protections if switching to cookies, structured logs/monitoring, backups, pagination, stronger transaction/concurrency tests for the target database, and a production WSGI server. Configure a strong secret in environment variables and restrict `FRONTEND_ORIGIN`. Use PostgreSQL by setting `DATABASE_URL` to a PostgreSQL SQLAlchemy URL. Image URLs are externally hosted demo assets; upload handling is not implemented. Notifications are in-app database records only; no email/SMS is sent. Checkout does not collect online payments; payment is at pickup. Search currently supports meal/restaurant text and category; location and discount filters are not yet exposed in the UI. Admin management currently provides restaurant approval and dashboard counts; customer/charity suspension and complaint management need further implementation. `Recharts` is installed as a dependency but charts are not yet wired into dashboard screens.

Impact calculations count quantities from completed orders, estimate savings against the listing's current original price, and count completed donation quantities. For fully historically accurate savings, persist original-price snapshots on each order item; this MVP snapshots the discounted unit price only. No carbon-emission savings are reported.
