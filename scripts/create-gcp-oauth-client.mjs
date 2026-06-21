#!/usr/bin/env node
/** Create GCP OAuth Web client with JS origin for Google Sign-In. */
import { chromium } from 'playwright';
import fs from 'node:fs';

const PROJECT = process.env.GCP_PROJECT || 'iso-compliance-platform';
const ORIGIN = process.env.OAUTH_JS_ORIGIN
  || 'https://iso-web-iso-platform.apps.ocp.8mkwb.sandbox3159.opentlc.com';
const OUT = process.env.OAUTH_OUT || '/tmp/iso-google-oauth.json';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  const browser = await chromium.launch({ headless: false, channel: 'chrome' });
  const page = await browser.newPage();
  const url = `https://console.cloud.google.com/auth/clients/create?project=${PROJECT}`;
  console.error(`Open ${url} — sign in to Google Cloud if needed (90s)`);
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 120000 });
  await sleep(90000);

  // Web application
  const typeSelect = page.locator('mat-select, [role="combobox"]').filter({ hasText: /application type|סוג/i }).first();
  if (await typeSelect.isVisible().catch(() => false)) {
    await typeSelect.click();
    await page.getByRole('option', { name: /Web application/i }).click();
    await sleep(2000);
  }

  const nameInput = page.locator('input').filter({ has: page.locator('xpath=..') }).first();
  await page.getByLabel(/^Name$/i).fill('ISO Compliance Platform').catch(async () => {
    await page.locator('input[formcontrolname="displayName"], input[aria-label*="Name"]').first().fill('ISO Compliance Platform');
  });

  // JS origins
  const addBtns = page.getByRole('button', { name: /Add URI/i });
  const count = await addBtns.count();
  for (let i = 0; i < count; i++) {
    const section = addBtns.nth(i);
    const parent = section.locator('xpath=ancestor::*[contains(@class,"form") or contains(@class,"section")][1]');
    const text = await parent.innerText().catch(() => '');
    if (text.match(/JavaScript origins/i)) {
      await section.click();
      await parent.locator('input').last().fill(ORIGIN);
      break;
    }
  }
  // fallback: fill first empty URI input
  await page.locator('input[type="url"], input[placeholder*="https"]').first().fill(ORIGIN).catch(() => undefined);

  await page.getByRole('button', { name: /^Create$/i }).click({ timeout: 15000 }).catch(() => undefined);
  await sleep(10000);

  const html = await page.content();
  const clientId = html.match(/(\d+-[a-z0-9]+\.apps\.googleusercontent\.com)/i)?.[1] || '';
  const result = { clientId, jsOrigin: ORIGIN, project: PROJECT };
  fs.writeFileSync(OUT, JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result));
  if (!clientId) console.error('No client ID found — complete creation in browser; check', OUT);
  await sleep(60000);
  await browser.close();
}

main().catch((e) => { console.error(e); process.exit(1); });
