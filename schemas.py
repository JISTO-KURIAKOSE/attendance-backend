from pydantic import BaseModel
from datetime import datetime

class Activity(BaseModel):
    id: int
    description: str
    timestamp: datetime
