"""
Extend Schema classes to include methods for persistence serialization.
"""
from models.schemas import Explanation
import json
from dataclasses import asdict

# Patch Explanation to have a JSON serializer helper if not already present
# (The original schemas.py defined to_dict but didn't explicitly check Explanation.to_json)

def explanation_to_json(self) -> str:
    """Serialize explanation to JSON string."""
    return json.dumps(asdict(self))

Explanation.to_json = explanation_to_json
