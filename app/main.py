
import streamlit as st

from app.graph.workflow import answer_customer

st.set_page_config(
    page_title="AI Customer Support Agent",
    page_icon="💬",
    layout="centered"
)

st.title("AI Customer Support & Resolution Agent")
st.caption("Policy-grounded support • Semantic search • Demo order lookup")

with st.sidebar:
    st.header("Demo instructions")
    st.write("Try questions about returns, damaged products, or refunds.")
    st.write("Demo order IDs: ORD1001, ORD1002, ORD1003.")
    st.warning(
        "This is a demo. It does not issue real refunds or connect to a live store."
    )

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        if message.get("sources"):
            with st.expander("Retrieved policy sources"):
                for source in message["sources"]:
                    st.write(source)

        if message.get("order") or message.get("refund_check"):
            with st.expander("Order check"):
                if message.get("order"):
                    order = message["order"]
                    st.write(f"Order: {order['order_id']}")
                    st.write(f"Status: {order['status']}")
                    st.write(f"Product: {order['product']}")

                if message.get("refund_check"):
                    eligibility = message["refund_check"]
                    status = "May be eligible" if eligibility["eligible"] else "Not eligible"
                    st.write(f"Preliminary demo check: {status}")
                    st.write(eligibility["reason"])

        if message.get("ticket"):
            st.info(f"Manual review ticket: {message['ticket']['ticket_id']}")

        if message.get("email_notifications"):
            with st.expander("Email notification status"):
                for notification in message["email_notifications"]:
                    st.write(
                        f"{notification.get('status', 'unknown')}: "
                        f"{notification.get('reason', '')}"
                    )
                    if notification.get("preview"):
                        st.code(notification["preview"])

with st.form("support_form", clear_on_submit=True):
    question = st.text_area(
        "How can we help you?",
        placeholder="I received the wrong product. Can I return it?",
        max_chars=1500
    )
    order_id = st.text_input(
        "Order ID (optional)",
        placeholder="ORD1001"
    )
    customer_email = st.text_input(
        "Email for case updates (optional)",
        placeholder="you@example.com"
    )
    submitted = st.form_submit_button("Get support", type="primary")

if submitted:
    if not question.strip():
        st.warning("Please enter a question.")
    else:
        st.session_state.messages.append({
            "role": "user",
            "content": question.strip()
        })

        with st.spinner("Checking policy and preparing a response..."):
            result = answer_customer(question, order_id, customer_email)

        assistant_message = {
            "role": "assistant",
            "content": result["answer"],
            "sources": result.get("sources", []),
            "ticket": result.get("ticket"),
            "order": result.get("order"),
            "refund_check": result.get("refund_check"),
            "email_notifications": result.get("email_notifications", [])
        }
        st.session_state.messages.append(assistant_message)

        st.rerun()

if st.button("Clear chat"):
    st.session_state.messages = []
    st.rerun()
