from flask import Flask, request, make_response

from slack_sdk.oauth import AuthorizeUrlGenerator
from slack_sdk.oauth.installation_store import FileInstallationStore, Installation
from slack_sdk.oauth.state_store import FileOAuthStateStore
from slack_sdk.web import WebClient

import settings

# A lot of code taken from Slack API docs
# https://slack.dev/python-slack-sdk/oauth/index.html

# Issue and consume state parameter value on the server-side.
state_store = FileOAuthStateStore(expiration_seconds=300, base_dir=settings.slack_state_dir)

# Persist installation data and lookup it by IDs.
installation_store = FileInstallationStore(base_dir=settings.slack_state_dir)

# Build https://slack.com/oauth/v2/authorize with sufficient query parameters
authorize_url_generator = AuthorizeUrlGenerator(
    client_id=settings.slack_client_id,
    user_scopes=settings.slack_oauth_scopes,
)

app = Flask(__name__)

def shutdown_server():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()

@app.route("/slack/oauth/callback", methods=["GET"])
def oauth_callback():
    # Retrieve the auth code and state from the request params
    if "code" in request.args:
        # Verify the state parameter
        if state_store.consume(request.args["state"]):
            client = WebClient()  # no prepared token needed for this
            # Complete the installation by calling oauth.v2.access API method
            oauth_response = client.oauth_v2_access(
                client_id=settings.slack_client_id,
                client_secret=settings.slack_client_secret,
                redirect_uri=settings.auth_redir_url,
                code=request.args["code"]
            )

            installer = oauth_response.get("authed_user", {})
            user_token = installer.get("access_token")

            if user_token is None:
                return make_response(f"Failure getting user token :( {str(oauth_response)}", 500)

            settings.slack_token = user_token

            shutdown_server()
            return "Thanks for installing this app!"
        else:
            return make_response(f"Try the installation again (the state value is already expired)", 400)

    error = request.args["error"] if "error" in request.args else ""
    return make_response(f"Something is wrong with the installation (error: {error})", 400)

@app.route("/slack/install", methods=["GET"])
def oauth_start():

    state = state_store.issue()

    url = authorize_url_generator.generate(state)
    return f'<a href="{url}">Add to Slack</a>'

def run():
    global app

    print("Open this link to authenticate with Slack:")
    print(f"http://{settings.auth_http_bind}:{settings.auth_http_port}/slack/install")

    app.run(settings.auth_http_bind, settings.auth_http_port, debug=False)