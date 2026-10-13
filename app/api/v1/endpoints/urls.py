from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.analytics import URLAnalyticsResponse
from app.schemas.url import URLCreateRequest, URLResponse, URLUpdateRequest
from app.services.url_service import url_service

router = APIRouter(prefix="/urls", tags=["URL Management"])


@router.post(
    "",
    response_model=URLResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Shorten a URL",
    description="Accepts a target URL, generates a Base62 short code or uses a custom alias, and writes to read-through cache.",
)
async def create_short_url(
    payload: URLCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    return await url_service.create_url(db=db, request=payload)


@router.get(
    "/{short_code}",
    response_model=URLResponse,
    summary="Get URL metadata",
    description="Retrieves metadata and current click count for a short code.",
)
async def get_url_details(
    short_code: str,
    db: AsyncSession = Depends(get_db),
):
    cached = await url_service.get_analytics(db=db, short_code=short_code)
    return URLResponse(
        short_code=cached.short_code,
        short_url=url_service._format_short_url(cached.short_code),
        original_url=cached.original_url,
        created_at=cached.created_at,
        expires_at=cached.expires_at,
        is_active=cached.is_active,
        click_count=cached.total_clicks,
    )


@router.get(
    "/{short_code}/analytics",
    response_model=URLAnalyticsResponse,
    summary="Get detailed click analytics",
    description="Returns aggregate clicks, 24h click history, and top referrers.",
)
async def get_url_analytics(
    short_code: str,
    db: AsyncSession = Depends(get_db),
):
    return await url_service.get_analytics(db=db, short_code=short_code)


@router.patch(
    "/{short_code}",
    response_model=URLResponse,
    summary="Update URL settings",
    description="Allows updating active status and expiration timestamp. Automatically invalidates cached entry.",
)
async def update_short_url(
    short_code: str,
    payload: URLUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    return await url_service.update_url(db=db, short_code=short_code, update_data=payload)


@router.delete(
    "/{short_code}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete short URL",
    description="Deletes short URL from database and immediately invalidates cache.",
)
async def delete_short_url(
    short_code: str,
    db: AsyncSession = Depends(get_db),
):
    await url_service.delete_url(db=db, short_code=short_code)
    return None
