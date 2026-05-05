import { expect, test } from "@playwright/test";

test("tigrcorn WebTransport peer probe", async ({ page, baseURL }, testInfo) => {
  const wtUrl = process.env.TIGRCORN_WT_URL ?? `${baseURL}/__tigrcorn/probe/wt`;
  const reportUrl = process.env.TIGRCORN_WT_REPORT_URL ?? `${baseURL}/__tigrcorn/probe/wt/report`;

  await page.goto("about:blank");

  const report = await page.evaluate(
    async ({ peerId, wtUrl, reportUrl }) => {
      const mod = await import("/src/index.ts");
      return mod.runTigrcornWTPeerProbe({ peerId, wtUrl, reportUrl, timeoutMs: 5000 });
    },
    { peerId: testInfo.project.name, wtUrl, reportUrl },
  );

  expect(report.ok, JSON.stringify(report, null, 2)).toBe(true);
});
