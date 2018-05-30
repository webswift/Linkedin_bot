import os

from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

LINKEDIN_URL = "https://www.linkedin.com"
IDLE_INTERVAL_IN_SECONDS = 5


def marionette_driver(**kwargs):
    proxy_port = kwargs.get('proxy_port', None)
    proxy_ip = kwargs.get('proxy_ip', None)

    options = Options()
    if kwargs.get('headless', True):
        options.add_argument('--headless')

    dir_ = os.path.dirname(__file__)
    ffProfilePath = os.path.join(dir_, "FirefoxSeleniumProfile")
    if os.path.isdir(ffProfilePath) == False:
        os.mkdir(ffProfilePath)

    #profile = webdriver.FirefoxProfile(profile_directory=ffProfilePath)

    profile = webdriver.FirefoxProfile()
    if proxy_ip and proxy_port:
        print('setting proxy')
        profile.set_preference('network.proxy.socks_port', int(proxy_port))
        profile.set_preference('network.proxy.socks', proxy_ip)
        profile.set_preference("network.proxy.type", 1)
        profile.set_preference("network.proxy.http", proxy_ip)
        profile.set_preference("network.proxy.http_port", int(proxy_port))
        profile.update_preferences()

    firefox_capabilities = DesiredCapabilities.FIREFOX
    firefox_capabilities['marionette'] = True
    #firefox_capabilities['binary'] = '/usr/bin/firefox'
    #driver = webdriver.Firefox(capabilities=firefox_capabilities)
    firefox_capabilities['handleAlerts'] = True
    firefox_capabilities['acceptSslCerts'] = True
    firefox_capabilities['acceptInsecureCerts'] = True
    firefox_capabilities['javascriptEnabled'] = True

    # cap = {'platform': 'ANY', 'browserName': 'firefox', 'version': '', 'marionette': True, 'javascriptEnabled': True}
    driver = webdriver.Firefox(options=options, firefox_profile=profile,
                               capabilities=firefox_capabilities)

    #driver = webdriver.Firefox(options=options,
    #                        capabilities=firefox_capabilities)

    return driver


def login_linkedin_withwebdriver(email, password, driver=None):
    user_email = email
    user_password = password
    
    # driver = botdriver.ff_driver()
    if driver is None:
        # , proxy_ip='127.0.0.1', proxy_port=8080,
        #vdriver = marionette_driver(headless=False)
        # driver = marionette_driver(proxy_ip='127.0.0.1', proxy_port=8080)
        # head less
        driver = marionette_driver()

    driver.get(LINKEDIN_URL)
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
