from dotenv import load_dotenv

import os

load_dotenv()

_default_scopes = [
    "channels:history",
    "channels:read",
    "emoji:read",
    "files:read",
    "groups:history",
    "groups:read",
    "im:history",
    "im:read",
    "mpim:history",
    "mpim:read",
    "pins:read",
    "reminders:read",
    "team:read",
    "users:read",
]

def process_scopes(scopes):
    if scopes is None:
        return _default_scopes

    return scopes.split(",")

slack_token = os.getenv("SLACK_TOKEN")

slack_client_id = os.getenv("SLACK_CLIENT_ID")
slack_client_secret = os.getenv("SLACK_CLIENT_SECRET")
slack_signing_secret = os.getenv("SLACK_SIGNING_SECRET")
slack_oauth_scopes = process_scopes(os.getenv("SLACK_SCOPES"))
slack_state_dir = os.getenv("SLACK_STATE_DIR", "./state")

file_output_directory = os.getenv("FILE_OUTPUT_DIRECTORY", "./data")

auth_redir_url = os.getenv("AUTH_REDIR_URL", "http://localhost:5000/slack/oauth/callback")
auth_http_bind = os.getenv("AUTH_HTTP_BIND", "127.0.0.1")
auth_http_port = os.getenv("AUTH_HTTP_PORT", 5000)