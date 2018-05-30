from datetime import date, datetime
import re
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from bot_db import get_cursor, get_db
from bot_driver import login_linkedin_withwebdriver, LINKEDIN_URL, \
    IDLE_INTERVAL_IN_SECONDS
import bot_msgtype
from bot_mysql import get_user_email_pw
import bottask_status
import bottask_type


message_select = """select * from messenger_chatmessage where id = %s"""
contact_select = """select * from messenger_inbox where id = %s"""
message_update_sql = """update messenger_chatmessage set is_sent=1 where id = %s"""
bottask_update_status_sql = "UPDATE app_bottask SET status=%s WHERE id=%s "
bottask_update_done_sql = "UPDATE app_bottask SET status=(%s), lastrun_date=(%s), completed_date=(%s) WHERE id=%s "

message_update_reply_sql = """update messenger_chatmessage set replied_other_date=%s where id = %s"""
message_update_reply_ignore_sql = """update messenger_chatmessage set replied_date=%s where id = %s"""
contact_update_connect_sql = """update messenger_inbox set is_connected=1, connected_date=%s where id = %s"""

messages_replied_insert_query = """INSERT INTO messenger_chatmessage (created_at, update_at, text, time, type, contact_id,
replied_date, campaign_id, owner_id, parent_id, is_direct, is_read, is_sent)
 VALUES (%s,%s,%s,%s,%s,%s, %s, %s, %s, %s, %s, %s, %s)"""

def update_message_is_sent(cur, message_id):
    cur.execute(message_update_sql, (message_id))


def update_message_replied(cur, replied_date, msg, msgdetail):
    cur.execute(message_update_reply_sql, (replied_date, msgdetail[0]))

def update_message_replied_ignore(cur, replied_date, msg, msgdetail):
    cur.execute(message_update_reply_ignore_sql, (replied_date, msgdetail[0]))

def update_contact_connected(cur, connected_date, msgdetail):
    cur.execute(contact_update_connect_sql, (connected_date, msgdetail[6]))


def handle_postconnect_pre(cur, taskrow):
    print('taskrow:', taskrow)
    msgdetail = get_db(cur, message_select, (taskrow[8],))
    print('message detail:', msgdetail)
    # update runniing status
    cur.execute(bottask_update_status_sql, (bottask_status.RUNNING, taskrow[0]))
    return msgdetail


def handle_postconnect(cur, taskrow):
    msgdetail = handle_postconnect_pre(cur, taskrow)
    # do_post with webdriver
    res = postconnect_browser(cur, taskrow, msgdetail)
    # update message
    task_status = bottask_status.ERROR
    if res:
        task_status = bottask_status.DONE
        update_message_is_sent(cur, msgdetail[0])

    handle_postconnect_post(cur, task_status, taskrow[0])


def handle_postconnect_post(cur, task_status, task_id):
    # update bottask

    now = datetime.now()
    cur.execute(bottask_update_done_sql, (task_status, now, now, task_id))


def handle_checkconnect(cur, taskrow):
    msgdetail = handle_postconnect_pre(cur, taskrow)
    print('msgdetail:', msgdetail)
    # do_post with webdriver
    res, replied_date, connect, msg = checkconnect_browser(cur, taskrow, msgdetail)

    task_status = bottask_status.DONE
    # update connected when connect
    if connect=="connected":
        update_contact_connected(cur, replied_date, msgdetail)

    # update replied_other_date
    if connect == "ignored":
        update_message_replied(cur, replied_date, connect, msgdetail)

        if msg is not None:
            update_message_replied_ignore(cur, replied_date, connect, msgdetail)

    handle_postconnect_post(cur, task_status, taskrow[0])

def checkconnect_browser(cur, taskrow, msgdetail):
    email, password = get_user_email_pw(cur, taskrow[6])
    contact = get_db(cur, contact_select, (msgdetail[6],))
    print('contact:', contact)
    driver = login_linkedin_withwebdriver(email, password)

    user_path = "/in/{0}/".format(contact[10])
    # go to the user homme
    userhome = "{0}{1}".format(LINKEDIN_URL, user_path)
    print('userhome:', userhome)
    status = True
    replied_date = datetime.now()
    connect = ""
    message = None
    # click on the send connect
    try:
        wait = WebDriverWait(driver, IDLE_INTERVAL_IN_SECONDS)
        driver.get(userhome)

        # pv-s-profile-actions--message
        # connect_btn = driver.find_element_by_class_name("button.pv-s-profile-actions--connect")
        message_btn = wait.until(EC.visibility_of_element_located(
            (By.CSS_SELECTOR, "button.pv-s-profile-actions--message")))

        message_btn_wrapper = wait.until(EC.visibility_of_element_located(
            (By.CSS_SELECTOR, message_btn)))

        pending_btn = wait.until(EC.visibility_of_element_located(
            (By.CSS_SELECTOR, "button.pv-s-profile-actions--pending")))

        pending_btn_wrapper = wait.until(EC.visibility_of_element_located(
            (By.CSS_SELECTOR, pending_btn)))

        inmail_btn = wait.until(EC.visibility_of_element_located(
            (By.CSS_SELECTOR, "button.pv-s-profile-actions--inmail")))

        inmail_btn_wrapper = wait.until(EC.visibility_of_element_located(
            (By.CSS_SELECTOR, inmail_btn)))

        if message_btn_wrapper is not None:
            connect = "connected"

        if pending_btn_wrapper is not None:
            connect = "pending"

        if inmail_btn_wrapper is not None:
            connect = "ignored"

            # post the text in the right box
            box_css = """div.application-outlet>aside.msg-overlay-container div.msg-overlay-conversation-bubble div.msg-overlay-conversation-bubble__content-wrapper div.msg-s-message-list-container """

            #  textarea.ember-text-area msg-form__textarea"

            msg_box = wait.until(EC.visibility_of_element_located(
                (By.CSS_SELECTOR, box_css)))

            script = "window.scrollBy({x},{y});".format(x=msg_box.location.get('x', 0),
                                                        y=msg_box.location.get('y', 1000))
            print('script:', script)
            driver.execute_script(script)
            # print('get_attribute:', msg_box.get_attribute('innerHTML'))

            msg_list_css = "{0} {1}".format(box_css, "ul.msg-s-message-list>li")
            print('msg_list_css:', msg_list_css)
            message_list = driver.find_elements_by_css_selector(msg_list_css)
            html = message_list[-1].get_attribute('innerHTML')
            print('message_list:', html)
            if user_path in html:
                # found replied
                replied_date = datetime.now()
                m = re.search(r'([\d]+):([\d]+)\s+([AP]M)', html)
                print('time:', m)

                if m:
                    hr = int(m.group(1))
                    mi = int(m.group(2))
                    if m.group(3) == "PM":
                        hr += 12
                    d = replied_date.day
                    if hr < replied_date.hour:
                        d = d - 1

                    replied_date = replied_date.replace(minute=mi, hour=hr,
                                                        day=d)
                    print('replied_date:', replied_date)

                # get message
                m = re.search(r'<p class="msg-s-event-listitem__body[^"]*">([^<]+)</p>', html)
                if m:
                    message = m.group(1).strip()
                    print('message:', message)

    except Exception  as err:
        print('check connect error:', err)
        status = False

    # check back id?

    driver.close()

    return status, replied_date, connect, message


def postconnect_browser(cur, taskrow, msgdetail):
    email, password = get_user_email_pw(cur, taskrow[6])
    contact = get_db(cur, contact_select, (msgdetail[6],))
    print('contact:', contact)
    driver = login_linkedin_withwebdriver(email, password)

    user_path = "/in/{0}/".format(contact[10])
    # go to the user homme
    userhome = "{0}{1}".format(LINKEDIN_URL, user_path)
    print('userhome:', userhome)
    status = True
    replied_date = None
    message = ""
    # click on the send connect
    try:
        wait = WebDriverWait(driver, IDLE_INTERVAL_IN_SECONDS)
        driver.get(userhome)

        # pv-s-profile-actions--message
        # connect_btn = driver.find_element_by_class_name("button.pv-s-profile-actions--connect")
        connect_btn = wait.until(EC.visibility_of_element_located(
            (By.CSS_SELECTOR, "button.pv-s-profile-actions--connect")))

        connect_btn.click()

        # post the text in the popup
        box_css = """div#li-modal-container>div.modal-content-wrapper"""

        # add a note in popup
        addnote_css = """div#li-modal-container>div.modal-content-wrapper div.send-invite__actions button.button-secondary-large """
        btn_addnote = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, addnote_css)))
        btn_addnote.click()

        text_box_css = "{0} {1}".format(box_css, "div.msg-form__compose-area>textarea[name='message']")
        print('text_box_css:', text_box_css)
        message_box = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, text_box_css)))
        message_box.send_keys(msgdetail[3])

        message_box.send_keys(Keys.RETURN)
        time.sleep(IDLE_INTERVAL_IN_SECONDS)

        # connect send in popup
        connect_css = """div#li-modal-container>div.modal-content-wrapper div.send-invite__actions button.button-primary-large """
        btn_send = wait.until(EC.visibility_of_element_located(
            (By.CSS_SELECTOR, connect_css)))

        btn_send.click()

        time.sleep(IDLE_INTERVAL_IN_SECONDS)

    except Exception  as err:
        print('send connect error:', err)
        status = False

    # check back id?

    driver.close()

    return status


def checkmessage_browser(cur, taskrow, msgdetail):
    email, password = get_user_email_pw(cur, taskrow[6])
    contact = get_db(cur, contact_select, (msgdetail[6],))
    print('contact:', contact)
    driver = login_linkedin_withwebdriver(email, password)

    user_path = "/in/{0}/".format(contact[10])
    # go to the user homme
    userhome = "{0}{1}".format(LINKEDIN_URL, user_path)
    print('userhome:', userhome)
    status = True
    replied_date = None
    message = ""
    # click on the send message
    try:
        wait = WebDriverWait(driver, IDLE_INTERVAL_IN_SECONDS)
        driver.get(userhome)

        # pv-s-profile-actions--message
        # message_btn = driver.find_element_by_class_name("pv-s-profile-actions--message")
        message_btn = wait.until(EC.visibility_of_element_located(
            (By.CSS_SELECTOR, "button.pv-s-profile-actions--message")))

        message_btn.click()

        # post the text in the right box
        box_css = """div.application-outlet>aside.msg-overlay-container div.msg-overlay-conversation-bubble div.msg-overlay-conversation-bubble__content-wrapper div.msg-s-message-list-container """

        #  textarea.ember-text-area msg-form__textarea"

        msg_box = wait.until(EC.visibility_of_element_located(
            (By.CSS_SELECTOR, box_css)))

        script = "window.scrollBy({x},{y});".format(x=msg_box.location.get('x', 0),
                                                    y=msg_box.location.get('y', 1000))
        print('script:', script)
        driver.execute_script(script)
        # print('get_attribute:', msg_box.get_attribute('innerHTML'))

        msg_list_css = "{0} {1}".format(box_css, "ul.msg-s-message-list>li")
        print('msg_list_css:', msg_list_css)
        message_list = driver.find_elements_by_css_selector(msg_list_css)
        html = message_list[-1].get_attribute('innerHTML')
        print('message_list:', html)
        if user_path in html:
            # found replied
            replied_date = datetime.now()
            m = re.search(r'([\d]+):([\d]+)\s+([AP]M)', html)
            print('time:', m)

            if m:
                hr = int(m.group(1))
                mi = int(m.group(2))
                if m.group(3) == "PM":
                    hr += 12
                d = replied_date.day
                if hr < replied_date.hour:
                    d = d - 1

                replied_date = replied_date.replace(minute=mi, hour=hr,
                                                    day=d)
                print('replied_date:', replied_date)

            # get message
            m = re.search(r'<p class="msg-s-event-listitem__body[^"]*">([^<]+)</p>', html)
            if m:
                message = m.group(1).strip()
                print('message:', message)

    except Exception  as err:
        print('send message error:', err)
        status = False

    # check back id?

    driver.close()

    return status, replied_date, message


def test_handle_connect():
    cur = get_cursor()
    cur.execute(
        "SELECT * FROM app_bottask where status ='%s' or status='%s' order by id desc limit 1" % (bottask_status.QUEUED,
                                                                                                  bottask_status.PIN_CHECKING))
    row = cur.fetchone()
    print('row:', row)
    if row is not None and row[1] == bottask_type.POSTCONNECT:
        handle_checkconnect(cur, row)


if __name__ == "__main__":
    test_handle_connect()


