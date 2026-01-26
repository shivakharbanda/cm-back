from app.schemas.auth import (
    UserCreate,
    UserLogin,
    UserResponse,
    TokenResponse,
    RefreshTokenRequest,
)
from app.schemas.instagram import (
    InstagramAuthURL,
    InstagramCallbackRequest,
    InstagramAccountResponse,
    InstagramPostResponse,
)
from app.schemas.automation import (
    AutomationCreate,
    AutomationUpdate,
    AutomationResponse,
    DMSentLogResponse,
)
from app.schemas.bio_page import (
    BioPageCreate,
    BioPageUpdate,
    BioPageResponse,
    BioPagePublicResponse,
)
from app.schemas.bio_link import (
    BioLinkCreate,
    BioLinkUpdate,
    BioLinkResponse,
    BioLinkPublicResponse,
)
from app.schemas.bio_card import (
    BioCardCreate,
    BioCardUpdate,
    BioCardResponse,
    BioCardPublicResponse,
    CardSubmitRequest,
    CardSubmitResponse,
)
from app.schemas.page_item import (
    PageItemResponse,
    PageItemWithData,
    ReorderItem,
    ReorderRequest,
    PageItemsResponse,
)
from app.schemas.routing_rule import (
    RoutingRuleCreate,
    RoutingRuleUpdate,
    RoutingRuleResponse,
)
from app.schemas.lead import (
    LeadResponse,
    LeadListResponse,
)
from app.schemas.analytics import (
    ViewRequest,
    ClickRequest,
    ClickResponse,
    AnalyticsDatePoint,
    PageAnalyticsResponse,
    LinkAnalyticsItem,
    CardAnalyticsItem,
    ItemAnalyticsResponse,
    AnalyticsAggregateResponse,
)

__all__ = [
    "UserCreate",
    "UserLogin",
    "UserResponse",
    "TokenResponse",
    "RefreshTokenRequest",
    "InstagramAuthURL",
    "InstagramCallbackRequest",
    "InstagramAccountResponse",
    "InstagramPostResponse",
    "AutomationCreate",
    "AutomationUpdate",
    "AutomationResponse",
    "DMSentLogResponse",
    # Link-in-Bio schemas
    "BioPageCreate",
    "BioPageUpdate",
    "BioPageResponse",
    "BioPagePublicResponse",
    "BioLinkCreate",
    "BioLinkUpdate",
    "BioLinkResponse",
    "BioLinkPublicResponse",
    "BioCardCreate",
    "BioCardUpdate",
    "BioCardResponse",
    "BioCardPublicResponse",
    "CardSubmitRequest",
    "CardSubmitResponse",
    "PageItemResponse",
    "PageItemWithData",
    "ReorderItem",
    "ReorderRequest",
    "PageItemsResponse",
    "RoutingRuleCreate",
    "RoutingRuleUpdate",
    "RoutingRuleResponse",
    "LeadResponse",
    "LeadListResponse",
    "ViewRequest",
    "ClickRequest",
    "ClickResponse",
    "AnalyticsDatePoint",
    "PageAnalyticsResponse",
    "LinkAnalyticsItem",
    "CardAnalyticsItem",
    "ItemAnalyticsResponse",
    "AnalyticsAggregateResponse",
]
