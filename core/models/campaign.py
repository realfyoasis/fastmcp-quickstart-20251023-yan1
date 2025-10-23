"""Campaign data model"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Campaign:
    """Google Ads campaign model"""
    id: str
    name: str
    status: str
    impressions: int
    clicks: int
    cost: float
    conversions: float
    account_id: Optional[str] = None
    
    @property
    def ctr(self) -> float:
        """Calculate Click-Through Rate"""
        if self.impressions == 0:
            return 0.0
        return (self.clicks / self.impressions) * 100
    
    @property
    def cpc(self) -> float:
        """Calculate Cost Per Click"""
        if self.clicks == 0:
            return 0.0
        return self.cost / self.clicks
    
    @property
    def cpa(self) -> float:
        """Calculate Cost Per Acquisition"""
        if self.conversions == 0:
            return 0.0
        return self.cost / self.conversions
    
    def __str__(self) -> str:
        return f"{self.name} (ID: {self.id}) - Status: {self.status}"
