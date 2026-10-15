type Listener = () => void;

const logoutListeners = new Set<Listener>();

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
};
