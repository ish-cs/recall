import { useStore } from '../../store'
import { Sidebar } from './Sidebar'
import { RecordingStatusBar } from './RecordingStatusBar'

interface AppShellProps {
  children: React.ReactNode
}

export function AppShell({ children }: AppShellProps) {
  const activeView = useStore((s) => s.activeView)

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto" key={activeView}>
          {children}
        </main>
      </div>
      <RecordingStatusBar />
    </div>
  )
}
