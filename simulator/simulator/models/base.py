
from enum import Enum
from pydantic import BaseModel


class ReadConsistency(Enum):
    LINEARIZABLE = 0  # Strongest, reads from leader.
    STALE = 1  # Lower latency, reads from any replica.


class Request(BaseModel):
    client_id: str
    request_id: str
    timestamp: float


from typing import Optional

class Response(BaseModel):
    request_id: str
    timestamp: float
    success: bool = True
    message: str = "OK"
    redirect_to: Optional[str] = None
