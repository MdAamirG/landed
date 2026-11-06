"""The scenario picker's routes. They have no sign-in, because a reviewer opens the demo from a QR
code on their phone. Picking a scenario costs no Gemini call: only an upload does, and the upload
limit counts from the audit log, so resetting can't get round it.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.demo import SCENARIOS, require_demo_mode, start_scenario
from app.schemas import DemoScenarioOut, DemoStartOut

router = APIRouter(prefix="/demo", dependencies=[Depends(require_demo_mode)])


@router.get("/scenarios", response_model=list[DemoScenarioOut])
def scenarios() -> list[DemoScenarioOut]:
    return [DemoScenarioOut.model_validate(scenario) for scenario in SCENARIOS]


@router.post("/scenarios/{scenario_id}/start", response_model=DemoStartOut)
def start(scenario_id: str, db: Annotated[Session, Depends(get_db)]) -> DemoStartOut:
    return DemoStartOut(driver_token=start_scenario(db, scenario_id))
