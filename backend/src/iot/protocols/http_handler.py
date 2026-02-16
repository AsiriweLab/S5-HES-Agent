"""
HTTP/REST Protocol Handler - Implementation for REST API communication.

Sprint 11 - S11.5: Implement HTTPRESTHandler

Features:
- Full HTTP method support (GET, POST, PUT, DELETE, PATCH)
- Request/response headers
- Query parameters
- Async HTTP client using httpx
- Request retries with backoff
- Connection pooling
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import secrets
import hashlib
import base64
import hmac
from enum import Enum
from typing import Any, Callable, Coroutine, Optional
from urllib.parse import urljoin, urlencode
from uuid import uuid4
from loguru import logger

from .base_handler import (
    AbstractProtocolHandler,
    ProtocolType,
    ProtocolConfig,
    ProtocolMessage,
    ConnectionState,
    QoSLevel,
    MessageCallback,
    AsyncMessageCallback,
)


class HTTPMethod(str, Enum):
    """HTTP methods."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class OAuthGrantType(str, Enum):
    """OAuth 2.0 grant types."""
    AUTHORIZATION_CODE = "authorization_code"
    CLIENT_CREDENTIALS = "client_credentials"
    REFRESH_TOKEN = "refresh_token"
    DEVICE_CODE = "urn:ietf:params:oauth:grant-type:device_code"


@dataclass
class OAuthConfig:
    """OAuth 2.0 configuration."""
    enabled: bool = False
    client_id: str = ""
    client_secret: str = ""
    authorization_url: str = ""  # /authorize endpoint
    token_url: str = ""  # /token endpoint
    redirect_uri: str = "http://localhost:8080/callback"
    scope: str = ""
    grant_type: OAuthGrantType = OAuthGrantType.CLIENT_CREDENTIALS

    # For device code flow
    device_authorization_url: str = ""

    # Token storage
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None


@dataclass
class OAuthTokenResponse:
    """OAuth token response."""
    access_token: str
    token_type: str = "Bearer"
    expires_in: Optional[int] = None
    refresh_token: Optional[str] = None
    scope: Optional[str] = None
    id_token: Optional[str] = None  # For OIDC

    @classmethod
    def from_dict(cls, data: dict) -> "OAuthTokenResponse":
        return cls(
            access_token=data.get("access_token", ""),
            token_type=data.get("token_type", "Bearer"),
            expires_in=data.get("expires_in"),
            refresh_token=data.get("refresh_token"),
            scope=data.get("scope"),
            id_token=data.get("id_token"),
        )


@dataclass
class HTTPConfig(ProtocolConfig):
    """HTTP-specific configuration."""
    port: int = 80
    base_url: str = ""
    # Default headers
    default_headers: dict[str, str] = field(default_factory=lambda: {
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    # Retry settings
    max_retries: int = 3
    retry_backoff: float = 1.0
    # Connection settings
    max_connections: int = 100
    http2: bool = True
    # Authentication
    auth_type: str = "none"  # none, basic, bearer, api_key, oauth2
    api_key: Optional[str] = None
    api_key_header: str = "X-API-Key"
    bearer_token: Optional[str] = None
    # OAuth 2.0 configuration
    oauth: Optional[OAuthConfig] = None


@dataclass
class HTTPResponse:
    """HTTP response container."""
    status_code: int
    headers: dict[str, str]
    body: Any
    elapsed: float  # Request time in seconds

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    @property
    def is_error(self) -> bool:
        return self.status_code >= 400


class HTTPRESTHandler(AbstractProtocolHandler):
    """
    HTTP/REST Protocol Handler for IoT cloud communication.

    Provides async HTTP client functionality for:
    - IoT platform APIs
    - Cloud service endpoints
    - Device management APIs
    """

    def __init__(self, config: HTTPConfig):
        """
        Initialize HTTP handler.

        Args:
            config: HTTP configuration
        """
        super().__init__(config)
        self.http_config = config
        self._client = None
        self._base_url = config.base_url or f"http://{config.host}:{config.port}"

        # Webhook subscriptions (simulated push notifications)
        self._webhooks: dict[str, list[MessageCallback | AsyncMessageCallback]] = {}

        # Polling tasks for subscription simulation
        self._polling_tasks: dict[str, asyncio.Task] = {}

        # Simulation mode
        self._simulation_mode = config.extra_config.get("simulation_mode", True)

        # Mock responses for simulation
        self._mock_data: dict[str, Any] = {}

    @property
    def protocol_type(self) -> ProtocolType:
        return ProtocolType.HTTP

    async def connect(self) -> bool:
        """
        Initialize HTTP client connection pool.
        """
        if self.state == ConnectionState.CONNECTED:
            return True

        self.state = ConnectionState.CONNECTING
        logger.info(f"Initializing HTTP client for {self._base_url}")

        try:
            if self._simulation_mode:
                await asyncio.sleep(0.05)
                self.state = ConnectionState.CONNECTED
                self.stats.connected_since = datetime.now()
                logger.info("HTTP handler ready (simulation mode)")
                return True
            else:
                try:
                    import httpx

                    # Build headers with authentication
                    headers = dict(self.http_config.default_headers)

                    if self.http_config.auth_type == "bearer" and self.http_config.bearer_token:
                        headers["Authorization"] = f"Bearer {self.http_config.bearer_token}"
                    elif self.http_config.auth_type == "api_key" and self.http_config.api_key:
                        headers[self.http_config.api_key_header] = self.http_config.api_key

                    # Create async client
                    self._client = httpx.AsyncClient(
                        base_url=self._base_url,
                        headers=headers,
                        timeout=self.config.connection_timeout,
                        http2=self.http_config.http2,
                        limits=httpx.Limits(max_connections=self.http_config.max_connections),
                    )

                    # Test connection
                    # response = await self._client.get("/health")

                    self.state = ConnectionState.CONNECTED
                    self.stats.connected_since = datetime.now()
                    logger.info("HTTP client initialized")
                    return True

                except ImportError:
                    logger.warning("httpx not available, using simulation mode")
                    self._simulation_mode = True
                    return await self.connect()

        except Exception as e:
            logger.error(f"HTTP client initialization error: {e}")
            self.state = ConnectionState.ERROR
            self.stats.record_error()
            return False

    async def disconnect(self) -> None:
        """Close HTTP client."""
        logger.info("Closing HTTP client")

        # Cancel polling tasks
        for task in self._polling_tasks.values():
            task.cancel()
        self._polling_tasks.clear()

        if self._client:
            await self._client.aclose()
            self._client = None

        self.state = ConnectionState.DISCONNECTED
        logger.info("HTTP client closed")

    async def publish(self, message: ProtocolMessage) -> bool:
        """
        Publish data via HTTP POST.

        Args:
            message: Message with topic as path and payload as body

        Returns:
            True if successful
        """
        response = await self.request(
            HTTPMethod.POST,
            message.topic,
            body=message.payload,
            headers=message.headers,
        )
        return response is not None and response.is_success

    async def subscribe(
        self,
        topic: str,
        callback: MessageCallback | AsyncMessageCallback,
        poll_interval: float = 5.0,
    ) -> bool:
        """
        Subscribe to an endpoint via polling.

        For REST APIs, subscriptions are simulated via periodic polling.

        Args:
            topic: Endpoint path to poll
            callback: Callback for received data
            poll_interval: Polling interval in seconds

        Returns:
            True if subscription started
        """
        if not self.is_connected:
            return False

        if topic not in self._subscriptions:
            self._subscriptions[topic] = []

        self._subscriptions[topic].append(callback)

        # Start polling task
        if topic not in self._polling_tasks:
            self._polling_tasks[topic] = asyncio.create_task(
                self._poll_endpoint(topic, poll_interval)
            )

        logger.info(f"HTTP polling started for: {topic}")
        return True

    async def unsubscribe(self, topic: str) -> bool:
        """Stop polling an endpoint."""
        if topic in self._subscriptions:
            del self._subscriptions[topic]

        if topic in self._polling_tasks:
            self._polling_tasks[topic].cancel()
            del self._polling_tasks[topic]

        logger.info(f"HTTP polling stopped for: {topic}")
        return True

    async def request(
        self,
        method: HTTPMethod,
        path: str,
        body: Any = None,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, str]] = None,
    ) -> Optional[HTTPResponse]:
        """
        Send HTTP request.

        Args:
            method: HTTP method
            path: Request path
            body: Request body
            headers: Additional headers
            params: Query parameters

        Returns:
            HTTPResponse or None on error
        """
        if not self.is_connected:
            logger.error("Cannot send request: not connected")
            return None

        url = path if path.startswith("http") else urljoin(self._base_url, path)
        if params:
            url = f"{url}?{urlencode(params)}"

        logger.debug(f"HTTP {method.value} {url}")

        try:
            if self._simulation_mode:
                return await self._simulate_request(method, path, body)
            else:
                return await self._real_request(method, url, body, headers)

        except Exception as e:
            logger.error(f"HTTP request error: {e}")
            self.stats.record_error()
            return None

    async def _simulate_request(
        self,
        method: HTTPMethod,
        path: str,
        body: Any,
    ) -> HTTPResponse:
        """Simulate HTTP request/response."""
        await asyncio.sleep(0.05)  # Simulate network latency

        # Handle mock data
        if method == HTTPMethod.GET:
            if path in self._mock_data:
                return HTTPResponse(
                    status_code=200,
                    headers={"Content-Type": "application/json"},
                    body=self._mock_data[path],
                    elapsed=0.05,
                )
            return HTTPResponse(
                status_code=200,
                headers={"Content-Type": "application/json"},
                body={"path": path, "method": method.value, "timestamp": datetime.now().isoformat()},
                elapsed=0.05,
            )

        elif method == HTTPMethod.POST:
            self._mock_data[path] = body
            self.stats.record_sent(len(json.dumps(body)) if body else 0)
            return HTTPResponse(
                status_code=201,
                headers={"Content-Type": "application/json"},
                body={"created": True, "path": path},
                elapsed=0.05,
            )

        elif method == HTTPMethod.PUT:
            self._mock_data[path] = body
            self.stats.record_sent(len(json.dumps(body)) if body else 0)
            return HTTPResponse(
                status_code=200,
                headers={"Content-Type": "application/json"},
                body={"updated": True, "path": path},
                elapsed=0.05,
            )

        elif method == HTTPMethod.DELETE:
            if path in self._mock_data:
                del self._mock_data[path]
            return HTTPResponse(
                status_code=204,
                headers={},
                body=None,
                elapsed=0.05,
            )

        return HTTPResponse(
            status_code=200,
            headers={},
            body=None,
            elapsed=0.05,
        )

    async def _real_request(
        self,
        method: HTTPMethod,
        url: str,
        body: Any,
        headers: Optional[dict[str, str]],
    ) -> HTTPResponse:
        """Send real HTTP request."""
        import httpx

        request_headers = dict(self.http_config.default_headers)
        if headers:
            request_headers.update(headers)

        # Retry logic
        last_error = None
        for attempt in range(self.http_config.max_retries):
            try:
                start = datetime.now()

                response = await self._client.request(
                    method=method.value,
                    url=url,
                    json=body if body and isinstance(body, (dict, list)) else None,
                    content=body if body and isinstance(body, (str, bytes)) else None,
                    headers=request_headers,
                )

                elapsed = (datetime.now() - start).total_seconds()

                # Parse response body
                try:
                    response_body = response.json()
                except Exception:
                    response_body = response.text

                result = HTTPResponse(
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    body=response_body,
                    elapsed=elapsed,
                )

                if result.is_success:
                    self.stats.record_sent(len(str(body)) if body else 0)
                    self.stats.record_received(len(str(response_body)))
                else:
                    self.stats.record_error()

                return result

            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(f"Request timeout (attempt {attempt + 1})")
            except httpx.RequestError as e:
                last_error = e
                logger.warning(f"Request error (attempt {attempt + 1}): {e}")

            if attempt < self.http_config.max_retries - 1:
                await asyncio.sleep(self.http_config.retry_backoff * (attempt + 1))

        logger.error(f"Request failed after {self.http_config.max_retries} attempts: {last_error}")
        self.stats.record_error()
        return None

    async def _poll_endpoint(self, path: str, interval: float) -> None:
        """Poll an endpoint periodically."""
        while self._running and self.is_connected and path in self._subscriptions:
            try:
                response = await self.request(HTTPMethod.GET, path)

                if response and response.is_success:
                    message = ProtocolMessage(
                        topic=path,
                        payload=response.body,
                        timestamp=datetime.now(),
                    )
                    await self._handle_message(message)

                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Polling error for {path}: {e}")
                await asyncio.sleep(interval)

    # Convenience methods

    async def get(
        self,
        path: str,
        params: Optional[dict[str, str]] = None,
    ) -> Optional[HTTPResponse]:
        """Send GET request."""
        return await self.request(HTTPMethod.GET, path, params=params)

    async def post(
        self,
        path: str,
        body: Any,
        headers: Optional[dict[str, str]] = None,
    ) -> Optional[HTTPResponse]:
        """Send POST request."""
        return await self.request(HTTPMethod.POST, path, body=body, headers=headers)

    async def put(
        self,
        path: str,
        body: Any,
        headers: Optional[dict[str, str]] = None,
    ) -> Optional[HTTPResponse]:
        """Send PUT request."""
        return await self.request(HTTPMethod.PUT, path, body=body, headers=headers)

    async def delete(self, path: str) -> Optional[HTTPResponse]:
        """Send DELETE request."""
        return await self.request(HTTPMethod.DELETE, path)

    async def patch(
        self,
        path: str,
        body: Any,
        headers: Optional[dict[str, str]] = None,
    ) -> Optional[HTTPResponse]:
        """Send PATCH request."""
        return await self.request(HTTPMethod.PATCH, path, body=body, headers=headers)

    def set_mock_response(self, path: str, data: Any) -> None:
        """Set mock response for simulation mode."""
        self._mock_data[path] = data

    # ========== OAuth 2.0 Flow Implementation ==========

    async def oauth_authenticate(self) -> tuple[Optional[OAuthTokenResponse], Optional[str]]:
        """
        Authenticate using OAuth 2.0 based on configured grant type.

        Returns:
            Tuple of (token_response, error_message)
        """
        oauth = self.http_config.oauth
        if not oauth or not oauth.enabled:
            return None, "OAuth not configured"

        try:
            if oauth.grant_type == OAuthGrantType.CLIENT_CREDENTIALS:
                return await self._oauth_client_credentials()
            elif oauth.grant_type == OAuthGrantType.AUTHORIZATION_CODE:
                return None, "Authorization code flow requires user interaction - use oauth_get_authorization_url()"
            elif oauth.grant_type == OAuthGrantType.REFRESH_TOKEN:
                return await self._oauth_refresh_token()
            elif oauth.grant_type == OAuthGrantType.DEVICE_CODE:
                return None, "Device code flow requires polling - use oauth_device_code_flow()"
            else:
                return None, f"Unsupported grant type: {oauth.grant_type}"

        except Exception as e:
            logger.error(f"OAuth authentication error: {e}")
            return None, str(e)

    async def _oauth_client_credentials(self) -> tuple[Optional[OAuthTokenResponse], Optional[str]]:
        """
        Execute OAuth 2.0 Client Credentials flow (machine-to-machine).

        Returns:
            Tuple of (token_response, error_message)
        """
        oauth = self.http_config.oauth
        if not oauth:
            return None, "OAuth not configured"

        logger.info("Starting OAuth Client Credentials flow")

        # Build token request
        token_data = {
            "grant_type": "client_credentials",
            "client_id": oauth.client_id,
            "client_secret": oauth.client_secret,
        }
        if oauth.scope:
            token_data["scope"] = oauth.scope

        if self._simulation_mode:
            # Simulate token response
            await asyncio.sleep(0.1)
            token_response = OAuthTokenResponse(
                access_token=f"sim_access_{secrets.token_hex(16)}",
                token_type="Bearer",
                expires_in=3600,
                scope=oauth.scope,
            )
            self._store_oauth_token(token_response)
            logger.info("OAuth Client Credentials: Token acquired (simulation)")
            return token_response, None

        # Real token request
        response = await self._oauth_token_request(token_data)
        if response and response.is_success:
            token_response = OAuthTokenResponse.from_dict(response.body)
            self._store_oauth_token(token_response)
            logger.info("OAuth Client Credentials: Token acquired")
            return token_response, None

        error_msg = response.body.get("error_description", response.body.get("error", "Unknown error")) if response else "Token request failed"
        return None, error_msg

    async def _oauth_refresh_token(self) -> tuple[Optional[OAuthTokenResponse], Optional[str]]:
        """
        Execute OAuth 2.0 Refresh Token flow.

        Returns:
            Tuple of (token_response, error_message)
        """
        oauth = self.http_config.oauth
        if not oauth or not oauth.refresh_token:
            return None, "No refresh token available"

        logger.info("Starting OAuth Refresh Token flow")

        token_data = {
            "grant_type": "refresh_token",
            "refresh_token": oauth.refresh_token,
            "client_id": oauth.client_id,
            "client_secret": oauth.client_secret,
        }

        if self._simulation_mode:
            await asyncio.sleep(0.1)
            token_response = OAuthTokenResponse(
                access_token=f"sim_refreshed_{secrets.token_hex(16)}",
                token_type="Bearer",
                expires_in=3600,
                refresh_token=f"sim_refresh_{secrets.token_hex(16)}",
                scope=oauth.scope,
            )
            self._store_oauth_token(token_response)
            logger.info("OAuth Refresh: Token refreshed (simulation)")
            return token_response, None

        response = await self._oauth_token_request(token_data)
        if response and response.is_success:
            token_response = OAuthTokenResponse.from_dict(response.body)
            self._store_oauth_token(token_response)
            logger.info("OAuth Refresh: Token refreshed")
            return token_response, None

        error_msg = response.body.get("error_description", "Refresh failed") if response else "Refresh request failed"
        return None, error_msg

    def oauth_get_authorization_url(self, state: Optional[str] = None) -> tuple[str, str]:
        """
        Generate OAuth 2.0 Authorization URL for Authorization Code flow.

        Args:
            state: Optional state parameter for CSRF protection

        Returns:
            Tuple of (authorization_url, state)
        """
        oauth = self.http_config.oauth
        if not oauth:
            raise ValueError("OAuth not configured")

        state = state or secrets.token_urlsafe(32)

        # Generate PKCE code verifier and challenge (RFC 7636)
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).rstrip(b"=").decode()

        # Store for later exchange
        self._oauth_pkce = {
            "code_verifier": code_verifier,
            "state": state,
        }

        params = {
            "response_type": "code",
            "client_id": oauth.client_id,
            "redirect_uri": oauth.redirect_uri,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        if oauth.scope:
            params["scope"] = oauth.scope

        auth_url = f"{oauth.authorization_url}?{urlencode(params)}"
        logger.info(f"Generated OAuth authorization URL (state={state[:8]}...)")

        return auth_url, state

    async def oauth_exchange_code(
        self,
        code: str,
        state: str,
    ) -> tuple[Optional[OAuthTokenResponse], Optional[str]]:
        """
        Exchange authorization code for access token (Authorization Code flow).

        Args:
            code: Authorization code received from callback
            state: State parameter to validate

        Returns:
            Tuple of (token_response, error_message)
        """
        oauth = self.http_config.oauth
        if not oauth:
            return None, "OAuth not configured"

        # Validate state (CSRF protection)
        if not hasattr(self, "_oauth_pkce") or self._oauth_pkce.get("state") != state:
            return None, "Invalid state parameter - possible CSRF attack"

        logger.info("Exchanging OAuth authorization code for token")

        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": oauth.redirect_uri,
            "client_id": oauth.client_id,
            "client_secret": oauth.client_secret,
            "code_verifier": self._oauth_pkce["code_verifier"],
        }

        if self._simulation_mode:
            await asyncio.sleep(0.1)
            token_response = OAuthTokenResponse(
                access_token=f"sim_authcode_{secrets.token_hex(16)}",
                token_type="Bearer",
                expires_in=3600,
                refresh_token=f"sim_refresh_{secrets.token_hex(16)}",
                scope=oauth.scope,
            )
            self._store_oauth_token(token_response)
            logger.info("OAuth Authorization Code: Token acquired (simulation)")
            return token_response, None

        response = await self._oauth_token_request(token_data)
        if response and response.is_success:
            token_response = OAuthTokenResponse.from_dict(response.body)
            self._store_oauth_token(token_response)
            logger.info("OAuth Authorization Code: Token acquired")
            return token_response, None

        error_msg = response.body.get("error_description", "Code exchange failed") if response else "Token request failed"
        return None, error_msg

    async def oauth_device_code_flow(
        self,
        poll_callback: Optional[MessageCallback] = None,
    ) -> tuple[Optional[OAuthTokenResponse], Optional[str]]:
        """
        Execute OAuth 2.0 Device Authorization flow (RFC 8628).

        This flow is for devices with limited input capability.
        User must visit URL and enter code on another device.

        Args:
            poll_callback: Optional callback to receive polling updates

        Returns:
            Tuple of (token_response, error_message)
        """
        oauth = self.http_config.oauth
        if not oauth or not oauth.device_authorization_url:
            return None, "Device authorization URL not configured"

        logger.info("Starting OAuth Device Code flow")

        # Step 1: Request device code
        device_data = {
            "client_id": oauth.client_id,
        }
        if oauth.scope:
            device_data["scope"] = oauth.scope

        if self._simulation_mode:
            # Simulate device code response
            user_code = secrets.token_hex(4).upper()
            device_code = secrets.token_hex(32)
            verification_uri = "https://example.com/device"

            logger.info(f"Device Code: Visit {verification_uri} and enter code: {user_code}")

            if poll_callback:
                poll_callback(ProtocolMessage(
                    topic="oauth/device",
                    payload={
                        "user_code": user_code,
                        "verification_uri": verification_uri,
                        "status": "pending",
                    },
                ))

            # Simulate user authorization after delay
            await asyncio.sleep(2.0)

            token_response = OAuthTokenResponse(
                access_token=f"sim_device_{secrets.token_hex(16)}",
                token_type="Bearer",
                expires_in=3600,
                refresh_token=f"sim_refresh_{secrets.token_hex(16)}",
                scope=oauth.scope,
            )
            self._store_oauth_token(token_response)
            logger.info("OAuth Device Code: Token acquired (simulation)")
            return token_response, None

        # Real device code request
        device_response = await self.post(oauth.device_authorization_url, device_data)
        if not device_response or not device_response.is_success:
            return None, "Failed to get device code"

        device_code = device_response.body.get("device_code")
        user_code = device_response.body.get("user_code")
        verification_uri = device_response.body.get("verification_uri")
        interval = device_response.body.get("interval", 5)
        expires_in = device_response.body.get("expires_in", 1800)

        logger.info(f"Device Code: Visit {verification_uri} and enter code: {user_code}")

        if poll_callback:
            poll_callback(ProtocolMessage(
                topic="oauth/device",
                payload={
                    "user_code": user_code,
                    "verification_uri": verification_uri,
                    "verification_uri_complete": device_response.body.get("verification_uri_complete"),
                    "status": "pending",
                },
            ))

        # Step 2: Poll for token
        start_time = datetime.now()
        while (datetime.now() - start_time).seconds < expires_in:
            await asyncio.sleep(interval)

            token_data = {
                "grant_type": OAuthGrantType.DEVICE_CODE.value,
                "device_code": device_code,
                "client_id": oauth.client_id,
            }

            response = await self._oauth_token_request(token_data)
            if response and response.is_success:
                token_response = OAuthTokenResponse.from_dict(response.body)
                self._store_oauth_token(token_response)
                logger.info("OAuth Device Code: Token acquired")
                return token_response, None

            if response:
                error = response.body.get("error")
                if error == "authorization_pending":
                    continue  # Keep polling
                elif error == "slow_down":
                    interval += 5  # Back off
                else:
                    return None, response.body.get("error_description", error)

        return None, "Device code expired"

    async def _oauth_token_request(self, token_data: dict) -> Optional[HTTPResponse]:
        """Send OAuth token request."""
        oauth = self.http_config.oauth
        if not oauth:
            return None

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }

        # Temporarily bypass auth for token endpoint
        old_auth = self.http_config.auth_type
        self.http_config.auth_type = "none"

        try:
            response = await self.request(
                HTTPMethod.POST,
                oauth.token_url,
                body=urlencode(token_data),
                headers=headers,
            )
            return response
        finally:
            self.http_config.auth_type = old_auth

    def _store_oauth_token(self, token_response: OAuthTokenResponse) -> None:
        """Store OAuth token for future use."""
        oauth = self.http_config.oauth
        if not oauth:
            return

        oauth.access_token = token_response.access_token
        if token_response.refresh_token:
            oauth.refresh_token = token_response.refresh_token
        if token_response.expires_in:
            oauth.token_expires_at = datetime.now() + timedelta(seconds=token_response.expires_in)

        # Update bearer token for authenticated requests
        self.http_config.bearer_token = token_response.access_token
        self.http_config.auth_type = "bearer"

        logger.debug(f"OAuth token stored (expires: {oauth.token_expires_at})")

    def oauth_is_token_valid(self) -> bool:
        """Check if current OAuth token is still valid."""
        oauth = self.http_config.oauth
        if not oauth or not oauth.access_token:
            return False
        if not oauth.token_expires_at:
            return True  # No expiry info, assume valid
        # Add 60 second buffer
        return datetime.now() < (oauth.token_expires_at - timedelta(seconds=60))

    async def oauth_ensure_valid_token(self) -> bool:
        """
        Ensure we have a valid OAuth token, refreshing if necessary.

        Returns:
            True if we have a valid token
        """
        if self.oauth_is_token_valid():
            return True

        oauth = self.http_config.oauth
        if not oauth:
            return False

        # Try to refresh
        if oauth.refresh_token:
            token, error = await self._oauth_refresh_token()
            if token:
                return True
            logger.warning(f"Token refresh failed: {error}")

        # Re-authenticate
        token, error = await self.oauth_authenticate()
        return token is not None

    def get_oauth_status(self) -> dict[str, Any]:
        """Get OAuth status information."""
        oauth = self.http_config.oauth
        if not oauth or not oauth.enabled:
            return {"enabled": False}

        return {
            "enabled": True,
            "grant_type": oauth.grant_type.value,
            "has_access_token": bool(oauth.access_token),
            "has_refresh_token": bool(oauth.refresh_token),
            "token_valid": self.oauth_is_token_valid(),
            "token_expires_at": oauth.token_expires_at.isoformat() if oauth.token_expires_at else None,
        }

    def get_stats(self) -> dict[str, Any]:
        """Get HTTP-specific statistics."""
        stats = super().get_stats()
        stats.update({
            "base_url": self._base_url,
            "active_polls": len(self._polling_tasks),
            "simulation_mode": self._simulation_mode,
            "auth_type": self.http_config.auth_type,
            "oauth": self.get_oauth_status(),
            "webhooks": self.get_webhook_stats(),
        })
        return stats

    # ========== Webhook Implementation ==========

    def __init_webhooks(self) -> None:
        """Initialize webhook-related attributes (called from __init__)."""
        # Already initialized in __init__ via _webhooks dict
        pass

    async def webhook_register(
        self,
        webhook_id: str,
        url: str,
        events: list[str],
        secret: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
        active: bool = True,
    ) -> "WebhookSubscription":
        """
        Register a webhook subscription.

        Args:
            webhook_id: Unique identifier for this webhook
            url: URL to receive webhook payloads
            events: List of event types to subscribe to (e.g., ["device.update", "alert.triggered"])
            secret: Shared secret for HMAC signature verification
            headers: Custom headers to include in webhook requests
            active: Whether the webhook is active

        Returns:
            WebhookSubscription object
        """
        subscription = WebhookSubscription(
            id=webhook_id,
            url=url,
            events=events,
            secret=secret or secrets.token_hex(32),
            headers=headers or {},
            active=active,
        )

        if not hasattr(self, "_webhook_subscriptions"):
            self._webhook_subscriptions: dict[str, "WebhookSubscription"] = {}

        self._webhook_subscriptions[webhook_id] = subscription
        logger.info(f"Webhook registered: {webhook_id} -> {url} for events: {events}")

        return subscription

    async def webhook_unregister(self, webhook_id: str) -> bool:
        """
        Unregister a webhook subscription.

        Args:
            webhook_id: ID of the webhook to remove

        Returns:
            True if removed, False if not found
        """
        if not hasattr(self, "_webhook_subscriptions"):
            return False

        if webhook_id in self._webhook_subscriptions:
            del self._webhook_subscriptions[webhook_id]
            logger.info(f"Webhook unregistered: {webhook_id}")
            return True

        return False

    async def webhook_deliver(
        self,
        event_type: str,
        payload: dict[str, Any],
        source_id: Optional[str] = None,
    ) -> list["WebhookDeliveryResult"]:
        """
        Deliver a webhook event to all matching subscribers.

        Args:
            event_type: Type of event (e.g., "device.update", "alert.triggered")
            payload: Event payload data
            source_id: Optional source identifier

        Returns:
            List of delivery results
        """
        if not hasattr(self, "_webhook_subscriptions"):
            return []

        results: list["WebhookDeliveryResult"] = []
        delivery_id = str(uuid4())
        timestamp = datetime.now()

        # Build webhook payload
        webhook_payload = {
            "id": delivery_id,
            "event": event_type,
            "timestamp": timestamp.isoformat(),
            "source_id": source_id,
            "data": payload,
        }

        # Find matching subscriptions
        for sub_id, subscription in self._webhook_subscriptions.items():
            if not subscription.active:
                continue

            # Check if this subscription matches the event
            if not self._webhook_event_matches(event_type, subscription.events):
                continue

            # Deliver to this webhook
            result = await self._webhook_deliver_single(
                subscription, webhook_payload, delivery_id
            )
            results.append(result)

            # Track delivery
            subscription.delivery_count += 1
            if result.success:
                subscription.last_success = timestamp
            else:
                subscription.failure_count += 1
                subscription.last_failure = timestamp

        return results

    def _webhook_event_matches(self, event_type: str, subscribed_events: list[str]) -> bool:
        """Check if an event type matches any subscribed patterns."""
        for pattern in subscribed_events:
            if pattern == "*":
                return True
            if pattern == event_type:
                return True
            # Support wildcards like "device.*"
            if pattern.endswith(".*"):
                prefix = pattern[:-2]
                if event_type.startswith(prefix + "."):
                    return True
        return False

    async def _webhook_deliver_single(
        self,
        subscription: "WebhookSubscription",
        payload: dict[str, Any],
        delivery_id: str,
    ) -> "WebhookDeliveryResult":
        """Deliver webhook to a single subscription."""
        start_time = datetime.now()

        # Generate signature
        payload_bytes = json.dumps(payload, sort_keys=True).encode()
        signature = self._webhook_generate_signature(payload_bytes, subscription.secret)

        # Build headers
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-ID": subscription.id,
            "X-Webhook-Delivery": delivery_id,
            "X-Webhook-Signature": f"sha256={signature}",
            "X-Webhook-Timestamp": payload["timestamp"],
            **subscription.headers,
        }

        try:
            if self._simulation_mode:
                # Simulate webhook delivery
                await asyncio.sleep(0.05)
                elapsed = (datetime.now() - start_time).total_seconds()

                logger.debug(f"Webhook delivered (simulation): {subscription.id} -> {subscription.url}")

                return WebhookDeliveryResult(
                    webhook_id=subscription.id,
                    delivery_id=delivery_id,
                    success=True,
                    status_code=200,
                    response_time=elapsed,
                    timestamp=start_time,
                )

            # Real webhook delivery
            response = await self.request(
                HTTPMethod.POST,
                subscription.url,
                body=payload,
                headers=headers,
            )

            elapsed = (datetime.now() - start_time).total_seconds()

            if response and response.is_success:
                logger.info(f"Webhook delivered: {subscription.id} -> {subscription.url}")
                return WebhookDeliveryResult(
                    webhook_id=subscription.id,
                    delivery_id=delivery_id,
                    success=True,
                    status_code=response.status_code,
                    response_time=elapsed,
                    timestamp=start_time,
                )
            else:
                status = response.status_code if response else 0
                error = response.body if response else "Request failed"
                logger.warning(f"Webhook delivery failed: {subscription.id} -> {status}")
                return WebhookDeliveryResult(
                    webhook_id=subscription.id,
                    delivery_id=delivery_id,
                    success=False,
                    status_code=status,
                    error=str(error),
                    response_time=elapsed,
                    timestamp=start_time,
                )

        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.error(f"Webhook delivery error: {subscription.id} -> {e}")
            return WebhookDeliveryResult(
                webhook_id=subscription.id,
                delivery_id=delivery_id,
                success=False,
                status_code=0,
                error=str(e),
                response_time=elapsed,
                timestamp=start_time,
            )

    def _webhook_generate_signature(self, payload: bytes, secret: str) -> str:
        """Generate HMAC-SHA256 signature for webhook payload."""
        return hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

    def webhook_verify_signature(
        self,
        payload: bytes,
        signature: str,
        secret: str,
    ) -> bool:
        """
        Verify a webhook signature (for incoming webhooks).

        Args:
            payload: Raw request body bytes
            signature: Signature from X-Webhook-Signature header
            secret: Shared secret

        Returns:
            True if signature is valid
        """
        # Remove "sha256=" prefix if present
        if signature.startswith("sha256="):
            signature = signature[7:]

        expected = self._webhook_generate_signature(payload, secret)
        return hmac.compare_digest(expected, signature)

    def webhook_list(self) -> list["WebhookSubscription"]:
        """Get all registered webhook subscriptions."""
        if not hasattr(self, "_webhook_subscriptions"):
            return []
        return list(self._webhook_subscriptions.values())

    def webhook_get(self, webhook_id: str) -> Optional["WebhookSubscription"]:
        """Get a specific webhook subscription."""
        if not hasattr(self, "_webhook_subscriptions"):
            return None
        return self._webhook_subscriptions.get(webhook_id)

    async def webhook_test(self, webhook_id: str) -> Optional["WebhookDeliveryResult"]:
        """
        Send a test event to a webhook.

        Args:
            webhook_id: ID of the webhook to test

        Returns:
            Delivery result or None if webhook not found
        """
        subscription = self.webhook_get(webhook_id)
        if not subscription:
            return None

        test_payload = {
            "test": True,
            "message": "This is a test webhook delivery",
            "webhook_id": webhook_id,
        }

        results = await self.webhook_deliver(
            "webhook.test",
            test_payload,
            source_id="webhook_test",
        )

        return results[0] if results else None

    async def webhook_retry(
        self,
        webhook_id: str,
        delivery_id: str,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
    ) -> Optional["WebhookDeliveryResult"]:
        """
        Retry a failed webhook delivery with exponential backoff.

        Args:
            webhook_id: ID of the webhook
            delivery_id: Original delivery ID
            max_retries: Maximum number of retry attempts
            backoff_seconds: Initial backoff time in seconds

        Returns:
            Final delivery result or None if webhook not found
        """
        subscription = self.webhook_get(webhook_id)
        if not subscription:
            return None

        # This would typically retrieve the original payload from storage
        # For simulation, we'll create a retry payload
        retry_payload = {
            "id": delivery_id,
            "event": "webhook.retry",
            "timestamp": datetime.now().isoformat(),
            "data": {"original_delivery_id": delivery_id, "retry": True},
        }

        last_result = None
        for attempt in range(max_retries):
            if attempt > 0:
                await asyncio.sleep(backoff_seconds * (2 ** attempt))

            result = await self._webhook_deliver_single(
                subscription, retry_payload, f"{delivery_id}_retry_{attempt + 1}"
            )
            last_result = result

            if result.success:
                logger.info(f"Webhook retry succeeded on attempt {attempt + 1}")
                return result

        logger.warning(f"Webhook retry failed after {max_retries} attempts")
        return last_result

    def get_webhook_stats(self) -> dict[str, Any]:
        """Get webhook statistics."""
        if not hasattr(self, "_webhook_subscriptions"):
            return {
                "total_webhooks": 0,
                "active_webhooks": 0,
                "total_deliveries": 0,
                "total_failures": 0,
            }

        total = len(self._webhook_subscriptions)
        active = sum(1 for s in self._webhook_subscriptions.values() if s.active)
        deliveries = sum(s.delivery_count for s in self._webhook_subscriptions.values())
        failures = sum(s.failure_count for s in self._webhook_subscriptions.values())

        return {
            "total_webhooks": total,
            "active_webhooks": active,
            "total_deliveries": deliveries,
            "total_failures": failures,
            "success_rate": (deliveries - failures) / deliveries * 100 if deliveries > 0 else 0,
        }


@dataclass
class WebhookSubscription:
    """Webhook subscription configuration."""
    id: str
    url: str
    events: list[str]  # Event types to receive (supports wildcards like "device.*")
    secret: str  # Shared secret for HMAC signature
    headers: dict[str, str] = field(default_factory=dict)  # Custom headers
    active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    # Statistics
    delivery_count: int = 0
    failure_count: int = 0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (excluding secret)."""
        return {
            "id": self.id,
            "url": self.url,
            "events": self.events,
            "active": self.active,
            "created_at": self.created_at.isoformat(),
            "delivery_count": self.delivery_count,
            "failure_count": self.failure_count,
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "last_failure": self.last_failure.isoformat() if self.last_failure else None,
        }


@dataclass
class WebhookDeliveryResult:
    """Result of a webhook delivery attempt."""
    webhook_id: str
    delivery_id: str
    success: bool
    status_code: int
    timestamp: datetime = field(default_factory=datetime.now)
    response_time: float = 0.0  # seconds
    error: Optional[str] = None
    response_body: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "webhook_id": self.webhook_id,
            "delivery_id": self.delivery_id,
            "success": self.success,
            "status_code": self.status_code,
            "timestamp": self.timestamp.isoformat(),
            "response_time": self.response_time,
            "error": self.error,
        }
