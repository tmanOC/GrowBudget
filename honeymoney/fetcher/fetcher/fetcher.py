from selenium import webdriver
import time

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException


class Fetcher:
    """CMS TEST"""
    balances = []

    def __init__(self):
        chrome_options = Options()
        # chrome_options.add_argument("--headless")
        chrome_options.add_argument("--window-size=1920x1080")

        self.browser = webdriver.Chrome(chrome_options=chrome_options, executable_path=r"/usr/local/bin/chromedriver")

    def set_up_browser(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--window-size=1920x1080")

        self.browser = webdriver.Chrome(chrome_options=chrome_options, executable_path=r"/usr/local/bin/chromedriver")

    def tear_down_browser(self):
        self.browser.quit()

    def nedbank_login_and_work(self, username, password, work):
        self.browser.get('https://secured.nedbank.co.za')
        time.sleep(5)
        self.browser.find_element_by_xpath('//*[@id="username"]').send_keys(username)
        self.browser.find_element_by_id('password').send_keys(password)
        self.browser.find_element_by_id('log_in').click()

        try:
            WebDriverWait(self.browser, 40).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="scroll-page"]/div/div/div/app-landing/div[1]/div/div[2]/div/div/div/div[5]/app-accounts/div/app-account-widget[1]/div/div[2]/div[1]/div/div[1]/div/div/div[3]/div[2]'))
            )

            time.sleep(5)
            work()
        except TimeoutException:
            pass
        finally:

            self.browser.quit()

    def login_and_work(self, username, password, work):
        self.browser.get('https://fnb.co.za')
        try:
            self.browser.find_element_by_name('Username').send_keys(username)
            self.browser.find_element_by_name('Password').send_keys(password)
            self.browser.find_element_by_id('OBSubmit').click()
            WebDriverWait(self.browser, 40).until(
                EC.presence_of_element_located((By.ID, "newsLanding"))
            )
            time.sleep(5)
            work()
        finally:

            self.browser.quit()

    def get_balances(self):
        # find and click the accounts button
        
        clear_button = self.browser.find_element_by_xpath('//*[@id="newsLanding"]/div[3]/ul/li[4]/div')
        clear_button.click()
        # wait for balances to show and get them
        WebDriverWait(self.browser, 40).until(
            EC.presence_of_element_located((By.ID, "availablebalance_2"))
        )
        element_balance = self.browser.find_element_by_id("availablebalance_2")
        check_balance = element_balance.text
        array = str.split(check_balance, ' ')
        check_balance = array[1]
        check_balance = check_balance.replace(',', '')
        element_credit = self.browser.find_element_by_id("availablebalance_3")
        credit_balance = element_credit.text
        credit_balance = credit_balance.replace(',', '')
        self.balances = [check_balance, credit_balance]

    def nedbank_get_balances(self):
        # self.browser.find_element_by_class_name()
        check_balance = self.browser.find_element_by_xpath('//*[@id="scroll-page"]/div/div/div/app-landing/div[1]/div/div[2]/div/div/div/div[5]/app-accounts/div/app-account-widget[1]/div/div[2]/div[1]/div/div[1]/div/div/div[3]/div[2]').text
        check_balance = check_balance.replace('R', '')
        check_balance = check_balance.replace(' ', '')
        self.balances = [check_balance, '']


# obj = Fetcher()
# obj.set_up_browser()

