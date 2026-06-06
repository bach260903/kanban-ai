const fs = require("fs");
const path = require("path");

const root = process.argv[2];
const commit = process.argv[3] || "";
const inter = path.join(root, ".understand-anything", "intermediate");

const readJson = (p) => JSON.parse(fs.readFileSync(p, "utf8"));
const writeJson = (p, data) => fs.writeFileSync(p, JSON.stringify(data, null, 2), "utf8");
const posix = (p) => p.replace(/\\/g, "/");
const slug = (s) => String(s).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "item";

function nodeTypeFor(file) {
  if (file.fileCategory === "config") return "config";
  if (file.fileCategory === "docs") return "document";
  if (file.fileCategory === "infra") return "service";
  if (file.fileCategory === "data") return "document";
  return "file";
}

function prefixForType(type) {
  return type === "file" ? "file" : type;
}

function complexity(lines) {
  if (lines > 300) return "complex";
  if (lines > 100) return "moderate";
  return "simple";
}

function layerName(relPath) {
  const parts = relPath.split("/");
  if (parts[0] === "backend") return "Backend";
  if (parts[0] === "frontend") return "Frontend";
  if (parts[0] === "agents") return "AI Agents";
  if (parts[0] === "docs" || parts[0] === "specs") return "Documentation and Specs";
  if (parts[0] === "design" || parts[0] === "design-system") return "Design";
  if (parts[0] === "evaluation" || parts[0] === "audit") return "Evaluation and Audit";
  if (parts[0].startsWith(".")) return "Tooling";
  return "Project Root";
}

function tagsFor(file, result) {
  const tags = new Set([file.fileCategory || "file", file.language || "unknown"]);
  const top = file.path.split("/")[0];
  if (top) tags.add(top.replace(/^\./, ""));
  if (result?.metrics?.functionCount) tags.add("functions");
  if (result?.metrics?.classCount) tags.add("classes");
  if (result?.endpoints?.length) tags.add("api");
  return [...tags].filter(Boolean);
}

const scan = readJson(path.join(inter, "scan-result.json"));
const importData = readJson(path.join(inter, "import-map.json")).importMap || {};
const extractFiles = fs.readdirSync(inter)
  .filter((n) => /^extract-\d+\.json$/.test(n))
  .sort((a, b) => Number(a.match(/\d+/)[0]) - Number(b.match(/\d+/)[0]));

const resultsByPath = new Map();
for (const name of extractFiles) {
  const data = readJson(path.join(inter, name));
  for (const result of data.results || []) resultsByPath.set(posix(result.path), result);
}

const nodes = [];
const edges = [];
const layerMap = new Map();
const fileIdByPath = new Map();
const usedNodeIds = new Set();

function uniqueNodeId(base, line) {
  let candidate = base;
  if (!usedNodeIds.has(candidate)) {
    usedNodeIds.add(candidate);
    return candidate;
  }
  candidate = `${base}:${line || "duplicate"}`;
  let i = 2;
  while (usedNodeIds.has(candidate)) candidate = `${base}:${line || "duplicate"}-${i++}`;
  usedNodeIds.add(candidate);
  return candidate;
}

for (const file of scan.files || []) {
  const rel = posix(file.path);
  const result = resultsByPath.get(rel) || {};
  const type = nodeTypeFor(file);
  const id = `${prefixForType(type)}:${rel}`;
  fileIdByPath.set(rel, id);
  usedNodeIds.add(id);
  nodes.push({
    id,
    type,
    name: path.posix.basename(rel),
    filePath: rel,
    summary: `${file.fileCategory || "Project"} file in ${rel}.`,
    tags: tagsFor(file, result),
    complexity: complexity(file.sizeLines || result.totalLines || 0),
    metrics: result.metrics || {},
  });

  const lname = layerName(rel);
  if (!layerMap.has(lname)) {
    layerMap.set(lname, {
      id: `layer:${slug(lname)}`,
      name: lname,
      description: `Files and artifacts under the ${lname} area.`,
      nodeIds: [],
    });
  }
  layerMap.get(lname).nodeIds.push(id);

  for (const fn of result.functions || []) {
    const fid = uniqueNodeId(`function:${rel}:${slug(fn.name)}`, fn.startLine);
    nodes.push({
      id: fid,
      type: "function",
      name: fn.name,
      filePath: rel,
      summary: `Function ${fn.name} defined in ${rel}.`,
      tags: ["function", file.language || "unknown"],
      complexity: complexity((fn.endLine || 0) - (fn.startLine || 0)),
      startLine: fn.startLine,
      endLine: fn.endLine,
    });
    edges.push({ source: id, target: fid, type: "contains", weight: 1, direction: "forward" });
  }

  for (const cls of result.classes || []) {
    const cid = uniqueNodeId(`class:${rel}:${slug(cls.name)}`, cls.startLine);
    nodes.push({
      id: cid,
      type: "class",
      name: cls.name,
      filePath: rel,
      summary: `Class or type ${cls.name} defined in ${rel}.`,
      tags: ["class", file.language || "unknown"],
      complexity: complexity((cls.endLine || 0) - (cls.startLine || 0)),
      startLine: cls.startLine,
      endLine: cls.endLine,
    });
    edges.push({ source: id, target: cid, type: "contains", weight: 1, direction: "forward" });
  }

  for (const ep of result.endpoints || []) {
    const eid = uniqueNodeId(`endpoint:${rel}:${slug(`${ep.method || ""}-${ep.path || ep.name}`)}`, ep.startLine);
    nodes.push({
      id: eid,
      type: "endpoint",
      name: `${ep.method || ""} ${ep.path || ep.name}`.trim(),
      filePath: rel,
      summary: `API endpoint declared in ${rel}.`,
      tags: ["endpoint", "api"],
      complexity: "simple",
      startLine: ep.startLine,
      endLine: ep.endLine,
    });
    edges.push({ source: id, target: eid, type: "contains", weight: 1, direction: "forward" });
  }
}

for (const [sourcePath, targets] of Object.entries(importData)) {
  const source = fileIdByPath.get(posix(sourcePath));
  if (!source || !Array.isArray(targets)) continue;
  for (const targetPath of targets) {
    const target = fileIdByPath.get(posix(targetPath));
    if (target && target !== source) {
      edges.push({ source, target, type: "imports", weight: 0.7, direction: "forward" });
    }
  }
}

const edgeSeen = new Set();
const dedupedEdges = [];
for (const e of edges) {
  const key = `${e.source}\0${e.target}\0${e.type}\0${e.direction || "forward"}`;
  if (!edgeSeen.has(key)) {
    edgeSeen.add(key);
    dedupedEdges.push(e);
  }
}

const layers = [...layerMap.values()].filter((l) => l.nodeIds.length);
const tour = [
  {
    order: 1,
    title: "Project Overview",
    description: "Start with the root documentation and manifests to understand the repository purpose and package layout.",
    nodeIds: ["document:README.md", "config:package.json"].filter((id) => nodes.some((n) => n.id === id)),
  },
  {
    order: 2,
    title: "Backend",
    description: "Review backend services, API code, and server-side configuration.",
    nodeIds: layers.find((l) => l.name === "Backend")?.nodeIds.slice(0, 8) || [],
  },
  {
    order: 3,
    title: "Frontend",
    description: "Review frontend application files and UI implementation.",
    nodeIds: layers.find((l) => l.name === "Frontend")?.nodeIds.slice(0, 8) || [],
  },
  {
    order: 4,
    title: "AI Agent Layer",
    description: "Inspect agent orchestration and AI-specific project modules.",
    nodeIds: layers.find((l) => l.name === "AI Agents")?.nodeIds.slice(0, 8) || [],
  },
].filter((s) => s.nodeIds.length);

const graph = {
  version: "1.0.0",
  project: {
    name: scan.projectName || "kanban-ai",
    languages: Object.keys(scan.stats?.byLanguage || {}).filter((l) => l !== "unknown"),
    frameworks: [],
    description: scan.description || "Kanban AI project",
    analyzedAt: new Date().toISOString(),
    gitCommitHash: commit,
  },
  nodes,
  edges: dedupedEdges,
  layers,
  tour,
};

writeJson(path.join(inter, "assembled-graph.json"), graph);
writeJson(path.join(root, ".understand-anything", "knowledge-graph.json"), graph);
writeJson(path.join(inter, "summary.json"), {
  files: scan.totalFiles || scan.files?.length || 0,
  filteredByIgnore: scan.filteredByIgnore || 0,
  categories: scan.stats?.byCategory || {},
  languages: scan.stats?.byLanguage || {},
  nodes: nodes.reduce((acc, n) => (acc[n.type] = (acc[n.type] || 0) + 1, acc), {}),
  edges: dedupedEdges.reduce((acc, e) => (acc[e.type] = (acc[e.type] || 0) + 1, acc), {}),
  layers: layers.map((l) => l.name),
  tourSteps: tour.length,
});
