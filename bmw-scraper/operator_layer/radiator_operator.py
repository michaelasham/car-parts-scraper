from info_layer.radiator_info import RadiatorInfo
from playwright.sync_api import Page, Error

class RadiatorOperator:
    def __init__(self, page: Page):
        self.page = page
        
    def click_radiator(self):
        self.page.locator(RadiatorInfo.RADIATOR,has_text="MOUNTING").click()
    
    def click_expansion_tank(self):
        self.page.locator(RadiatorInfo.EXPANSION_TANK).click()
        
    def click_fan_housing_w_fan(self):
        try:
            self.page.locator(RadiatorInfo.FAN_HOUSING_W_FAN).click(timeout=5000)
        except Error:
            self.page.locator(RadiatorInfo.FAN_HOUSING_W_FAN_ALT).click(timeout=10000)
            
    def filter_radiator_parts(self, keyword: str):
        table = self.page.locator(RadiatorInfo.RADIATOR_TABLE)
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

                # Exclude rows with "screw cap" in description
                if keyword.lower() in description and "screw cap" not in description and "bracket" not in description and "ended" not in notes:
                    part_number_link = tds.nth(6).locator("a.inline-a")
                    part_number_link.wait_for(state="attached")
                    if part_number_link.count() > 0:
                        part_number = part_number_link.inner_text().strip()
                        part_numbers.append(part_number)

            except Exception:
                continue

        return list(set(part_numbers))