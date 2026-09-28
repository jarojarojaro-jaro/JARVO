#!/usr/bin/env node
/**
 * Pełny audyt dostępności axe-core (WCAG 2.2 A/AA) w prawdziwej przeglądarce.
 *
 *   node a11y.cjs <url> <out.json>
 *
 * Wynik: JSON z naruszeniami pogrupowanymi po wadze (critical/serious/moderate/minor).
 */
const fs = require('fs');
const { chromium } = require('playwright-core');

function browserPath() {
  if (process.env.CHROME_PATH && fs.existsSync(process.env.CHROME_PATH)) return process.env.CHROME_PATH;
  const f = '/etc/hermes/agent-browser-executable-path';
  return fs.existsSync(f) ? fs.readFileSync(f, 'utf8').trim() : undefined;
}

(async () => {
  const [url, out] = process.argv.slice(2);
  if (!url || !out) { console.error('Użycie: node a11y.cjs <url> <out.json>'); process.exit(2); }
  const axeSource = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8');
  const browser = await chromium.launch({ executablePath: browserPath(), args: ['--no-sandbox'] });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
    await page.addScriptTag({ content: axeSource });
    const results = await page.evaluate(async () => window.axe.run(document, {
      runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'] },
    }));
    const byImpact = {};
    for (const v of results.violations) {
      (byImpact[v.impact || 'minor'] ||= []).push({
        id: v.id, help: v.help, helpUrl: v.helpUrl, nodes: v.nodes.length,
        examples: v.nodes.slice(0, 3).map((n) => n.target.join(' ')),
      });
    }
    const summary = {
      url, violations: results.violations.length, passes: results.passes.length, incomplete: results.incomplete.length,
      by_impact: Object.fromEntries(Object.entries(byImpact).map(([k, v]) => [k, v.length])), details: byImpact,
    };
    fs.writeFileSync(out, JSON.stringify(summary, null, 1));
    console.log(JSON.stringify({ violations: summary.violations, by_impact: summary.by_impact }, null, 1));
  } finally {
    await browser.close();
  }
})().catch((e) => { console.error(e.message); process.exit(1); });
