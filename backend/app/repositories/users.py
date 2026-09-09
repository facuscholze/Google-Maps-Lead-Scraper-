"""User / workspace repositories."""
from __future__ import annotations

from sqlalchemy import select

from app.models.user import User, Workspace
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    def by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email.lower()))

    def by_workspace(self, workspace_id: int, user_id: int) -> User | None:
        return self.db.scalar(
            select(User).where(User.workspace_id == workspace_id, User.id == user_id)
        )


class WorkspaceRepository(BaseRepository[Workspace]):
    model = Workspace

    def by_name(self, name: str) -> Workspace | None:
        return self.db.scalar(select(Workspace).where(Workspace.name == name))
