from urllib.parse import urlparse
import uuid

from flask import Flask, request, make_response
import praw
import settings

app = Flask(__name__)

def get_redir_path() -> str:
    url = urlparse(settings.auth_redir_url)

    return url.path

def shutdown_server():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()

def validate_auth_response(state: str, code: str) -> bool:
    global reddit, reddit_state

    if state != reddit_state:
        return False

    token = reddit.auth.authorize(code)

    if token is None:
        return False

    with open(settings.refresh_token_file, "w") as fd:
        fd.write(token)

    return True

@app.route(get_redir_path(), methods=["GET"])
def root():
    state = request.args.get("state")
    code = request.args.get("code")

    if state is None or code is None:
        return make_response("Didn't get a valid state or code, please try again", 400)

    if not validate_auth_response(state, code):
        return make_response("Something went wrong in validation, please try again", 400)

    shutdown_server()

    return "Cool."

def run():
    global app, reddit, reddit_state

    reddit = praw.Reddit(client_id=settings.reddit_client_id,
                         client_secret=settings.reddit_client_secret,
                         redirect_uri=settings.auth_redir_url,
                         user_agent=settings.reddit_user_agent)

    reddit_state = str(uuid.uuid4())
    reddit_url = reddit.auth.url(["*"], reddit_state, "permanent")

    print("Open this link to authenticate with Reddit:")
    print(reddit_url)

    app.run(settings.auth_http_bind, settings.auth_http_port, debug=False)