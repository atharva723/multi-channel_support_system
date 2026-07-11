"""Authentication & channel-connection endpoints.

Sign-in *is* connecting a channel. The flow:

  1. ``GET /auth/{provider}/login`` -> returns/redirects to the provider's consent
     screen. If called with a Bearer token, the resulting connection is linked to
     the current account (adding a channel) rather than creating a new one.
  2. Provider redirects back to ``GET /auth/{provider}/callback?code&state`` ->
     we exchange the code, fetch identity, upsert the account+connection, mint an
     app session JWT, and redirect to the app with the token.
  3. ``GET /me`` and ``GET/DELETE /connections`` manage the signed-in account.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentAccount, DBSession
from app.core.config import settings
from app.models.account import Account
from app.schemas.account import AccountOut, ConnectionOut, MeOut, SessionOut
from app.services import connections as conn_store
from app.services.auth import (
    SessionTokenError,
    create_oauth_state,
    create_session_token,
    decode_oauth_state,
    decode_session_token,
)
from app.services.providers import (
    ProviderError,
    available_providers,
    get_provider,
)

router = APIRouter(tags=["auth"])


@router.get("/auth/providers", summary="List connectable providers")
async def list_providers() -> dict:
    return {"providers": available_providers()}


@router.get(
    "/auth/{provider}/login",
    response_model=None,
    summary="Begin OAuth sign-in / connect for a provider",
)
async def login(
    provider: str,
    request: Request,
    redirect: bool = Query(
        default=False, description="302 to the provider instead of returning JSON."
    ),
    authorization: str | None = None,
) -> dict | RedirectResponse:
    try:
        prov = get_provider(provider)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # If an authenticated user is adding a channel, link to their account.
    link_account_id: int | None = None
    auth_header = authorization or request.headers.get("authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        try:
            link_account_id = decode_session_token(auth_header.split(" ", 1)[1].strip())
        except SessionTokenError:
            link_account_id = None

    state = create_oauth_state(provider, link_account_id)
    url = prov.authorize_url(state)
    if redirect:
        return RedirectResponse(url)
    return {"authorize_url": url, "state": state}


@router.get(
    "/auth/{provider}/callback",
    response_model=None,
    summary="OAuth redirect target: exchange code and issue a session",
)
async def callback(
    provider: str,
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = DBSession,
    json: bool = Query(default=False, description="Return JSON instead of redirect."),
):
    try:
        state_provider, link_account_id = decode_oauth_state(state)
    except SessionTokenError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if state_provider != provider:
        raise HTTPException(status_code=400, detail="State/provider mismatch.")

    try:
        prov = get_provider(provider)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        tokens = await prov.exchange_code(code)
        identity = await prov.fetch_identity(tokens)
    except ProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OAuth exchange failed: {exc}",
        ) from exc

    account, _connection, is_new = await conn_store.connect_provider(
        db,
        provider=provider,
        tokens=tokens,
        identity=identity,
        link_account_id=link_account_id,
    )
    session_token = create_session_token(account.id)

    if json:
        return SessionOut(
            access_token=session_token,
            account=AccountOut.model_validate(account),
            connected_provider=provider,
            is_new_account=is_new,
        )

    # Redirect back into the app (e.g. a mobile deep link) carrying the token.
    sep = "&" if "?" in settings.oauth_success_redirect else "?"
    target = (
        f"{settings.oauth_success_redirect}{sep}token={session_token}"
        f"&provider={provider}&new={str(is_new).lower()}"
    )
    return RedirectResponse(target)


@router.get("/me", response_model=MeOut, summary="Current account + connections")
async def me(
    account: Account = CurrentAccount,
    db: AsyncSession = DBSession,
) -> MeOut:
    conns = await conn_store.list_connections(db, account.id)
    return MeOut(
        account=AccountOut.model_validate(account),
        connections=[ConnectionOut.model_validate(c) for c in conns],
    )


@router.get(
    "/connections",
    response_model=list[ConnectionOut],
    summary="List the account's channel connections",
)
async def get_connections(
    account: Account = CurrentAccount,
    db: AsyncSession = DBSession,
) -> list[ConnectionOut]:
    conns = await conn_store.list_connections(db, account.id)
    return [ConnectionOut.model_validate(c) for c in conns]


@router.delete(
    "/connections/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disconnect a channel",
)
async def delete_connection(
    connection_id: int,
    account: Account = CurrentAccount,
    db: AsyncSession = DBSession,
) -> None:
    ok = await conn_store.delete_connection(
        db, account_id=account.id, connection_id=connection_id
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Connection not found.")
