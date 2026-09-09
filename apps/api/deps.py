from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from apps.api.db import get_db

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user_id(
    authorization: str | None = Header(default=None),
) -> str:
    if not authorization:
        raise HTTPException(401, detail="Authorization header required")

    if not authorization.startswith("Bearer "):
        raise HTTPException(401, detail="Invalid authorization header")

    token = authorization[7:]
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(401, detail="Invalid token payload")
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, detail="Invalid token")


CurrentUserId = Annotated[str, Depends(get_current_user_id)]
