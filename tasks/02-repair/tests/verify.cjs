const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const http = require('node:http');
const path = require('node:path');
const { chromium } = require('playwright');

const appDir = path.resolve(process.argv[2] || '/app');
const reportDir = path.resolve(process.argv[3] || '/logs/verifier');
async function createTicket(page, title, priority = 'Normal') {
  await page.getByLabel('Ticket title', { exact: true }).fill(title);
  await page.getByLabel('Priority', { exact: true }).selectOption({ label: priority });
  await page.getByRole('button', { name: 'Create ticket', exact: true }).click();
}
function ticket(page, title) { return page.getByTestId('ticket').filter({ hasText: title }); }
const cases = [
  ['heading', 'Required heading', async page => {
    assert.equal(await page.getByRole('heading', { level: 1, name: 'Raccoon Help Desk', exact: true }).count(), 1);
  }],
  ['create', 'Create two tickets with distinct priorities', async page => {
    await createTicket(page, 'The printer ate my lunch', 'Urgent');
    await createTicket(page, 'A raccoon stole the mouse', 'Low');
    assert.equal(await page.getByTestId('ticket').count(), 2);
    assert.match(await ticket(page, 'The printer ate my lunch').innerText(), /Urgent/);
    assert.match(await ticket(page, 'A raccoon stole the mouse').innerText(), /Low/);
    assert.match(await ticket(page, 'The printer ate my lunch').innerText(), /Open/);
  }],
  ['validation', 'Reject empty and whitespace titles', async page => {
    await page.getByRole('button', { name: 'Create ticket', exact: true }).click();
    assert.equal(await page.getByTestId('ticket').count(), 0);
    assert.ok(await page.getByText('Enter a ticket title.', { exact: true }).isVisible());
    await page.getByLabel('Ticket title', { exact: true }).fill('   ');
    await page.getByRole('button', { name: 'Create ticket', exact: true }).click();
    assert.equal(await page.getByTestId('ticket').count(), 0);
    assert.ok(await page.getByText('Enter a ticket title.', { exact: true }).isVisible());
  }],
  ['resolve', 'Resolve one ticket without changing another', async page => {
    await createTicket(page, 'Trash can authentication failed');
    await createTicket(page, 'Keyboard covered in crumbs');
    await ticket(page, 'Trash can authentication failed').getByRole('button', { name: 'Resolve', exact: true }).click();
    assert.match(await ticket(page, 'Trash can authentication failed').innerText(), /Resolved/);
    assert.match(await ticket(page, 'Keyboard covered in crumbs').innerText(), /Open/);
  }],
  ['filter', 'Filter All, Open, Resolved, and empty results', async page => {
    const filter = page.getByLabel('Status filter', { exact: true });
    await filter.selectOption({ label: 'Resolved' });
    assert.equal(await page.getByTestId('ticket').filter({ visible: true }).count(), 0);
    await filter.selectOption({ label: 'All' });
    await createTicket(page, 'VPN refuses tiny paws', 'Urgent');
    await createTicket(page, 'Need a larger snack budget', 'Low');
    await ticket(page, 'VPN refuses tiny paws').getByRole('button', { name: 'Resolve', exact: true }).click();
    await filter.selectOption({ label: 'Open' });
    assert.equal(await page.getByTestId('ticket').filter({ visible: true }).count(), 1);
    assert.ok(await ticket(page, 'Need a larger snack budget').isVisible());
    await filter.selectOption({ label: 'Resolved' });
    assert.equal(await page.getByTestId('ticket').filter({ visible: true }).count(), 1);
    assert.ok(await ticket(page, 'VPN refuses tiny paws').isVisible());
    await filter.selectOption({ label: 'All' });
    assert.equal(await page.getByTestId('ticket').filter({ visible: true }).count(), 2);
  }],
  ['persistence', 'Persist titles, priorities, and statuses after reload', async page => {
    await createTicket(page, 'Trash dashboard is offline', 'Urgent');
    await createTicket(page, 'Please reboot the moon', 'Low');
    await ticket(page, 'Trash dashboard is offline').getByRole('button', { name: 'Resolve', exact: true }).click();
    await page.reload();
    await page.getByLabel('Status filter', { exact: true }).selectOption({ label: 'All' });
    assert.equal(await page.getByTestId('ticket').count(), 2);
    const resolved = await ticket(page, 'Trash dashboard is offline').innerText();
    const open = await ticket(page, 'Please reboot the moon').innerText();
    assert.match(resolved, /Urgent/); assert.match(resolved, /Resolved/);
    assert.match(open, /Low/); assert.match(open, /Open/);
  }],
  ['plain_text', 'Render HTML-like titles as plain text', async page => {
    const title = '<img src=x onerror="window.__ticketInjected=1">';
    await createTicket(page, title);
    assert.ok((await page.getByTestId('ticket').innerText()).includes(title));
    assert.equal(await page.getByTestId('ticket').locator('img').count(), 0);
    assert.equal(await page.evaluate(() => window.__ticketInjected), undefined);
    await page.reload();
    assert.ok((await page.getByTestId('ticket').innerText()).includes(title));
    assert.equal(await page.evaluate(() => window.__ticketInjected), undefined);
  }],
  ['mobile', 'Use mobile layout without horizontal overflow', async page => {
    await page.setViewportSize({ width: 390, height: 844 });
    await createTicket(page, 'RACCOON'.repeat(30), 'Urgent');
    assert.ok(await page.getByRole('button', { name: 'Create ticket', exact: true }).isVisible());
    assert.ok(await page.getByLabel('Status filter', { exact: true }).isVisible());
    const dimensions = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, width: window.innerWidth }));
    assert.ok(dimensions.scroll <= dimensions.width + 1, JSON.stringify(dimensions));
  }],
];

async function main() {
  await fs.mkdir(reportDir, { recursive: true });
  const options = { headless: true, args: ['--disable-dev-shm-usage'] };
  if (process.env.PLAYWRIGHT_EXECUTABLE_PATH) options.executablePath = process.env.PLAYWRIGHT_EXECUTABLE_PATH;
  // Browser startup failure is an infrastructure error, not a model score.
  const browser = await chromium.launch(options);
  const server = http.createServer(async (req, res) => {
    if (!['/', '/index.html'].includes(req.url.split('?')[0])) { res.writeHead(404); res.end('Not found'); return; }
    try {
      const html = await fs.readFile(path.join(appDir, 'index.html'));
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' }); res.end(html);
    } catch {
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' }); res.end('<!doctype html><html><body>Missing app submission</body></html>');
    }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const baseUrl = 'http://127.0.0.1:' + server.address().port;
  const results = [];
  try {
    for (const [id, name, run] of cases) {
      const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const page = await context.newPage();
      page.setDefaultTimeout(2500); page.setDefaultNavigationTimeout(8000);
      await context.route('**/*', route => {
        if (new URL(route.request().url()).origin === baseUrl) return route.continue();
        return route.abort();
      });
      const started = Date.now(); let passed = false; let error = null;
      try { await page.goto(baseUrl, { waitUntil: 'load' }); await run(page); passed = true; }
      catch (err) { error = String(err.message).slice(0, 2500); }
      await page.screenshot({ path: path.join(reportDir, id + '.png'), fullPage: true, timeout: 5000 }).catch(() => {});
      results.push({ id, name, passed, error, duration_ms: Date.now() - started });
      console.log((passed ? 'PASS ' : 'FAIL ') + name);
      await context.close();
    }
    const passed = results.filter(result => result.passed).length;
    const score = passed / cases.length;
    await fs.writeFile(path.join(reportDir, 'report.json'), JSON.stringify({ type: 'independent-browser-verification', passed, total: cases.length, score, results }, null, 2));
    await fs.writeFile(path.join(reportDir, 'reward.txt'), String(score));
    console.log('Functionality: ' + passed + '/' + cases.length + ' (' + score + ')');
  } finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
}
main().catch(async err => {
  console.error(err); await fs.mkdir(reportDir, { recursive: true });
  await fs.writeFile(path.join(reportDir, 'infrastructure-error.txt'), String(err.stack || err)); process.exitCode = 1;
});
