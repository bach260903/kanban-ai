import { useCallback, useState } from 'react'

import type { InlineCommentItem, InlineCommentListRow } from '../services/task-api'

function normPath(p: string): string {
  return p.trim().replace(/\\/g, '/').replace(/^\.\/+/, '')
}

function pathsMatch(a: string, b: string): boolean {
  return normPath(a) === normPath(b)
}

export type InlineCommentPayloadItem = {
  file_path: string
  line_number: number
  comment_text: string
}

/**
 * Inline review comments for a task diff (US16 / T110).
 * Keeps a normalized list, supports reject body via ``getCommentPayload``.
 */
export function useInlineComments() {
  const [comments, setComments] = useState<InlineCommentListRow[]>([])

  const replaceFromApi = useCallback((items: InlineCommentItem[]) => {
    setComments(
      items.map((i) => ({
        id: i.id,
        file_path: i.file_path,
        line_number: i.line_number,
        comment_text: i.comment_text,
      })),
    )
  }, [])

  const addComment = useCallback(
    (input: Omit<InlineCommentListRow, 'id'> & { id?: string }): string => {
      const id = input.id ?? crypto.randomUUID()
      const row: InlineCommentListRow = {
        id,
        file_path: input.file_path,
        line_number: input.line_number,
        comment_text: input.comment_text,
      }
      setComments((prev) => [...prev, row])
      return id
    },
    [],
  )

  const removeComment = useCallback((id: string) => {
    setComments((prev) => prev.filter((c) => c.id !== id))
  }, [])

  const getCommentsForLine = useCallback(
    (file_path: string, line_number: number): InlineCommentListRow[] => {
      return comments.filter((c) => pathsMatch(c.file_path, file_path) && c.line_number === line_number)
    },
    [comments],
  )

  const getCommentPayload = useCallback((): InlineCommentPayloadItem[] => {
    return comments.map(({ file_path, line_number, comment_text }) => ({
      file_path,
      line_number,
      comment_text,
    }))
  }, [comments])

  return {
    comments,
    replaceFromApi,
    addComment,
    removeComment,
    getCommentsForLine,
    getCommentPayload,
  }
}

export type UseInlineCommentsReturn = ReturnType<typeof useInlineComments>
