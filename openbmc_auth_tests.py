import unittest
import time
from getpass import getpass

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


URL = "https://localhost:8000"
USER = input("OpenBMC username: ")
PASSWORD = getpass("OpenBMC password: ")


class OpenBMCTests(unittest.TestCase):

    def setUp(self):
        options = webdriver.ChromeOptions()
        options.binary_location = "/snap/chromium/3548/usr/lib/chromium-browser/chrome"
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--no-sandbox")

        self.driver = webdriver.Chrome(
            service=Service("/snap/chromium/3548/usr/lib/chromium-browser/chromedriver"),
            options=options
        )
        self.wait = WebDriverWait(self.driver, 20)
        self.driver.get(URL)

    def login(self, password=PASSWORD):
        self.wait.until(EC.visibility_of_element_located((By.ID, "username"))).send_keys(USER)
        self.driver.find_element(By.ID, "password").send_keys(password)
        self.wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "button[type='submit']")
        )).click()

    def open_page(self, path):
        self.wait.until(lambda d: "#/login" not in d.current_url)
        link = self.wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, f'a[href="#{path}"]')
        ))
        self.driver.execute_script("arguments[0].click();", link)
        self.wait.until(lambda d: d.current_url.endswith("#" + path))

    def test_1_successful_login(self):
        self.login()
        self.wait.until(lambda d: "#/login" not in d.current_url)
        self.assertNotIn("#/login", self.driver.current_url, "Login failed.")

    def test_2_invalid_password(self):
        self.login("wrong_password")
        error = WebDriverWait(self.driver, 20, poll_frequency=0.2).until(
            EC.visibility_of_element_located((By.XPATH, "//*[text()='Invalid username or password']"))
        )
        self.assertTrue(error.is_displayed())

    def test_3_account_lockout(self):
        for _ in range(10):
            self.login("wrong_password")
            self.wait.until(EC.visibility_of_element_located(
                (By.XPATH, "//*[contains(., 'Invalid username or password')]")
            ))
            self.driver.find_element(By.ID, "username").clear()
            self.driver.find_element(By.ID, "password").clear()

        self.login(PASSWORD)
        time.sleep(5)
        self.assertIn("#/login", self.driver.current_url)

    def test_4_inventory(self):
        self.login()
        self.wait.until(lambda d: "#/login" not in d.current_url)
        self.open_page("/hardware-status/inventory")

        self.wait.until(lambda d: len(d.find_elements(
            By.CSS_SELECTOR, "div.container-xl div.page-section table"
        )) == 8)
        time.sleep(10)

        inventory = self.driver.execute_script("""
            return Array.from(document.querySelectorAll('div.container-xl div.page-section table tbody'))
                .map(t => Array.from(t.querySelectorAll('tr'))
                .filter(r => !r.classList.contains('b-table-empty-row'))
                .map(r => r.innerText.trim()).filter(Boolean));
        """)

        sections = ["System", "BMC", "Chassis", "DIMM slot", "Fans",
                    "Power supplies", "Processors", "Assemblies"]

        total_items = 0
        for section, items in zip(sections, inventory):
            print(f"{section}: {len(items)} item(s)")
            total_items += len(items)

        self.assertGreater(total_items, 0, "No equipment found in inventory.")

    def test_5_sensors(self):
        self.login()
        self.wait.until(lambda d: "#/login" not in d.current_url)
        self.open_page("/hardware-status/sensors")
        time.sleep(10)

        page_text = self.driver.find_element(By.TAG_NAME, "body").text
        self.assertIn("Sensors", page_text)
        self.assertIn("No items available", page_text)

    def tearDown(self):
        if hasattr(self, "driver"):
            self.driver.quit()


if __name__ == "__main__":
    unittest.main(verbosity=2)
