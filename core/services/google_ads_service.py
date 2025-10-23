"""
Core Google Ads API service with multi-account support
"""
import logging
import os
from typing import List, Optional, Dict
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

from core.config.settings import config
from core.models.account import Account
from core.models.campaign import Campaign
from core.models.keyword import Keyword

logger = logging.getLogger(__name__)


class GoogleAdsService:
    """Centralized Google Ads API service that can be configured per-user."""
    
    def __init__(self, user_credentials: Optional[Dict[str, str]] = None, google_ads_config=None):
        """
        Initialize Google Ads service
        
        Args:
            user_credentials: Optional dict with at least 'refresh_token' for user-specific auth
            google_ads_config: Optional custom config (legacy); ignored when user_credentials provided
        """
        if user_credentials and user_credentials.get("refresh_token"):
            # Initialize client with user-provided refresh token and Web App OAuth credentials
            client_config = {
                "developer_token": os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN"),
                "client_id": os.getenv("GOOGLE_OAUTH_CLIENT_ID"),
                "client_secret": os.getenv("GOOGLE_OAUTH_CLIENT_SECRET"),
                "refresh_token": user_credentials["refresh_token"],
                "use_proto_plus": True,
            }
            self.client = GoogleAdsClient.load_from_dict(client_config, version=config.google_ads.api_version)
            logger.info("GoogleAdsService initialized with user-specific credentials (Web App OAuth).")
        else:
            # Fallback to provided or global config
            self.config = google_ads_config or config.google_ads
            self.client = self._create_client()
            logger.info("GoogleAdsService initialized with global credentials.")
    
    def _create_client(self) -> GoogleAdsClient:
        """Create Google Ads client from config"""
        if not self.config.validate():
            raise ValueError("Google Ads credentials are incomplete")
        
        return GoogleAdsClient.load_from_dict(
            self.config.to_dict(),
            version=self.config.api_version
        )
    
    def format_customer_id(self, customer_id: str) -> str:
        """Format customer ID to 10 digits without dashes"""
        return ''.join(c for c in str(customer_id) if c.isdigit()).zfill(10)
    
    def get_accessible_accounts(self) -> List[Account]:
        """Get all accessible Google Ads accounts"""
        try:
            customer_service = self.client.get_service("CustomerService")
            accessible_customers = customer_service.list_accessible_customers()
            
            accounts = []
            googleads_service = self.client.get_service("GoogleAdsService")
            
            for resource_name in accessible_customers.resource_names:
                customer_id = resource_name.split('/')[-1]
                
                try:
                    query = """
                        SELECT customer.id, customer.descriptive_name, customer.manager,
                               customer.currency_code, customer.time_zone
                        FROM customer LIMIT 1
                    """
                    response = googleads_service.search(customer_id=customer_id, query=query)
                    
                    for row in response:
                        account = Account(
                            id=str(row.customer.id),
                            name=row.customer.descriptive_name,
                            is_manager=row.customer.manager,
                            currency=row.customer.currency_code,
                            timezone=row.customer.time_zone
                        )
                        accounts.append(account)
                        
                except GoogleAdsException as e:
                    logger.warning(f"Cannot access account {customer_id}: {e}")
                    continue
            
            return accounts
            
        except Exception as e:
            logger.error(f"Error fetching accounts: {e}")
            raise
    
    def get_campaigns(self, customer_id: str, days: int = 30, limit: int = 100) -> List[Campaign]:
        """
        Get campaigns for a specific account
        
        Args:
            customer_id: Google Ads customer ID
            days: Number of days to look back (default: 30)
            limit: Maximum campaigns to return (default: 100)
        
        Returns:
            List of Campaign objects
        """
        try:
            googleads_service = self.client.get_service("GoogleAdsService")
            formatted_id = self.format_customer_id(customer_id)
            
            query = f"""
                SELECT
                    campaign.id,
                    campaign.name,
                    campaign.status,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.cost_micros,
                    metrics.conversions
                FROM campaign
                WHERE segments.date DURING LAST_{days}_DAYS
                ORDER BY metrics.cost_micros DESC
                LIMIT {limit}
            """
            
            response = googleads_service.search(customer_id=formatted_id, query=query)
            
            campaigns = []
            for row in response:
                campaign = Campaign(
                    id=str(row.campaign.id),
                    name=row.campaign.name,
                    status=row.campaign.status.name,
                    impressions=row.metrics.impressions,
                    clicks=row.metrics.clicks,
                    cost=row.metrics.cost_micros / 1_000_000,
                    conversions=row.metrics.conversions,
                    account_id=formatted_id
                )
                campaigns.append(campaign)
            
            return campaigns
            
        except GoogleAdsException as e:
            logger.error(f"Error fetching campaigns for {customer_id}: {e}")
            raise
    
    def get_keywords(self, customer_id: str, campaign_id: Optional[str] = None,
                    days: int = 30, limit: int = 100) -> List[Keyword]:
        """
        Get keywords for a specific account
        
        Args:
            customer_id: Google Ads customer ID
            campaign_id: Optional campaign ID to filter by
            days: Number of days to look back (default: 30)
            limit: Maximum keywords to return (default: 100)
        
        Returns:
            List of Keyword objects
        """
        try:
            googleads_service = self.client.get_service("GoogleAdsService")
            formatted_id = self.format_customer_id(customer_id)
            
            campaign_filter = f"AND campaign.id = {campaign_id}" if campaign_id else ""
            
            query = f"""
                SELECT
                    campaign.id,
                    campaign.name,
                    ad_group.id,
                    ad_group.name,
                    ad_group_criterion.keyword.text,
                    ad_group_criterion.keyword.match_type,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.cost_micros,
                    metrics.conversions
                FROM keyword_view
                WHERE segments.date DURING LAST_{days}_DAYS {campaign_filter}
                ORDER BY metrics.cost_micros DESC
                LIMIT {limit}
            """
            
            response = googleads_service.search(customer_id=formatted_id, query=query)
            
            keywords = []
            for row in response:
                keyword = Keyword(
                    text=row.ad_group_criterion.keyword.text,
                    match_type=row.ad_group_criterion.keyword.match_type.name,
                    campaign_name=row.campaign.name,
                    ad_group_name=row.ad_group.name,
                    impressions=row.metrics.impressions,
                    clicks=row.metrics.clicks,
                    cost=row.metrics.cost_micros / 1_000_000,
                    conversions=row.metrics.conversions,
                    campaign_id=str(row.campaign.id),
                    ad_group_id=str(row.ad_group.id)
                )
                keywords.append(keyword)
            
            return keywords
            
        except GoogleAdsException as e:
            logger.error(f"Error fetching keywords for {customer_id}: {e}")
            raise
    
    def get_account_summary(self, customer_id: str, days: int = 30) -> dict:
        """
        Get performance summary for an account
        
        Args:
            customer_id: Google Ads customer ID
            days: Number of days to look back (default: 30)
        
        Returns:
            Dictionary with account performance metrics
        """
        try:
            googleads_service = self.client.get_service("GoogleAdsService")
            formatted_id = self.format_customer_id(customer_id)
            
            query = f"""
                SELECT
                    customer.id,
                    customer.descriptive_name,
                    customer.currency_code,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.cost_micros,
                    metrics.conversions,
                    metrics.conversions_value
                FROM customer
                WHERE segments.date DURING LAST_{days}_DAYS
            """
            
            response = googleads_service.search(customer_id=formatted_id, query=query)
            
            for row in response:
                cost = row.metrics.cost_micros / 1_000_000
                ctr = (row.metrics.clicks / row.metrics.impressions * 100) if row.metrics.impressions > 0 else 0
                cpc = (cost / row.metrics.clicks) if row.metrics.clicks > 0 else 0
                
                return {
                    "account_id": str(row.customer.id),
                    "account_name": row.customer.descriptive_name,
                    "currency": row.customer.currency_code,
                    "period_days": days,
                    "impressions": row.metrics.impressions,
                    "clicks": row.metrics.clicks,
                    "ctr": round(ctr, 2),
                    "cost": round(cost, 2),
                    "cpc": round(cpc, 2),
                    "conversions": round(row.metrics.conversions, 2),
                    "conversion_value": round(row.metrics.conversions_value, 2)
                }
            
            return {}
            
        except GoogleAdsException as e:
            logger.error(f"Error fetching summary for {customer_id}: {e}")
            raise
    
    def run_gaql_query(self, customer_id: str, query: str) -> list:
        """
        Execute a custom GAQL query
        
        Args:
            customer_id: Google Ads customer ID
            query: GAQL query string
        
        Returns:
            List of query results
        """
        try:
            googleads_service = self.client.get_service("GoogleAdsService")
            formatted_id = self.format_customer_id(customer_id)
            
            response = googleads_service.search(customer_id=formatted_id, query=query)
            
            return list(response)
            
        except GoogleAdsException as e:
            logger.error(f"Error executing GAQL query for {customer_id}: {e}")
            raise
