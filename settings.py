from dotenv import load_dotenv

import os

load_dotenv()

slack_token = os.getenv("SLACK_TOKEN")

minio_endpoint = os.getenv("MINIO_ENDPOINT")
minio_access_key = os.getenv("MINIO_ACCESS_KEY")
minio_secret_key = os.getenv("MINIO_SECRET_KEY")
minio_bucket = os.getenv("MINIO_BUCKET", "slack")
minio_secure = os.getenv("MINIO_SECURE", "true").lower() == "true"

file_output_directory = os.getenv("FILE_OUTPUT_DIRECTORY", "")