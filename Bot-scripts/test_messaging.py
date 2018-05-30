import os

import bot_db
from bot_mysql2 import get_messages


def test_message():
    
    get_messages(user_email, user_pw, bot_db.get_cursor(), 59)
    
user_email = os.environ.get('email', None)
user_pw = os.environ.get('pw', None)

if __name__ == '__main__':
    print("Running.....")
    
    test_message()