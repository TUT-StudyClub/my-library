"use client";

import { useEffect, useState } from "react";
import { type SeriesVolume, subscribeSeriesVolumeRegistered } from "@/lib/seriesVolumeSignal";
import styles from "./page.module.css";

type RegisteredVolumesSectionProps = {
  seriesId: string;
  initialVolumes: SeriesVolume[];
};

function sortSeriesVolumes(volumes: SeriesVolume[]): SeriesVolume[] {
  return [...volumes].sort((leftVolume, rightVolume) => {
    const leftUnknownOrder = leftVolume.volume_number === null ? 1 : 0;
    const rightUnknownOrder = rightVolume.volume_number === null ? 1 : 0;
    if (leftUnknownOrder !== rightUnknownOrder) {
      return leftUnknownOrder - rightUnknownOrder;
    }

    if (leftVolume.volume_number !== null && rightVolume.volume_number !== null) {
      const volumeNumberDiff = leftVolume.volume_number - rightVolume.volume_number;
      if (volumeNumberDiff !== 0) {
        return volumeNumberDiff;
      }
    }

    const registeredAtDiff = leftVolume.registered_at.localeCompare(rightVolume.registered_at);
    if (registeredAtDiff !== 0) {
      return registeredAtDiff;
    }

    return leftVolume.isbn.localeCompare(rightVolume.isbn);
  });
}

function mergeSeriesVolume(
  currentVolumes: SeriesVolume[],
  incomingVolume: SeriesVolume
): SeriesVolume[] {
  const nextVolumesByIsbn = new Map<string, SeriesVolume>();

  for (const volume of currentVolumes) {
    nextVolumesByIsbn.set(volume.isbn, volume);
  }

  nextVolumesByIsbn.set(incomingVolume.isbn, incomingVolume);
  return sortSeriesVolumes(Array.from(nextVolumesByIsbn.values()));
}

function formatRegisteredAt(registeredAt: string): string {
  const parsedDate = new Date(registeredAt);
  if (Number.isNaN(parsedDate.getTime())) {
    return registeredAt;
  }

  return parsedDate.toLocaleString("ja-JP", { hour12: false });
}

export function RegisteredVolumesSection({
  seriesId,
  initialVolumes,
}: RegisteredVolumesSectionProps) {
  const [volumes, setVolumes] = useState<SeriesVolume[]>(() => sortSeriesVolumes(initialVolumes));

  useEffect(() => {
    setVolumes(sortSeriesVolumes(initialVolumes));
  }, [initialVolumes]);

  useEffect(() => {
    return subscribeSeriesVolumeRegistered((detail) => {
      if (detail.seriesId !== seriesId) {
        return;
      }

      setVolumes((currentVolumes) => mergeSeriesVolume(currentVolumes, detail.volume));
    });
  }, [seriesId]);

  return (
    <section className={styles.volumeSection}>
      <h2 className={styles.sectionTitle}>登録済み巻</h2>
      {volumes.length === 0 ? (
        <div aria-live="polite" className={styles.placeholderPanel} role="status">
          <p className={styles.placeholderText}>登録済みの巻はありません。</p>
        </div>
      ) : (
        <ul className={styles.volumeList}>
          {volumes.map((volume) => (
            <li className={styles.volumeListItem} key={volume.isbn}>
              <article className={styles.volumeCard}>
                <p className={styles.volumeNumber}>
                  {volume.volume_number === null ? "巻数不明" : `${volume.volume_number}巻`}
                </p>
                <p className={styles.volumeMeta}>ISBN: {volume.isbn}</p>
                <p className={styles.volumeMeta}>
                  登録日時: {formatRegisteredAt(volume.registered_at)}
                </p>
              </article>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
