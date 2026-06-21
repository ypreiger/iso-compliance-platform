#!/usr/bin/env node
import { chromium } from 'playwright';
import fs from 'node:fs';

const PROJECT = process.env.GCP_PROJECT || 'iso-compliance-platform';
const REDIRECT = process.env.OAUTH_REDIRECT_URI
  || 'https://iso-web-iso-platform.apps.ocp.8mkwb.sandbox3159.opentlc.com/auth/callback';
const ORIGIN = process.env.OAUTH_JS_ORIGIN
  || 'https://iso-web-iso-platform.apps.ocp.8mkwb.sandbox3159.opentlc.com';
const CLIENT_NAME = process.env.OAUTH_CLIENT_NAME || 'ISO Compliance Web';
const OUT = process.env.OAUTH_OUT || '/tmp/iso-google-oauth.json';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function fillUri(page, labelRe, value) {
  const section = page.locator('cfc-form-section, mat-form-field, .cm-field').filter({ hasText: labelRe });
  const addBtn = section.getByRole('button', { name: /Add URI/i });
  if (await addBtn.count()) await addBtn.first().click();
  const input = section.locator('input').last();
  await input.waitFor({ state: 'visible', timeout: 15000 });
  await input.fill(value);
}

async function main() {
  const browser = await chromium.launch({ headless: false });
  const page = await browser.newPage();
  const createUrl = `https://console.cloud.google.com/auth/clients/create?project=${PROJECT}`;
  console.log(`Open ${createUrl} — sign in if prompted`);
  await page.goto(createUrl, { waitUntil: 'domcontentloaded', timeout: 180000 });
  await sleep(8000);
  await page.screenshot({ path: '/tmp/gcp-oauth-step1.png', fullPage: true });

  // Application type: Web application
  const appType = page.getByLabel(/Application type/i);
  if (await appType.isVisible().catch(() => false)) {
    await appType.click();
    await page.getByRole('option', { name: /Web application/i }).click();
  }

  await page.getByLabel(/^Name$/i).fill(CLIENT_NAME).catch(async () => {
    await page.locator('input[formcontrolname="displayName"], input[name="displayName"]').first().fill(CLIENT_NAME);
  });

  await fillUri(page, /JavaScript origins/i, ORIGIN).catch(() => undefined);
  await fillUri(page, /redirect URIs/i, REDIRECT).catch(() => undefined);

  await page.screenshot({ path: '/tmp/gcp-oauth-step2.png', fullPage: true });
  await page.getByRole('button', { name: /^Create$/i }).click({ timeout: 10000 }).catch(() => undefined);
  await sleep(8000);
  await page.screenshot({ path: '/tmp/gcp-oauth-step3.png', fullPage: true });

  const body = await page.content();
  const clientId = body.match(/(\d+-[a-z0-9]+\.apps\.googleusercontent\.com)/i)?.[1] || '';
  const clientSecret = body.match(/(GOCSPX-[A-Za-z0-9_-]+)/)?.[1] || '';

  const result = { clientId, clientSecret, redirectUri: REDIRECT, jsOrigin: ORIGIN, project: PROJECT };
  fs.writeFileSync(OUT, JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
  if (!clientId) console.error('Set credentials manually; screenshots in /tmp/gcp-oauth-step*.png');
  await sleep(30000);
  await browser.close();
}

main().catch((e) => { console.error(e); process.exit(1); });
