from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.services.url_service import url_service

router = APIRouter(tags=["Redirection"])


@router.get(
    "/{short_code}",
    response_class=RedirectResponse,
    status_code=307,
    summary="Redirect to original target URL",
    description="Resolves short code via Read-Through Cache (or DB fallback), asynchronously tracks click analytics, and redirects.",
)
async def redirect_short_url(
    short_code: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Extract client metadata
    forwarded_for = request.headers.get("x-forwarded-for")
    client_ip = forwarded_for.split(",")[0].strip() if forwarded_for else (request.client.host if request.client else None)
    user_agent = request.headers.get("user-agent")
    referer = request.headers.get("referer")

    target_url = await url_service.resolve_url(
        db=db,
        short_code=short_code,
        client_ip=client_ip,
        user_agent=user_agent,
        referer=referer,
    )

    return RedirectResponse(url=target_url, status_code=307)
