"""
Pydantic models for LLM-structured output.
"""

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class Category(str, Enum):
    """Workload category for a cloud server type."""

    GENERAL_PURPOSE = "General Purpose"
    COMPUTE_OPTIMIZED = "Compute Optimized"
    MEMORY_OPTIMIZED = "Memory Optimized"
    STORAGE_AND_DATABASE = "Storage & Database"
    GPU_ACCELERATED = "GPU Accelerated"
    BURSTABLE_AND_BUDGET = "Burstable & Budget"


class ServerSummary(BaseModel):
    """Structured summary fields from the LLM."""

    page: list[str] = Field(
        description=(
            "Up to 500 words total across multiple paragraphs when warranted; "
            "each list item is one paragraph. "
            "Simple servers may use fewer words. Avoid repetition across paragraphs."
        )
    )
    description: str = Field(
        description=(
            "Around 150 words, up to 175, single paragraph, technical overview."
        )
    )
    og_description: str = Field(
        description=(
            "Around 200 characters, longer factual summary in encyclopedia style; "
            "include vendor and server name. No CTAs or reader invitations."
        )
    )
    meta_description: str = Field(
        description=(
            "Around 150 characters, factual HTML meta summary in encyclopedia style; "
            "include vendor and server name. No CTAs or reader invitations."
        )
    )
    tagline: str = Field(
        description=(
            "Around 20 words, readable tagline, "
            "without mentioning vendor or server name."
        )
    )
    bullet_points: list[str] = Field(
        description=(
            "4-6 concise bullet points highlighting key features "
            "and best-fit workloads."
        )
    )
    categories: list[Category] = Field(
        description=(
            "One or more workload categories for this server type, "
            "ordered by relevance (most fitting first)."
        )
    )

    @field_validator("page")
    @classmethod
    def validate_page(cls, v: list[str]) -> list[str]:
        assert len(v) >= 1, "page must have at least one paragraph"
        assert all(p.strip() for p in v), "page paragraphs must not be empty"
        n = sum(len(p.strip().split()) for p in v)
        assert n <= 500, f"page must be at most 500 words, got {n}"
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        n = len(v.strip().split())
        assert n <= 175, f"description must be at most 175 words, got {n}"
        return v

    @field_validator("og_description")
    @classmethod
    def validate_og_description(cls, v: str) -> str:
        n = len(v.strip())
        assert 175 <= n <= 225, f"og_description must be 175-225 characters, got {n}"
        return v

    @field_validator("meta_description")
    @classmethod
    def validate_meta_description(cls, v: str) -> str:
        n = len(v.strip())
        assert 125 <= n <= 175, (
            f"meta_description must be 125-175 characters, got {n}"
        )
        return v

    @field_validator("tagline")
    @classmethod
    def validate_tagline(cls, v: str) -> str:
        n = len(v.strip().split())
        assert 15 <= n <= 25, f"tagline must be 15-25 words, got {n}"
        return v

    @field_validator("bullet_points")
    @classmethod
    def validate_bullet_points(cls, v: list[str]) -> list[str]:
        assert 4 <= len(v) <= 6, f"bullet_points must have 4-6 items, got {len(v)}"
        return v

    @field_validator("categories")
    @classmethod
    def validate_categories(cls, v: list[Category]) -> list[Category]:
        assert 1 <= len(v) <= 3, f"categories must have 1-3 items, got {len(v)}"
        assert len(v) == len(set(v)), "categories must not contain duplicates"
        return v
