"""Registers every module's tables on one metadata (used by Alembic and the drift test)."""

from careerpilot.core.db import Base
from careerpilot.modules.auth.models import AuthSession, User

# Importing the classes is what registers the tables; listing them keeps the import "used".
REGISTERED_MODELS = (User, AuthSession)

metadata = Base.metadata
