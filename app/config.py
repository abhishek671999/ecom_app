from pydantic_settings import BaseSettings
 
 
class Settings(BaseSettings):
    db_host: str
    db_port: int
    db_user: str
    db_password: str
    db_name: str
 
    class Config:
        env_file = "env/.env.database"
        env_file_encoding = "utf-8"
 
class SparkSettings(BaseSettings):
     spark_mode: str
     app_name: str
     
     class Config:
        env_file = "env/.env.spark"
        env_file_encoding = "utf-8"
     
 
settings = Settings()
spark_settings = SparkSettings()