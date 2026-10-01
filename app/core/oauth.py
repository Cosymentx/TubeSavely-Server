from typing import Dict, Any
import requests
import logging
from fastapi import HTTPException, status
from datetime import timedelta

from .config import settings
from .auth import create_access_token

# 配置日志
logger = logging.getLogger(__name__)

class OAuth2Provider:
    def __init__(self, name: str):
        self.name = name

class GoogleOAuth2(OAuth2Provider):
    def __init__(self):
        super().__init__("google")
        self.client_id = settings.GOOGLE_CLIENT_ID
        self.client_secret = settings.GOOGLE_CLIENT_SECRET
        self.conf_url = settings.GOOGLE_CONF_URL
        self._conf = None

    @property
    def configuration(self) -> Dict[str, Any]:
        if self._conf is None:
            resp = requests.get(self.conf_url)
            resp.raise_for_status()
            self._conf = resp.json()
        return self._conf

    def get_user_info(self, access_token: str) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = requests.get(self.configuration["userinfo_endpoint"], headers=headers)
        resp.raise_for_status()
        return resp.json()

class GitHubOAuth2(OAuth2Provider):
    def __init__(self):
        super().__init__("github")
        self.client_id = settings.GITHUB_CLIENT_ID
        self.client_secret = settings.GITHUB_CLIENT_SECRET
        self.authorize_url = settings.GITHUB_AUTHORIZE_URL
        self.token_url = settings.GITHUB_TOKEN_URL
        self.api_base_url = settings.GITHUB_API_BASE_URL

    def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        Get GitHub user info with retry mechanism
        """
        headers = {
            "Authorization": f"token {access_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "TubeSavely"  # GitHub API 要求设置 User-Agent
        }

        # 配置重试会话
        session = requests.Session()
        retries = requests.adapters.Retry(
            total=3,  # 最多重试3次
            backoff_factor=0.5,  # 重试间隔
            status_forcelist=[500, 502, 503, 504],  # 这些状态码会触发重试
            allowed_methods=["GET", "POST"]  # 允许重试的请求方法
        )
        adapter = requests.adapters.HTTPAdapter(max_retries=retries)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        try:
            # 获取用户基本信息
            user_resp = session.get(
                f"{self.api_base_url}/user",
                headers=headers,
                timeout=10  # 设置超时时间
            )
            user_resp.raise_for_status()
            user_data = user_resp.json()

            # 获取用户邮箱
            emails_resp = session.get(
                f"{self.api_base_url}/user/emails",
                headers=headers,
                timeout=10
            )
            emails_resp.raise_for_status()
            emails = emails_resp.json()

            # 获取主邮箱
            primary_email = next(
                (email["email"] for email in emails if email["primary"]),
                user_data.get("email")
            )

            if not primary_email:
                raise ValueError("No primary email found in GitHub account")

            return {
                "id": str(user_data["id"]),
                "email": primary_email,
                "name": user_data.get("name") or user_data["login"],
                "avatar": user_data.get("avatar_url"),
                "login": user_data["login"]  # 添加 login 字段
            }

        except requests.exceptions.SSLError as e:
            logger.error(f"SSL Error when connecting to GitHub: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to connect to GitHub securely. Please try again later."
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching GitHub user info: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to fetch user information from GitHub. Please try again later."
            )
        except Exception as e:
            logger.error(f"Unexpected error in GitHub OAuth: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred. Please try again later."
            )
        finally:
            session.close()

class FacebookOAuth2(OAuth2Provider):
    def __init__(self):
        super().__init__("facebook")
        self.client_id = settings.FACEBOOK_CLIENT_ID
        self.client_secret = settings.FACEBOOK_CLIENT_SECRET
        self.authorize_url = settings.FACEBOOK_AUTHORIZE_URL
        self.token_url = settings.FACEBOOK_TOKEN_URL
        self.api_base_url = settings.FACEBOOK_API_BASE_URL

    def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        获取 Facebook 用户信息
        """
        try:
            # 获取用户基本信息
            params = {
                "fields": "id,name,email,picture",
                "access_token": access_token
            }
            response = requests.get(self.api_base_url, params=params)
            response.raise_for_status()
            user_info = response.json()

            # 处理头像URL
            if "picture" in user_info and "data" in user_info["picture"]:
                user_info["avatar"] = user_info["picture"]["data"]["url"]

            return user_info
        except Exception as e:
            logger.error(f"Failed to get Facebook user info: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to get user info from Facebook"
            )
        
        headers = {
            "Authorization": f"token {access_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "TubeSavely"  # GitHub API 要求设置 User-Agent
        }

        # 配置重试会话
        session = requests.Session()
        retries = requests.adapters.Retry(
            total=3,  # 最多重试3次
            backoff_factor=0.5,  # 重试间隔
            status_forcelist=[500, 502, 503, 504],  # 这些状态码会触发重试
            allowed_methods=["GET", "POST"]  # 允许重试的请求方法
        )
        adapter = requests.adapters.HTTPAdapter(max_retries=retries)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        try:
            # 获取用户基本信息
            user_resp = session.get(
                f"{self.api_base_url}/user",
                headers=headers,
                timeout=10  # 设置超时时间
            )
            user_resp.raise_for_status()
            user_data = user_resp.json()

            # 获取用户邮箱
            emails_resp = session.get(
                f"{self.api_base_url}/user/emails",
                headers=headers,
                timeout=10
            )
            emails_resp.raise_for_status()
            emails = emails_resp.json()

            # 获取主邮箱
            primary_email = next(
                (email["email"] for email in emails if email["primary"]),
                user_data.get("email")
            )

            if not primary_email:
                raise ValueError("No primary email found in GitHub account")

            return {
                "id": str(user_data["id"]),
                "email": primary_email,
                "name": user_data.get("name") or user_data["login"],
                "avatar": user_data.get("avatar_url"),
                "login": user_data["login"]  # 添加 login 字段
            }

        except requests.exceptions.SSLError as e:
            logger.error(f"SSL Error when connecting to GitHub: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to connect to GitHub securely. Please try again later."
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching GitHub user info: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to fetch user information from GitHub. Please try again later."
            )
        except Exception as e:
            logger.error(f"Unexpected error in GitHub OAuth: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred. Please try again later."
            )
        finally:
            session.close()

class WeChatOAuth2(OAuth2Provider):
    def __init__(self):
        super().__init__("wechat")
        self.client_id = settings.WECHAT_APP_ID
        self.client_secret = settings.WECHAT_APP_SECRET
        self.authorize_url = settings.WECHAT_AUTHORIZE_URL
        self.token_url = settings.WECHAT_ACCESS_TOKEN_URL
        self.userinfo_url = settings.WECHAT_USERINFO_URL

    def get_user_info(self, access_token: str, openid: str) -> Dict[str, Any]:
        params = {
            "access_token": access_token,
            "openid": openid,
            "lang": "zh_CN"
        }
        resp = requests.get(self.userinfo_url, params=params)
        resp.raise_for_status()
        user_data = resp.json()
        
        return {
            "id": user_data["openid"],
            "email": f"{user_data['openid']}@wechat.com",  # WeChat doesn't provide email
            "name": user_data.get("nickname"),
            "picture": user_data.get("headimgurl")
        }

def create_oauth_token(user_info: Dict[str, Any], provider: str) -> str:
    """
    Create OAuth token from user info.
    Returns only the JWT string.
    """
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return create_access_token(
        data={
            "sub": user_info["email"],  # Use email as subject
            "oauth_provider": provider,
            "oauth_id": user_info.get("oauth_id")
        },
        expires_delta=access_token_expires
    )

# Initialize OAuth providers
google_oauth = GoogleOAuth2()
github_oauth = GitHubOAuth2()
wechat_oauth = WeChatOAuth2()
facebook_oauth = FacebookOAuth2()

def get_oauth_provider(provider: str) -> OAuth2Provider:
    """
    Get OAuth provider by name.
    """
    providers = {
        "google": google_oauth,
        "github": github_oauth,
        "wechat": wechat_oauth,
        "facebook": facebook_oauth
    }
    
    if provider not in providers:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported OAuth provider: {provider}"
        )
    
    return providers[provider]

def oauth():
    return None