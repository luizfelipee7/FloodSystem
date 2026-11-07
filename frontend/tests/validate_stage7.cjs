// Isolated UI smoke check. The Python stage-7 runner supplies a test API and URL.
const assert = require("node:assert/strict");
const { chromium } = require(process.env.PLAYWRIGHT_PACKAGE);

async function main() {
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.CHROME_PATH,
    args: ["--no-sandbox"],
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const site = process.env.FLOODSYSTEM_FRONTEND_TEST_URL;
  try {
    await page.goto(site, { waitUntil: "domcontentloaded" });
    if (process.env.FLOODSYSTEM_FRONTEND_TEST_MODE === "offline") {
      await page.getByRole("heading", { name: "Não conseguimos buscar as leituras." }).waitFor();
      assert.match(await page.locator(".error-state").innerText(), /API retornou um erro|Não foi possível conectar/);
      console.log("OK: frontend mostra erro quando a API não responde");
      return;
    }
    await page.getByText("Este período ainda não tem registros.").waitFor();
    console.log("OK: Tempo real não apresenta cenários históricos como medições atuais");
    await page.getByRole("button", { name: "Histórico" }).click();
    await page.getByRole("combobox", { name: "Tipo de consulta histórica" }).selectOption("rain");
    await page.getByRole("button", { name: "Aplicar filtros" }).click();
    await page.getByText("Ambiente de simulação").waitFor();
    assert.match(await page.locator(".context-banner").innerText(), /DADOS SINTÉTICOS/);
    const cards = page.locator(".metric-card");
    assert.match(await cards.nth(0).innerText(), /10,0\s*cm/);
    assert.match(await cards.nth(1).innerText(), /2,0\s*mm/);
    assert.match(await cards.nth(2).innerText(), /0,0\s*cm\/min/);
    assert.match(await page.locator(".rain-total").innerText(), /2,0\s*mm/);
    assert.match(await page.locator(".rain-count").innerText(), /10/);
    assert.equal(await page.locator(".records tbody tr").count(), 6);
    await page.getByRole("tab", { name: /Basculadas/ }).click();
    assert.equal(await page.locator(".records tbody tr").count(), 7); // 10 eventos, 7 por página
    assert.match(await page.locator(".records .table-footer").innerText(), /1–7 de 10 carregados/);
    console.log("OK: Histórico mostra origem sintética, chuva diária/recorte, 6 leituras e 10 basculadas paginadas");

    await page.getByRole("combobox", { name: "Tipo de consulta histórica" }).selectOption("dry");
    await page.getByRole("button", { name: "Aplicar filtros" }).click();
    await page.getByText("Este período ainda não tem registros.").waitFor();
    assert.match(await page.locator(".metric-card").first().innerText(), /—/);
    console.log("OK: frontend mostra período vazio sem preencher métricas");

    await page.getByRole("button", { name: "Dispositivo" }).click();
    await page.getByLabel("Identificador do dispositivo").fill("dispositivo-inexistente-stage7");
    await page.getByRole("button", { name: "Aplicar filtros" }).click();
    await page.getByRole("heading", { name: "Não conseguimos buscar as leituras." }).waitFor();
    assert.match(await page.locator(".error-state").innerText(), /Dispositivo ou rota não encontrado/);
    console.log("OK: frontend mostra erro para dispositivo desconhecido");
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
