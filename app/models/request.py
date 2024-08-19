from enum import Enum
from typing import Optional
from pydantic import BaseModel


class Presets(str, Enum):
    ULTRA_FAST='ultra_fast'
    FAST='fast'
    STANDARD='standard'
    HIGH_QUALITY='high_quality'
    
class TranscriptionRequest(BaseModel):
    text: str
    voice: str
    candidates: int = 1
    seed: Optional[int] = None
    cvvp_amount: float = 0.0
    output_path: Optional[str] = None
    preset: str = "ultra_fast"
    produce_debug_state: bool = True