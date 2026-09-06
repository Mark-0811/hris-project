## Docker Setup

### 1. Create a Docker env file

Copy the example file:

```powershell
Copy-Item .env.docker.example .env.docker
```

Update the values in `.env.docker`, especially:

- `SECRET_KEY`
- `MAIL_USERNAME`
- `MAIL_PASSWORD`
- `FIRST_SUPERADMIN_PASSWORD`
- `BIOMETRIC_API_TOKEN`

### 2. Start HRIS with Docker

```powershell
docker compose up --build
```

This starts:

- `hris-web` on `http://127.0.0.1:5000`
- `hris-db` on PostgreSQL port `5432`

Image split:

- `hris-web:latest` (Flask app image)
- `hris-postgres:16` (dedicated PostgreSQL image)

### 3. What happens on startup

The app container will:

1. wait for PostgreSQL
2. run `flask db upgrade`
3. run `flask seed`
4. run `flask seed-demo` (idempotent demo records for users, attendance, tasks, payroll)
5. start HRIS

### 4. Stop the containers

```powershell
docker compose down
```

To also remove the PostgreSQL data volume:

```powershell
docker compose down -v
```

### 5. Default Docker database URL

Use this inside Docker:

```env
DATABASE_URL=postgresql+psycopg2://postgres:postgres@db:5432/hris_postgres
```

### 6. Open the app

- App: `http://127.0.0.1:5000`
- Login user: value from `FIRST_SUPERADMIN_USERNAME`
- Login password: value from `FIRST_SUPERADMIN_PASSWORD`
