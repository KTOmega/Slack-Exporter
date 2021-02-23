import json
import logging
import os
import tempfile
from typing import Any, Dict

from progress.counter import Counter
from slack_sdk.errors import SlackApiError

from . import constants, models, utils
from .context import ExporterContext

log = logging.getLogger("exporter")

# TODO: maybe just make a class instead of passing in ctx every time
async def export_emojis(ctx: ExporterContext):
    emojis = await utils.with_retry(ctx.slack_client.emoji_list)

    print("Exporting emojis")

    try:
        for emoji, url in emojis["emoji"].items():
            if not url.startswith("https://"):
                continue

            emoji_filename = os.path.basename(url)
            emoji_fullname = os.path.join(constants.EMOJI_EXPORT_DIR, emoji_filename)
            ctx.downloader.enqueue_download(url, emoji_fullname, use_auth=True)

        await ctx.downloader.flush_download_queue() # probably catch something here
    except SlackApiError as e:
        log.error("Got an API error while trying to export emojis", exc_info=e)

    ctx.downloader.write_json(os.path.join(constants.EMOJI_EXPORT_DIR, constants.EMOJI_JSON_FILE), emojis["emoji"])

async def export_team(ctx: ExporterContext):
    team_data = await utils.with_retry(ctx.slack_client.team_info)

    print("Exporting team info")

    try:
        for icon_name, icon_url in team_data["team"]["icon"].items():
            if not icon_url.startswith("https://"):
                continue

            icon_filename = os.path.basename(icon_url)
            icon_fullname = os.path.join(constants.TEAM_EXPORT_DIR, icon_filename)

            ctx.downloader.enqueue_download(icon_url, icon_fullname)

        await ctx.downloader.flush_download_queue() # probably catch something here
    except SlackApiError as e:
        log.error("Got an API error while trying to export team info", exc_info=e)

    ctx.downloader.write_json(os.path.join(constants.TEAM_EXPORT_DIR, constants.TEAM_JSON_FILE), team_data["team"])

async def export_reminders(ctx: ExporterContext):
    try:
        reminders = await utils.with_retry(ctx.slack_client.reminders_list)

        print("Exporting reminders")

        ctx.downloader.write_json(constants.REMINDERS_JSON_FILE, reminders["reminders"])
    except SlackApiError as e:
        log.error("Got an API error while trying to export reminders", exc_info=e)

async def export_users(ctx: ExporterContext):
    users_generator = await utils.with_retry(ctx.slack_client.users_list)
    all_users = []

    counter = Counter("Exporting users ")

    try:
        async for users in users_generator:
            all_users.extend(users["members"])
            for user in users["members"]:
                user_obj = models.SlackUser(user)
                all_users.append(user)
                counter.next()

                for url, filename in user_obj.get_exportable_data():
                    full_filename = os.path.join(constants.USERS_EXPORT_DIR, filename)
                    ctx.downloader.enqueue_download(url, full_filename)

        await ctx.downloader.flush_download_queue()
    except SlackApiError as e:
        log.error("Got an API error while trying to export user info", exc_info=e)

    ctx.downloader.write_json(os.path.join(constants.USERS_EXPORT_DIR, constants.USERS_JSON_FILE), all_users)
    counter.finish()

def export_file(ctx: ExporterContext, slack_file: models.SlackFile):
    for url, filename in slack_file.get_exportable_data():
        full_filename = os.path.join(constants.FILES_EXPORT_DIR, filename)
        ctx.downloader.enqueue_download(url, full_filename, use_auth=True)

async def export_files(ctx: ExporterContext):
    files_generator = utils.AsyncIteratorWithRetry(
        ctx.slack_client.files_list, count=constants.ITEM_COUNT_LIMIT, ts_to=ctx.export_time #, ts_from=ctx.last_export_time
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
            except utils.AggregateError as e:
                log.warning(f"Caught {len(e.errors)} errors while downloading files.")

                for err in e.errors:
                    log.warning(str(err))
    except SlackApiError as e:
        log.error(f"Got an API error while trying to obtain file info", exc_info=e)

    ctx.downloader.write_json(os.path.join(constants.FILES_EXPORT_DIR, constants.FILES_JSON_FILE), all_files)
    counter.finish()

async def export_conversations(ctx: ExporterContext):
    convo_generator = utils.AsyncIteratorWithRetry(
        ctx.slack_client.conversations_list, limit=constants.ITEM_COUNT_LIMIT, types=constants.CONVERSATIONS_TYPES
    )
    all_conversations = []

    print("Exporting conversation list")

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

        print(f"Exporting conversation pins ({convo.name})")

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

    temporary_dir = tempfile.TemporaryDirectory()
    temp_fragment = ctx.fragments.create(temporary_dir.name)

    counter = Counter(f"Exporting conversation history ({convo.name}) ")

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

                temp_fragment.append(msg_obj.data)
                counter.next()

            try:
                await ctx.downloader.flush_download_queue()
            except utils.AggregateError as e:
                log.warning(f"Caught {len(e.errors)} errors while downloading files.")

                for err in e.errors:
                    log.warning(str(err))

            temp_fragment.commit_fragments()
    except SlackApiError as e:
        log.error(f"Got an API error while trying to obtain conversation history", exc_info=e)
    except Exception as e:
        log.error(f"Uncaught {e.__class__.__name__}; you may need to do a full resync", exc_info=e)

    history_fragment.extend(temp_fragment[::-1]) # Slack messages are stored in descending order

    temp_fragment.close()
    history_fragment.close()
    temporary_dir.cleanup()

    counter.finish()

def export_metadata(ctx):
    ctx.downloader.write_json(constants.CONTEXT_JSON_FILE, ctx.to_metadata().to_dict())

async def export_all(ctx: ExporterContext):
    await export_emojis(ctx)
    await export_team(ctx)
    await export_reminders(ctx)
    await export_users(ctx)
    await export_files(ctx)
    await export_conversations(ctx)
    export_metadata(ctx)