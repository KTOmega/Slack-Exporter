from dotenv import load_dotenv

import os

load_dotenv()

slack_token = os.getenv("SLACK_TOKEN")

slack_client_id = os.getenv("SLACK_CLIENT_ID")
slack_client_secret = os.getenv("SLACK_CLIENT_SECRET")
slack_signing_secret = os.getenv("SLACK_SIGNING_SECRET")

file_output_directory = os.getenv("FILE_OUTPUT_DIRECTORY", "")