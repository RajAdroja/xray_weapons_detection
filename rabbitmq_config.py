import os
from pydantic_settings import BaseSettings

class RabbitMQSettings(BaseSettings):
    rabbitmq_url: str = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
    prediction_queue: str = "prediction_queue"
    result_queue: str = "result_queue"
    status_queue: str = "status_queue"
    exchange_name: str = "prediction_exchange"
    routing_key: str = "prediction.process"
    
    # Additional optional fields from .env
    rabbitmq_management_url: str = "http://localhost:15672"
    redis_url: str = "redis://localhost:6379"
    api_port: int = 8000
    api_host: str = "0.0.0.0"
    worker_concurrency: int = 2
    worker_log_level: str = "INFO"
    environment: str = "development"
    
    class Config:
        env_file = ".env"

rabbitmq_settings = RabbitMQSettings()