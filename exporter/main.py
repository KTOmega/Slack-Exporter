from slack_sdk.web.async_client import AsyncWebClient, AsyncSlackResponse
from slack_sdk.errors import SlackApiError

import httpx
from progress.counter import Counter

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
from fragment import FragmentFactory
import models
import patch
import settings
import utils

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

    fragment_factory = FragmentFactory()

    # Initialize context
    ctx = ExporterContext(
        export_time=int(time.time()),
        output_directory=settings.file_output_directory,
        slack_client=slack_client,
        downloader=downloader,
        fragments=fragment_factory
    )

    # Run
    try:
        await export_everything(ctx)
    except Exception as e:
        log.error(f"Uncaught {e.__class__.__name__}", exc_info=e)

    # Clean up
    await ctx.close()

async def export_emojis(ctx: ExporterContext):
    emojis = await utils.with_retry(ctx.slack_client.emoji_list)

    try:
        for emoji, url in emojis["emoji"].items():
            if not url.startswith("https://"):
                continue

            emoji_filename = os.path.basename(url)
            emoji_fullname = os.path.join(constants.EMOJI_EXPORT_DIR, emoji_filename)
            ctx.downloader.enqueue_download(emoji_fullname, url, use_auth=True)

        await ctx.downloader.flush_download_queue() # probably catch something here
    except SlackApiError as e:
        log.error("Got an API error while trying to export emojis", exc_info=e)

    ctx.downloader.write_json(os.path.join(constants.EMOJI_EXPORT_DIR, constants.EMOJI_JSON_FILE), emojis["emoji"])

async def export_team(ctx: ExporterContext):
    team_data = await utils.with_retry(ctx.slack_client.team_info)

    try:
        for icon_name, icon_url in team_data["team"]["icon"].items():
            if not icon_url.startswith("https://"):
                continue

            icon_filename = os.path.basename(icon_url)
            icon_fullname = os.path.join(constants.TEAM_EXPORT_DIR, icon_filename)

            ctx.downloader.enqueue_download(icon_fullname, icon_url)

        await ctx.downloader.flush_download_queue() # probably catch something here
    except SlackApiError as e:
        log.error("Got an API error while trying to export team info", exc_info=e)

    ctx.downloader.write_json(os.path.join(constants.TEAM_EXPORT_DIR, constants.TEAM_JSON_FILE), team_data["team"])

async def export_reminders(ctx: ExporterContext):
    try:
        reminders = await utils.with_retry(ctx.slack_client.reminders_list)

        ctx.downloader.write_json(constants.REMINDERS_JSON_FILE, reminders["reminders"])
    except SlackApiError as e:
        log.error("Got an API error while trying to export reminders", exc_info=e)

async def export_users(ctx: ExporterContext):
    users_generator = await utils.with_retry(ctx.slack_client.users_list)
    all_users = []

    try:
        async for users in users_generator:
            all_users.extend(users["members"])
            for user in users["members"]:
                user_obj = models.SlackUser(user)
                all_users.append(user)

                for url, filename in user_obj.get_exportable_data():
                    full_filename = os.path.join(constants.USERS_EXPORT_DIR, filename)
                    ctx.downloader.enqueue_download(full_filename, url)

            await ctx.downloader.flush_download_queue()
    except SlackApiError as e:
        log.error("Got an API error while trying to export user info", exc_info=e)

    ctx.downloader.write_json(os.path.join(constants.USERS_EXPORT_DIR, constants.USERS_JSON_FILE), all_users)

def export_file(ctx: ExporterContext, slack_file: models.SlackFile):
    for url, filename in slack_file.get_exportable_data():
        full_filename = os.path.join(constants.FILES_EXPORT_DIR, filename)
        ctx.downloader.enqueue_download(full_filename, url, use_auth=True)

async def export_files(ctx: ExporterContext):
    files_generator = utils.AsyncIteratorWithRetry(
        ctx.slack_client.files_list, count=constants.ITEM_COUNT_LIMIT, ts_to=ctx.export_time, ts_from=ctx.last_export_time
    )
    all_files = []

    counter = Counter("Exporting files ")

    try:
        await files_generator.run()

        async for file_resp in files_generator:
            all_files.extend(file_resp["files"])
            for sfile in file_resp["files"]:
                file_obj = models.SlackFile(sfile)
                export_file(ctx, file_obj)
                counter.next()

            try:
                await ctx.downloader.flush_download_queue()
            except httpx.HTTPStatusError as e:
                log.error(f"Caught HTTP status code {e.response.status_code}", exc_info=e)
    except SlackApiError as e:
        log.error(f"Got an API error while trying to obtain file info", exc_info=e)

    ctx.downloader.write_json(os.path.join(constants.FILES_EXPORT_DIR, constants.FILES_JSON_FILE), all_files)
    counter.finish()

async def export_conversations(ctx: ExporterContext):
    convo_generator = utils.AsyncIteratorWithRetry(
        ctx.slack_client.conversations_list, limit=constants.ITEM_COUNT_LIMIT, types="public_channel,private_channel,mpim,im"
    )
    all_conversations = []

    try:
        await convo_generator.run()

        async for convo_resp in convo_generator:
            all_conversations.extend(convo_resp["channels"])
            for convo in convo_resp["channels"]:
                convo_obj = models.SlackConversation(convo)
                convo_folder = os.path.join(constants.CONVERSATIONS_EXPORT_DIR, convo_obj.id)

                await export_pins(ctx, convo_obj)
                await export_conversation_history(ctx, convo_obj)
    except SlackApiError as e:
        log.error("Got an API error while trying to export conversations", exc_info=e)

    ctx.downloader.write_json(os.path.join(constants.CONVERSATIONS_EXPORT_DIR, constants.CONVERSATIONS_JSON_FILE), all_conversations)

async def export_pins(ctx: ExporterContext, convo: models.SlackConversation):
    try:
        pins = await utils.with_retry(ctx.slack_client.pins_list, channel=convo.id)

        filename = os.path.join(constants.CONVERSATIONS_EXPORT_DIR, convo.id, constants.PINS_JSON_FILE)
        ctx.downloader.write_json(filename, pins["items"])
    except SlackApiError as e:
        log.error(f"Got an API error while trying to export pins for conversation {convo.id}", exc_info=e)

async def export_conversation_history(ctx: ExporterContext, convo: models.SlackConversation):
    def file_filter(raw_file: Dict[str, Any]) -> bool:
        if "mode" in raw_file and raw_file["mode"] == "tombstone":
            return False

        filename = os.path.join(constants.FILES_EXPORT_DIR, raw_file["id"])

        return not ctx.downloader.exists(filename)

    history_generator = utils.AsyncIteratorWithRetry(
        ctx.slack_client.conversations_history,
        channel=convo.id,
        limit=constants.ITEM_COUNT_LIMIT,
        latest=ctx.export_time,
        oldest=ctx.last_export_time
    )

    history_folder = os.path.join(ctx.output_directory, constants.CONVERSATIONS_EXPORT_DIR, convo.id, constants.HISTORY_JSON_DIR)

    history_fragment = ctx.fragments.create(history_folder)

    counter = Counter(f"Exporting conversation history ({convo.id}) ")

    try:
        await history_generator.run()

        async for history_resp in history_generator:
            for msg in history_resp["messages"]:
                msg_obj = models.SlackMessage(msg)

                try:
                    if msg_obj.has_files:
                        files = await msg_obj.get_files(ctx, file_filter)

                        for f in files:
                            export_file(ctx, f)
                except SlackApiError as e:
                    log.error(f"Error while obtaining file metadata for message {msg_obj.ts} in channel {convo.id}", exc_info=e)

                try:
                    if msg_obj.has_replies:
                        await msg_obj.populate_replies(ctx, convo)
                except SlackApiError as e:
                    log.error(f"Error while obtaining reply metadata for message {msg_obj.ts} in channel {convo.id}", exc_info=e)

                history_fragment.append(msg_obj.data)
                counter.next()

            try:
                await ctx.downloader.flush_download_queue()
            except httpx.HTTPStatusError as e:
                log.error(f"Caught HTTP status code {e.response.status_code}", exc_info=e)

            history_fragment.commit_fragments()
    except SlackApiError as e: # TODO: maybe catch a wider net here to save context?
        log.error(f"Got an API error while trying to obtain conversation history", exc_info=e)

    counter.finish()

def export_metadata(ctx):
    ctx.downloader.write_json("metadata.json", ctx.to_metadata().to_dict())

async def export_everything(ctx: ExporterContext):
    await export_emojis(ctx)
    await export_team(ctx)
    await export_reminders(ctx)
    await export_users(ctx)
    await export_files(ctx)
    await export_conversations(ctx)
    export_metadata(ctx)

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