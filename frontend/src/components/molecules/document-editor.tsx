import Editor from '@monaco-editor/react'

type DocumentEditorProps = {
  value: string
  onChange: (value: string) => void
  readOnly?: boolean
  height?: number | string
}

export function DocumentEditor({
  value,
  onChange,
  readOnly = false,
  height = '60vh',
}: DocumentEditorProps) {
  return (
    <Editor
      height={height}
      defaultLanguage="markdown"
      value={value}
      onChange={(next) => onChange(next ?? '')}
      options={{
        readOnly,
        minimap: { enabled: false },
        wordWrap: 'on',
        lineNumbers: 'on',
        scrollBeyondLastLine: false,
        automaticLayout: true,
      }}
    />
  )
}
