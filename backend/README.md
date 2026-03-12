# Backend

FastAPI backend for system dynamics simulation and explanation.

## Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

## Structure

- `app/main.py`: API entry
- `app/routes/`: route modules
- `app/services/`: business logic
- `app/models/`: internal backend models/schemas helpers
- `app/utils/`: utility helpers
