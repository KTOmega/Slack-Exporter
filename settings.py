from dotenv import load_dotenv

import os

load_dotenv()

slack_token = os.getenv("SLACK_TOKEN")

file_output_directory = os.getenv("FILE_OUTPUT_DIRECTORY", "")