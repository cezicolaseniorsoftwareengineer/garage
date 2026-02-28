"""PostgreSQL-backed user repository."""
from typing import Optional
from datetime import datetime, timezone

from app.domain.user import User
from app.infrastructure.database.models import UserModel, UserMetricsModel


class PgUserRepository:
    """User persistence via PostgreSQL (Neon)."""

    def __init__(self, session_factory):
        self._sf = session_factory

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save(self, user: User) -> None:
        """Insert or update a user record."""
        data = user.to_dict()
        with self._sf() as session:
            existing = session.get(UserModel, data["id"])
            if existing:
                existing.full_name = data["full_name"]
                existing.username = data["username"]
                existing.email = data["email"]
                existing.whatsapp = data["whatsapp"]
                existing.profession = data["profession"]
                existing.password_hash = data["password_hash"]
                existing.salt = data["salt"]
                existing.hash_algorithm = (
                    "bcrypt" if data["password_hash"].startswith("$2") else "sha256"
                )
                if "email_verified" in data:
                    existing.email_verified = data["email_verified"]
            else:
                created_at = data.get("created_at")
                if isinstance(created_at, str):
                    try:
                        created_at = datetime.fromisoformat(created_at)
                    except (ValueError, TypeError):
                        created_at = datetime.now(timezone.utc)
                else:
                    created_at = created_at or datetime.now(timezone.utc)

                model = UserModel(
                    id=data["id"],
                    full_name=data["full_name"],
                    username=data["username"],
                    email=data["email"],
                    whatsapp=data["whatsapp"],
                    profession=data["profession"],
                    password_hash=data["password_hash"],
                    salt=data["salt"],
                    hash_algorithm=(
                        "bcrypt" if data["password_hash"].startswith("$2") else "sha256"
                    ),
                    created_at=created_at,
                    email_verified=data.get("email_verified", False),
                )
                session.add(model)
                # Initialise empty metrics row for new users
                if not session.query(UserMetricsModel).filter_by(user_id=data["id"]).first():
                    session.add(UserMetricsModel(user_id=data["id"]))
            session.commit()

    def update_password(self, user_id: str, new_hash: str, new_salt: str) -> None:
        """Upgrade password hash (e.g. SHA-256 to bcrypt)."""
        with self._sf() as session:
            row = session.get(UserModel, user_id)
            if row:
                row.password_hash = new_hash
                row.salt = new_salt
                row.hash_algorithm = "bcrypt" if new_hash.startswith("$2") else "sha256"
                session.commit()

    def update_last_login(self, user_id: str) -> None:
        with self._sf() as session:
            row = session.get(UserModel, user_id)
            if row:
                row.last_login_at = datetime.now(timezone.utc)
                session.commit()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def find_by_username(self, username: str) -> Optional[User]:
        target = username.lower().strip()
        with self._sf() as session:
            row = session.query(UserModel).filter(UserModel.username == target).first()
            return self._to_domain(row) if row else None

    def find_by_email(self, email: str) -> Optional[User]:
        target = email.lower().strip()
        with self._sf() as session:
            row = session.query(UserModel).filter(UserModel.email == target).first()
            return self._to_domain(row) if row else None

    def find_by_id(self, user_id: str) -> Optional[User]:
        with self._sf() as session:
            row = session.get(UserModel, user_id)
            return self._to_domain(row) if row else None

    def exists_username(self, username: str) -> bool:
        return self.find_by_username(username) is not None

    def exists_email(self, email: str) -> bool:
        return self.find_by_email(email) is not None

    def exists_full_name(self, full_name: str) -> bool:
        """Return True if any user already has this display name (case-insensitive)."""
        target = full_name.strip().lower()
        with self._sf() as session:
            row = session.query(UserModel).filter(
                UserModel.full_name.ilike(target)
            ).first()
            return row is not None

    def get_all(self) -> list:
        """Return all registered users."""
        with self._sf() as session:
            rows = session.query(UserModel).order_by(UserModel.created_at.desc()).all()
            return [self._to_domain(r) for r in rows]

    def count(self) -> int:
        """Return total number of registered users."""
        with self._sf() as session:
            return session.query(UserModel).count()

    def delete_user(self, user_id: str) -> bool:
        """Permanently delete a user and all related data (cascade).

        Cascade order (FK dependencies):
          1. attempts         → FK game_sessions.id
          2. leaderboard_entries → FK users.id
          3. game_sessions    → FK users.id
          4. email_verifications → FK users.id
          5. user_metrics     → FK users.id
          6. game_events      → user_id (nullable, no hard FK)
          7. users            → the user row itself
        """
        from sqlalchemy import text
        with self._sf() as session:
            # Step 1: delete attempts belonging to this user's sessions
            try:
                session.execute(
                    text(
                        "DELETE FROM attempts WHERE session_id IN "
                        "(SELECT id FROM game_sessions WHERE user_id = :uid)"
                    ),
                    {"uid": user_id},
                )
            except Exception:
                session.rollback()

            # Steps 2-6: delete remaining FK-dependent rows keyed by user_id
            for table in (
                "leaderboard_entries",
                "game_sessions",
                "email_verifications",
                "user_metrics",
                "game_events",
            ):
                try:
                    session.execute(
                        text(f"DELETE FROM {table} WHERE user_id = :uid"),
                        {"uid": user_id},
                    )
                except Exception:
                    session.rollback()

            # Step 7: delete the user row
            row = session.query(UserModel).filter(UserModel.id == user_id).first()
            if not row:
                return False
            session.delete(row)
            session.commit()
            return True

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _to_domain(row: UserModel) -> User:
        return User(
            user_id=row.id,
            full_name=row.full_name,
            username=row.username,
            email=row.email,
            whatsapp=row.whatsapp,
            profession=row.profession,
            password_hash=row.password_hash,
            salt=row.salt,
            created_at=row.created_at.isoformat() if row.created_at else None,
            email_verified=bool(row.email_verified) if row.email_verified is not None else True,
        )
