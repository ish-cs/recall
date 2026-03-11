import { useStore, type ActiveView } from '../../store'

const NAV_ITEMS: { view: ActiveView; label: string; badge?: boolean }[] = [
  { view: 'timeline', label: 'Timeline' },
  { view: 'search', label: 'Search' },
  { view: 'speakers', label: 'Speakers', badge: true },
  { view: 'settings', label: 'Settings' },
]

export function Sidebar() {
  const activeView = useStore((s) => s.activeView)
  const setActiveView = useStore((s) => s.setActiveView)
  const pendingSuggestions = useStore((s) => s.pendingSpeakerSuggestions)

  return (
    <aside className="w-48 bg-white border-r flex flex-col shrink-0">
      <div className="p-4 border-b">
        <h1 className="font-bold text-base">Recall</h1>
      </div>
      <nav className="flex-1 p-2 space-y-1">
        {NAV_ITEMS.map(({ view, label, badge }) => (
          <button
            key={view}
            onClick={() => setActiveView(view)}
            className={`w-full text-left px-3 py-2 rounded text-sm flex items-center justify-between ${
              activeView === view
                ? 'bg-blue-100 text-blue-700 font-medium'
                : 'text-gray-700 hover:bg-gray-100'
            }`}
          >
            {label}
            {badge && pendingSuggestions.length > 0 && (
              <span className="bg-red-500 text-white text-xs px-1.5 py-0.5 rounded-full">
                {pendingSuggestions.length}
              </span>
            )}
          </button>
        ))}
      </nav>
    </aside>
  )
}
