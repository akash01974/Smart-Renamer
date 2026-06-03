from pydantic import BaseModel


class Conflict(BaseModel):
    file_ids: list[str]
    proposed_name: str
    reason: str


class ValidationReport(BaseModel):
    conflicts: list[Conflict] = []
    warnings: list[str] = []
    suggestions: list[str] = []
