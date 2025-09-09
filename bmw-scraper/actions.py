from operator_layer.general_operator import GeneralOperator
from operator_layer.ac_operator import ACOperator
from playwright.sync_api import Page

AC_KEYWORD_MAP = {
    "evaporator": "evaporator_expansion_valve",
    "expansion valve": "evaporator_expansion_valve",
    "microfilter": "microfilter",
    "heater": "heater_radiator",
    "fresh air": "fresh_air_grille",
    "air channel": "air_channel",
    "cooling hose": "cooling_water_hoses",
    "aux hose": "coolant_hoses_aux",
    "distribution housing": "dist_housing",
    "filter housing": "filter_housing",
    "condenser": "condenser",
    "compressor": "compressor",
    "compressor bracket": "compressor",
    "bracket": "compressor"
}

class Actions:
    def __init__(self, page):
        self.general = GeneralOperator(page)
        self.ac = ACOperator(page)

    def find_ac_part_by_keyword(self, vin: str, keyword: str):
        section = AC_KEYWORD_MAP.get(keyword.lower())
        if not section:
            raise ValueError(f"No AC section found for keyword: {keyword}")
        self.general.dismiss_adblock()
        self.general.click_bmw_catalog()
        self.general.enter_vin(vin)
        self.general.click_first_search()
        self.general.click_browse_parts()
        self.general.click_heater_ac()
        ac_method = getattr(self.ac, f"click_{section}", None)
        if ac_method:
            ac_method()
        else:
            raise ValueError(f"AC section '{section}' not found in ACOperator.")

        self.general.page.wait_for_selector("tbody tr")

        part_numbers = []
        rows = self.general.page.locator("tbody tr").all()
        for row in rows:
            tds = row.locator("td")
            td_count = tds.count()
            if td_count < 10:
                continue
            try:
                description = tds.nth(1).inner_text().lower()
                notes = tds.nth(9).inner_text().lower()
                # Exclude compressor oil and bracket for compressor keyword
                if keyword.lower() == "compressor":
                    if "oil" in description or "bracket" in description:
                        continue
                if keyword.lower() in description and "discontinued" not in notes:
                    part_number_link = tds.nth(6).locator("a.inline-a")
                    if part_number_link.count() > 0:
                        part_number = part_number_link.inner_text().strip()
                        part_numbers.append(part_number)
            except Exception:
                continue
        return part_numbers
    
    def get_car_details(self, vin: str):
        self.general.dismiss_adblock()
        self.general.click_bmw_catalog()
        self.general.enter_vin(vin)
        self.general.click_first_search()
        return self.general.get_car_details()