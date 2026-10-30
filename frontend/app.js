"use strict";
const $ = (id) => document.getElementById(id);
const labels = { prediction: "Prediction", explanation: "SHAP explanation", literature: "Literature" };
let catalogReady = false;

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

async function loadCatalog() {
  $("submit").disabled = true;
  $("retry-catalog").hidden = true;
  try {
    const response = await fetch("/catalog", { signal: AbortSignal.timeout(15000) });
    if (!response.ok) throw new Error("Catalog unavailable");
    const data = await response.json();
    if (!data.cell_line_ids.length || !data.drug_names.length) throw new Error("Catalog empty");
    for (const [id, values, preferred] of [["cell-line", data.cell_line_ids, "SIDM00001"], ["drug", data.drug_names, "Cisplatin"]]) {
      $(id).replaceChildren(...values.map((value) => new Option(value, value)));
      if (values.includes(preferred)) $(id).value = preferred;
    }
    catalogReady = true;
    $("submit").disabled = false;
    $("catalog-status").textContent = "Supported identifiers loaded from the prediction model.";
  } catch {
    catalogReady = false;
    $("catalog-status").textContent = "Could not load supported identifiers. Check that the prediction service is running.";
    $("retry-catalog").hidden = false;
  }
}

function render(result) {
  $("empty").hidden = true;
  $("output").hidden = false;
  $("prediction-value").textContent = Number(result.prediction.prediction).toFixed(3);
  $("prediction-context").textContent = `${result.prediction.cell_line_id} · ${result.prediction.drug_name} · ${result.prediction.model_version}`;
  $("answer").textContent = result.answer;
  const partial = result.explanation_status !== "completed" || result.citations.length === 0;
  $("result-state").textContent = partial ? "Partial evidence" : "Evidence gathered";
  $("cache-status").textContent = result.explanation_cache_hit ? "Cache hit" : result.explanation_status;
  $("features").replaceChildren();
  const max = Math.max(...result.top_features.map((f) => Math.abs(f.contribution)), 0.00001);
  for (const feature of result.top_features) {
    const row = element("div", undefined, "feature");
    const track = element("div", undefined, "track");
    const bar = element("div", undefined, `bar ${feature.contribution >= 0 ? "positive" : "negative"}`);
    bar.style.width = `${Math.abs(feature.contribution) / max * 48}%`;
    track.append(bar);
    row.append(element("span", feature.name), track, element("span", `${feature.contribution >= 0 ? "+" : ""}${feature.contribution.toFixed(3)}`, "amount"));
    $("features").append(row);
  }
  if (!result.top_features.length) $("features").append(element("p", `Explanation ${result.explanation_status}. Prediction and available literature remain above.`, "hint"));
  $("citations").replaceChildren();
  $("citation-count").textContent = `${result.citations.length} passages`;
  for (const citation of result.citations) {
    const card = element("article", undefined, "panel citation");
    const heading = element("h3");
    const link = element("a", citation.title);
    // Rebuild the URL from a validated numeric PMID; never render source HTML.
    if (/^\d+$/.test(citation.pmid)) link.href = `https://pubmed.ncbi.nlm.nih.gov/${citation.pmid}/`;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    heading.append(link);
    card.append(element("div", `PUBMED · PMID ${citation.pmid}${citation.year ? " · " + citation.year : ""}`, "source"), heading, element("p", citation.snippet));
    $("citations").append(card);
  }
  if (!result.citations.length) $("citations").append(element("p", "No literature passages were available for this request.", "hint"));
  $("limitations").replaceChildren(...result.limitations.map((value) => element("li", value)));
  $("trace-id").textContent = result.trace_id;
  $("evidence").textContent = JSON.stringify(result, null, 2);
}

async function consume(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let completed = false;
  function event(line) {
    if (!line.trim()) return;
    const item = JSON.parse(line);
    if (item.event === "error") throw new Error(item.message);
    if (item.event === "progress" && labels[item.stage]) $("progress-" + item.stage).textContent = `${labels[item.stage]} · ${item.status}`;
    if (item.event === "result") { render(item.data); completed = true; }
  }
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      let end;
      while ((end = buffer.indexOf("\n")) >= 0) { event(buffer.slice(0, end)); buffer = buffer.slice(end + 1); }
      if (done) break;
    }
    event(buffer);
    if (!completed) throw new Error("The connection ended before a result arrived. Please retry.");
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}

$("research-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!catalogReady || !$("question").value.trim()) return;
  $("submit").disabled = true;
  $("submit").textContent = "Gathering evidence…";
  $("error").hidden = true;
  $("output").hidden = true;
  $("empty").hidden = true;
  $("progress").hidden = false;
  $("results").setAttribute("aria-busy", "true");
  for (const stage of Object.keys(labels)) $("progress-" + stage).textContent = `${labels[stage]} · waiting`;
  try {
    const response = await fetch("/research/stream", {
      method: "POST", headers: { "Content-Type": "application/json" }, signal: AbortSignal.timeout(120000),
      body: JSON.stringify({ cell_line_id: $("cell-line").value, drug_name: $("drug").value, question: $("question").value.trim() })
    });
    if (!response.ok) throw new Error(`Request failed (${response.status}). Check your inputs and try again.`);
    await consume(response);
  } catch (error) {
    $("error").textContent = error.name === "TimeoutError" ? "The request timed out. Check service health and retry." : error.message;
    $("error").hidden = false;
  } finally {
    $("submit").disabled = false;
    $("submit").textContent = "Gather evidence ↗";
    $("results").setAttribute("aria-busy", "false");
  }
});
$("retry-catalog").addEventListener("click", loadCatalog);
loadCatalog();
