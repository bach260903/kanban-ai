import { create } from 'zustand'

import type { Project, ProjectListItem } from '../types'

export type ProjectStore = {
  projects: ProjectListItem[]
  currentProject: Project | null
  setProjects: (projects: ProjectListItem[]) => void
  setCurrentProject: (project: Project | null) => void
}

export const useProjectStore = create<ProjectStore>((set) => ({
  projects: [],
  currentProject: null,
  setProjects: (projects) => set({ projects }),
  setCurrentProject: (currentProject) => set({ currentProject }),
}))
