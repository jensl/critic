from dataclasses import dataclass
from typing import Optional

from critic import api


@dataclass
class StepsTaken:
    strategy_used: Optional[api.review.IntegrationStrategy] = None
    squashed: Optional[bool] = None
    autosquashed: Optional[bool] = None
