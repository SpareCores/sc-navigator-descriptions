"""
Pydantic models for LLM-structured output.
"""

from pydantic import BaseModel, field_validator


class ServerSummary(BaseModel):
    """Structured summary fields from the LLM."""

    # tagline
    w20: str
    # meta description
    c150: str
    # OG description
    c200: str
    # full description
    w150: str

    @field_validator("w20")
    def validate_w20(cls, v: str) -> str:
        n = len(v.strip().split())
        assert 15 <= n <= 25, f"w20 must be 15-25 words, got {n}"
        return v

    @field_validator("c150")
    def validate_c150(cls, v: str) -> str:
        n = len(v.strip())
        assert 125 <= n <= 175, f"c150 must be 125-175 characters, got {n}"
        return v

    @field_validator("c200")
    def validate_c200(cls, v: str) -> str:
        n = len(v.strip())
        assert 175 <= n <= 225, f"c200 must be 175-225 characters, got {n}"
        return v

    @field_validator("w150")
    def validate_w150(cls, v: str) -> str:
        n = len(v.strip().split())
        assert 125 <= n <= 175, f"w150 must be 125-175 words, got {n}"
        return v
