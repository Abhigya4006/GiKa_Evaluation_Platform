
from __future__ import annotations


class GikaError(Exception):
    pass


class DatasetValidationError(GikaError):
    pass


class IngestionError(GikaError):
    pass


class RetrievalAPIError(GikaError):
    pass


class ResponseContractError(GikaError):
    pass


class RunNotFoundError(GikaError):
    pass
