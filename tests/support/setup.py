"""Set up the test suite."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import respx
import structlog
from httpx import AsyncClient
from safir.dependencies.http_client import http_client_dependency
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from gafaelfawr.constants import COOKIE_NAME
from gafaelfawr.dependencies.config import config_dependency
from gafaelfawr.dependencies.redis import redis_dependency
from gafaelfawr.factory import ComponentFactory
from gafaelfawr.models.state import State
from gafaelfawr.models.token import Token, TokenData, TokenGroup, TokenUserInfo
from tests.support.constants import TEST_HOSTNAME
from tests.support.github import mock_github
from tests.support.oidc import (
    mock_oidc_provider_config,
    mock_oidc_provider_token,
)
from tests.support.tokens import create_upstream_oidc_token

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any, AsyncIterator, List, Optional

    from aioredis import Redis

    from gafaelfawr.config import Config
    from gafaelfawr.keypair import RSAKeyPair
    from gafaelfawr.models.oidc import OIDCToken, OIDCVerifiedToken
    from gafaelfawr.providers.github import GitHubUserInfo


class SetupTest:
    """Utility class for test setup.

    This class wraps creating a test FastAPI application, creating a factory
    for building the components, and accessing configuration settings.

    This object should always be created via the :py:meth:`create` method.
    The constructor should be considered private.

    Notes
    -----
    This class is named SetupTest instead of TestSetup because pytest thinks
    the latter is a test case and tries to execute it.
    """

    @classmethod
    @asynccontextmanager
    async def create(
        cls, tmp_path: Path, respx_mock: respx.Router
    ) -> AsyncIterator[SetupTest]:
        """Create a new `SetupTest` instance.

        This is the only supported way to set up the test environment and
        should be called instead of calling the constructor directly.  It
        initializes and starts the application and configures an
        `httpx.AsyncClient` to talk to it.

        Parameters
        ----------
        tmp_path : `pathlib.Path`
            The path for temporary files.
        respx_mock : `respx.Router`
            The mock for simulating `httpx.AsyncClient` calls.
        """
        config = await config_dependency()
        redis = await redis_dependency(config)

        # Create the database session that will be used by SetupTest and by
        # the factory it contains.  The application will use a separate
        # session handled by its middleware.
        engine = create_async_engine(config.database_url, future=True)
        session_factory = sessionmaker(
            engine, expire_on_commit=False, class_=AsyncSession
        )

        # Build the SetupTest object inside all of the contexts required by
        # its components and handle clean shutdown.  We have to build two
        # separate AsyncClients here, one which will be used to make requests
        # to the application under test and the other of which will be used in
        # the factory for components that require a client.  They have to be
        # separate or requests for routes that are also served by the app will
        # bypass the mock and call the app instead, causing tests to fail.
        try:
            async with AsyncClient() as http_client:
                async with session_factory() as session:
                    yield cls(
                        tmp_path=tmp_path,
                        respx_mock=respx_mock,
                        config=config,
                        redis=redis,
                        session=session,
                        http_client=http_client,
                    )
        finally:
            await http_client_dependency.aclose()
            await redis_dependency.aclose()
            await engine.dispose()

    def __init__(
        self,
        *,
        tmp_path: Path,
        respx_mock: respx.Router,
        config: Config,
        redis: Redis,
        session: AsyncSession,
        http_client: AsyncClient,
    ) -> None:
        self.tmp_path = tmp_path
        self.respx_mock = respx_mock
        self.redis = redis
        self.session = session
        self.http_client = http_client
        self.logger = structlog.get_logger(config.safir.logger_name)
        assert self.logger

    @property
    def factory(self) -> ComponentFactory:
        """Return a `~gafaelfawr.factory.ComponentFactory`.

        Build a new one each time to ensure that it picks up the current
        configuration information.

        Returns
        -------
        factory : `gafaelfawr.factory.ComponentFactory`
            Newly-created factory.
        """
        assert config_dependency._config
        return ComponentFactory(
            config=config_dependency._config,
            redis=self.redis,
            http_client=self.http_client,
            session=self.session,
            logger=self.logger,
        )

    async def create_session_token(
        self,
        *,
        username: Optional[str] = None,
        group_names: Optional[List[str]] = None,
        scopes: Optional[List[str]] = None,
    ) -> TokenData:
        """Create a session token.

        Parameters
        ----------
        username : `str`, optional
            Override the username of the generated token.
        group_namess : List[`str`], optional
            Group memberships the generated token should have.
        scopes : List[`str`], optional
            Scope for the generated token.

        Returns
        -------
        data : `gafaelfawr.models.token.TokenData`
            The data for the generated token.
        """
        if not username:
            username = "some-user"
        if group_names:
            groups = [TokenGroup(name=g, id=1000) for g in group_names]
        else:
            groups = []
        user_info = TokenUserInfo(
            username=username,
            name="Some User",
            email="someuser@example.com",
            uid=1000,
            groups=groups,
        )
        if not scopes:
            scopes = ["user:token"]
        token_service = self.factory.create_token_service()
        token = await token_service.create_session_token(
            user_info, scopes=scopes, ip_address="127.0.0.1"
        )
        data = await token_service.get_data(token)
        assert data
        await self.session.commit()
        return data

    async def create_upstream_oidc_token(
        self,
        *,
        kid: Optional[str] = None,
        groups: Optional[List[str]] = None,
        **claims: Any,
    ) -> OIDCVerifiedToken:
        """Create a signed OpenID Connect token.

        Parameters
        ----------
        kid : `str`, optional
            Key ID for the token header.  Defaults to the first key in the
            key_ids configuration for the OpenID Connect provider.
        groups : List[`str`], optional
            Group memberships the generated token should have.
        **claims : `str`, optional
            Other claims to set or override in the token.

        Returns
        -------
        token : `gafaelfawr.models..oidc.OIDCVerifiedToken`
            The generated token.
        """
        config = await config_dependency()
        if not kid:
            assert config.oidc
            kid = config.oidc.key_ids[0]
        return create_upstream_oidc_token(config, kid, groups=groups, **claims)

    async def login(self, client: AsyncClient, token: Token) -> str:
        """Create a valid Gafaelfawr session.

        Add a valid Gafaelfawr session cookie to the `httpx.AsyncClient`, use
        the login URL, and return the resulting CSRF token.

        Parameters
        ----------
        client : `httpx.AsyncClient`
            The client to add the session cookie to.
        token : `gafaelfawr.models.token.Token`
            The token for the client identity to use.

        Returns
        -------
        csrf : `str`
            The CSRF token to use in subsequent API requests.
        """
        cookie = await State(token=token).as_cookie()
        client.cookies.set(COOKIE_NAME, cookie, domain=TEST_HOSTNAME)
        r = await client.get("/auth/api/v1/login")
        assert r.status_code == 200
        return r.json()["csrf"]

    def logout(self, client: AsyncClient) -> None:
        """Delete the Gafaelfawr session token.

        Parameters
        ----------
        client : `httpx.AsyncClient`
            The client from which to remove the session cookie.
        """
        del client.cookies[COOKIE_NAME]

    async def set_github_response(
        self,
        code: str,
        user_info: GitHubUserInfo,
        *,
        paginate_teams: bool = False,
        expect_revoke: bool = False,
    ) -> None:
        """Mock the GitHub API.

        Parameters
        ----------
        code : `str`
            The code that Gafaelfawr must send to redeem a token.
        user_info : `gafaelfawr.providers.github.GitHubUserInfo`
            User information to use to synthesize GitHub API responses.
        paginate_teams : `bool`, optional
            Whether to paginate the team results.  Default: `False`
        expect_revoke : `bool`, optional
            Whether to expect a revocation of the token after returning all
            user information.  Default: `False`
        """
        await mock_github(
            self.respx_mock,
            code,
            user_info,
            paginate_teams=paginate_teams,
            expect_revoke=expect_revoke,
        )

    async def set_oidc_configuration_response(
        self,
        keypair: Optional[RSAKeyPair] = None,
        kid: Optional[str] = None,
    ) -> None:
        """Register configuration callbacks for upstream OpenID Connect.

        Parameters
        ----------
        keypair : `gafaelfawr.keypair.RSAKeyPair`, optional
            The key pair used to sign the token, which will be used to
            register the keys callback.
        kid : `str`, optional
            Key ID for the key.  If not given, defaults to the first key ID in
            the configured key_ids list.
        """
        await mock_oidc_provider_config(self.respx_mock, keypair, kid)

    async def set_oidc_token_response(
        self,
        code: str,
        token: OIDCToken,
    ) -> None:
        """Register token callbacks for upstream OpenID Connect provider.

        Parameters
        ----------
        code : `str`
            The code that Gafaelfawr must send.
        token : `gafaelfawr.tokens.Token`
            The token.
        """
        await mock_oidc_provider_token(self.respx_mock, code, token)
