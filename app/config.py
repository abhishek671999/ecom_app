from pydantic_settings import BaseSettings
 
 
class Settings(BaseSettings):
    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "ecom_app_oltp"
 
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
 
 
settings = Settings()