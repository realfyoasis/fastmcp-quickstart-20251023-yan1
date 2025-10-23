"""Account data model"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Account:
    """Google Ads account model"""
    id: str
    name: str
    is_manager: bool
    currency: Optional[str] = None
    timezone: Optional[str] = None
    status: Optional[str] = None
    
    def __str__(self) -> str:
        account_type = "Manager" if self.is_manager else "Client"
        return f"[{account_type}] {self.name} (ID: {self.id})"
