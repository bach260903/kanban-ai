const fs = require("fs");
const graphPath = process.argv[2];
const outPath = process.argv[3];
const graph = JSON.parse(fs.readFileSync(graphPath, "utf8"));
const issues = [];
const warnings = [];
const nodeIds = new Set();
for (const [i, node] of (graph.nodes || []).entries()) {
  if (!node.id) issues.push(`Node[${i}] missing id`);
  if (!node.type) issues.push(`Node[${i}] missing type`);
  if (!node.name) issues.push(`Node[${i}] missing name`);
  if (!node.summary) issues.push(`Node[${i}] missing summary`);
  if (!Array.isArray(node.tags) || node.tags.length === 0) issues.push(`Node[${i}] missing tags`);
  if (node.id) {
    if (nodeIds.has(node.id)) issues.push(`Duplicate node id ${node.id}`);
    nodeIds.add(node.id);
  }
}
for (const [i, edge] of (graph.edges || []).entries()) {
  if (!nodeIds.has(edge.source)) issues.push(`Edge[${i}] source missing: ${edge.source}`);
  if (!nodeIds.has(edge.target)) issues.push(`Edge[${i}] target missing: ${edge.target}`);
  if (!edge.type) issues.push(`Edge[${i}] missing type`);
}
for (const layer of graph.layers || []) {
  if (!layer.id || !layer.name || !layer.description || !Array.isArray(layer.nodeIds)) {
    issues.push(`Layer malformed: ${layer.id || layer.name || "<unknown>"}`);
  }
  for (const id of layer.nodeIds || []) if (!nodeIds.has(id)) issues.push(`Layer ${layer.id} refs missing ${id}`);
}
for (const step of graph.tour || []) {
  if (!step.order || !step.title || !step.description || !Array.isArray(step.nodeIds)) {
    issues.push(`Tour step malformed: ${step.title || step.order || "<unknown>"}`);
  }
  for (const id of step.nodeIds || []) if (!nodeIds.has(id)) issues.push(`Tour step ${step.order} refs missing ${id}`);
}
const stats = {
  totalNodes: (graph.nodes || []).length,
  totalEdges: (graph.edges || []).length,
  totalLayers: (graph.layers || []).length,
  tourSteps: (graph.tour || []).length,
  nodeTypes: (graph.nodes || []).reduce((a, n) => (a[n.type] = (a[n.type] || 0) + 1, a), {}),
  edgeTypes: (graph.edges || []).reduce((a, e) => (a[e.type] = (a[e.type] || 0) + 1, a), {}),
};
fs.writeFileSync(outPath, JSON.stringify({ issues, warnings, stats }, null, 2), "utf8");
process.exit(issues.length ? 1 : 0);
