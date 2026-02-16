"""User persistence (JSON file + in-memory cache)."""
import json
import os
from typing import Dict, Optional

from app.domain.user import User


class UserRepository:
    """JSON-backed user storage."""

    def __init__(self, data_path: str = "data/users.json"):
        self._data_path = data_path
        self._users: Dict[str, User] = {}
        self._load()

    def save(self, user: User) -> None:
        """Persist user to file."""
        self._users[user.id] = user
        self._persist()

    def find_by_username(self, username: str) -> Optional[User]:
        """Lookup by username (case-insensitive)."""
        target = username.lower().strip()
        for user in self._users.values():
            if user.username == target:
                return user
        return None

    def find_by_email(self, email: str) -> Optional[User]:
        """Lookup by email (case-insensitive)."""
        target = email.lower().strip()
        for user in self._users.values():
            if user.email == target:
                return user
        return None

    def exists_username(self, username: str) -> bool:
        return self.find_by_username(username) is not None

    def exists_email(self, email: str) -> bool:
        return self.find_by_email(email) is not None

    def find_by_id(self, user_id: str) -> Optional[User]:
        """Lookup user by UUID string."""
        return self._users.get(user_id)

    def get_all(self) -> list:
        """Return all users."""
        return list(self._users.values())

    def update_password(self, user_id: str, new_hash: str, new_salt: str) -> None:
        """Update password hash and salt for a user."""
        user = self._users.get(user_id)
        if user:
            d = user.to_dict()
            d["password_hash"] = new_hash
            d["salt"] = new_salt
            self._users[user_id] = User(**{k: v for k, v in d.items() if k != "id"}, user_id=d["id"])
            self._persist()

    def update_last_login(self, user_id: str) -> None:
        """No-op for JSON backend (field not tracked)."""
        pass

    def _persist(self) -> None:
        """Write all users to JSON file."""
        os.makedirs(os.path.dirname(self._data_path), exist_ok=True)
        data = {}
        for uid, user in self._users.items():
            data[uid] = user.to_dict()
        with open(self._data_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _load(self) -> None:
        """Load users from JSON file."""
        if not os.path.exists(self._data_path):
            return
        try:
            with open(self._data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return
        for uid, udata in data.items():
            self._users[uid] = User(
                user_id=udata["id"],
                full_name=udata["full_name"],
                username=udata["username"],
                email=udata["email"],
                whatsapp=udata["whatsapp"],
                profession=udata["profession"],
                password_hash=udata["password_hash"],
                salt=udata["salt"],
                created_at=udata.get("created_at"),
            )
