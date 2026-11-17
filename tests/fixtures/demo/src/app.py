import os

db = os.getenv("DATABASE_URL")
level = os.environ.get("LOG_LEVEL")
port = os.getenv("DB_PORT")
region = os.getenv("AWS_REGION")
