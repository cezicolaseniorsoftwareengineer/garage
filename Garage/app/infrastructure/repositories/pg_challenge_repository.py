"""PostgreSQL-backed challenge repository."""
from typing import List

from app.domain.challenge import Challenge, ChallengeOption
from app.domain.enums import ChallengeCategory, CareerStage, MapRegion
from app.infrastructure.database.models import ChallengeModel


class PgChallengeRepository:
    """Challenge persistence via PostgreSQL (Neon)."""

    def __init__(self, session_factory):
        self._sf = session_factory

    def get_all(self) -> List[Challenge]:
        try:
            with self._sf() as session:
                rows = session.query(ChallengeModel).all()
                return [self._to_domain(r) for r in rows]
        except Exception as exc:
            print(f"[GARAGE][ERROR] PgChallengeRepository.get_all() failed: {type(exc).__name__}: {exc}")
            raise

    def get_by_id(self, challenge_id: str) -> Challenge | None:
        try:
            with self._sf() as session:
                row = session.get(ChallengeModel, challenge_id)
                return self._to_domain(row) if row else None
        except Exception as exc:
            print(f"[GARAGE][ERROR] PgChallengeRepository.get_by_id({challenge_id!r}) failed: {exc}")
            raise

    def get_by_stage(self, stage: CareerStage) -> List[Challenge]:
        with self._sf() as session:
            rows = (
                session.query(ChallengeModel)
                .filter(ChallengeModel.required_stage == stage.value)
                .all()
            )
            return [self._to_domain(r) for r in rows]

    def get_by_region(self, region: MapRegion) -> List[Challenge]:
        with self._sf() as session:
            rows = (
                session.query(ChallengeModel)
                .filter(ChallengeModel.region == region.value)
                .all()
            )
            return [self._to_domain(r) for r in rows]

    def count(self) -> int:
        with self._sf() as session:
            return session.query(ChallengeModel).count()

    @staticmethod
    def _to_domain(row: ChallengeModel) -> Challenge:
        options = [
            ChallengeOption(
                text=opt["text"],
                is_correct=opt["is_correct"],
                explanation=opt["explanation"],
            )
            for opt in row.options
        ]
        return Challenge(
            challenge_id=row.id,
            title=row.title,
            description=row.description,
            context_code=row.context_code,
            category=ChallengeCategory(row.category),
            required_stage=CareerStage(row.required_stage),
            region=MapRegion(row.region),
            options=options,
            mentor_name=row.mentor,
            points_on_correct=row.points_on_correct,
        )
