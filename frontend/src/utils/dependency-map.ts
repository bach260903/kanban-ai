import type { DependencyGraphResponse } from '../services/dependency-api'

/** Build taskId → prerequisite titles that are not done (for blocked badge tooltips). */
export function buildBlockedByTitlesMap(
  graph: DependencyGraphResponse,
): Map<string, string[]> {
  const nodeById = new Map(graph.nodes.map((n) => [n.id, n]))
  const map = new Map<string, string[]>()

  for (const edge of graph.edges) {
    const prereq = nodeById.get(edge.to)
    if (!prereq || prereq.status === 'done') continue
    const list = map.get(edge.from) ?? []
    list.push(prereq.title)
    map.set(edge.from, list)
  }

  return map
}

/** Count direct dependencies per task (edge.from depends on edge.to). */
export function buildDependsOnCountMap(graph: DependencyGraphResponse): Map<string, number> {
  const map = new Map<string, number>()
  for (const edge of graph.edges) {
    map.set(edge.from, (map.get(edge.from) ?? 0) + 1)
  }
  return map
}
