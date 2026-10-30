export interface AuthUser {
  id: string
  email?: string
  user_metadata?: {
    full_name?: string
  }
}

interface AuthSession {
  access_token: string
  refresh_token: string
  expires_in: number
  user: AuthUser
}

interface SignUpResponse {
  access_token?: string
  refresh_token?: string
  expires_in?: number
  user: AuthUser
}

const apiBaseUrl = import.meta.env.VITE_API_URL ?? "/api"
const sessionKey = "codemap.auth.session"

function selectedStorage(remember: boolean): Storage {
  return remember ? localStorage : sessionStorage
}

function findStoredSession(): AuthSession | null {
  const rawSession =
    localStorage.getItem(sessionKey) ?? sessionStorage.getItem(sessionKey)
  if (!rawSession) return null

  try {
    return JSON.parse(rawSession) as AuthSession
  } catch {
    clearSession()
    return null
  }
}

function saveSession(session: AuthSession, remember: boolean): void {
  clearSession()
  selectedStorage(remember).setItem(sessionKey, JSON.stringify(session))
}

function clearSession(): void {
  localStorage.removeItem(sessionKey)
  sessionStorage.removeItem(sessionKey)
}

async function responseJson<T>(response: Response): Promise<T> {
  const body = (await response.json().catch(() => null)) as {
    detail?: string
  } | null
  if (!response.ok) {
    throw new Error(body?.detail ?? "Authentication request failed")
  }
  return body as T
}

export async function signIn(
  email: string,
  password: string,
  remember: boolean
): Promise<AuthUser> {
  const response = await fetch(`${apiBaseUrl}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  })
  const session = await responseJson<AuthSession>(response)
  saveSession(session, remember)
  return session.user
}

export async function signUp(
  fullName: string,
  email: string,
  password: string,
  remember: boolean
): Promise<{ user: AuthUser; needsEmailConfirmation: boolean }> {
  const response = await fetch(`${apiBaseUrl}/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ full_name: fullName, email, password }),
  })
  const result = await responseJson<SignUpResponse>(response)
  const hasSession = Boolean(result.access_token && result.refresh_token)
  if (hasSession) {
    saveSession(result as AuthSession, remember)
  }
  return { user: result.user, needsEmailConfirmation: !hasSession }
}

export async function getCurrentUser(): Promise<AuthUser | null> {
  const session = findStoredSession()
  if (!session) return null

  let response = await fetch(`${apiBaseUrl}/auth/me`, {
    headers: { Authorization: `Bearer ${session.access_token}` },
  })

  if (response.status === 401) {
    const refreshResponse = await fetch(`${apiBaseUrl}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: session.refresh_token }),
    })
    if (!refreshResponse.ok) {
      clearSession()
      return null
    }
    const refreshedSession = await responseJson<AuthSession>(refreshResponse)
    const remember = localStorage.getItem(sessionKey) !== null
    saveSession(refreshedSession, remember)
    response = await fetch(`${apiBaseUrl}/auth/me`, {
      headers: { Authorization: `Bearer ${refreshedSession.access_token}` },
    })
  }

  if (!response.ok) {
    clearSession()
    return null
  }
  return responseJson<AuthUser>(response)
}

export async function signOut(): Promise<void> {
  const session = findStoredSession()
  clearSession()
  if (!session) return

  await fetch(`${apiBaseUrl}/auth/logout`, {
    method: "POST",
    headers: { Authorization: `Bearer ${session.access_token}` },
  }).catch(() => undefined)
}
