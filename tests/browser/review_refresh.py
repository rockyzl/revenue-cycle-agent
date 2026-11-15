"""UI regression with mocked portal responses; no real sign-in/model/workflow calls."""
from playwright.sync_api import sync_playwright
import json, os
row={'id':'test-review','bill_id':'BILL-A101','message':'Why did I receive this statement?','status':'awaiting_review','created_at':1794718400,'updated_at':1794718401,'draft':{'response':'Original draft','needs_specialist':False},'trace':[],'checks':{}}
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.getenv('CHROMIUM_EXECUTABLE'),headless=True)
 page=browser.new_page()
 def api(route):
  path=route.request.url.split('/portal/api')[-1]
  data={'/config':{'accounts':[]},'/me':{'account':{'id':'reviewer','name':'Demo reviewer','role':'reviewer'},'csrf':'test'},'/inquiries':{'inquiries':[row]}}[path]
  route.fulfill(json=data)
 page.route('**/portal/api/**',api)
 page.goto(os.getenv('DEMO_URL','http://127.0.0.1:8089').rstrip('/')+'/billing',wait_until='networkidle')
 draft=page.locator('#reply-test-review');draft.fill('Edited by reviewer: the payment has posted.')
 row['updated_at']+=1
 page.locator('#refresh').click();page.wait_for_timeout(400)
 assert draft.input_value()=='Edited by reviewer: the payment has posted.'
 page.locator('#refresh').click();page.wait_for_timeout(400)
 assert draft.input_value()=='Edited by reviewer: the payment has posted.'
 print('Reviewer edit survives changing server snapshot and repeated manual refresh.')
 browser.close()
