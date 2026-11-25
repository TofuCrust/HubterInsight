import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// HTML mentah tidak dirender (bawaan react-markdown), jadi aman dari injeksi.
export default function Markdown({ text }: { text: string }) {
  return (
    <div className="md">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ node: _node, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" />,
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  )
}
