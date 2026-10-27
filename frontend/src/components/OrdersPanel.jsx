import Icon from './Icon.jsx'

export default function OrdersPanel() {
  return (
    <section className="secondary-page">
      <div className="secondary-heading">
        <div>
          <div className="eyebrow"><span className="status-dot" /> ORDER SUPPORT</div>
          <h1>My orders</h1>
          <p className="page-intro">Get help with a delivery, return, or anything you ordered.</p>
        </div>
      </div>

      <div className="orders-intro-card">
        <div className="orders-intro-icon"><Icon name="package" size={22} /></div>
        <div>
          <h2>Need help with an order?</h2>
          <p>Share your order number in a support chat and we’ll help check the demo order details.</p>
        </div>
      </div>

      <div className="empty-state-card orders-empty">
        <div className="empty-state-icon"><Icon name="package" size={24} /></div>
        <h2>Your orders will show up here</h2>
        <p>Order history isn’t connected to this customer app yet. You can still ask about an order using its order ID in chat.</p>
        <div className="demo-order-note">
          <span className="demo-order-label">DEMO ORDER IDS</span>
          <span>ORD1001</span><span>ORD1002</span><span>ORD1003</span>
        </div>
        <div className="empty-state-foot"><Icon name="shield" size={15} /> No live store or customer order account is connected.</div>
      </div>
    </section>
  )
}
