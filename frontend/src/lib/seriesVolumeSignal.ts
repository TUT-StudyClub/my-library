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

const SERIES_VOLUME_REGISTERED_EVENT_NAME = "series-volume-registered";

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
