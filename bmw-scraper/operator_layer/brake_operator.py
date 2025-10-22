from playwright.sync_api import Page
from info_layer.brake_info import BrakeInfo

class BrakeOperator:
    def __init__(self, page: Page):
        self.page = page
        
    def click_front_sensor(self):
        self.page.locator(BrakeInfo.FRONT_SENSOR).nth(0).click()
        
    def click_front_brake(self):
        self.page.locator(BrakeInfo.FRONT_BRAKE).click()
        
    def click_rear_brake(self):
        self.page.locator(BrakeInfo.REAR_BRAKE).click()
    
    def click_rear_sensor(self):
        try:
            self.page.locator(BrakeInfo.REAR_SENSOR).click()
        except:
            self.page.locator(BrakeInfo.REAR_SENSOR_ALT).click()
        
    def click_brake_pads(self):
        self.page.locator(BrakeInfo.BRAKE_PADS).click()
    
    def filter_brake_table(self, keyword: str):
        table = self.page.locator(BrakeInfo.BRAKE_TABLE)
        part_numbers = []
        rows = table.locator("tr")
        rows.first.wait_for(state="attached")

        for row in rows.all():
            tds = row.locator("td")
            td_count = tds.count()
            if td_count < 10:
                continue
            try:
                description = tds.nth(1).inner_text().lower()
                notes = tds.nth(9).inner_text().lower()

                # Exclude rows with "repair kit" in description
                if keyword.lower() in description and "repair kit" not in description and "ended" not in notes:
                    part_number_link = tds.nth(6).locator("a.inline-a")
                    part_number_link.wait_for(state="attached")
                    if part_number_link.count() > 0:
                        part_number = part_number_link.inner_text().strip()
                        part_numbers.append(part_number)

            except Exception:
                continue

        return part_numbers