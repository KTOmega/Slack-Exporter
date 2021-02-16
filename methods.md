# Slack methods for archival

from least difficult to most difficult

- emoji.list
- team.info
- reminders.list
  - reminders.info is redundant
- users.list
  - users.info/users.profile.get is redundant
- pins.list
- files.list/info
  - files.info has some unique data like comments/shares
- conversations.list/history/replies/members
  - conversations.info is already in conversations.list
  - conversations.history does not have replies

## paged methods

- conversations.list
  - via cursor
- conversations.history
  - via cursor + `latest` for time control
- files.list
  - via `ts_to` for time control. no cursor
- users.list
  - via cursor

## methods to avoid

- reactions.list maybe, it lists all the reactions by user. reactions by message is already in conversations.history
- stars.list is personalized and private
- team.profile.get is a weird one, there's nothing really here
- users.profile.get is just users.list

## dir structure

- data
  - emoji
    - <emoji files>
    - emoji.json
  - team
    - <icon files>
    - team.json
  - reminders.json
  - users
    - <avatar files>
    - users.json
  - files
    - <files>
    - files.json
  - conversations
    - conversations.json
    - <conversation id>
      - pins.json
      - history
        - <fragments>