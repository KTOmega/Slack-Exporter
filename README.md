# Slack Exporter

Exports all of a user's data from a Slack workspace, including DMs and private groups.

Requires Python >= 3.7.

# Instructions

1. Make sure you have Python 3.7 or newer: `python3 --version`
2. Clone this repo: `git clone https://github.com/KTOmega/Slack-Exporter.git`
3. Create a virtual environment: `virtualenv -p python3 venv`
4. Load the virtual environment: `source venv/bin/activate`
5. Install dependencies: `pip install -r requirements.txt`
6. Copy `.env.example` to `.env`: `cp .env.example .env`
7. Edit `.env` with your values.
   1. If you have an existing Slack token for your workspace with the right scopes, set the `SLACK_TOKEN` variable.
   2. Otherwise, create a new Slack app by reading the [Creating an app](#creating-an-app) section.
   3. Fill out the `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, and `SLACK_SIGNING_SECRET` variables.
   4. Change `FILE_OUTPUT_DIRECTORY` to your desired output directory.
8. Run the app: `python app.py`

## Creating an app

1. Create an app at https://api.slack.com/apps?new_app=1.
2. Note the **Client ID**, **Client Secret**, and **Signing Secret** boxes.
3. In the **OAuth & Permissions** page, add `http://localhost:5000/slack/oauth/callback` as a redirect URL.
4. In the same page, add the following OAuth user token scopes:
   - `channels.history`
   - `channels:read`
   - `emoji:read`
   - `files:read`
   - `groups:history`
   - `groups:read`
   - `im:history`
   - `im:read`
   - `mpim:history`
   - `mpim:read`
   - `pins:read`
   - `reminders:read`
   - `team:read`
   - `users:read` 