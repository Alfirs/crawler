from fastapi import FastAPI

from app.routers import estimate, health, intake, mail, projects, reports, suppliers


def create_app() -> FastAPI:
    app = FastAPI(title="Project Intake and Procurement Automation")
    app.include_router(health.router)
    app.include_router(intake.router)
    app.include_router(estimate.router)
    app.include_router(suppliers.router)
    app.include_router(reports.router)
    app.include_router(mail.router)
    app.include_router(projects.router)
    return app


app = create_app()


@app.get("/")
async def root() -> dict:
    return {"status": "ok", "message": "Intake service is running"}
