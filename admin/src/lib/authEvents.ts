/** Lightweight bus so the API layer can tell the UI that the session ended. */
const target = new EventTarget();
const LOGOUT_EVENT = 'auth:logout';

export function emitLogout(): void {
  target.dispatchEvent(new Event(LOGOUT_EVENT));
}

export function onLogout(listener: () => void): () => void {
  target.addEventListener(LOGOUT_EVENT, listener);
  return () => target.removeEventListener(LOGOUT_EVENT, listener);
}
