
from __future__ import annotations

from enum import Enum


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"  # some queries errored but run finished


class ResponseStatus(str, Enum):
    OK = "ok"
    API_ERROR = "api_error"      # HTTP/network error after retries
    INVALID = "invalid"          # response did not match contract
    TIMEOUT = "timeout"


class FailureType(str, Enum):

    SUCCESS = "success"
    NO_RETRIEVAL = "no_retrieval"                # empty knowledge_state
    WRONG_DOCUMENT = "wrong_document"            # docs retrieved but none GT
    PARTIAL_FACT_COVERAGE = "partial_fact_coverage"  # 0 < recall < 1
    IRRELEVANT_RETRIEVAL = "irrelevant_retrieval"    # recall==0 but nodes present
    EXACT_ANSWER_MISS = "exact_answer_miss"      # facts ok but EM==0
    LOW_RANK_RELEVANT_NODE = "low_rank_relevant_node"  # relevant node ranked low
    RESPONSE_INVALID = "response_invalid"        # payload unparseable
    API_ERROR = "api_error"                      # request failed entirely


class ScopeType(str, Enum):

    OVERALL = "overall"
    CATEGORY = "category"
    DIFFICULTY = "difficulty"
    FAILURE_TYPE = "failure_type"


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
