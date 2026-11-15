import {expect,test} from '@playwright/test';
import {createCaseUi,fixture,runUi,uploadUi} from './helpers';

test('legacy workflow routes redirect to consolidated destinations',async({page})=>{
 await page.goto('/#/detection',{waitUntil:'domcontentloaded'});
 await expect(page).toHaveURL(/#\/analysis$/);
 await expect(page.getByRole('heading',{name:'Media Analysis'})).toBeVisible();
 await page.goto('/#/explainability',{waitUntil:'domcontentloaded'});
 await expect(page).toHaveURL(/#\/review$/);
 await expect(page.getByRole('heading',{name:'Review & Report'})).toBeVisible();
});

test('referenced review summary remains gated until review and approval',async({page})=>{
 await createCaseUi(page);
 await uploadUi(page,fixture('valid.png'));
 await runUi(page);
 await page.getByRole('button',{name:'Review & Report'}).first().click();
 await expect(page.getByText(/EVID-/).first()).toBeVisible();
 await expect(page.getByText(/FIND-|F-/).first()).toBeVisible();
 await expect(page.getByRole('button',{name:'Generate report'})).toBeDisabled();
});
