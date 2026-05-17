from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.contacts import router as contacts_router
from database.db import get_db

app = FastAPI(title="UMT pythonweb HW08")
app.include_router(contacts_router, prefix="/api")


@app.get("/api/healthchecker")
def healthcheck(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok"}
