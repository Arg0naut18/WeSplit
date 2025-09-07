import os
from dotenv import load_dotenv


load_dotenv()


class MongoConfigs:
    url = os.getenv("MONGO_SRV_URL", "mongo_srv")


class EndpointConfigs:
    host = os.environ["HOST"]
    port = os.environ["PORT"]
    endpoint = f"https://{host}:{port}" if not os.getenv(
        "ENDPOINT") else os.getenv("ENDPOINT")
    app_key = os.getenv("APP_KEY", "app_key")
