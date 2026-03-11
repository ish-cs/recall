interface TimestampLabelProps {
  ms: number
}

function formatTime(ms: number): string {
  const date = new Date(ms)
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function TimestampLabel({ ms }: TimestampLabelProps) {
  return (
    <span className="text-xs text-gray-400 font-mono" title={new Date(ms).toISOString()}>
      {formatTime(ms)}
    </span>
  )
}
