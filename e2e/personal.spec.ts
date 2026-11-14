import {expect,test} from '@playwright/test';

test('personal mode keeps technical complexity behind task-based results',async({page})=>{
  await page.goto('/#/personal/check',{waitUntil:'domcontentloaded'});
  await expect(page.getByRole('heading',{name:'Check a suspicious photo, video or voice message'})).toBeVisible();
  await expect(page.getByText('Your file stays in this browser in Personal mode')).toBeVisible();

  await page.locator('input[type=file]').setInputFiles({name:'message.png',mimeType:'image/png',buffer:Buffer.from('personal-check')});
  await page.getByRole('button',{name:'Check this file'}).click();
  await expect(page.getByRole('heading',{name:'We couldn’t tell'})).toBeVisible();
  await expect(page.getByText('WHAT WE COULDN’T CHECK')).toBeVisible();
  await expect(page.getByRole('button',{name:'Download summary'})).toBeVisible();

  await page.getByRole('button',{name:'Compare copies'}).click();
  await page.locator('input[type=file]').setInputFiles([
    {name:'copy-one.png',mimeType:'image/png',buffer:Buffer.from('same-bytes')},
    {name:'copy-two.png',mimeType:'image/png',buffer:Buffer.from('same-bytes')},
  ]);
  await page.getByRole('button',{name:'Compare files'}).click();
  await expect(page.getByRole('heading',{name:'These files are exact copies'})).toBeVisible();

  await page.getByRole('button',{name:'My checks'}).click();
  await expect(page.getByText('These files are exact copies').first()).toBeVisible();
  await expect(page.getByText('We couldn’t tell').first()).toBeVisible();
});
