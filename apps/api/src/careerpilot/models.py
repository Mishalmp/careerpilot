"""Registers every module's tables on one metadata (used by Alembic and the drift test)."""

from careerpilot.core.audit import AuditEvent
from careerpilot.core.db import Base
from careerpilot.core.llm import LlmCall
from careerpilot.modules.apply.models import ApplyItem
from careerpilot.modules.auth.models import AuthSession, User
from careerpilot.modules.digest.models import Digest
from careerpilot.modules.discovery.models import DiscoveredJob, DiscoverySource
from careerpilot.modules.intel.models import IntelItem, IntelSource
from careerpilot.modules.knowledge.models import Chunk, Document
from careerpilot.modules.learn.models import (
    LearnAttempt,
    LearnCheckpoint,
    LearnCheckpointItem,
    LearnOption,
    LearnQuestion,
    LearnReviewCard,
    LearnSource,
    LearnTopic,
)
from careerpilot.modules.mock.models import MockSession
from careerpilot.modules.offers.models import FxRate
from careerpilot.modules.outreach.models import OutreachDraft
from careerpilot.modules.practice.models import Submission
from careerpilot.modules.prep.models import PrepDay, PrepPlan, PrepTopic, StudySession
from careerpilot.modules.profile.models import UserProfile
from careerpilot.modules.research.models import ResearchFinding, ResearchRun
from careerpilot.modules.scoring.models import JobScore
from careerpilot.modules.stories.models import StarStory
from careerpilot.modules.tasks.models import Task, TaskEvent
from careerpilot.modules.tracker.models import (
    Application,
    ApplicationEvent,
    Company,
    Contact,
    Job,
)
from careerpilot.modules.verification.models import CompanyCheck

# Importing the classes is what registers the tables; listing them keeps the import "used".
REGISTERED_MODELS = (
    ApplyItem,
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
    CompanyCheck,
    JobScore,
    OutreachDraft,
    IntelSource,
    IntelItem,
    MockSession,
    DiscoverySource,
    DiscoveredJob,
    Task,
    TaskEvent,
    Digest,
    FxRate,
    StarStory,
    LearnTopic,
    LearnQuestion,
    LearnOption,
    LearnSource,
    LearnAttempt,
    LearnReviewCard,
    LearnCheckpoint,
    LearnCheckpointItem,
    UserProfile,
    ResearchRun,
    ResearchFinding,
    Submission,
    Document,
    Chunk,
    LlmCall,
    AuditEvent,
)

metadata = Base.metadata
