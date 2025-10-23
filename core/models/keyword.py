"""Keyword data model"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Keyword:
    """Google Ads keyword model"""
    text: str
    match_type: str
    campaign_name: str
    ad_group_name: str
    impressions: int
    clicks: int
    cost: float
    conversions: float
    campaign_id: Optional[str] = None
    ad_group_id: Optional[str] = None
    
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
    
    def __str__(self) -> str:
        return f"{self.text} ({self.match_type})"
