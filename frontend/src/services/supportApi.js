const API_BASE_URL = (import.meta.env.VITE_SUPPORT_API_URL || '').replace(/\/$/, '')

export class SupportApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'SupportApiError'
    this.status = status
  }
}

async function parseResponse(response) {
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    if (response.status === 401) {
      throw new SupportApiError(
        'The support service rejected its server-side credentials. Check API_ACCESS_TOKEN in the project .env file and restart the backend and Vite.',
        response.status,
      )
    }
    if (response.status === 503) {
      throw new SupportApiError(
        'The backend has not loaded API_ACCESS_TOKEN. Confirm it is set in the project .env file, restart FastAPI, then refresh this page.',
        response.status,
      )
    }
    if (response.status === 422) {
      throw new SupportApiError(
        data.detail?.[0]?.msg || 'Please check the information and try again.',
        response.status,
      )
    }
    throw new SupportApiError(
      data.detail || 'We could not reach support right now. Please try again.',
      response.status,
    )
  }
  return data
}

export async function sendSupportMessage({ question, orderId, customerEmail, idempotencyKey }) {
  let response
  try {
    response = await fetch(`${API_BASE_URL}/api/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Idempotency-Key': idempotencyKey,
      },
      body: JSON.stringify({
        question,
        order_id: orderId || '',
        customer_email: customerEmail || '',
      }),
    })
  } catch (error) {
    if (!(error instanceof TypeError)) {
      throw error
    }
    throw new SupportApiError(
      'Could not connect to the support API. Make sure FastAPI is running at http://127.0.0.1:8000 and restart Vite.',
    )
  }
  return parseResponse(response)
}
