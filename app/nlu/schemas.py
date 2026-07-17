"""Extraction output shape shared by the rule-based and LLM extractors."""

from pydantic import BaseModel

from app.state.models import Intent, Timeline


class ExtractedFields(BaseModel):
    intent: Intent | None = None
    locality: str | None = None
    budget_min: int | None = None
    budget_max: int | None = None
    bhk: int | None = None
    timeline: Timeline | None = None


def merge_preferring(
    primary: ExtractedFields, secondary: ExtractedFields
) -> ExtractedFields:
    """Field-wise merge of two extractions; primary's non-null values win."""
    return ExtractedFields(
        **{
            field: (
                getattr(primary, field)
                if getattr(primary, field) is not None
                else getattr(secondary, field)
            )
            for field in ExtractedFields.model_fields
        }
    )
