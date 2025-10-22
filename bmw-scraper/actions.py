from operator_layer.general_operator import GeneralOperator
from operator_layer.ac_operator import ACOperator
from playwright.sync_api import Page
from operator_layer.quick_service_operator import QuickServiceOperator
from operator_layer.brake_operator import BrakeOperator

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

OIL_SERVICE_KEYWORDS = [
    "oil-filter",
    "air filter",
    "spark plugs",
    "spark plug",
    "micro filter",
]

BRAKE_SERVICE_KEYWORDS = {
    "brake discs" : "brake disc",
    "brake disc": "brake disc",
    "front brake disc": "brake disc",
    "rear brake disc": "brake disc"
}

class Actions:
    def __init__(self, page):
        self.general = GeneralOperator(page)
        self.ac = ACOperator(page)
        self.quick = QuickServiceOperator(page)
        self.brake = BrakeOperator(page)

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
                if keyword.lower() in description and "ended" not in notes:
                    part_number_link = tds.nth(6).locator("a.inline-a")
                    part_number_link.wait_for(state="attached")
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
    
    def find_service_part_by_keyword(self, vin: str, keyword:str):
        self.general.dismiss_adblock()
        self.general.click_bmw_catalog()
        self.general.enter_vin(vin)
        self.general.click_first_search()
        self.general.click_browse_parts()
        self.general.click_quick_service_parts()
        
        result = None
        if keyword.lower() in OIL_SERVICE_KEYWORDS:
            self.quick.click_oil_maintenance()
            result = self.quick.filter_quick_service_table(keyword)
        elif keyword.lower() in BRAKE_SERVICE_KEYWORDS:
            self.quick.click_brake_service()
            result = self.quick.filter_brake_service_table(BRAKE_SERVICE_KEYWORDS[keyword])
        
        return result
    
    def find_brake_part_by_keyword(self, vin: str, keyword:str):
        self.general.dismiss_adblock()
        self.general.click_bmw_catalog()
        self.general.enter_vin(vin)
        self.general.click_first_search()
        self.general.click_browse_parts()
        self.general.click_brakes()
        result = None
        if keyword == "front brake disc":
            self.brake.click_front_brake()
            result = self.brake.filter_brake_table("brake disc")
            
        elif keyword == "rear brake disc":
            self.brake.click_rear_brake()
            result = self.brake.filter_brake_table("brake disc")
            
        elif keyword == "front brake pad wear sensor":
            self.brake.click_front_sensor()
            result = self.brake.filter_brake_table("Brake pad wear sensor")
            
        elif keyword == "rear brake pad wear sensor":
            self.brake.click_rear_sensor()
            result = self.brake.filter_brake_table("Brake pad wear sensor, rear")
            
        elif keyword == "brake pads":
            self.brake.click_brake_pads()
            result = self.brake.filter_brake_table(keyword)
            
        return result