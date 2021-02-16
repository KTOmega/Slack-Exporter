from slack_sdk.web.async_client import AsyncWebClient, AsyncSlackResponse
from slack_sdk.errors import SlackApiError

import httpx

import asyncio
import json
import logging
import os
import sys
import time
from typing import Dict, Any

import constants
from context import ExporterContext
from downloader import FileDownloader
import models
import patch
import settings

root = logging.getLogger()
root.setLevel(logging.INFO)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('[%(asctime)s][%(levelname)s][%(name)s] %(message)s')
handler.setFormatter(formatter)
root.addHandler(handler)

log = logging.getLogger()

async def main():
    # Patch Slack API functions
    patch.patch()

    # DEPENDENCY INJECTION: Construct all needed instances of objects
    downloader = FileDownloader(settings.file_output_directory,
        settings.slack_token)

    slack_client = AsyncWebClient(token=settings.slack_token)

    # Initialize context
    ctx = ExporterContext(export_time=int(time.time()), slack_client=slack_client, downloader=downloader)

    # Run
    try:
        await export_files(ctx)
    except Exception as e:
        log.error(f"Uncaught {e.__class__.__name__}", exc_info=e)

    # Clean up
    await ctx.close()

async def export_emojis(ctx: ExporterContext):
    try:
        emojis = await ctx.slack_client.emoji_list()

        for emoji, url in emojis["emoji"].items():
            if not url.startswith("https://"):
                continue

            emoji_filename = os.path.basename(url)
            emoji_fullname = os.path.join(constants.EMOJI_EXPORT_DIR, emoji_filename)
            ctx.downloader.enqueue_download(emoji_fullname, url, use_auth=True)

        await ctx.downloader.flush_download_queue()
        ctx.downloader.write_json(os.path.join(constants.EMOJI_EXPORT_DIR, constants.EMOJI_JSON_FILE), emojis["emoji"])
    except SlackApiError as e:
        log.error("Got an API error while trying to export emojis", exc_info=e)

async def export_team(ctx: ExporterContext):
    try:
        team_data = await ctx.slack_client.team_info()

        for icon_name, icon_url in team_data["team"]["icon"].items():
            if not icon_url.startswith("https://"):
                continue

            icon_filename = os.path.basename(icon_url)
            icon_fullname = os.path.join(constants.TEAM_EXPORT_DIR, icon_filename)

            ctx.downloader.enqueue_download(icon_fullname, icon_url)

        await ctx.downloader.flush_download_queue()

        ctx.downloader.write_json(os.path.join(constants.TEAM_EXPORT_DIR, constants.TEAM_JSON_FILE), team_data["team"])
    except SlackApiError as e:
        log.error("Got an API error while trying to export team info", exc_info=e)

async def export_reminders(ctx: ExporterContext):
    try:
        reminders = await ctx.slack_client.reminders_list()

        ctx.downloader.write_json(constants.REMINDERS_JSON_FILE, reminders["reminders"])
    except SlackApiError as e:
        log.error("Got an API error while trying to export reminders", exc_info=e)

async def export_users(ctx: ExporterContext):
    try:
        users_generator = await ctx.slack_client.users_list()
        all_users = []

        async for users in users_generator:
            all_users.extend(users["members"])
            for user in users["members"]:
                user_obj = models.SlackUser(user)
                all_users.append(user)

                for url, filename in user_obj.get_exportable_data():
                    full_filename = os.path.join(constants.USERS_EXPORT_DIR, filename)
                    ctx.downloader.enqueue_download(full_filename, url)

            await ctx.downloader.flush_download_queue()

        ctx.downloader.write_json(os.path.join(constants.USERS_EXPORT_DIR, constants.USERS_JSON_FILE), all_users)
    except SlackApiError as e:
        log.error("Got an API error while trying to export user info", exc_info=e)

async def export_files(ctx: ExporterContext):
    try:
        files_generator = await ctx.slack_client.files_list(count=10, ts_to=ctx.export_time, ts_from=1612050000) #TODO: change with real  values
        all_files = []

        async for file_resp in files_generator:
            all_files.extend(file_resp["files"])
            for sfile in file_resp["files"]:
                file_obj = models.SlackFile(sfile)

                for url, filename in file_obj.get_exportable_data():
                    full_filename = os.path.join(constants.FILES_EXPORT_DIR, filename)
                    ctx.downloader.enqueue_download(full_filename, url, use_auth=True)

            await ctx.downloader.flush_download_queue()

        ctx.downloader.write_json(os.path.join(constants.FILES_EXPORT_DIR, constants.FILES_JSON_FILE), all_files)
    except SlackApiError as e:
        log.error("Got an API error while trying to export files", exc_info=e)

async def export_conversations(ctx: ExporterContext):
    try:
        convo_generator = await ctx.slack_client.conversations_list(limit=1, types="public_channel,private_channel,mpim,im")
        all_conversations = []

        async for convo_resp in convo_generator:
            all_conversations.extend(convo_resp["channels"])
            for convo in convo_resp["channels"]:
                convo_obj = models.SlackConversation(convo)
                convo_folder = os.path.join(constants.CONVERSATIONS_EXPORT_DIR, convo_obj.id)

                await export_pins(ctx, convo_obj)

        ctx.downloader.write_json(os.path.join(constants.CONVERSATIONS_EXPORT_DIR, constants.CONVERSATIONS_JSON_FILE), all_conversations)
    except SlackApiError as e:
        log.error("Got an API error while trying to export conversations", exc_info=e)

async def export_pins(ctx: ExporterContext, convo: models.SlackConversation):
    try:
        pins = await ctx.slack_client.pins_list(channel=convo.id)

        filename = os.path.join(constants.CONVERSATIONS_EXPORT_DIR, convo.id, constants.PINS_JSON_FILE)
        ctx.downloader.write_json(filename, pins["items"])
    except SlackApiError as e:
        log.error(f"Got an API error while trying to export pins for conversation {convo.id}", exc_info=e)

async def test(ctx: ExporterContext):
    try:
        files_generator = await ctx.slack_client.files_list(count=1, ts_to=ctx.export_time, ts_from=1613267318)

        async for slack_response in files_generator:
            print(json.dumps(slack_response.data, indent=2))
            for slack_file in slack_response["files"]:
                ctx.downloader.enqueue_download(slack_file["id"], slack_file["url_private"], use_auth=True)

        await ctx.downloader.flush_download_queue()
    except SlackApiError as e:
        log.error("Got an error when calling Slack API", exc_info=e)

if __name__ == "__main__":
    asyncio.run(main())