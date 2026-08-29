import { computed, defineComponent, h, ref } from "vue";

const defaultQuery = "给我生成一份关于 Pilbara 锂矿的今日简报";

const pipeline = [
  { label: "解析计划", detail: "识别资产、矿种、时间窗" },
  { label: "新闻采集", detail: "抓取公司页、公告页、RSS" },
  { label: "PDF 抽取", detail: "定位资源量页并抽取表格" },
  { label: "价格行情", detail: "拉取公开行情时间序列" },
  { label: "质量校验", detail: "检查引用和抽取置信度" },
  { label: "生成简报", detail: "输出 Markdown 与结构化 JSON" },
];

function stageState(index, running, result, error) {
  if (error && index === 0) return "failed";
  if (result) return "done";
  return running ? (index <= 3 ? "running" : "queued") : "idle";
}

function toolStatus(report, prefix) {
  const entries = Object.entries(report?.tools ?? {}).filter(([key]) => key.startsWith(prefix));
  if (!entries.length) return { ok: false, label: "--" };
  const failed = entries.filter(([, value]) => !value.ok);
  const ms = entries.reduce((sum, [, value]) => sum + Number(value.latency_ms || 0), 0);
  return { ok: failed.length === 0, label: `${Math.round(ms)} ms` };
}

function metricCard(label, value, sub) {
  return h("div", { class: "metric" }, [
    h("span", label),
    h("strong", value),
    sub ? h("small", sub) : null,
  ]);
}

function panel(title, body, klass = "") {
  return h("section", { class: ["panel", klass] }, [h("header", [h("h2", title)]), body]);
}

function sourceBadge(source) {
  const live = String(source).startsWith("live:");
  return h("span", { class: ["badge", live ? "live" : "fallback"] }, live ? "实时" : "兜底");
}

function formatTime(value) {
  if (!value || value === "1970-01-01T00:00:00Z") return "未识别";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", {
    hour12: false,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function trendLabel(value) {
  return value === "up" ? "上涨" : value === "down" ? "下跌" : "持平";
}

function drawSparkline(points) {
  const values = points.map((point) => Number(point.price)).filter((value) => Number.isFinite(value));
  if (values.length < 2) {
    return h("div", { class: "sparkline-empty" }, "暂无趋势");
  }
  const width = 220;
  const height = 72;
  const pad = 8;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const spread = max - min || 1;
  const coords = values.map((value, index) => {
    const x = pad + (index / (values.length - 1)) * (width - pad * 2);
    const y = height - pad - ((value - min) / spread) * (height - pad * 2);
    return [x, y];
  });
  const path = coords.map(([x, y], index) => `${index === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
  const area = `${path} L ${coords.at(-1)[0].toFixed(1)} ${height - pad} L ${coords[0][0].toFixed(1)} ${height - pad} Z`;
  const positive = values.at(-1) >= values[0];
  return h("svg", { class: "sparkline", viewBox: `0 0 ${width} ${height}`, role: "img" }, [
    h("path", { class: positive ? "spark-area up" : "spark-area down", d: area }),
    h("path", { class: positive ? "spark-line up" : "spark-line down", d: path }),
    h("circle", {
      class: positive ? "spark-dot up" : "spark-dot down",
      cx: coords.at(-1)[0],
      cy: coords.at(-1)[1],
      r: 3.2,
    }),
  ]);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function markdownToHtml(markdown) {
  const lines = String(markdown || "").split("\n");
  const html = [];
  let inList = false;
  let inTable = false;

  function closeList() {
    if (inList) {
      html.push("</ul>");
      inList = false;
    }
  }

  function closeTable() {
    if (inTable) {
      html.push("</tbody></table>");
      inTable = false;
    }
  }

  for (const line of lines) {
    if (!line.trim()) {
      closeList();
      closeTable();
      continue;
    }
    if (line.startsWith("# ")) {
      closeList();
      closeTable();
      html.push(`<h1>${escapeHtml(line.slice(2))}</h1>`);
    } else if (line.startsWith("## ")) {
      closeList();
      closeTable();
      html.push(`<h2>${escapeHtml(line.slice(3))}</h2>`);
    } else if (line.startsWith("|") && !line.includes("---")) {
      closeList();
      const cells = line
        .split("|")
        .slice(1, -1)
        .map((cell) => `<td>${escapeHtml(cell.trim())}</td>`)
        .join("");
      if (!inTable) {
        html.push("<table><tbody>");
        inTable = true;
      }
      html.push(`<tr>${cells}</tr>`);
    } else if (line.startsWith("- ")) {
      closeTable();
      if (!inList) {
        html.push("<ul>");
        inList = true;
      }
      html.push(`<li>${escapeHtml(line.slice(2))}</li>`);
    } else {
      closeList();
      closeTable();
      html.push(`<p>${escapeHtml(line)}</p>`);
    }
  }
  closeList();
  closeTable();
  return html.join("");
}

export default defineComponent({
  name: "MiningDailyConsole",
  setup() {
    const query = ref(defaultQuery);
    const running = ref(false);
    const activeTab = ref("brief");
    const result = ref(null);
    const error = ref("");

    const metrics = computed(() => {
      const report = result.value?.run_report;
      const summary = result.value?.evidence_summary;
      return {
        latency: report ? `${report.total_latency_ms} ms` : "--",
        citations: report ? String(report.citation_count) : "--",
        liveSources: summary ? String(summary.live_source_count) : "--",
        warnings: report ? String(report.warning_count) : "--",
      };
    });

    const toolCards = computed(() => {
      const report = result.value?.run_report;
      return [
        ["mining-news-mcp", toolStatus(report, "news.")],
        ["mineral-pdf-mcp", toolStatus(report, "pdf.")],
        ["lme-price-mcp", toolStatus(report, "price.")],
        ["mining-risk-mcp", toolStatus(report, "risk.")],
      ];
    });
    const sourceBreakdown = computed(() => result.value?.evidence_summary?.source_breakdown ?? {});
    const crawlTrace = computed(() => result.value?.run_report?.crawl_trace ?? []);
    const mcpContract = computed(() => result.value?.run_report?.mcp_contract ?? null);
    const briefHtml = computed(() =>
      result.value?.markdown ? markdownToHtml(result.value.markdown) : ""
    );

    async function runAgent() {
      running.value = true;
      result.value = null;
      error.value = "";
      try {
        const response = await fetch("http://127.0.0.1:8765/api/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: query.value.trim() || defaultQuery }),
        });
        const payload = await response.json();
        if (!response.ok) {
          error.value = payload.error || "Run failed";
          return;
        }
        result.value = payload;
      } catch (err) {
        error.value = err instanceof Error ? err.message : String(err);
      } finally {
        running.value = false;
      }
    }

    return () =>
      h("main", { class: "app-shell" }, [
        h("section", { class: "command-bar" }, [
          h("div", { class: "brand" }, [
            h("span", { class: "mark" }, "MCP"),
            h("div", [
              h("h1", "矿权日报 Agent"),
              h("p", "实时爬虫 + PDF 资源量抽取 + 价格趋势分析"),
            ]),
          ]),
          h("div", { class: "command-input" }, [
            h("textarea", {
              value: query.value,
              rows: 2,
              onInput: (event) => {
                query.value = event.target.value;
              },
            }),
            h(
              "button",
              { type: "button", disabled: running.value, onClick: runAgent },
              running.value ? "运行中" : "生成简报"
            ),
          ]),
        ]),

        h("section", { class: "metrics" }, [
          metricCard("总耗时", metrics.value.latency, "端到端执行"),
          metricCard("引用数", metrics.value.citations, "进入简报的来源"),
          metricCard("实时来源", metrics.value.liveSources, "爬虫/接口返回"),
          metricCard("质量提示", metrics.value.warnings, "置信度与降级检查"),
        ]),

        h("section", { class: "workspace" }, [
          h("aside", { class: "left-rail" }, [
            panel(
              "运行轨迹监测",
              h("div", { class: "trace-list" }, [
                ...(crawlTrace.value.length
                  ? crawlTrace.value.map((item) =>
                      h("article", { class: "trace-row" }, [
                        h("div", { class: "trace-meta" }, [
                          sourceBadge(item.source),
                          h("span", `抓取 ${formatTime(item.fetched_at)}`),
                        ]),
                        h("strong", item.tool || "unknown-tool"),
                        h("small", { class: "trace-published" }, `发布 ${formatTime(item.published_at)}`),
                        h("a", { href: item.url, target: "_blank", title: item.url }, item.title || item.url),
                      ])
                    )
                  : [h("p", { class: "empty" }, "运行后显示每个爬取页面和接口的时间戳。")]),
              ])
            ),
            panel(
              "Agent 执行链路",
              h(
                "ol",
                { class: "pipeline" },
                pipeline.map((step, index) =>
                  h("li", { class: stageState(index, running.value, result.value, error.value) }, [
                    h("span", { class: "dot" }),
                    h("div", [h("strong", step.label), h("small", step.detail)]),
                  ])
                )
              )
            ),
            panel(
              "MCP 工具耗时",
              h(
                "div",
                { class: "tool-list" },
                toolCards.value.map(([name, status]) =>
                  h("div", { class: "tool-row" }, [
                    h("span", name),
                    h("strong", { class: status.ok ? "ok" : "" }, status.label),
                  ])
                )
              )
            ),
            panel(
              "交付核验",
              h("div", { class: "contract-box" }, [
                h("div", [
                  h("span", "Agent client"),
                  h("strong", mcpContract.value?.agent_client ?? "agent.daily_brief_agent"),
                ]),
                ...(mcpContract.value?.servers ?? [
                  { name: "mining-news-mcp", tools: ["search", "fetch_article"] },
                  { name: "mineral-pdf-mcp", tools: ["extract_resources"] },
                  { name: "lme-price-mcp", tools: ["get_price", "get_trend"] },
                  { name: "mining-risk-mcp", tools: ["assess_risks"] },
                ]).map((server) =>
                  h("div", [
                    h("span", server.name),
                    h("small", (server.tools ?? []).join(" · ")),
                  ])
                ),
              ])
            ),
            panel(
              "数据覆盖",
              h("div", { class: "coverage-grid" }, [
                h("div", [h("span", "新闻"), h("strong", String(sourceBreakdown.value.news ?? 0))]),
                h("div", [h("span", "PDF"), h("strong", String(sourceBreakdown.value.pdf ?? 0))]),
                h("div", [h("span", "行情"), h("strong", String(sourceBreakdown.value.price ?? 0))]),
                h("div", [h("span", "兜底"), h("strong", String(sourceBreakdown.value.fallback ?? 0))]),
              ])
            ),
          ]),

          h("section", { class: "evidence-stack" }, [
            panel(
              "证据流",
              h("div", { class: "news-list" }, [
                ...(result.value?.news?.slice(0, 5) ?? []).map((item) =>
                  h("article", { class: "news-card" }, [
                    h("div", { class: "news-head" }, [
                      sourceBadge(item.source),
                      h("span", `相关性 ${Number(item.score).toFixed(2)}`),
                    ]),
                    h("h3", item.title),
                    h("p", item.snippet),
                    h("a", { href: item.url, target: "_blank" }, item.url),
                  ])
                ),
                !result.value ? h("p", { class: "empty" }, "点击“生成简报”加载实时证据。") : null,
              ])
            ),
            panel(
              "资源量抽取",
              h("div", { class: "resource-box" }, [
                h("div", { class: "status-line" }, [
                  h("span", "PDF 抽取状态"),
                  h("strong", result.value?.resources?.status ?? "--"),
                ]),
                h("table", [
                  h("thead", [
                    h("tr", [
                        h("th", "类别"),
                        h("th", "矿石量"),
                        h("th", "品位"),
                        h("th", "置信度"),
                    ]),
                  ]),
                  h(
                    "tbody",
                    (result.value?.resources?.resources ?? []).map((row) =>
                      h("tr", [
                        h("td", row.category),
                        h("td", `${row.ore_tonnage_mt} Mt`),
                        h("td", `${row.grade} ${row.grade_unit}`),
                        h("td", { class: row.confidence < 0.8 ? "warn" : "ok" }, Number(row.confidence).toFixed(2)),
                      ])
                    )
                  ),
                ]),
              ])
            ),
            panel(
              "价格趋势",
              h(
                "div",
                { class: "price-grid" },
                (result.value?.prices ?? []).map((trend) =>
                  h("article", { class: "price-card" }, [
                    h("div", { class: "price-head" }, [
                      h("span", trend.commodity),
                      h("small", `${trend.currency}/${trend.unit}`),
                    ]),
                    h("strong", `${trend.change_pct}%`),
                    h("small", `${trendLabel(trend.trend)} · 波动率 ${trend.volatility}`),
                    drawSparkline(trend.points ?? []),
                  ])
                )
              )
            ),
          ]),

          h("section", { class: "brief-column" }, [
            h("div", { class: "tabs" }, [
              h(
                "button",
                { class: activeTab.value === "brief" ? "active" : "", onClick: () => (activeTab.value = "brief") },
                "简报"
              ),
              h(
                "button",
                { class: activeTab.value === "json" ? "active" : "", onClick: () => (activeTab.value = "json") },
                "JSON"
              ),
            ]),
            error.value ? h("div", { class: "error" }, error.value) : null,
            activeTab.value === "brief"
              ? h("div", {
                  class: "brief-rendered",
                  innerHTML: briefHtml.value || "<p>点击“生成简报”后查看矿权日报。</p>",
                })
              : h("pre", { class: "brief-output" }, result.value ? JSON.stringify(result.value, null, 2) : "{}"),
          ]),
        ]),
      ]);
  },
});
