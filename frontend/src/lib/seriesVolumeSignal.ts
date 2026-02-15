export type SeriesVolume = {
  isbn: string;
  volume_number: number | null;
  cover_url: string | null;
  registered_at: string;
};

type SeriesVolumeRegisteredDetail = {
  seriesId: string;
  volume: SeriesVolume;
};

type SeriesVolumeDeletedDetail = {
  seriesId: string;
  isbn: string;
};

const SERIES_VOLUME_REGISTERED_EVENT_NAME = "series-volume-registered";
const SERIES_VOLUME_DELETED_EVENT_NAME = "series-volume-deleted";

export function publishSeriesVolumeRegistered(detail: SeriesVolumeRegisteredDetail): void {
  if (typeof window === "undefined") {
    return;
  }

  window.dispatchEvent(
    new CustomEvent<SeriesVolumeRegisteredDetail>(SERIES_VOLUME_REGISTERED_EVENT_NAME, {
      detail,
    })
  );
}

export function subscribeSeriesVolumeRegistered(
  onRegistered: (detail: SeriesVolumeRegisteredDetail) => void
): () => void {
  if (typeof window === "undefined") {
    return () => {};
  }

  const listener: EventListener = (event) => {
    if (!(event instanceof CustomEvent)) {
      return;
    }

    const detail = event.detail as SeriesVolumeRegisteredDetail | null;
    if (detail === null || typeof detail !== "object") {
      return;
    }

    onRegistered(detail);
  };

  window.addEventListener(SERIES_VOLUME_REGISTERED_EVENT_NAME, listener);

  return () => {
    window.removeEventListener(SERIES_VOLUME_REGISTERED_EVENT_NAME, listener);
  };
}

export function publishSeriesVolumeDeleted(detail: SeriesVolumeDeletedDetail): void {
  if (typeof window === "undefined") {
    return;
  }

  window.dispatchEvent(
    new CustomEvent<SeriesVolumeDeletedDetail>(SERIES_VOLUME_DELETED_EVENT_NAME, {
      detail,
    })
  );
}

export function subscribeSeriesVolumeDeleted(
  onDeleted: (detail: SeriesVolumeDeletedDetail) => void
): () => void {
  if (typeof window === "undefined") {
    return () => {};
  }

  const listener: EventListener = (event) => {
    if (!(event instanceof CustomEvent)) {
      return;
    }

    const detail = event.detail as SeriesVolumeDeletedDetail | null;
    if (detail === null || typeof detail !== "object") {
      return;
    }

    onDeleted(detail);
  };

  window.addEventListener(SERIES_VOLUME_DELETED_EVENT_NAME, listener);

  return () => {
    window.removeEventListener(SERIES_VOLUME_DELETED_EVENT_NAME, listener);
  };
}
