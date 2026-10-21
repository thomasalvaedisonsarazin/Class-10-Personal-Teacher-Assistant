type Listener = () => void;

const logoutListeners = new Set<Listener>();
const sessionBusyListeners = new Set<Listener>();

/** Tiny event bus so the API layer can tell AuthContext the session is gone. */
export const authEvents = {
  onLogout(listener: Listener): () => void {
    logoutListeners.add(listener);
    return () => {
      logoutListeners.delete(listener);
    };
  },

  emitLogout(): void {
    logoutListeners.forEach((listener) => listener());
  },

  /** The account is in use on another device (409 ``session_active``). */
  onSessionBusy(listener: Listener): () => void {
    sessionBusyListeners.add(listener);
    return () => {
      sessionBusyListeners.delete(listener);
    };
  },

  emitSessionBusy(): void {
    sessionBusyListeners.forEach((listener) => listener());
  },
};
