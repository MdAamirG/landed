from fastapi import FastAPI

from app.routers import auth, driver, health, review

app = FastAPI(title="Landed API")

# Everything sits under /api, because Vercel forwards /api/* to this service unchanged.
app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(driver.router, prefix="/api")
app.include_router(review.router, prefix="/api")
