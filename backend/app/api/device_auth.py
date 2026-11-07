"""Authenticate telemetry writers against device-specific bearer tokens."""

from secrets import compare_digest

from fastapi import HTTPException, Request


def require_device_auth(request: Request, device_id: str) -> None:
    settings = request.app.state.settings
    if not settings.require_device_auth:
        return
    if settings.environment == "production" and request.url.scheme != "https":
        raise HTTPException(status_code=403, detail="HTTPS obrigatório para envio em produção.")
    authorization = request.headers.get("Authorization", "")
    scheme, separator, presented = authorization.partition(" ")
    expected = (settings.device_tokens or {}).get(device_id)
    if (scheme.lower() != "bearer" or separator != " " or not presented or
            expected is None or not compare_digest(presented, expected)):
        raise HTTPException(
            status_code=401,
            detail="Credencial do dispositivo inválida.",
            headers={"WWW-Authenticate": "Bearer"},
        )
