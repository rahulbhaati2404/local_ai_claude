import re

# FAST REGEX ROUTER PATTERNS
SEARCH_PATTERNS = [
    r"top\s+\d+\s+stocks",
    r"breakout",
    r"best\s+stocks",
    r"find\s+stocks",
    r"stocks\s+to\s+buy",
]

ANALYSIS_PATTERNS = [
    r"analyze",
    r"analysis",
    r"technical",
    r"stock\s+review",
]

PORTFOLIO_PATTERNS = [
    r"portfolio",
    r"holdings",
    r"audit",
    r"my\s+stocks",
]

TICKER_REGEX = r"\b[A-Z]{2,15}\b"

# CLASSIFIER LABELS

INTENT_LABELS = [
    "SEARCH_WEB",
    "ANALYSIS",
    "MANAGER",
    "INVALID_DATA"
]