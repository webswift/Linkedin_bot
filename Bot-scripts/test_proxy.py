from datetime import datetime
import os

from selenium.webdriver.support.wait import WebDriverWait

from bot_driver import marionette_driver, login_linkedin_withwebdriver, \
    IDLE_INTERVAL_IN_SECONDS
from bot_mysql import exist_user
from bot_mysql2 import check_password_correct, pinverify
from captcha_solver import check_captcha

import bottask_status as botstatus


def login_linkedin(email, password, pincode=None,
    cur=None, owner_id=None, task_id=None, task_type=None):
    print("==== LOGIN =====")
    lastrun_date = datetime.now()
    completed_date = datetime.now()
    driver = login_linkedin_withwebdriver(email, password)
    try:
        wait = WebDriverWait(driver, IDLE_INTERVAL_IN_SECONDS)
        # check if user is exist
        bot_status = botstatus.DONE
        if exist_user(wait):
            print("That user is an existing user.")
            
            if check_password_correct(wait):
                print('pw is correct')
            
                res = check_captcha(driver)
                if res == False:
                    driver.close()
                    return bot_status, lastrun_date, completed_date
                
                # pin code verification
                res, no_pin_required = pinverify(wait, pincode, cur, owner_id, task_id, task_type)
                if res and no_pin_required:
                    completed_date = datetime.now()
                    driver.close()
                    return bot_status, lastrun_date, completed_date, completed_date
                
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
        
        
        driver.close()
        return bot_status, lastrun_date, completed_date

    except Exception as e:
        bot_status = botstatus.ERROR
        
        print(bot_status , ':', e)
        driver.close()
        return bot_status, lastrun_date, completed_date
    
    


user_email = os.environ.get('email', None)
user_pw = os.environ.get('pw', None)

browser = marionette_driver(proxy_ip='127.0.0.1', proxy_port=8080, 
                            headless=False)

login_linkedin(user_email,user_pw, browser)

browser.close()
