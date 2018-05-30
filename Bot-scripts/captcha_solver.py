"""
# this solves captcha of linkedin & returns captcha response
"""
from python_anticaptcha import NoCaptchaTaskProxylessTask, AnticaptchaClient
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import time


IDLE_INTERVAL_IN_SECONDS = 5

# 
API_KEY = '91e6b240571c9b718be9095125ca51a0'

#site_key = '6LfTDSgTAAAAAMgNPKDdkNqxq81KTDWrL7gOabTt' # grab from site
SITE_KEY = '6Lc7CQMTAAAAAIL84V_tPRYEWZtljsJQJZ5jSijw' #linkedin
            
def solve_captcha(url):
    print("solving captcha....")
    res = None
    try:

        client = AnticaptchaClient(API_KEY)
        task = NoCaptchaTaskProxylessTask(url, SITE_KEY)
        job = client.createTask(task)
        job.join()
        res=job.get_solution_response()
        print("Captcha solved !!")
        
    except Exception as err:
        print("Captcha not solved... Error:", err)
        
      
    return res

def check_captcha(browser):
    
    recaptcha_elem = None
    
    url = None
    # it not done yet
    #return True

    #
    try:
        selector = browser.find_element_by_css_selector("#noCaptchaIframe")
        
    except Exception as err:
        print('noCaptchaIframe:', err)
        return True
    
    try:
        selector = browser.find_element_by_css_selector("#noCaptchaIframe")
        browser.switch_to.frame(selector)
        
        #, "#nocaptcha > div > div > iframe")
        frame2css = "#nocaptcha > div > div > iframe"
        iframe2 = browser.find_element_by_css_selector(frame2css)
        
        
        url = iframe2.get_attribute('src')
        print('captchar url:',  url)
        
        
        recaptcha_elem=browser.find_element_by_id('g-recaptcha-response')
        script= """document.getElementById('g-recaptcha-response').style.height='50px';
         document.getElementById('g-recaptcha-response').style.display='block';"""
        browser.execute_script(script,recaptcha_elem)
        recaptcha_elem.clear()
        
        print("Processing re-captcha...")
        ## Captcha processed
        res=solve_captcha(url)
        #res= "safasfasdfasfasdfasdfasdfasdfadsfasdfasdfasdfasdfsadfasdffffff"
        done = False
        if res:
            recaptcha_elem.send_keys(res)
            browser.switch_to.default_content()
            print("solved...")
            
            
            nocaptcha_id = 'nocaptcha-response'
            nocaptca =browser.find_element_by_id(nocaptcha_id)
            x = nocaptca.location.get('x', 0)
            y = nocaptca.location.get('y', 1000)
            script = "window.scrollBy({x},{y});".format(x=x,y=y)
            print('script:', script)
            browser.execute_script(script)
            script= 'document.getElementById("{nocaptcha_id}").value = "{val}"'.format(
                val=res, nocaptcha_id=nocaptcha_id)
            print('script:', script)
            browser.execute_script(script,nocaptca)
            
            
            submit_button_id = 'btn-fallback-submit'
            coninue_button=browser.find_element_by_id(submit_button_id)
            script= """document.getElementById('{button_id}').style.height='50px';
             document.getElementById('{button_id}').style.display='block';""".format(button_id=submit_button_id)
            browser.execute_script(script,coninue_button)
            print('script:', script)
            browser.execute_script("window.scrollBy({x},{y});".format(x=coninue_button.location.get('x', 0), 
                                                                      y=coninue_button.location.get('y', 1000)))
            print('scroll to button:', submit_button_id)
            time.sleep(3)
            #coninue_button = browser.find_element_by_id(submit_button_id)
            coninue_button.click()
            time.sleep(IDLE_INTERVAL_IN_SECONDS)
            done = True
        else:
            browser.switch_to.default_content()
        
        
        return done

    except Exception as err:
        print('g-recaptcha error:', err)
        time.sleep(IDLE_INTERVAL_IN_SECONDS)
        return False
    
    
        
    
