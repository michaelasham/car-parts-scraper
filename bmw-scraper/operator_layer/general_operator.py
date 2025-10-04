from playwright.sync_api import Page
from info_layer.general_info import GeneralInfo

class GeneralOperator:
    def __init__(self, page: Page):
        self.page = page
        
    def dismiss_adblock(self):
        if self.page.locator(GeneralInfo.DISMISS_ADBLOCK).is_visible():
            self.page.locator(GeneralInfo.DISMISS_ADBLOCK).click()

    def click_bmw_catalog(self):
        self.page.locator(GeneralInfo.BMW_CATALOG).click()

    def enter_vin(self, vin: str):
        self.page.locator(GeneralInfo.VIN_INPUT).fill(vin)

    def click_first_search(self):
        self.page.locator(GeneralInfo.FIRST_SEARCH_BUTTON).nth(0).click()

    def click_browse_parts(self):
        self.page.locator(GeneralInfo.BROWSE_PARTS_BUTTON).click()

    def click_engine(self):
        self.page.locator(GeneralInfo.ENGINE).click()

    def click_technical_literature(self):
        self.page.locator(GeneralInfo.TECHNICAL_LITERATURE).click()

    def click_radiator(self):
        self.page.locator(GeneralInfo.RADIATOR).click()

    def click_clutch(self):
        self.page.locator(GeneralInfo.CLUTCH).click()

    def click_fuel_supply(self):
        self.page.locator(GeneralInfo.FUEL_SUPPLY).click()

    def click_exhaust_system(self):
        self.page.locator(GeneralInfo.EXHAUST_SYSTEM).click()

    def click_drive_shaft(self):
        self.page.locator(GeneralInfo.DRIVE_SHAFT).click()

    def click_gearshift(self):
        self.page.locator(GeneralInfo.GEARSHIFT).click()

    def click_steering(self):
        self.page.locator(GeneralInfo.STEERING).click()

    def click_suspension(self):
        self.page.locator(GeneralInfo.SUSPENSION).click()

    def click_brakes(self):
        self.page.locator(GeneralInfo.BRAKES).click()

    def click_wheels(self):
        self.page.locator(GeneralInfo.WHEELS).click()

    def click_retrofitting(self):
        self.page.locator(GeneralInfo.RETROFITTING).click()

    def click_engine_elec_system(self):
        self.page.locator(GeneralInfo.ENGINE_ELEC_SYSTEM).click()

    def click_fuel_prep(self):
        self.page.locator(GeneralInfo.FUEL_PREP).click()

    def click_automatic_transmission(self):
        self.page.locator(GeneralInfo.AUTOMATIC_TRANSMISSION).click()

    def click_manual_transmission(self):
        self.page.locator(GeneralInfo.MANUAL_TRANSMISSION).click()

    def click_trim(self):
        self.page.locator(GeneralInfo.TRIM).click()

    def click_pedals(self):
        self.page.locator(GeneralInfo.PEDALS).click()

    def click_bodywork(self):
        self.page.locator(GeneralInfo.BODYWORK).click()

    def click_vehicle_trim(self):
        self.page.locator(GeneralInfo.VEHICLE_TRIM).click()

    def click_seats(self):
        self.page.locator(GeneralInfo.SEATS).click()

    def click_sliding_roof(self):
        self.page.locator(GeneralInfo.SLIDING_ROOF).click()

    def click_instruments(self):
        self.page.locator(GeneralInfo.INSTRUMENTS).click()

    def click_lighting(self):
        self.page.locator(GeneralInfo.LIGHTING).click()

    def click_heater_ac(self):
        self.page.locator(GeneralInfo.HEATER_AC).click()

    def click_audio_nav(self):
        self.page.locator(GeneralInfo.AUDIO_NAV).click()

    def click_distance_systems(self):
        self.page.locator(GeneralInfo.DISTANCE_SYSTEMS).click()

    def click_equ_parts(self):
        self.page.locator(GeneralInfo.EQU_PARTS).click()

    def click_restraint_system(self):
        self.page.locator(GeneralInfo.RESTRAINT_SYSTEM).click()

    def click_aux_materials(self):
        self.page.locator(GeneralInfo.AUX_MATERIALS).click()

    def click_comm_systems(self):
        self.page.locator(GeneralInfo.COMM_SYSTEMS).click()

    def click_value_parts(self):
        self.page.locator(GeneralInfo.VALUE_PARTS).click()
    
    def click_quick_service_parts(self):
        self.page.locator(GeneralInfo.QUICK_SERVICE).click()
    
    def get_car_details(self):
        details = {}
        details["product"] = self.page.locator("option[selected='selected']").nth(1).inner_text()
        details["catalog"] = self.page.locator("option[selected='selected']").nth(2).inner_text()
        details["series"] = self.page.locator("option[selected='selected']").nth(3).inner_text()
        details["body"] = self.page.locator("option[selected='selected']").nth(4).inner_text()
        details["model"] = self.page.locator("option[selected='selected']").nth(5).inner_text()
        details["market"] = self.page.locator("option[selected='selected']").nth(6).inner_text()
        details["prod_month"] = self.page.locator("option[selected='selected']").nth(7).inner_text()
        details["engine"] = self.page.locator("option[selected='selected']").nth(8).inner_text()
        return details
        