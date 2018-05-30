import os

import pymysql
from db_config import DB_HOST, DB_PW, DB_USER, DB_NAME

insert_contacts_query = "INSERT INTO messenger_inbox (`company`, `industry`, `location`,\
 `title`, `linkedin_id`, `name`, `latest_activity`,`status`, `is_connected`, `connected_date`,\
  `owner_id`) VALUES ('%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s')"

login_query = "SELECT email, password FROM app_linkedinuser WHERE id=%s"


def get_user_email_pw(cur, owner_id):
    sql = login_query % owner_id
    print('sql:', sql)
    cur.execute(sql)
    result = cur.fetchone()
    email = result[0]
    password = result[1]
    return email, password


def add_to_db(cur, getcontacts_query, *values):
    # may check record exists
    sql = getcontacts_query % values
    print('sql:', sql)
    # print('add to db:', insert_contacts_query, values)
    try:
        cur.execute(sql)
    except Exception as err:
        print('Insert inbox error:', err)


def add_to_db2(cur, getcontacts_query, *values):
    # may check record exists
    sql = getcontacts_query % values
    print('sql:', sql)
    # print('add to db:', insert_contacts_query, values)
    try:
        cur.execute(getcontacts_query, values)
    except Exception as err:
        print('Insert inbox error:', err)
        add_to_db(cur, getcontacts_query, *values)

def get_db(cur, sql, values):
    print(sql  % values)
    cur.execute(sql, *values)
    return cur.fetchone()

def get_cursor():
    db_user = os.environ.get('dbuser', DB_USER)
    db_pw = os.environ.get('dbpw', DB_PW)
    db_host = os.environ.get('dbhost', DB_HOST)
    db_name = os.environ.get('dbname', DB_NAME)
    # db_user = os.environ.get('dbuser', 'root')
    # db_pw = os.environ.get('dbpw', '')
    # db_host = os.environ.get('dbhost', "localhost")
    # previous_rows_count = 0

    try:
        connect = pymysql.connect(
            host=db_host, user=db_user, password=db_pw, db=db_name, autocommit=True)
    except Exception as err:
        print("Could not open database:", err)
        exit(-1)

    connect.set_charset(('utf8'))
    cur = connect.cursor()
    # connect.set_character_set('utf8')
    # cur.execute('SET NAMES utf8;')
    # cur.execute('SET CHARACTER SET utf8;')
    # cur.execute('SET character_set_connection=utf8;')

    return cur