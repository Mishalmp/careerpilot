from fastapi import APIRouter, status

from careerpilot.core.clock import today_in
from careerpilot.core.deps import AppSettings, DbSession
from careerpilot.modules.auth.dependencies import Authenticated
from careerpilot.modules.offers import service
from careerpilot.modules.offers.schemas import CompareOut, CompareRequest, RateIn, RateOut

router = APIRouter(prefix="/offers", tags=["offers"])


@router.get("/rates", operation_id="list_fx_rates")
async def list_rates(session: Authenticated, db: DbSession, settings: AppSettings) -> list[RateOut]:
    return await service.list_rates(db, session.user_id, today_in(settings.timezone))


@router.put("/rates", operation_id="set_fx_rate")
async def set_rate(
    body: RateIn, session: Authenticated, db: DbSession, settings: AppSettings
) -> RateOut:
    """Store the rate you want to use for a currency, with the date it is from."""
    return await service.set_rate(db, session.user_id, body, today_in(settings.timezone))


@router.delete(
    "/rates/{currency}", operation_id="delete_fx_rate", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_rate(currency: str, session: Authenticated, db: DbSession) -> None:
    await service.delete_rate(db, session.user_id, currency.upper())


@router.post("/compare", operation_id="compare_offers")
async def compare_offers(
    body: CompareRequest, session: Authenticated, db: DbSession, settings: AppSettings
) -> CompareOut:
    """Compare up to six offers in rupees using your stored rates. Nothing is saved."""
    return await service.compare(db, session.user_id, body, today_in(settings.timezone))
