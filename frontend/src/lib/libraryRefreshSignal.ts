const LIBRARY_REFRESH_SIGNAL_KEY = "libraryRefreshSignalAt";

export function publishLibraryRefreshSignal(): void {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.sessionStorage.setItem(LIBRARY_REFRESH_SIGNAL_KEY, Date.now().toString());
  } catch {
    return;
  }
}

export function consumeLibraryRefreshSignal(): boolean {
  if (typeof window === "undefined") {
    return false;
  }

  try {
    const signal = window.sessionStorage.getItem(LIBRARY_REFRESH_SIGNAL_KEY);
    if (signal === null) {
      return false;
    }

    window.sessionStorage.removeItem(LIBRARY_REFRESH_SIGNAL_KEY);
    return true;
  } catch {
    return false;
  }
}
