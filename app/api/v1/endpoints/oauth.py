from fastapi import APIRouter, Depends, Response, Request
from sqlalchemy.orm import Session
from typing import Dict
import requests
import hmac
from urllib.parse import urlencode

from app.core import deps
from app.core.oauth import get_oauth_provider, create_oauth_token
from app.core.config import settings
from app.schemas.token import Token
from app.schemas.response import ApiResponse
from app.schemas.user import User
from app.services.user import create_or_update_user
from app.api.v1.endpoints.auth import set_refresh_cookie

router = APIRouter()


def get_oauth_redirect_url(provider: str) -> str:
    """
    Get OAuth redirect URL.
    """
    return f"{settings.FRONTEND_URL}/auth/oauth/{provider}/callback"


@router.get("/{provider}/url", response_model=ApiResponse[Dict[str, str]])
async def get_oauth_url(provider: str, state: str, response: Response):
    """
    Generate OAuth URL with state parameter
    """
    try:
        oauth = get_oauth_provider(provider)

        if provider == "google":
            params = {
                "client_id": oauth.client_id,
                "redirect_uri": get_oauth_redirect_url(provider),
                "response_type": "code",
                "scope": "openid email profile",
                "access_type": "offline",
                "state": state
            }
            authorize_url = f"{oauth.configuration['authorization_endpoint']}?{urlencode(params)}"

        elif provider == "github":
            params = {
                "client_id": oauth.client_id,
                "redirect_uri": get_oauth_redirect_url(provider),
                "scope": "user:email",
                "state": state
            }
            authorize_url = f"{oauth.authorize_url}?{urlencode(params)}"

        elif provider == "wechat":
            params = {
                "appid": oauth.client_id,
                "redirect_uri": get_oauth_redirect_url(provider),
                "response_type": "code",
                "scope": "snsapi_login",
                "state": state
            }
            authorize_url = f"{oauth.authorize_url}?{urlencode(params)}#wechat_redirect"
            
        elif provider == "facebook":
            params = {
                "client_id": oauth.client_id,
                "redirect_uri": get_oauth_redirect_url(provider),
                "response_type": "code",
                "scope": "email,public_profile",
                "state": state
            }
            authorize_url = f"{oauth.authorize_url}?{urlencode(params)}"
        
        else:
            return ApiResponse(
                code=400,
                msg=f"Unsupported OAuth provider: {provider}",
                data=None
            )

        response.set_cookie(
            key="oauth_state",
            value=state,
            max_age=600,
            httponly=True,
            secure=settings.PRODUCTION,
            samesite="none" if settings.PRODUCTION else "lax",
            path=f"{settings.API_V1_STR}/auth/oauth",
        )
        return ApiResponse(data={"url": authorize_url})

    except Exception as e:
        return ApiResponse(
            code=500,
            msg=f"Failed to generate {provider} OAuth URL: {str(e)}",
            data=None
        )


@router.get("/{provider}/callback", response_model=ApiResponse[Token])
async def oauth_callback(
        provider: str,
        code: str,
        state: str,
        response: Response,
        request: Request,
        db: Session = Depends(deps.get_db)
):
    """
    Process OAuth callback
    """
    try:
        saved_state = request.cookies.get("oauth_state")
        if not saved_state or not hmac.compare_digest(saved_state, state):
            return ApiResponse(code=400, msg="OAuth state mismatch", data=None)
        response.delete_cookie(
            key="oauth_state",
            path=f"{settings.API_V1_STR}/auth/oauth",
            secure=settings.PRODUCTION,
            samesite="none" if settings.PRODUCTION else "lax",
        )

        oauth = get_oauth_provider(provider)

        if provider == "google":
            # Exchange code for token
            token_response = requests.post(
                oauth.configuration["token_endpoint"],
                data={
                    "client_id": oauth.client_id,
                    "client_secret": oauth.client_secret,
                    "code": code,
                    "redirect_uri": get_oauth_redirect_url(provider),
                    "grant_type": "authorization_code"
                }
            )
            token_response.raise_for_status()
            token_data = token_response.json()
            user_info = oauth.get_user_info(token_data["access_token"])

        elif provider == "github":
            # Exchange code for token
            headers = {"Accept": "application/json"}
            token_response = requests.post(
                oauth.token_url,
                data={
                    "client_id": oauth.client_id,
                    "client_secret": oauth.client_secret,
                    "code": code,
                    "redirect_uri": get_oauth_redirect_url(provider)
                },
                headers=headers
            )
            token_response.raise_for_status()
            token_data = token_response.json()

            if "error" in token_data:
                return ApiResponse(
                    code=400,
                    msg=f"GitHub OAuth error: {token_data['error']}",
                    data=None
                )

            user_info = oauth.get_user_info(token_data["access_token"])

        elif provider == "wechat":
            # Exchange code for access token
            params = {
                "appid": oauth.client_id,
                "secret": oauth.client_secret,
                "code": code,
                "grant_type": "authorization_code"
            }
            token_response = requests.get(oauth.token_url, params=params)
            token_response.raise_for_status()
            token_data = token_response.json()

            if "errcode" in token_data:
                return ApiResponse(
                    code=400,
                    msg=f"WeChat OAuth error: {token_data['errmsg']}",
                    data=None
                )

            user_info = oauth.get_user_info(
                token_data["access_token"],
                token_data["openid"]
            )
            
        elif provider == "facebook":
            # Exchange code for token
            token_response = requests.get(
                oauth.token_url,
                params={
                    "client_id": oauth.client_id,
                    "client_secret": oauth.client_secret,
                    "code": code,
                    "redirect_uri": get_oauth_redirect_url(provider)
                }
            )
            token_response.raise_for_status()
            token_data = token_response.json()
            
            if "error" in token_data:
                return ApiResponse(
                    code=400,
                    msg=f"Facebook OAuth error: {token_data['error']['message']}",
                    data=None
                )
                
            user_info = oauth.get_user_info(token_data["access_token"])

        else:
            return ApiResponse(
                code=400,
                msg=f"Unsupported OAuth provider: {provider}",
                data=None
            )

        # Create or update user
        db_user = create_or_update_user(
            db=db,
            email=user_info["email"],
            name=user_info.get("name") or user_info.get("login"),
            oauth_provider=provider,
            oauth_id=str(user_info.get("id"))
        )

        # Create JWT token
        token_data = {
            "email": db_user.email,
            "oauth_provider": provider,
            "oauth_id": db_user.oauth_id
        }
        access_token = create_oauth_token(token_data, provider)
        set_refresh_cookie(response, db_user.email)

        # Return response in the correct format using the User model
        return ApiResponse(data=Token(
            access_token=access_token,
            token_type="bearer",
            user=User.model_validate(db_user)
        ))

    except Exception as e:
        return ApiResponse(
            code=500,
            msg=f"Failed to process {provider} OAuth callback: {str(e)}",
            data=None
        )
