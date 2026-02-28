"""Remove game_sessions and attempts orphaned by deleted users."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from app.infrastructure.database.connection import init_engine, get_session_factory
from sqlalchemy import text

init_engine()
sf = get_session_factory()

with sf() as sess:
    count = sess.execute(text("""
        SELECT COUNT(*) FROM game_sessions gs
        WHERE gs.user_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM users u WHERE u.id = gs.user_id)
    """)).scalar()
    print(f"Sessoes orfas encontradas: {count}")

    if count > 0:
        d1 = sess.execute(text("""
            DELETE FROM attempts WHERE session_id IN (
                SELECT gs.id FROM game_sessions gs
                WHERE gs.user_id IS NOT NULL
                  AND NOT EXISTS (SELECT 1 FROM users u WHERE u.id = gs.user_id)
            )
        """)).rowcount
        d2 = sess.execute(text("""
            DELETE FROM game_sessions
            WHERE user_id IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM users u WHERE u.id = user_id)
        """)).rowcount
        sess.commit()
        print(f"Limpeza concluida: {d1} attempts + {d2} sessoes deletadas.")
    else:
        print("Nenhuma sessao orfa — banco ja esta limpo.")
