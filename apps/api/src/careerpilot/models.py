"""Registers every module's tables on one metadata (used by Alembic and the drift test)."""

from careerpilot.core.db import Base
from careerpilot.modules.auth.models import AuthSession, User
from careerpilot.modules.prep.models import PrepDay, PrepPlan, PrepTopic, StudySession
from careerpilot.modules.tracker.models import (
    Application,
    ApplicationEvent,
    Company,
    Contact,
    Job,
)

# Importing the classes is what registers the tables; listing them keeps the import "used".
REGISTERED_MODELS = (
    User,
    AuthSession,
    Company,
    Job,
    Application,
    ApplicationEvent,
    Contact,
    PrepTopic,
    PrepDay,
    PrepPlan,
    StudySession,
)

metadata = Base.metadata
