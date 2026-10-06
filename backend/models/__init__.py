"""SQLAlchemy models."""

from app.modules.images.models import (
    GeneratedImage,
    ImagePlacement,
    ImagePlan,
    ImageProvider,
    ImageVersion,
)
from database.base import Base
from models.accounts import (
    APIKey,
    Permission,
    Profile,
    RefreshToken,
    Role,
    RolePermission,
    Session,
    User,
    UserRole,
)
from models.ai_provider_config import AIProviderPreference
from models.ai_usage import AIUsageRecord
from models.assets import (
    BookSettings,
    DocumentAsset,
    ImageAsset,
    KDPValidationReport,
    MarketingAsset,
    TranslationRecord,
)
from models.book_writing import (
    BookBlueprint,
    BookBrief,
    ChapterVersion,
    Manuscript,
    TranslatedChapter,
    WritingBook,
    WritingBookSettings,
    WritingBookTranslation,
    WritingChapter,
    WritingSession,
)
from models.custom_ai_provider import CustomAIProvider
from models.document import Chapter, Paragraph, Part, Section, Sentence
from models.editing import (
    EditingSession,
    EditingSuggestion,
    ReviewJob,
    SuggestionBatch,
)
from models.operations import ActivityLog, AuditLog, Job, Notification
from models.project import Book, BookVersion, Folder, Project, ProjectSettings
from models.studio import Bookmark, ProjectActivity, ProjectVersion, StudioNotification
from models.workspace import Workspace, WorkspaceMember

__all__ = [
    "AIProviderPreference",
    "AIUsageRecord",
    "APIKey",
    "ActivityLog",
    "AuditLog",
    "Base",
    "Book",
    "BookBlueprint",
    "BookBrief",
    "BookSettings",
    "BookVersion",
    "Bookmark",
    "Chapter",
    "ChapterVersion",
    "CustomAIProvider",
    "EditingSession",
    "EditingSuggestion",
    "DocumentAsset",
    "Folder",
    "GeneratedImage",
    "ImageAsset",
    "Job",
    "ImagePlacement",
    "ImagePlan",
    "ImageProvider",
    "ImageVersion",
    "KDPValidationReport",
    "Manuscript",
    "MarketingAsset",
    "Notification",
    "Paragraph",
    "Part",
    "Permission",
    "Profile",
    "Project",
    "ProjectActivity",
    "ProjectSettings",
    "ProjectVersion",
    "RefreshToken",
    "ReviewJob",
    "Role",
    "RolePermission",
    "Section",
    "Sentence",
    "Session",
    "SuggestionBatch",
    "StudioNotification",
    "TranslationRecord",
    "TranslatedChapter",
    "WritingBookTranslation",
    "User",
    "UserRole",
    "WritingBook",
    "WritingBookSettings",
    "WritingChapter",
    "WritingSession",
    "Workspace",
    "WorkspaceMember",
]
