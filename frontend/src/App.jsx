import { useEffect, useState } from 'react'
import ChatPanel from './components/ChatPanel.jsx'
import CasesPanel from './components/CasesPanel.jsx'
import Icon from './components/Icon.jsx'
import OrdersPanel from './components/OrdersPanel.jsx'
import Sidebar from './components/Sidebar.jsx'
import './App.css'

const PAGE_TITLES = {
  chat: 'Customer support',
  cases: 'My cases',
  orders: 'My orders',
}

function App() {
  const [activePage, setActivePage] = useState('chat')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [cases, setCases] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('support-cases') || '[]')
    } catch {
      return []
    }
  })

  useEffect(() => {
    localStorage.setItem('support-cases', JSON.stringify(cases))
  }, [cases])

  function rememberCase(nextCase) {
    setCases((current) => {
      const withoutDuplicate = current.filter((item) => item.case_id !== nextCase.case_id)
      return [nextCase, ...withoutDuplicate]
    })
  }

  function renderPage() {
    if (activePage === 'cases') {
      return <CasesPanel cases={cases} />
    }
    if (activePage === 'orders') {
      return <OrdersPanel />
    }
    return <ChatPanel onCaseCreated={rememberCase} />
  }

  return (
    <div className="app-shell">
      <Sidebar
        activePage={activePage}
        isOpen={sidebarOpen}
        onNavigate={(page) => {
          setActivePage(page)
          setSidebarOpen(false)
        }}
        onClose={() => setSidebarOpen(false)}
      />
      {sidebarOpen && (
        <button
          className="sidebar-backdrop"
          type="button"
          aria-label="Close navigation"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <main className="main-column">
        <header className="topbar">
          <button
            className="menu-button"
            type="button"
            aria-label="Open navigation"
            onClick={() => setSidebarOpen(true)}
          >
            <span />
            <span />
            <span />
          </button>
          <div className="breadcrumbs">
            <span>Help center</span>
            <span className="breadcrumb-divider">/</span>
            <strong>{PAGE_TITLES[activePage]}</strong>
          </div>
          <div className="topbar-right">
            <span className="secure-label">
              <Icon name="help" size={14} />
              Support center
            </span>
            <div className="user-avatar" aria-label="Customer profile">
              C
            </div>
          </div>
        </header>

        <div className="page-content">{renderPage()}</div>

        <footer className="page-footer">
          <span>Need more help?</span>
          <button type="button" onClick={() => setActivePage('chat')}>Contact support in chat</button>
          <span className="footer-separator">·</span>
          <span>Customer support</span>
        </footer>
      </main>
    </div>
  )
}

export default App
