from info_layer.ac_info import ACInfo
from playwright.sync_api import Page

class ACOperator:
    def __init__(self, page: Page):
        self.page = page

    def click_fresh_air_grille(self):
        self.page.locator(ACInfo.FRESH_AIR_GRILLE).click()

    def click_air_channel(self):
        self.page.locator(ACInfo.AIR_CHANNEL).click()

    def click_microfilter(self):
        self.page.locator(ACInfo.MICROFILTER).click()

    def click_heater_radiator(self):
        self.page.locator(ACInfo.HEATER_RADIATOR).click()

    def click_cooling_water_hoses(self):
        self.page.locator(ACInfo.COOLING_WATER_HOSES).click()

    def click_coolant_hoses_aux(self):
        self.page.locator(ACInfo.COOLANT_HOSES_AUX).click()

    def click_evaporator_expansion_valve(self):
        self.page.locator(ACInfo.EVAPORATOR_EXPANSION_VALVE).click()

    def click_dist_housing(self):
        self.page.locator(ACInfo.DIST_HOUSING).click()

    def click_filter_housing(self):
        self.page.locator(ACInfo.FILTER_HOUSING).click()
        
    def click_compressor(self):
        self.page.locator(ACInfo.COMPRESSOR).click()
        
    def click_condenser(self):
        self.page.locator(ACInfo.CONDENSER).click()