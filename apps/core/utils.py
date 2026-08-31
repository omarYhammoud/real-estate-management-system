"""Small shared helpers (money formatting, reference-number generation, etc.)."""
import uuid


def generate_reference(prefix: str) -> str:
    """e.g. generate_reference('INV') -> 'INV-3F2A9C1D'"""
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"
