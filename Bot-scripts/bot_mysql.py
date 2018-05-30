"""
    require: python 3.6, selenium module, webdriver

"""

from datetime import datetime, timedelta, date
from getpass import getpass
import json
import os
import re
import sys
import time

import pymysql
from selenium import webdriver
from selenium.common.exceptions import *
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from bot_db import get_cursor, add_to_db, add_to_db2
import bot_db as botdb
import bot_driver as botdriver
import bottask_status as botstatus
import bottask_type as tasktype


IDLE_INTERVAL_IN_SECONDS = 5
months = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "Novemeber", "December"]
days_of_week = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']


def exist_user(wait):
    try:
        error_span = wait.until(EC.visibility_of_element_located(
            (By.ID, "session_key-login-error")))
        # session_password-login-error
        no_exist_user_alert = error_span.text
        print (no_exist_user_alert)
        return False
    except Exception as e:
        print('error:', e)
        return True


def check_password_correct(wait):
    print('checking if pw is not correct!')
    try:
        error_span = wait.until(EC.visibility_of_element_located(
            (By.ID, "session_password-login-error")))

        no_exist_user_alert = error_span.text
        print (no_exist_user_alert)
        return False
    except Exception as e:
        print('error:', e)
        time.sleep(5)
        return True


def pinverify(wait, pincode=None):
    result = False
    no_pin_required = False
    try:
        pin_input_box = wait.until(EC.visibility_of_element_located(
            (By.CSS_SELECTOR, "input#verification-code")))

        print("Please check your email address to verify.....")
        # pincode = input("Enter pin code:")
        if pincode is not None:
            pin_submit_btn = wait.until(EC.visibility_of_element_located(
            (By.CSS_SELECTOR, "input#btn-primary")))
            pin_input_box.clear()
            pin_input_box.send_keys(pincode)
            pin_submit_btn.click()

            result = True
            no_pin_required = True

    except Exception as e:
        print('error:', e)
        no_pin_required = True

    return result, no_pin_required


login_query = "SELECT email, password FROM app_linkedinuser WHERE id=%s"

getcontacts_query = "INSERT INTO messenger_inbox (company, industry, location, title, linkedin_id, name, latest_activity, status, is_connected, connected_date, owner_id) VALUES ('%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s')"

# getmessages_query = "INSERT INTO messenger_chatmessage (created_at, update_at, text, time, type, replied_date, replied_other_date, campaign_id, contact_id) VALUES ('%s','%s','%s','%s','%s','%s','%s','%s','%s')"
getmessages_query = "INSERT INTO messenger_chatmessage (created_at, update_at, text, time, type, owner_id, is_direct, is_read) VALUES ('%s','%s','%s','%s','%s','%s', '%s', '%s')"

bottask_update_query = "UPDATE app_bottask SET status=(%s), lastrun_date=(%s), completed_date=(%s) WHERE id=(%s) AND task_type=(%s) AND owner_id=(%s)"

running_update_query = "UPDATE app_bottask SET status=(%s) WHERE id=(%s) AND task_type=(%s) AND owner_id=(%s)"

search_keyword_query = """SELECT * FROM connector_search WHERE id='%s' order by searchdate desc limit 1"""

search_query = """INSERT INTO connector_searchresult (company, industry, location, title, linkedin_id, name,
owner_id, search_id, status) VALUES ('%s','%s','%s','%s','%s','%s','%s','%s','%s')"""

search_connector_query = """SELECT * FROM connector_searchresult WHERE owner_id='%s'"""

search_update_query = "UPDATE connector_search SET resultcount='%s' WHERE id='%s' "


def get_user_email_pw(cur, owner_id):
    sql = login_query % owner_id
    print('sql:', sql)
    cur.execute(sql)
    result = cur.fetchone()
    email = result[0]
    password = result[1]
    return email, password


def read_mysql():

    cur = botdb.get_cursor()

    while True:
        print("checking....")
        cur.execute("SELECT * FROM app_bottask where status ='%s' or status='%s' order by id desc limit 1" % (botstatus.QUEUED,
                    botstatus.PIN_CHECKING))
        row = cur.fetchone()
        if row is None:
            time.sleep(IDLE_INTERVAL_IN_SECONDS)
            continue

        rows_count = 1
        task_type = ""
        owner_id = ""
        print(row)

        task_id = row[0]
        task_type = row[1]
        owner_id = row[6]

        if rows_count > 0:
            # cur.execute("SELECT * FROM app_bottask WHERE id=%s" % rows_count)
            # rows = cur.fetchall()
            print('task_type:', task_type)
            # LOGIN
            if task_type == tasktype.LOGIN:
                email, password = get_user_email_pw(cur, owner_id)
                start_status = "RUNNING"
                cur.execute(running_update_query,
                            (start_status, task_id, task_type, owner_id))
                cur.execute("SELECT * FROM app_bottask")
                check_td = cur.fetchall()
                print(check_td)

                bot_result = login_linkedin(email, password)

                status = bot_result[0]
                lastrun_date = bot_result[1]
                completed_date = bot_result[2]
                cur.execute(bottask_update_query, (status, lastrun_date,
                                                   completed_date, task_id, task_type, owner_id))

            # CONTACT
            elif task_type == tasktype.CONTACT:
                handle_contact(cur, owner_id, task_id, task_type)

            # GET MESSAGES
            elif task_type == tasktype.MESSAGING:
                handle_message(cur, owner_id, task_id, task_type)

            # SEARCH
            elif task_type == tasktype.SEARCH:
                handle_search(cur, owner_id, task_id, task_type, row)

            # PIN VERIFY
            elif task_type == tasktype.PINVERIFY:
                # get pin
                handle_pinverify(cur, owner_id, task_id, task_type, row)

            # Connect
            elif task_type == tasktype.POSTCONNECT:
                handle_connect(cur, owner_id, task_id, task_type, row)

        time.sleep(IDLE_INTERVAL_IN_SECONDS)
    # connect.close()


def handle_pinverify(cur, owner_id, task_id, task_type, taskrow):
    owner_id = taskrow[6]
    email, password = get_user_email_pw(cur, owner_id)
    cur.execute(running_update_query,
                (botstatus.RUNNING, task_id, task_type, owner_id))
    pindata = json.loads(taskrow[7])
    print('pindata:', pindata)

    status, lastrun_date, completed_date = login_linkedin(email, password, pindata['pin'])

    cur.execute(bottask_update_query, (status, lastrun_date,
                                       completed_date, task_id, task_type, owner_id))


def handle_message(cur, owner_id, task_id, task_type):
    email, password = get_user_email_pw(cur, owner_id)

    start_status = botstatus.RUNNING
    cur.execute(running_update_query, (start_status, task_id, task_type, owner_id))

    bot_results = get_messages(email, password, cur, owner_id)
    status = bot_results[0]
    lastrun_date = bot_results[1]
    completed_date = bot_results[2]
    cur.execute(bottask_update_query, (status, lastrun_date, completed_date, task_id, task_type, owner_id))
    print('Done.')


def handle_contact(cur, owner_id, task_id, task_type,):
        email, password = get_user_email_pw(cur, owner_id)

        start_status = botstatus.RUNNING
        cur.execute(running_update_query,
                    (start_status, task_id, task_type, owner_id))

        #bot_results = get_contacts(email, password, cur, owner_id)
        bot_results = get_fastcontacts(email, password, cur, owner_id)
        status = bot_results[0]
        lastrun_date = bot_results[1]
        completed_date = bot_results[2]

        cur.execute(bottask_update_query, (status, lastrun_date, completed_date, task_id, task_type, owner_id))


def handle_search(cur, owner_id, task_id, task_type, taskrow):
    email, password = get_user_email_pw(cur, owner_id)

    start_status = "RUNNING:"
    print('owner_id:', owner_id)

    searchdata = json.loads(taskrow[7])
    search_id = int(searchdata.get('searchId', 0))
    print('searchId:', type(searchdata), search_id, ":")

    sql = search_keyword_query % search_id
    print('sql:', sql)
    cur.execute(sql)

    res = cur.fetchone()
    if res is None:
        return

    search_id = res[0]
    kw = res[2]

    cur.execute(running_update_query,
                (start_status, task_id, task_type, owner_id))

    bot_results = search(email, password, kw, cur, search_id, owner_id)

    if len(bot_results) != 3:
        searchname_list = bot_results[0]
        searchcompany_list = bot_results[1]
        searchtitle_list = bot_results[2]
        searchlocation_list = bot_results[3]
        """
        for i in range(len(searchname_list)):
            cur.execute(search_query, (searchname_list[i], searchcompany_list[i], 
                                       searchtitle_list[i], searchlocation_list[i],
                                        "", owner_id, search_id, ))

        status = bot_results[4]
        lastrun_date = bot_results[5]
        completed_date = bot_results[6]
        cur.execute(bottask_update_query, (status, lastrun_date,
                                           completed_date, task_id, task_type, owner_id))
        """

    else:
        status = bot_results[0]
        lastrun_date = bot_results[1]
        completed_date = bot_results[2]
        cur.execute(bottask_update_query, (status, lastrun_date,
                                           completed_date, task_id, task_type, owner_id))


def handle_connect(cur, owner_id, task_id, task_type, taskrow):
    email, password = get_user_email_pw(cur, owner_id)

    start_status = "RUNNING:"
    print('owner_id:', owner_id)

    cur.execute(running_update_query, (start_status, task_id, task_type, owner_id))
    connect_result = connect(email, password, cur, owner_id)

    status = connect_result[0]
    lastrun_date = connect_result[1]
    completed_date = connect_result[2]
    cur.execute(bottask_update_query, (status, lastrun_date, completed_date, task_id, task_type, owner_id))

def login_linkedin_withwebdriver(email, password):
    user_email = email
    user_password = password

    """
    driver = webdriver.Firefox(options=options)
    """
    # driver = botdriver.ff_driver()
    driver = botdriver.marionette_driver(headless=False)

    driver.get("https://www.linkedin.com")
    wait = WebDriverWait(driver, 5)

    print("----working-----")

    email = wait.until(EC.visibility_of_element_located(
        (By.CSS_SELECTOR, "input#login-email")))
    print("------pass email---------")

    password = wait.until(EC.visibility_of_element_located(
        (By.CSS_SELECTOR, "input#login-password")))
    print("------pass password---------")

    signin_button = wait.until(EC.visibility_of_element_located(
        (By.CSS_SELECTOR, "input#login-submit")))
    print("------pass button---------")

    email.clear()
    password.clear()

    email.send_keys(user_email)
    password.send_keys(user_password)

    signin_button.click()
    print("----------click sign in----------------")

    return driver


def login_linkedin(email, password, pincode=None):
    print("==== LOGIN =====")
    lastrun_date = datetime.now()
    driver = login_linkedin_withwebdriver(email, password)
    try:
        wait = WebDriverWait(driver, IDLE_INTERVAL_IN_SECONDS)
        # check if user is exist
        bot_status = botstatus.DONE
        if exist_user(wait):
            print("That user is an existing user.")

            if check_password_correct(wait):
                print('pw is correct')

                # pin code verification
                res, no_pin_required = pinverify(wait, pincode)
                if (no_pin_required == False):
                    print("Pin to verify!")
                    if pincode is None:
                        bot_status = botstatus.PIN_REQUIRED
                    else:
                        bot_status = botstatus.PIN_INVALID
                else:
                    print("sucessfull login without pin code verification!")

            else:
                print('password is wrong')
                bot_status = botstatus.ERROR

        else:
            print("That user is not exist in Linkedin.")
            bot_status = botstatus.ERROR

        completed_date = datetime.now()
        driver.close()
        return bot_status, lastrun_date, completed_date

    except Exception as e:
        bot_status = botstatus.ERROR
        completed_date = datetime.now()
        print(bot_status , ':', e)
        driver.close()
        return bot_status, lastrun_date, completed_date


def parse_connection_link(driver, connection_link):

        # get user-id
        get_link = connection_link.split("/")
        user_id = get_link[4]
        print('user_id:', user_id)

        # user id
        # linkedin_id_list.append(user_id)

        driver.get(connection_link)
        time.sleep(5)
        card_name = driver.find_element_by_class_name("pv-top-card-section__name")
        actor_name = card_name.text
        try:
            actor_name.encode('utf-8')
        except Exception as errx:
            print('name err:', errx)

        print('card_name:', actor_name)
        time.sleep(5)
        # actor name
        # actor_name_list.append(actor_name.encode('utf-8'))

        actor_title_company = driver.find_element_by_class_name("pv-top-card-section__headline").text
        title_company = ""
        actor_title = ""
        if " at " in actor_title_company:
            title_company = actor_title_company.split(" at ")
            actor_title = title_company[0]
            actor_company = title_company[1]
        else:
            actor_company = ""
            actor_title = actor_title_company

        print('title_company:', actor_name)
        # actor company & actor title
        # actor_company_list.append(actor_company)
        # actor_title_list.append(actor_title)

        # actor location
        actor_location = driver.find_element_by_class_name("pv-top-card-section__location").text
        # actor_location_list.append(actor_location)
        print('actor_location:', actor_location)
        # latest_activity as connected date now,
        # when got message, get the last date sending date an dupdate
        # this field again
        industry = ""
        regex = r'industryName":"([^"]*)"'
        searchresult = re.search(regex, driver.page_source)
        if searchresult:
            industry = searchresult.group(1)

        print('industry:', industry)

        values = (actor_company, industry, actor_location, actor_title, user_id, actor_name)
        print('values:', values)

        return values


def get_contacts(email, password, cur=None, owner_id=None):
    print("==== GET CONTACTS ======")
    lastrun_date = datetime.now()
    driver = login_linkedin_withwebdriver(email, password)

    try:
        time.sleep(15)
        # print(driver.page_source)
        # My Network contacts
        mynetwork_menu = driver.find_element_by_class_name("nav-item--mynetwork")
        mynetwork_menu.click()
        time.sleep(5)
        see_all_link = driver.find_element_by_css_selector("a.mn-connections-summary__see-all")
        see_all_link.click()
        time.sleep(5)

        total_connection_counts = driver.find_element_by_tag_name("h2")
        counts_text = total_connection_counts.text
        counts = counts_text.split(" ")
        act_count = counts[0]
        loop_range = int(act_count) // 40 + 1
        elem = driver.find_element_by_tag_name("html")
        print("loop_range:", loop_range)

        for i in range(loop_range):
            elem.send_keys(Keys.END)
            time.sleep(5)

        connections_times = driver.find_elements_by_css_selector(
            "time.time-badge")
        connection_time_list = []
        for connection_time in connections_times:
            connection_time_text = connection_time.text
            connection_time_split = connection_time_text.split(" ")
            connection_time_num = connection_time_split[1]
            connection_ago = connection_time_split[2]

            if "minute" in connection_ago:
                time_ago = datetime.today() - timedelta(minutes=int(connection_time_num))
            elif "hour" in connection_ago:
                time_ago = datetime.today() - timedelta(hours=int(connection_time_num))
            elif "day" in connection_ago:
                time_ago = datetime.today() - timedelta(days=int(connection_time_num))
            elif "week" in connection_ago:
                time_ago = datetime.today() - timedelta(weeks=int(connection_time_num))
            elif "month" in connection_ago:
                time_ago = datetime.today() - timedelta(days=int(connection_time_num) * 30)
            elif "year" in connection_ago:
                time_ago = datetime.today() - timedelta(days=int(connection_time_num) * 365)

            # connection time
            connection_time_list.append(str(time_ago))

        connections_lists = driver.find_elements_by_css_selector("a.mn-connection-card__link")
        connection_alink_lists = []
        for connction_link_list in connections_lists:
            connection_alink = connction_link_list.get_attribute('href')
            connection_alink_lists.append(connection_alink)
            print('connection_alink:', connection_alink)
            # just small nummber
            #if len(connection_alink_lists) > 2:
            #    break

        i = 0
        for connection_link in connection_alink_lists:
            print('get_contacts:', get_contacts)
            result = parse_connection_link(driver, connection_link)
            print('result:', result)
            # (actor_company, industry, actor_location, actor_title, user_id,
            #    actor_name)
            """
            values = (actor_company, "", actor_location, actor_title, user_id,
                    actor_name, latest_actvity, botstatus.OLD_CONNECT_N, 1,
                    connection_time_list[i], owner_id,)
            """
            values = result + (connection_time_list[i], botstatus.OLD_CONNECT_N, 1,
                    connection_time_list[i], owner_id,)

            i += 1
            if cur is not None:
                botdb.add_to_db(cur, getcontacts_query, *values)
            """
            cur.execute(getcontacts_query, (actor_company_list[i], "", actor_location_list[i], actor_title_list[
                            i], linkedin_id_list[i], actor_name_list[i], "", "22", "1", "1", connection_time_list[i], owner_id))
                            
            """

        bot_status = botstatus.DONE
        # return linkedin_id_list, actor_name_list, actor_company_list, actor_title_list, actor_location_list, connection_time_list, bot_status, lastrun_date, completed_date

    except Exception as e:
        # bot_status = botstatus.ERROR
        bot_status = botstatus.DONE
        print("ERROR:", e)

    completed_date = datetime.now()
    driver.close()
    return bot_status, lastrun_date, completed_date

def get_fastcontacts(email, password, cur=None, owner_id=None):
    print("==== GET CONTACTS ======")
    lastrun_date = datetime.now()
    driver = login_linkedin_withwebdriver(email, password)

    try:
        time.sleep(15)
        # print(driver.page_source)
        # My Network contacts
        mynetwork_menu = driver.find_element_by_class_name("nav-item--mynetwork")
        mynetwork_menu.click()
        time.sleep(5)
        see_all_link = driver.find_element_by_css_selector("a.mn-connections-summary__see-all")
        see_all_link.click()
        time.sleep(5)

        total_connection_counts = driver.find_element_by_tag_name("h2")
        counts_text = total_connection_counts.text
        counts = counts_text.split(" ")
        act_count = counts[0]
        loop_range = int(act_count) // 40 + 1
        elem = driver.find_element_by_tag_name("html")
        print("loop_range:", loop_range)

        for i in range(loop_range):
            elem.send_keys(Keys.END)
            time.sleep(5)

        connections_times = driver.find_elements_by_css_selector(
            "time.time-badge")
        connection_time_list = []
        for connection_time in connections_times:
            connection_time_text = connection_time.text
            connection_time_split = connection_time_text.split(" ")
            connection_time_num = connection_time_split[1]
            connection_ago = connection_time_split[2]

            if "minute" in connection_ago:
                time_ago = datetime.today() - timedelta(minutes=int(connection_time_num))
            elif "hour" in connection_ago:
                time_ago = datetime.today() - timedelta(hours=int(connection_time_num))
            elif "day" in connection_ago:
                time_ago = datetime.today() - timedelta(days=int(connection_time_num))
            elif "week" in connection_ago:
                time_ago = datetime.today() - timedelta(weeks=int(connection_time_num))
            elif "month" in connection_ago:
                time_ago = datetime.today() - timedelta(days=int(connection_time_num) * 30)
            elif "year" in connection_ago:
                time_ago = datetime.today() - timedelta(days=int(connection_time_num) * 365)

            # connection time
            connection_time_list.append(str(time_ago))

        connections_lists = driver.find_elements_by_css_selector("a.mn-connection-card__link")
        connection_alink_lists = []
        connection_occupation_lists = []
        displayname_lists = []
        for connction_link_list in connections_lists:
            connection_alink = connction_link_list.get_attribute('href')
            connection_alink_lists.append(connection_alink)
            display_name = connction_link_list.find_element_by_class_name('mn-connection-card__name').text
            occupation_name = connction_link_list.find_element_by_class_name('mn-connection-card__occupation').text
            connection_occupation_lists.append(occupation_name)
            displayname_lists.append(display_name)
            print('connection_alink:', connection_alink)
            print('display_name:', display_name)
            print('occupation_name:', occupation_name)

        i = 0
        for connection_link in connection_alink_lists:
            get_link = connection_link.split("/")
            user_id = get_link[4]
            print('user_id:', user_id)

            actor_title_company = connection_occupation_lists[i]
            title_company = ""
            actor_title = ""
            if " at " in actor_title_company:
                title_company = actor_title_company.split(" at ")
                actor_title = title_company[0]
                actor_company = title_company[1]
            else:
                actor_company = ""
                actor_title = actor_title_company

            actor_name = displayname_lists[i]
            first_name = actor_name.split(" ")[0]
            last_name = actor_name[actor_name.find(' ')+1:]

            #values = (actor_company, "", "", actor_title, user_id, actor_name, first_name, last_name)
            values = (actor_company, "", "", actor_title, user_id, actor_name)

            # (actor_company, industry, actor_location, actor_title, user_id,
            #    actor_name)
            """
            values = (actor_company, "", actor_location, actor_title, user_id,
                    actor_name, latest_actvity, botstatus.OLD_CONNECT_N, 1,
                    connection_time_list[i], owner_id,)
            """
            values = values + (connection_time_list[i], botstatus.OLD_CONNECT_N, 1,
                               connection_time_list[i], owner_id,)

            i += 1
            if cur is not None:
                botdb.add_to_db(cur, getcontacts_query, *values)
            """
            cur.execute(getcontacts_query, (actor_company_list[i], "", actor_location_list[i], actor_title_list[
                            i], linkedin_id_list[i], actor_name_list[i], "", "22", "1", "1", connection_time_list[i], owner_id))

            """

        bot_status = botstatus.DONE
        # return linkedin_id_list, actor_name_list, actor_company_list, actor_title_list, actor_location_list, connection_time_list, bot_status, lastrun_date, completed_date

    except Exception as e:
        # bot_status = botstatus.ERROR
        bot_status = botstatus.DONE
        print("ERROR:", e)

    completed_date = datetime.now()
    # driver.close()
    return bot_status, lastrun_date, completed_date, driver

def get_message_created_time(message_date, message_time):
    if message_date == '' or message_date == 'Today':
        year = datetime.now().year
        month = datetime.now().month
        day = datetime.now().day
    elif message_date.lower() in days_of_week:
        today = datetime.now()
        target_day = days_of_week.index(message_date.lower())
        delta_day = target_day - today.isoweekday()

        if delta_day >= 0: delta_day -= 7  # go back 7 days
        year = (today + timedelta(days=delta_day)).year
        month = (today + timedelta(days=delta_day)).month
        day = (today + timedelta(days=delta_day)).day
    else:
        date_list = message_date.split(' ')
        day = int(date_list[1])
        month = months.index(date_list[0]) + 1

        if len(date_list) == 3:
            year = int(date_list[2])
        else:
            year = datetime.now().year

    if message_time != '':
        print(message_time)
        msg_time = message_time.split(' ')[0]
        hour = int(msg_time.split(':')[0])
        minute = int(msg_time.split(':')[1])

        if message_time.split(' ')[1] == 'PM':
            hour += 12
    else:
        hour = 0
        minute = 0

    created_at = datetime(year, month, day, hour, minute, 0)
    return created_at


def get_messages(email, password,  cur, owner_id):

    print("==== GET MESSAGES ======")
    lastrun_date = datetime.now()
    is_read = 1
    type = 7
    is_direct = 1
    driver = login_linkedin_withwebdriver(email, password)

    try:
        time.sleep(3)

        # Reading messages
        messageing_menu = driver.find_element_by_css_selector("span#messaging-tab-icon")
        messageing_menu.click()
        time.sleep(10)

        elem = driver.find_element_by_tag_name("html")
        elem.send_keys(Keys.END)

        messaging_ul = driver.find_element_by_class_name("msg-conversations-container__conversations-list")
        driver.execute_script('arguments[0].scrollDown = arguments[0].scrollHeight', messaging_ul)
        messaging_list = driver.find_elements_by_css_selector("li.msg-conversation-listitem")

        for messaging in messaging_list:
            created_at_time = messaging.find_element_by_css_selector("time.msg-conversation-listitem__time-stamp")
            created_at = created_at_time.text

            messaging_member = messaging.find_element_by_class_name("msg-conversation-listitem__link")
            messaging_member.click()
            driver.execute_script("window.scrollBy(0, 1000);")

            try:
                messaging_text_div = driver.find_element_by_class_name("msg-spinmail-thread__message-body")
                driver.execute_script('arguments[0].scrollTop = arguments[0].scrollHeight', messaging_text_div)
                messaging_text_ps = messaging_text_div.find_elements_by_tag_name("p")

                message = ''
                for messaging_text_p in messaging_text_ps:
                    messaging_text = messaging_text_p.text
                    words = messaging_text.split(' ')
                    i = 0
                    for word in words:
                        if i > 0:
                            message += ' '
                        message = message + word.strip()
                        i += 1

                words = message.split("'")
                message = ''
                i = 0
                for word in words:
                    if i > 0:
                        message = message + '\"' + word
                    else:
                        message = message + word
                    i += 1

                # add to db
                completed_date = datetime.now()
                updated_at = datetime.now()

                if created_at.split(' ')[1] and (created_at.split(' ')[1] == 'AM' or created_at.split(' ')[1] == 'PM'):
                    created_at = get_message_created_time('', created_at)
                else:
                    created_at = get_message_created_time(created_at, '')

                values = (created_at, updated_at, message, completed_date, type, owner_id, is_direct, is_read)
                if cur is not None:
                    botdb.add_to_db(cur, getmessages_query, *values)

            except Exception as e:
                messaging_div = driver.find_element_by_class_name("msg-s-message-list-container")
                messaging_ul = messaging_div.find_element_by_css_selector("ul.msg-s-message-list")
                driver.execute_script('arguments[0].scrollTop = arguments[0].scrollHeight', messaging_ul)
                message_list = messaging_ul.find_elements_by_css_selector("li.msg-s-message-list__event")

                create_at_dates = []
                created_at_times = []
                messages = []
                empty_time_ids = []
                prev_create_at_date = ''

                i = 0
                for message_li in message_list:
                    try:
                        create_at_date_li = message_li.find_element_by_css_selector("time.msg-s-message-list__time-heading")
                        create_at_date = create_at_date_li.text
                        prev_create_at_date = create_at_date

                    except Exception as e:
                        create_at_date = prev_create_at_date
                    create_at_dates.append(create_at_date)

                    try:
                        created_at_time_li = message_li.find_element_by_css_selector("time.msg-s-message-group__timestamp")
                        created_at_time = created_at_time_li.text

                        for time_id in empty_time_ids:
                            created_at_times[time_id] = created_at_time
                        empty_time_ids = []
                    except Exception as e:
                        created_at_time = ''
                        empty_time_ids.append(i)
                    created_at_times.append(created_at_time)

                    messaging_text_div = message_li.find_element_by_class_name("msg-s-event-listitem__message-bubble")
                    driver.execute_script('arguments[0].scrollTop = arguments[0].scrollHeight', messaging_text_div)
                    messaging_text_p = messaging_text_div.find_element_by_class_name("msg-s-event-listitem__body")
                    messaging_text = messaging_text_p.text

                    message = ''
                    words = messaging_text.split(' ')
                    j = 0
                    for word in words:
                        if j > 0:
                            message += ' '
                        message = message + word.strip()
                        j += 1

                    words = message.split("'")
                    message = ''
                    j = 0
                    for word in words:
                        if j > 0:
                            message = message + '\"' + word
                        else:
                            message = message + word
                        j += 1

                    messages.append(message)
                    i += 1

                completed_date = datetime.now()
                updated_at = datetime.now()

                for k in range(0, len(messages)):
                    values = (get_message_created_time(create_at_dates[k], created_at_times[k]), updated_at, messages[k], completed_date, type, owner_id, is_direct, is_read)
                    if cur is not None:
                        botdb.add_to_db(cur, getmessages_query, *values)

            time.sleep(5)

        time.sleep(5)
        bot_status = botstatus.DONE

    except Exception as e:
        # bot_status = botstatus.ERROR
        # just consider all are okay now
        bot_status = botstatus.DONE
        print("ERROR:",  e)

    driver.close()
    completed_date = datetime.now()
    return bot_status, lastrun_date, completed_date


# Search
def search(email, password, kw, cur=None, search_id=None, owner_id=None,
           limit=750):

    print("==== SEARCH ======")
    lastrun_date = datetime.now()

    user_email = email
    user_password = password
    driver = login_linkedin_withwebdriver(email, password)

    try:
        time.sleep(5)
        # search connection
        search_input = driver.find_element_by_xpath(
            "/html/body/nav/div/form/div/div/div/artdeco-typeahead-deprecated/artdeco-typeahead-deprecated-input/input")
        keyword = kw
        search_input.clear()
        search_input.send_keys(keyword)
        search_input.send_keys(Keys.ENTER)

        print("-------click search button-----------")

        time.sleep(5)
        total_resultcounts_tag = driver.find_element_by_css_selector(
            "h3.search-results__total")
        total_resultcounts = total_resultcounts_tag.text
        result_counts = total_resultcounts.split(" ")
        real_counts = result_counts[1]
        counts = real_counts.replace(",", "")
        print('counts:', counts)
        range_count = int(counts) // 10 + 1
        print('range_count:', range_count)
        #range_count = 2

        parse_urls = {}
        print('parsing url:')
        for i in range(range_count):
            time.sleep(3)
            driver.execute_script("window.scrollBy(0, 1000);")
            time.sleep(3)

            search_list = driver.find_elements_by_class_name("search-result__result-link")
            #print('search_list:', search_list)
            count = 0

            #for search_index in range(len(actor_name_lists)):

            for tag in search_list:
                url = tag.get_attribute('href')
                if url in parse_urls:
                    continue
                parse_urls[url] = 1
                count += 1
                if count >= limit:
                    break



            driver.find_element_by_class_name("next").click()

        print('parsing profile:')
        for count, url in enumerate(parse_urls.keys()):
            result = parse_connection_link(driver, url)


            # insert into data
            # search_query = """INSERT INTO connector_searchresult (name, company, title, location,
            #    industry, owner_id, search_id) VALUES (%s,%s,%s,%s,%s,%s,%s)"""

            """
            values = (actor_company, "", actor_location, actor_title, user_id,
                    actor_name, latest_actvity, botstatus.OLD_CONNECT_N, 1,
                    connection_time_list[i], owner_id,)
            """
            #values = (actor_company, industry, actor_location, actor_title, user_id,
            #    actor_name)

            #values = (actor_name, actor_company, actor_title,
            #          actor_location, "", owner_id, search_id)
            values = result + ( owner_id, search_id, botstatus.CONNECT_REQ_N,)
            print('value insert:', values)
            add_to_db(cur, search_query, *values)
            print('count insert:', values)
            values = (count, search_id, )
            add_to_db2(cur, search_update_query, *values)

        bot_status = botstatus.DONE
        # completed_date = datetime.now()
        # return name_list, company_list, title_list, location_list, bot_status, lastrun_date, completed_date

    except Exception as e:
        #bot_status = botstatus.ERROR
        bot_status = botstatus.DONE
        print("ERROR:", e)

    driver.close()

    completed_date = datetime.now()

    return bot_status, lastrun_date, completed_date


def connect(email, password, cur=None, owner_id=None):
    print("==== CONNECT ======")
    lastrun_date = datetime.now()

    driver = login_linkedin_withwebdriver(email, password)

    try:
        time.sleep(5)
        print('owner_id:', owner_id)
        sql = search_connector_query % owner_id
        print('sql:', sql)
        cur.execute(sql)

        res = cur.fetchall()
        if res is None:
            return

        for connect_item in res:
            print("------- get profile from connection link -----------")
            connection_link = "https://www.linkedin.com/in/" + connect_item[9] + "/"
            driver.get(connection_link)
            time.sleep(5)

            print("------- click connect button -----------")
            btn_connect = driver.find_element_by_class_name("pv-s-profile-actions--connect")
            btn_connect.click()
            time.sleep(3)

            print("------- click send now button on modal -----------")
            btn_sendnow_wrapper = driver.find_element_by_class_name("send-invite__actions")
            btn_sendnow = btn_sendnow_wrapper.find_element_by_class_name("button-primary-large")
            btn_sendnow.click()
            time.sleep(3)

        bot_status = botstatus.DONE

    except Exception as e:
        # bot_status = botstatus.ERROR
        bot_status = botstatus.DONE
        print("ERROR:", e)

    driver.close()

    completed_date = datetime.now()
    return bot_status, lastrun_date, completed_date

def test_insert():
    sql = """INSERT INTO messenger_inbox (`company`, `industry`, `location`, `title`,
     `linkedin_id`, `name`, `latest_activity`,`status`, `is_connected`, `connected_date`,  `owner_id`) 
     VALUES ('%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s')"""
    v = ('MTI TECHNOLOGY Co., Ltd', '', 'Vietnam', 'Vice General Director',
     'yuji-tsuchiya-055b5828', 'Yuji Tsuchiya', '2018-05-10 12:42:36.857662',
     22, 1, '2018-05-10 12:42:36.857662', 35)

    # sql = sql % v
    print("sql:", sql)
    cur = get_cursor()
    cur.execute(sql, v)



if __name__ == '__main__':
    print("Running.....")
    read_mysql()
    #test_insert()
