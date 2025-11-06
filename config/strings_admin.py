# Note that get_users_info does not contain its strings in this file
# because it generates a big report about user what would be hard to
# modify in here

# Action prompts
SELECT_ACTION = 'Select action you want to do:'
PROMPT_TYPE_USER_ID = 'Type user id or username of user you want to check'
PROMPT_TYPE_TEXT = 'Type text you want to send all users'
PROMPT_TYPE_USER_ID_DELETE = 'Type user id of user you want to delete'
PROMPT_TYPE_YES = 'Confirm your action to delete user <code>{user_id}</code> with \"yes\" if you want to delete or type anything else if you want to cancel'

# Results
RESULT_SEND = 'Message:\n\n <code>{message_text}</code>\n\n was sent {count} users!'
SUCCESS_DELETE = '✅ Successfully deleted all data for user {user_id}'

# User listing messages
NO_USERS = 'You don\'t have any users yet'
FOUND_USERS = 'Found {quantity} users:'
USER_LIST_ITEM = 'UID: <code>{user_id}</code>, username: @{username}, Balance: <code>{cash:.2f}</code>, created: <code>{created}</code>'

# Error messages
ERROR_USERS_FETCH = 'Could not get users'
ERROR_USER_NOT_FOUND = 'User with ID or username <code>{user_id}</code> not found.'
ERROR_DELETE_USER = 'Error during deletion: {e}\nAll changes have been rolled back.'
