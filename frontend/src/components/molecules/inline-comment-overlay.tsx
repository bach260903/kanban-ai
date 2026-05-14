import { isAxiosError } from 'axios'
import * as monaco from 'monaco-editor'
import type { editor } from 'monaco-editor'
import { useEffect, useRef } from 'react'

import { createTaskComment } from '../../services/task-api'
import type { InlineCommentItem } from '../../services/task-api'

import './inline-comment-overlay.css'

function pathsMatch(a: string, b: string): boolean {
  const norm = (s: string) => s.trim().replace(/\\/g, '/').replace(/^\.\/+/, '')
  return norm(a) === norm(b)
}

export type InlineCommentOverlayProps = {
  modifiedEditor: editor.IStandaloneCodeEditor | null
  taskId: string
  /** Path used for ``POST`` body ``file_path`` (must match diff ``files_affected``). */
  apiFilePath: string
  comments: InlineCommentItem[]
  /** Open composer after modified-side line click (glyph / line target). */
  activeLine: number | null
  onCloseComposer: () => void
  onSaved: () => void | Promise<void>
}

/**
 * Inline PO comments on the modified diff pane (US16 / T109).
 * Saved rows use glyph-margin decorations + hover; composer uses a ViewZone (Monaco overlay)
 * below the clicked line — same UX goal as a margin widget without private Monaco APIs.
 */
export function InlineCommentOverlay({
  modifiedEditor,
  taskId,
  apiFilePath,
  comments,
  activeLine,
  onCloseComposer,
  onSaved,
}: InlineCommentOverlayProps) {
  const decorationIdsRef = useRef<string[]>([])
  const viewZoneIdRef = useRef<string | null>(null)
  const onCloseComposerRef = useRef(onCloseComposer)
  const onSavedRef = useRef(onSaved)

  onCloseComposerRef.current = onCloseComposer
  onSavedRef.current = onSaved

  /* Saved comments as read-only glyph decorations */
  useEffect(() => {
    if (!modifiedEditor) {
      return
    }
    const model = modifiedEditor.getModel()
    if (!model) {
      return
    }

    const filtered = comments.filter((c) => pathsMatch(c.file_path, apiFilePath))
    const decs: editor.IModelDeltaDecoration[] = filtered.map((c) => {
      const line = Math.min(Math.max(1, c.line_number), model.getLineCount())
      const maxCol = Math.max(1, model.getLineMaxColumn(line))
      return {
        range: new monaco.Range(line, 1, line, maxCol),
        options: {
          glyphMarginClassName: 'neo-inline-cmt-glyph',
          hoverMessage: { value: `**${c.file_path}:${line}**\n\n${c.comment_text}` },
          stickiness: monaco.editor.TrackedRangeStickiness.NeverGrowsWhenTypingAtEdges,
        },
      }
    })

    const prev = decorationIdsRef.current
    decorationIdsRef.current = modifiedEditor.deltaDecorations(prev, decs)

    return () => {
      if (modifiedEditor.getModel()) {
        decorationIdsRef.current = modifiedEditor.deltaDecorations(decorationIdsRef.current, [])
      } else {
        decorationIdsRef.current = []
      }
    }
  }, [modifiedEditor, comments, apiFilePath])

  /* Composer: ViewZone DOM (vanilla — stable inside Monaco lifecycle) */
  useEffect(() => {
    if (!modifiedEditor || activeLine == null || activeLine < 1) {
      if (modifiedEditor && viewZoneIdRef.current) {
        const zid = viewZoneIdRef.current
        viewZoneIdRef.current = null
        modifiedEditor.changeViewZones((accessor) => {
          accessor.removeZone(zid)
        })
      }
      return
    }

    const line = activeLine
    const host = document.createElement('div')
    host.className = 'neo-inline-cmt-viewzone'

    const errEl = document.createElement('p')
    errEl.className = 'neo-inline-cmt-err'
    errEl.hidden = true
    host.appendChild(errEl)

    const ta = document.createElement('textarea')
    ta.setAttribute('aria-label', 'Inline comment')
    ta.placeholder = 'Comment for this line…'
    host.appendChild(ta)

    const actions = document.createElement('div')
    actions.className = 'neo-inline-cmt-actions'

    const btnSave = document.createElement('button')
    btnSave.type = 'button'
    btnSave.className = 'neo-inline-cmt-btn neo-inline-cmt-btn-primary'
    btnSave.textContent = 'Save'

    const btnCancel = document.createElement('button')
    btnCancel.type = 'button'
    btnCancel.className = 'neo-inline-cmt-btn neo-inline-cmt-btn-secondary'
    btnCancel.textContent = 'Cancel'

    actions.appendChild(btnSave)
    actions.appendChild(btnCancel)
    host.appendChild(actions)

    const removeZone = () => {
      const zid = viewZoneIdRef.current
      viewZoneIdRef.current = null
      if (zid && modifiedEditor.getModel()) {
        modifiedEditor.changeViewZones((accessor) => {
          accessor.removeZone(zid)
        })
      }
    }

    const close = () => {
      removeZone()
      onCloseComposerRef.current()
    }

    btnCancel.addEventListener('click', () => {
      close()
    })

    btnSave.addEventListener('click', () => {
      const text = ta.value.trim()
      if (!text) {
        errEl.textContent = 'Comment must not be empty.'
        errEl.hidden = false
        return
      }
      errEl.hidden = true
      btnSave.disabled = true
      btnCancel.disabled = true
      void (async () => {
        try {
          await createTaskComment(taskId, {
            file_path: apiFilePath.trim(),
            line_number: line,
            comment_text: text,
          })
          await onSavedRef.current()
          close()
        } catch (e) {
          const msg = isAxiosError(e)
            ? typeof e.response?.data === 'object' &&
              e.response?.data !== null &&
              'detail' in e.response.data &&
              typeof (e.response.data as { detail?: unknown }).detail === 'string'
              ? (e.response.data as { detail: string }).detail
              : e.message
            : e instanceof Error
              ? e.message
              : 'Failed to save comment.'
          errEl.textContent = msg
          errEl.hidden = false
        } finally {
          btnSave.disabled = false
          btnCancel.disabled = false
        }
      })()
    })

    modifiedEditor.changeViewZones((accessor) => {
      if (viewZoneIdRef.current) {
        accessor.removeZone(viewZoneIdRef.current)
        viewZoneIdRef.current = null
      }
      viewZoneIdRef.current = accessor.addZone({
        afterLineNumber: line,
        heightInLines: 5,
        domNode: host,
        suppressMouseDown: false,
        showInHiddenAreas: false,
      })
    })

    requestAnimationFrame(() => {
      ta.focus()
    })

    return () => {
      removeZone()
    }
  }, [modifiedEditor, activeLine, taskId, apiFilePath])

  return null
}
