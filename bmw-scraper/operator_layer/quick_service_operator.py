from playwright.sync_api import Page
from info_layer.quick_service_info import QuickServiceInfo

class QuickServiceOperator:
    def __init__(self, page: Page):
        self.page = page
        
    def click_oil_maintenance(self):
        self.page.locator(QuickServiceInfo.OIL_MAINTENANCE).click()
        
    def filter_quick_service_table(self,keyword: str):
        table = self.page.locator(QuickServiceInfo.QUICK_SERVICE_TABLE)
        part_numbers = []
        quantities = []
        include_qty = False
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
                if keyword.lower() == "spark plugs":
                    include_qty = True
                if keyword.lower() in description and "ENDED" not in notes:
                    part_number_link = tds.nth(6).locator("a.inline-a")
                    part_number_link.wait_for(state="attached")
                    if part_number_link.count() > 0:
                        part_number = part_number_link.inner_text().strip()
                        part_numbers.append(part_number)
                    if include_qty:
                        qty = tds.nth(3).inner_text().strip()
                        quantities.append(qty)
                        
            except Exception:
                continue
        if include_qty:
            return list(zip(part_numbers,quantities))
        return part_numbers
        
        