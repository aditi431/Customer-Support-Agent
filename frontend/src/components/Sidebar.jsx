import Icon from './Icon.jsx'

const NAV_ITEMS = [
  { id: 'chat', label: 'Chat with us', icon: 'chat' },
  { id: 'cases', label: 'My cases', icon: 'cases' },
  { id: 'orders', label: 'My orders', icon: 'package' },
]

export default function Sidebar({ activePage, isOpen, onNavigate, onClose }) {
  return (
    <aside className={`sidebar${isOpen ? ' sidebar-open' : ''}`}>
      <div className="brand">
        <div className="brand-mark">
          <Icon name="sparkles" size={21} strokeWidth={2} />
        </div>
        <div>
          <div className="brand-name">kindred</div>
          <div className="brand-subtitle">CUSTOMER CARE</div>
        </div>
        <button
          className="sidebar-close"
          type="button"
          onClick={onClose}
          aria-label="Close navigation"
        >
          ×
        </button>
      </div>

      <div className="workspace-label">YOUR ACCOUNT</div>
      <nav className="primary-nav" aria-label="Main navigation">
        {NAV_ITEMS.map((item) => (
          <button
            className={`nav-item${activePage === item.id ? ' nav-item-active' : ''}`}
            key={item.id}
            type="button"
            onClick={() => onNavigate(item.id)}
            aria-current={activePage === item.id ? 'page' : undefined}
          >
            <Icon name={item.icon} size={19} />
            <span>{item.label}</span>
            {item.id === 'cases' && activePage === 'cases' && (
              <span className="nav-active-dot" />
            )}
          </button>
        ))}
      </nav>

      <div className="sidebar-spacer" />

      <div className="help-card">
        <div className="help-card-icon"><Icon name="help" size={19} /></div>
        <h3>We're here for you</h3>
        <p>Our team is ready to help with anything you need.</p>
        <button type="button" onClick={() => onNavigate('chat')}>
          Start a chat <Icon name="arrow" size={14} />
        </button>
      </div>

      <div className="sidebar-profile">
        <div className="profile-avatar">C</div>
        <div className="profile-copy">
          <strong>Your account</strong>
          <span>Customer</span>
        </div>
        <Icon name="chevron" size={17} />
      </div>
    </aside>
  )
}
