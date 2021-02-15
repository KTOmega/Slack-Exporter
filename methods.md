# Slack methods for archival

- bots.info
- conversations.list/history/replies/members
  - conversations.info is already in conversations.list
  - conversations.history does not have replies
- emoji.list
- files.list/info
  - files.info has some unique data like comments/shares
- pins.list
- reminders.list
  - reminders.info is redundant
- team.info
- users.list
  - users.info/users.profile.get is redundant

## paged methods

- conversations.list
  - via cursor
- conversations.history
  - via cursor + `latest` for time control
- files.list
  - via `ts_to` for time control. no cursor
- users.list
  - via cursor + `latest` for time control

## methods to avoid

- reactions.list maybe, it lists all the reactions by user. reactions by message is already in conversations.history
- stars.list is personalized and private
- team.profile.get is a weird one, there's nothing really here
- users.profile.get is just users.list