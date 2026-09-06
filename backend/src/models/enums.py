from enum import Enum


class DocumentationStatus(str, Enum):
    """How well a condition is documented in the note.

    Mirrors the three examples the product brief gives.
    """

    WELL_DOCUMENTED = "well_documented"
    AMBIGUOUS = "ambiguous"
    MENTIONED_WITHOUT_PLAN = "mentioned_without_plan"


class GapSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AnalysisStatus(str, Enum):
    """Outcome of one analysis attempt.

    A failed attempt is still persisted — "the model returned garbage at 14:02"
    is data worth keeping, and it is what lets the UI be honest.
    """

    SUCCEEDED = "succeeded"
    INVALID_OUTPUT = "invalid_output"
    PROVIDER_ERROR = "provider_error"


class ProviderName(str, Enum):
    MOCK = "mock"
    GEMINI = "gemini"


class QuoteVerificationStatus(str, Enum):
    """How an evidence quote was located in the source note."""

    EXACT = "exact"
    NORMALIZED = "normalized"
    FUZZY = "fuzzy"
    # Every fragment of the quote is in the note, but not in this order and not
    # adjacent — the model built a "verbatim" quote out of real pieces. Not a
    # fabrication, and not evidence either: the passage it claims to quote does
    # not exist.
    ASSEMBLED = "assembled"
    NOT_FOUND = "not_found"


class ReviewStatus(str, Enum):
    PENDING = "pending"
    REVIEWED = "reviewed"


class ConditionOrigin(str, Enum):
    """Who first proposed a condition — the model, or the clinician."""

    AI = "ai"
    HUMAN = "human"


class ReviewAction(str, Enum):
    """What the clinician did with a condition."""

    ACCEPTED = "accepted"
    EDITED = "edited"
    REJECTED = "rejected"
    ADDED = "added"
