import {chromium} from '@playwright/test';
export default async function setup(){const browser=await chromium.launch();const page=await browser.newPage();await page.goto('http://127.0.0.1:15173/#/cases');await page.getByRole('button',{name:/New case|Create your first case/}).first().waitFor();await browser.close()}
