import Icon from './Icon.jsx'

function formatDate(value) {
  if (!value) return 'Date unavailable'
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(new Date(value))
}

function statusLabel(status) {
  return (status || 'received').replaceAll('_', ' ')
}

export default function CasesPanel({ cases }) {
  return (
    <section className="secondary-page">
      <div className="secondary-heading">
        <div>
          <div className="eyebrow"><span className="status-dot" /> YOUR SUPPORT HISTORY</div>
          <h1>My cases</h1>
          <p className="page-intro">Keep track of support requests you’ve started from this browser.</p>
        </div>
        <div className="cases-count"><strong>{cases.length}</strong><span>{cases.length === 1 ? 'case' : 'cases'}</span></div>
      </div>

      {cases.length ? (
        <div className="case-list">
          {cases.map((item) => (
            <article className="case-card" key={item.case_id}>
              <div className="case-card-main">
                <div className="case-icon"><Icon name="chat" size={19} /></div>
                <div className="case-copy">
                  <div className="case-title-row">
                    <h2>Support request</h2>
                    <span className={`case-status status-${item.status || 'received'}`}>
                      <i /> {statusLabel(item.status)}
                    </span>
                  </div>
                  <p>{item.answer || 'Your support request has been received.'}</p>
                  <div className="case-meta">
                    <span>Case {item.case_id.slice(0, 8)}</span>
                    <span className="meta-dot">·</span>
                    <span>{formatDate(item.created_at)}</span>
                    {item.ticket_id && <><span className="meta-dot">·</span><span>Ticket {item.ticket_id}</span></>}
                  </div>
                </div>
                <Icon name="chevron" size={18} />
              </div>
              {item.approval_required && (
                <div className="case-review-note"><Icon name="clock" size={15} /> Waiting for a support team review. No refund has been issued.</div>
              )}
            </article>
          ))}
          <div className="local-data-note">
            <Icon name="info" size={16} />
            This history is saved in this browser. Sign-in and a server-side case list are not available yet.
          </div>
        </div>
      ) : (
        <div className="empty-state-card">
          <div className="empty-state-icon"><Icon name="cases" size={24} /></div>
          <h2>No cases yet</h2>
          <p>When you contact support, your requests will appear here for easy reference.</p>
          <div className="empty-state-foot"><Icon name="info" size={15} /> Your case history is currently stored in this browser.</div>
        </div>
      )}
    </section>
  )
}
