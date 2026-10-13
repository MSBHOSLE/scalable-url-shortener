"""URL Shortener Service handling business logic, read-through caching, and analytics."""

from datetime import datetime, timedelta, timezone
import hashlib
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.models.click import ClickAnalytics
from app.models.url import URL
from app.schemas.analytics import ClickEventSchema, URLAnalyticsResponse
from app.schemas.url import URLCreateRequest, URLResponse, URLUpdateRequest
from app.services.base62 import encode_base62
from app.services.cache_service import cache_service


class URLService:
    @staticmethod
    def _hash_ip(ip: Optional[str]) -> Optional[str]:
        if not ip:
            return None
        return hashlib.sha256(ip.encode("utf-8")).hexdigest()

    @staticmethod
    def _format_short_url(short_code: str) -> str:
        return f"{settings.BASE_URL.rstrip('/')}/{short_code}"

    async def create_url(self, db: AsyncSession, request: URLCreateRequest) -> URLResponse:
        """Create a shortened URL, utilizing Base62 encoding or custom alias."""
        # Calculate expiration
        expires_at = None
        if request.expires_in_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=request.expires_in_days)
        elif settings.DEFAULT_EXPIRY_DAYS:
            expires_at = datetime.now(timezone.utc) + timedelta(days=settings.DEFAULT_EXPIRY_DAYS)

        # Check for custom code conflict
        if request.custom_code:
            existing = await db.scalar(
                select(URL).where(URL.short_code == request.custom_code)
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Custom short code '{request.custom_code}' is already in use.",
                )
            short_code = request.custom_code
            new_url = URL(
                short_code=short_code,
                original_url=request.original_url,
                expires_at=expires_at,
            )
            db.add(new_url)
            await db.commit()
            await db.refresh(new_url)
        else:
            # Create placeholder to generate sequence ID
            # In SQLite or PG, insert with a temporary token and then update with Base62
            temp_code = f"tmp_{int(datetime.now().timestamp() * 1000)}"
            new_url = URL(
                short_code=temp_code,
                original_url=request.original_url,
                expires_at=expires_at,
            )
            db.add(new_url)
            await db.flush()

            # Encode auto-generated ID using Base62
            short_code = encode_base62(new_url.id, min_length=settings.SHORT_CODE_MIN_LENGTH)
            new_url.short_code = short_code
            await db.commit()
            await db.refresh(new_url)

        # Populate read-through cache
        cache_data = {
            "id": new_url.id,
            "original_url": new_url.original_url,
            "is_active": new_url.is_active,
            "expires_at": new_url.expires_at.isoformat() if new_url.expires_at else None,
        }
        await cache_service.set_url(short_code, cache_data)

        return URLResponse(
            short_code=new_url.short_code,
            short_url=self._format_short_url(new_url.short_code),
            original_url=new_url.original_url,
            created_at=new_url.created_at,
            expires_at=new_url.expires_at,
            is_active=new_url.is_active,
            click_count=new_url.click_count,
        )

    async def resolve_url(
        self,
        db: AsyncSession,
        short_code: str,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        referer: Optional[str] = None,
    ) -> str:
        """Resolve short code to original URL using Read-Through cache with DB fallback."""
        now = datetime.now(timezone.utc)

        # 1. Read-Through Cache Check
        cached = await cache_service.get_url(short_code)
        if cached:
            # Validate expiration if cached
            if not cached.get("is_active", True):
                raise HTTPException(status_code=status.HTTP_410_GONE, detail="Short URL is inactive.")

            exp_str = cached.get("expires_at")
            if exp_str:
                exp_date = datetime.fromisoformat(exp_str)
                if now > (exp_date if exp_date.tzinfo else exp_date.replace(tzinfo=timezone.utc)):
                    await cache_service.invalidate_url(short_code)
                    raise HTTPException(status_code=status.HTTP_410_GONE, detail="Short URL has expired.")

            # Record click asynchronously
            await self._record_click_event(
                db=db,
                url_id=cached["id"],
                client_ip=client_ip,
                user_agent=user_agent,
                referer=referer,
            )
            return cached["original_url"]

        # 2. Database Fallback (Cache Miss)
        url_record = await db.scalar(
            select(URL).where(URL.short_code == short_code)
        )

        if not url_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Short code '{short_code}' not found.",
            )

        if not url_record.is_active:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Short URL is inactive.",
            )

        if url_record.is_expired():
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Short URL has expired.",
            )

        # Re-populate cache
        cache_data = {
            "id": url_record.id,
            "original_url": url_record.original_url,
            "is_active": url_record.is_active,
            "expires_at": url_record.expires_at.isoformat() if url_record.expires_at else None,
        }
        await cache_service.set_url(short_code, cache_data)

        # Record click
        await self._record_click_event(
            db=db,
            url_id=url_record.id,
            client_ip=client_ip,
            user_agent=user_agent,
            referer=referer,
        )

        return url_record.original_url

    async def _record_click_event(
        self,
        db: AsyncSession,
        url_id: int,
        client_ip: Optional[str],
        user_agent: Optional[str],
        referer: Optional[str],
    ) -> None:
        """Record click analytics event and update counter."""
        try:
            # Update counter atomically
            await db.execute(
                update(URL)
                .where(URL.id == url_id)
                .values(click_count=URL.click_count + 1)
            )

            # Insert event record
            click = ClickAnalytics(
                url_id=url_id,
                ip_hash=self._hash_ip(client_ip),
                user_agent=user_agent[:500] if user_agent else None,
                referer=referer[:500] if referer else None,
            )
            db.add(click)
            await db.commit()
        except Exception:
            await db.rollback()

    async def get_analytics(self, db: AsyncSession, short_code: str) -> URLAnalyticsResponse:
        """Fetch click analytics and statistics for a given short code."""
        url_record = await db.scalar(
            select(URL).where(URL.short_code == short_code)
        )

        if not url_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Short code '{short_code}' not found.",
            )

        # Clicks last 24h
        cutoff_24h = datetime.now(timezone.utc) - timedelta(hours=24)
        clicks_24h_count = await db.scalar(
            select(func.count(ClickAnalytics.id))
            .where(
                ClickAnalytics.url_id == url_record.id,
                ClickAnalytics.timestamp >= cutoff_24h,
            )
        ) or 0

        # Top referrers
        referrers_query = (
            select(ClickAnalytics.referer, func.count(ClickAnalytics.id).label("count"))
            .where(ClickAnalytics.url_id == url_record.id, ClickAnalytics.referer.isnot(None))
            .group_by(ClickAnalytics.referer)
            .order_by(func.count(ClickAnalytics.id).desc())
            .limit(5)
        )
        referrers_res = await db.execute(referrers_query)
        top_referrers = {row[0]: row[1] for row in referrers_res.all() if row[0]}

        # Recent events
        recent_query = (
            select(ClickAnalytics)
            .where(ClickAnalytics.url_id == url_record.id)
            .order_by(ClickAnalytics.timestamp.desc())
            .limit(10)
        )
        recent_res = await db.execute(recent_query)
        recent_events = [
            ClickEventSchema.model_validate(c) for c in recent_res.scalars().all()
        ]

        return URLAnalyticsResponse(
            short_code=url_record.short_code,
            original_url=url_record.original_url,
            total_clicks=url_record.click_count,
            created_at=url_record.created_at,
            expires_at=url_record.expires_at,
            is_active=url_record.is_active,
            top_referrers=top_referrers,
            clicks_last_24h=clicks_24h_count,
            recent_events=recent_events,
        )

    async def update_url(
        self,
        db: AsyncSession,
        short_code: str,
        update_data: URLUpdateRequest,
    ) -> URLResponse:
        """Update active status or expiration of a URL."""
        url_record = await db.scalar(
            select(URL).where(URL.short_code == short_code)
        )
        if not url_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Short code '{short_code}' not found.",
            )

        if update_data.is_active is not None:
            url_record.is_active = update_data.is_active
        if update_data.expires_at is not None:
            url_record.expires_at = update_data.expires_at

        await db.commit()
        await db.refresh(url_record)

        # Invalidate cache to guarantee read freshness
        await cache_service.invalidate_url(short_code)

        return URLResponse(
            short_code=url_record.short_code,
            short_url=self._format_short_url(url_record.short_code),
            original_url=url_record.original_url,
            created_at=url_record.created_at,
            expires_at=url_record.expires_at,
            is_active=url_record.is_active,
            click_count=url_record.click_count,
        )

    async def delete_url(self, db: AsyncSession, short_code: str) -> None:
        """Permanently delete a short URL and evict from cache."""
        url_record = await db.scalar(
            select(URL).where(URL.short_code == short_code)
        )
        if not url_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Short code '{short_code}' not found.",
            )

        await db.delete(url_record)
        await db.commit()
        await cache_service.invalidate_url(short_code)


url_service = URLService()
