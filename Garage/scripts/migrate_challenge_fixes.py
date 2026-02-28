"""
Migration: apply content fixes to existing challenge records in PostgreSQL.

Fixes applied:
1. principal_06_bradesco_ai — title/description/option text: "computacao" → "IA"
2. principal_13/14/15 — region: "Aurora Labs" → "Nexus Labs"
3. junior_07/08/09 (Disney) — mentor: null → "The Refactorer"
4. mid_07/08/09 (IBM) — mentor: null → "The Simplifier"
5. senior_10/11/12 (PayPal) — mentor: null → "The Pragmatist"
6. senior_13/14/15 (Netflix) — mentor: null → "The Pragmatist"

Usage:
    python scripts/migrate_challenge_fixes.py
"""
import sys
import os
from dotenv import load_dotenv

# Allow imports from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Load .env so DATABASE_URL is available
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(env_path)

from app.infrastructure.database.connection import init_engine, get_session_factory
from app.infrastructure.database.models import ChallengeModel

init_engine()
session_factory = get_session_factory()

MENTOR_FIXES = {
    # Disney — Junior stage
    "junior_07_disney_oop_encapsulation": "The Refactorer",
    "junior_08_disney_oop_interface":     "The Refactorer",
    "junior_09_disney_oop_polymorphism":  "The Refactorer",
    # IBM — Mid stage
    "mid_07_ibm_stack_applications":   "The Simplifier",
    "mid_08_ibm_expression_parsing":   "The Simplifier",
    "mid_09_ibm_time_complexity":       "The Simplifier",
    # PayPal — Senior stage
    "senior_10_paypal_string_hashing":  "The Pragmatist",
    "senior_11_paypal_anagram_fraud":   "The Pragmatist",
    "senior_12_paypal_idempotency":     "The Pragmatist",
    # Netflix — Senior stage
    "senior_13_netflix_sliding_window": "The Pragmatist",
    "senior_14_netflix_recommendation": "The Pragmatist",
    "senior_15_netflix_time_series":    "The Pragmatist",
}

REGION_FIXES = {
    "principal_13_nexus_labs_dp_concept":  "Nexus Labs",
    "principal_14_nexus_labs_dp_vs_greedy": "Nexus Labs",
    "principal_15_nexus_labs_memoization":  "Nexus Labs",
}

AI_TITLE_FIX_ID = "principal_06_bradesco_ai"
AI_TITLE_NEW    = "IA Explicável em Banking"
AI_DESC_NEW     = (
    "O Bradesco usa Inteligência Artificial para aprovar/negar crédito. "
    "Um cliente tem o crédito negado. Como garantir que o modelo não é discriminatório?"
)
# Fix the correct option text (index 1)
AI_OPTION_NEW_TEXT = (
    "IA Explicável (XAI): SHAP values para explicar cada decisão + "
    "fairness metrics (demographic parity, equalized odds) + auditoria periódica do modelo"
)

def run():
    updated = 0
    with session_factory() as session:
        # ── 1. Mentor fixes ────────────────────────────────────────────────
        for challenge_id, mentor in MENTOR_FIXES.items():
            row = session.get(ChallengeModel, challenge_id)
            if row is None:
                print(f"  [SKIP] {challenge_id} — not found in DB")
                continue
            if row.mentor == mentor:
                print(f"  [OK]   {challenge_id} — mentor already correct")
                continue
            row.mentor = mentor
            session.add(row)
            updated += 1
            print(f"  [FIX]  {challenge_id} — mentor → {mentor!r}")

        # ── 2. Region fixes ────────────────────────────────────────────────
        for challenge_id, region in REGION_FIXES.items():
            row = session.get(ChallengeModel, challenge_id)
            if row is None:
                print(f"  [SKIP] {challenge_id} — not found in DB")
                continue
            if row.region == region:
                print(f"  [OK]   {challenge_id} — region already correct")
                continue
            row.region = region
            session.add(row)
            updated += 1
            print(f"  [FIX]  {challenge_id} — region → {region!r}")

        # ── 3. IA title + option text fix ──────────────────────────────────
        row = session.get(ChallengeModel, AI_TITLE_FIX_ID)
        if row:
            changed = False
            if row.title != AI_TITLE_NEW:
                row.title = AI_TITLE_NEW
                changed = True
            if row.description != AI_DESC_NEW:
                row.description = AI_DESC_NEW
                changed = True
            # options is stored as JSONB list
            opts = list(row.options)  # copy to trigger SQLAlchemy dirty detection
            if opts and opts[1].get("text", "").startswith("computacao"):
                opts[1] = dict(opts[1], text=AI_OPTION_NEW_TEXT)
                row.options = opts
                changed = True
            if changed:
                session.add(row)
                updated += 1
                print(f"  [FIX]  {AI_TITLE_FIX_ID} — title/description/option corrected (IA)")
            else:
                print(f"  [OK]   {AI_TITLE_FIX_ID} — already correct")

        session.commit()

    print(f"\n✅ Migration complete — {updated} record(s) updated.")

if __name__ == "__main__":
    run()
