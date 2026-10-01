import os
import json
from pydantic_settings import BaseSettings

def load_env_file():
    if os.environ.get("VERCEL"):
        return
    # 根据环境变量加载不同的配置文件
    env_file = ".env.production" if os.environ.get("PRODUCTION", "").lower() == "true" else ".env"
    if os.path.exists(env_file):
        from dotenv import load_dotenv
        load_dotenv(env_file)

load_env_file()

class Settings(BaseSettings):
    # 基本配置
    API_V1_STR: str = os.environ.get("API_V1_STR", "/api/v1")
    PROJECT_NAME: str = os.environ.get("PROJECT_NAME", "TubeSavely API")
    
    # JWT配置
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "")
    ALGORITHM: str = os.environ.get("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 24))
    
    # CORS配置
    BACKEND_CORS_ORIGINS: list[str] = json.loads(os.environ.get("BACKEND_CORS_ORIGINS", '["http://localhost:5173", "http://127.0.0.1:5173"]'))
    
    # 环境配置
    PRODUCTION: bool = os.environ.get("PRODUCTION", "false").lower() == "true"

    # 数据库配置
    DB_HOST: str = os.environ.get("DB_HOST", "localhost")
    DB_USER: str = os.environ.get("DB_USER", "root")
    DB_PASSWORD: str = os.environ.get("DB_PASSWORD", "root")
    DB_NAME: str = os.environ.get("DB_NAME", "tubesavely")
    DATABASE_URL: str = os.environ.get("DATABASE_URL", f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}?charset=utf8mb4")

    # Redis配置
    REDIS_HOST: str = os.environ.get("REDIS_HOST", "localhost")
    REDIS_PORT: str = os.environ.get("REDIS_PORT", "6379")
    REDIS_PASSWORD: str = os.environ.get("REDIS_PASSWORD", "")
    REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379")

    # API URL
    API_URL: str = os.environ.get("API_URL", "http://localhost:9527")

    # 前端URL配置
    FRONTEND_URL: str = os.environ.get("FRONTEND_URL", "http://localhost:5173")
    
    # Google OAuth2
    GOOGLE_CLIENT_ID: str = os.environ.get("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_CONF_URL: str = os.environ.get("GOOGLE_CONF_URL", "https://accounts.google.com/.well-known/openid-configuration")
    
    # GitHub OAuth2
    GITHUB_CLIENT_ID: str = os.environ.get("GITHUB_CLIENT_ID", "")
    GITHUB_CLIENT_SECRET: str = os.environ.get("GITHUB_CLIENT_SECRET", "")
    GITHUB_AUTHORIZE_URL: str = os.environ.get("GITHUB_AUTHORIZE_URL", "https://github.com/login/oauth/authorize")
    GITHUB_TOKEN_URL: str = os.environ.get("GITHUB_TOKEN_URL", "https://github.com/login/oauth/access_token")
    GITHUB_API_BASE_URL: str = os.environ.get("GITHUB_API_BASE_URL", "https://api.github.com")
    
    # Facebook OAuth2
    FACEBOOK_CLIENT_ID: str = os.environ.get("FACEBOOK_CLIENT_ID", "")
    FACEBOOK_CLIENT_SECRET: str = os.environ.get("FACEBOOK_CLIENT_SECRET", "")
    FACEBOOK_GRAPH_VERSION: str = os.environ.get("FACEBOOK_GRAPH_VERSION") or "v12.0"
    FACEBOOK_AUTHORIZE_URL: str = os.environ.get(
        "FACEBOOK_AUTHORIZE_URL",
        f"https://www.facebook.com/{FACEBOOK_GRAPH_VERSION}/dialog/oauth"
    )
    FACEBOOK_TOKEN_URL: str = os.environ.get(
        "FACEBOOK_TOKEN_URL",
        f"https://graph.facebook.com/{FACEBOOK_GRAPH_VERSION}/oauth/access_token"
    )
    FACEBOOK_API_BASE_URL: str = os.environ.get(
        "FACEBOOK_API_BASE_URL",
        f"https://graph.facebook.com/{FACEBOOK_GRAPH_VERSION}/me"
    )

    # WeChat OAuth2
    WECHAT_APP_ID: str = os.environ.get("WECHAT_APP_ID", "")
    WECHAT_APP_SECRET: str = os.environ.get("WECHAT_APP_SECRET", "")
    WECHAT_AUTHORIZE_URL: str = os.environ.get("WECHAT_AUTHORIZE_URL", "https://open.weixin.qq.com/connect/qrconnect")
    WECHAT_ACCESS_TOKEN_URL: str = os.environ.get("WECHAT_ACCESS_TOKEN_URL", "https://api.weixin.qq.com/sns/oauth2/access_token")
    WECHAT_USERINFO_URL: str = os.environ.get("WECHAT_USERINFO_URL", "https://api.weixin.qq.com/sns/userinfo")

    # PayPal配置
    PAYPAL_CLIENT_ID: str = os.environ.get("PAYPAL_CLIENT_ID", "")
    PAYPAL_CLIENT_SECRET: str = os.environ.get("PAYPAL_CLIENT_SECRET", "")

    # Stripe配置
    STRIPE_PUBLIC_KEY: str = os.environ.get("STRIPE_PUBLIC_KEY", "")
    STRIPE_SECRET_KEY: str = os.environ.get("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

    # Airwallex配置
    AIRWALLEX_CLIENT_ID:str = os.environ.get("AIRWALLEX_CLIENT_ID", "")
    AIRWALLEX_API_KEY :str = os.environ.get("AIRWALLEX_API_KEY", "")
    
    # 支付宝配置    
    ALIPAY_APP_ID: str = os.environ.get("ALIPAY_APP_ID", "") # 支付宝APPID
    # 应用私钥
    ALIPAY_PRIVATE_KEY: str= os.environ.get("ALIPAY_PRIVATE_KEY", "")
    # 支付宝公钥    
    ALIPAY_PUBLIC_KEY: str= os.environ.get("ALIPAY_PUBLIC_KEY", "")
    # 支付宝网关
    ALIPAY_GATEWAY: str = os.environ.get("ALIPAY_GATEWAY", "")

    # Creem配置
    CREEM_API_KEY: str = os.environ.get("CREEM_API_KEY", "")
    CREEM_WEBHOOK_SECRET: str = os.environ.get("CREEM_WEBHOOK_SECRET", "")
    CREEM_API_BASE_URL :str = os.environ.get("CREEM_API_BASE_URL", "https://test-api.creem.io/v1/checkouts")
    
    # 微信支付配置
    WECHAT_PAY_APP_ID: str = os.environ.get("WECHAT_PAY_APP_ID", "") # 微信APPID
    # 商户号
    WECHAT_PAY_MCH_ID: str = os.environ.get("WECHAT_PAY_MCH_ID", "")
    # API密钥
    WECHAT_PAY_KEY: str = os.environ.get("WECHAT_PAY_KEY", "")  
    # 商户证书   
    WECHAT_PAY_CERT: str = os.environ.get("WECHAT_PAY_CERT", "")     
    # 商户证书私钥
    WECHAT_PAY_KEY_STRING: str = os.environ.get("WECHAT_PAY_KEY_STRING", "")  

    # MinIO配置
    MINIO_ENDPOINT: str = os.environ.get("MINIO_ENDPOINT", "")
    MINIO_ACCESS_KEY: str = os.environ.get("MINIO_ACCESS_KEY", "")  # 与 MINIO_ROOT_USER 相同
    MINIO_SECRET_KEY: str = os.environ.get("MINIO_SECRET_KEY", "")  # 与 MINIO_ROOT_PASSWORD 相同
    MINIO_BUCKET_NAME: str = os.environ.get("MINIO_BUCKET_NAME", "")
    MINIO_SECURE: bool = os.environ.get("MINIO_SECURE", "false").lower() == "true"

    VIDEO_PROXY: str = os.environ.get("VIDEO_PROXY", "")
    YOUTUBE_COOKIES_BASE64: str = os.environ.get("YOUTUBE_COOKIES_BASE64", "")
    DOUYIN_COOKIES_BASE64: str = os.environ.get("DOUYIN_COOKIES_BASE64", "")
    TIKTOK_COOKIES_BASE64: str = os.environ.get("TIKTOK_COOKIES_BASE64", "")
    DOUYIN_PROXY: str | None = os.environ.get("DOUYIN_PROXY")
    TIKTOK_PROXY: str | None = os.environ.get("TIKTOK_PROXY")
    EXTERNAL_PARSE_TOKEN: str = os.environ.get("EXTERNAL_PARSE_TOKEN", "")
    VIDEO_PARSE_CREDITS_COST: int = int(os.environ.get("VIDEO_PARSE_CREDITS_COST", "3"))
    CONVERT_TASK_CREDITS_COST: int = int(os.environ.get("CONVERT_TASK_CREDITS_COST", "5"))
    GENERATE_TASK_CREDITS_COST: int = int(os.environ.get("GENERATE_TASK_CREDITS_COST", "10"))
    ENABLE_TASKS: bool = os.environ.get("ENABLE_TASKS", "false").lower() == "true"
    FALLBACK_PARSE_CLIENT_ID: str = os.environ.get("FALLBACK_PARSE_CLIENT_ID", "")
    FALLBACK_PARSE_SIGN: str = os.environ.get("FALLBACK_PARSE_SIGN", "")

    class Config:
        case_sensitive = True

settings = Settings()

if settings.PRODUCTION:
    missing = [
        name for name in ("SECRET_KEY", "DATABASE_URL", "REDIS_URL")
        if not os.environ.get(name)
    ]
    if missing:
        raise RuntimeError(
            "Missing required production environment variables: " + ", ".join(missing)
        )
    if len(settings.SECRET_KEY) < 32:
        raise RuntimeError("SECRET_KEY must be at least 32 characters in production")

