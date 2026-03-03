"""Repository for landing page analytics events."""
from datetime import datetime, timezone, timedelta
from sqlalchemy import text

from app.infrastructure.database.models import LandingEventModel


class PgLandingAnalyticsRepository:
    def __init__(self, session_factory):
        self._sf = session_factory

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def record(
        self,
        visitor_id: str,
        event_type: str,
        element: str | None = None,
        section: str | None = None,
        scroll_pct: int | None = None,
        plan: str | None = None,
        referrer: str | None = None,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        with self._sf() as session:
            row = LandingEventModel(
                visitor_id=visitor_id,
                event_type=event_type,
                element=element,
                section=section,
                scroll_pct=scroll_pct,
                plan=plan,
                referrer=(referrer or "")[:500] if referrer else None,
                user_agent=(user_agent or "")[:200] if user_agent else None,
                ip_address=ip_address,
            )
            session.add(row)
            session.commit()

    # ------------------------------------------------------------------
    # Read — summary for admin panel
    # ------------------------------------------------------------------

    def summary(self) -> dict:
        with self._sf() as session:
            now = datetime.now(timezone.utc)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = now - timedelta(days=7)

            def q(sql: str, params: dict | None = None):
                return session.execute(text(sql), params or {}).fetchall()

            # Total visits (page_view events)
            total_visits = q(
                "SELECT COUNT(*) FROM landing_events WHERE event_type='page_view'"
            )[0][0]

            # Unique visitors (distinct visitor_id on page_view)
            unique_visitors = q(
                "SELECT COUNT(DISTINCT visitor_id) FROM landing_events WHERE event_type='page_view'"
            )[0][0]

            # Today
            today_visits = q(
                "SELECT COUNT(*) FROM landing_events WHERE event_type='page_view' AND created_at >= :ts",
                {"ts": today_start},
            )[0][0]

            today_unique = q(
                "SELECT COUNT(DISTINCT visitor_id) FROM landing_events WHERE event_type='page_view' AND created_at >= :ts",
                {"ts": today_start},
            )[0][0]

            # Checkout clicks per plan
            checkout_rows = q(
                """
                SELECT plan, COUNT(*) as cnt
                FROM landing_events
                WHERE event_type='checkout_click' AND plan IS NOT NULL
                GROUP BY plan
                """
            )
            checkout_clicks = {r[0]: r[1] for r in checkout_rows}
            total_checkout = sum(checkout_clicks.values())

            # Conversion rate = checkout_clicks / unique_visitors
            conv_rate = (
                f"{round(total_checkout / unique_visitors * 100, 1)}%"
                if unique_visitors > 0 else "0%"
            )

            # Top clicked buttons
            top_buttons = q(
                """
                SELECT element, COUNT(*) as cnt
                FROM landing_events
                WHERE event_type IN ('click','checkout_click') AND element IS NOT NULL
                GROUP BY element
                ORDER BY cnt DESC
                LIMIT 10
                """
            )

            # Visits per day — last 7 days
            daily_rows = q(
                """
                SELECT DATE(created_at AT TIME ZONE 'UTC') as day, COUNT(*) as cnt
                FROM landing_events
                WHERE event_type='page_view' AND created_at >= :ts
                GROUP BY day
                ORDER BY day
                """,
                {"ts": week_start},
            )
            visits_7d = [{"date": str(r[0]), "visits": r[1]} for r in daily_rows]

            # Scroll depth distribution
            scroll_rows = q(
                """
                SELECT
                    COUNT(*) FILTER (WHERE scroll_pct >= 25) as p25,
                    COUNT(*) FILTER (WHERE scroll_pct >= 50) as p50,
                    COUNT(*) FILTER (WHERE scroll_pct >= 75) as p75,
                    COUNT(*) FILTER (WHERE scroll_pct >= 100) as p100
                FROM landing_events
                WHERE event_type='scroll_depth'
                """
            )
            sd = scroll_rows[0] if scroll_rows else (0, 0, 0, 0)

            # Most viewed sections
            section_rows = q(
                """
                SELECT section, COUNT(*) as cnt
                FROM landing_events
                WHERE event_type='section_view' AND section IS NOT NULL
                GROUP BY section
                ORDER BY cnt DESC
                """
            )

            return {
                "total_visits": total_visits,
                "unique_visitors": unique_visitors,
                "today_visits": today_visits,
                "today_unique": today_unique,
                "checkout_clicks": checkout_clicks,
                "total_checkout_clicks": total_checkout,
                "conversion_rate": conv_rate,
                "top_buttons": [{"element": r[0], "count": r[1]} for r in top_buttons],
                "visits_7d": visits_7d,
                "scroll_depth": {"p25": sd[0], "p50": sd[1], "p75": sd[2], "p100": sd[3]},
                "top_sections": [{"section": r[0], "count": r[1]} for r in section_rows],
            }

    def recent_events(self, limit: int = 100) -> list:
        with self._sf() as session:
            rows = session.execute(
                text("""
                    SELECT id, visitor_id, event_type, element, section, scroll_pct,
                           plan, referrer, ip_address, created_at
                    FROM landing_events
                    ORDER BY created_at DESC
                    LIMIT :lim
                """),
                {"lim": limit},
            ).fetchall()
            return [
                {
                    "id": r[0],
                    "visitor_id": r[1][:8] + "...",
                    "event_type": r[2],
                    "element": r[3],
                    "section": r[4],
                    "scroll_pct": r[5],
                    "plan": r[6],
                    "referrer": r[7],
                    "ip": r[8],
                    "created_at": r[9].isoformat() if r[9] else None,
                }
                for r in rows
            ]
