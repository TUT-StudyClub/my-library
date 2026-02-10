"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { buildUserFacingApiErrorMessage, extractApiErrorCode } from "@/lib/apiError";
import { publishLibraryRefreshSignal } from "@/lib/libraryRefreshSignal";
import { type SeriesVolume, subscribeSeriesVolumeRegistered } from "@/lib/seriesVolumeSignal";
import styles from "./page.module.css";

type RegisteredVolumesSectionProps = {
  seriesId: string;
  seriesTitle: string;
  initialVolumes: SeriesVolume[];
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const DEFAULT_DELETE_ERROR_MESSAGE = "巻の削除に失敗しました。";
const DELETE_REQUEST_ERROR_MESSAGE = "削除リクエストの送信に失敗しました。";

type DeleteResult = {
  tone: "success" | "error";
  message: string;
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

function extractDeletedIsbn(payload: unknown): string | null {
  if (
    typeof payload === "object" &&
    payload !== null &&
    "deleted" in payload &&
    typeof payload.deleted === "object" &&
    payload.deleted !== null &&
    "isbn" in payload.deleted &&
    typeof payload.deleted.isbn === "string"
  ) {
    const normalizedIsbn = payload.deleted.isbn.trim();
    if (normalizedIsbn !== "") {
      return normalizedIsbn;
    }
  }

  return null;
}

function formatVolumeLabel(volumeNumber: number | null): string {
  return volumeNumber === null ? "巻数不明" : `${volumeNumber}巻`;
}

export function RegisteredVolumesSection({
  seriesId,
  seriesTitle,
  initialVolumes,
}: RegisteredVolumesSectionProps) {
  const router = useRouter();
  const [volumes, setVolumes] = useState<SeriesVolume[]>(() => sortSeriesVolumes(initialVolumes));
  const [deletingByIsbn, setDeletingByIsbn] = useState<Record<string, boolean>>({});
  const [deleteResult, setDeleteResult] = useState<DeleteResult | null>(null);
  const deletingIsbnSetRef = useRef<Set<string>>(new Set());

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

  const deleteVolume = async (targetVolume: SeriesVolume) => {
    const isbn = targetVolume.isbn;
    if (deletingIsbnSetRef.current.has(isbn)) {
      return;
    }
    deletingIsbnSetRef.current.add(isbn);

    const targetSeriesTitle = seriesTitle.trim() === "" ? "この作品" : seriesTitle.trim();
    const shouldDelete = window.confirm(
      [
        "以下の巻を削除します。よろしいですか？",
        `シリーズ: ${targetSeriesTitle}`,
        `巻数: ${formatVolumeLabel(targetVolume.volume_number)}`,
        `ISBN: ${isbn}`,
      ].join("\n")
    );
    if (!shouldDelete) {
      deletingIsbnSetRef.current.delete(isbn);
      return;
    }

    setDeleteResult(null);
    setDeletingByIsbn((currentValue) => ({
      ...currentValue,
      [isbn]: true,
    }));

    try {
      const requestUrl = new URL(`/api/volumes/${isbn}`, API_BASE_URL);
      const response = await fetch(requestUrl.toString(), {
        method: "DELETE",
      });

      if (!response.ok) {
        const errorPayload = (await response.json().catch(() => null)) as unknown;
        const errorCode = extractApiErrorCode(errorPayload);
        if (response.status === 404 && errorCode === "VOLUME_NOT_FOUND") {
          setVolumes((currentVolumes) =>
            currentVolumes.filter((currentVolume) => currentVolume.isbn !== isbn)
          );
          setDeleteResult({
            tone: "success",
            message: `ISBN: ${isbn} は既に削除済みです。`,
          });
          publishLibraryRefreshSignal();
          router.refresh();
          return;
        }

        throw new Error(
          buildUserFacingApiErrorMessage({
            errorPayload,
            statusCode: response.status,
            fallbackMessage: DEFAULT_DELETE_ERROR_MESSAGE,
          })
        );
      }

      const successPayload = (await response.json().catch(() => null)) as unknown;
      const deletedIsbn = extractDeletedIsbn(successPayload) ?? isbn;
      setVolumes((currentVolumes) =>
        currentVolumes.filter(
          (currentVolume) => currentVolume.isbn !== isbn && currentVolume.isbn !== deletedIsbn
        )
      );
      setDeleteResult({
        tone: "success",
        message: `ISBN: ${deletedIsbn} を削除しました。`,
      });
      publishLibraryRefreshSignal();
      router.refresh();
    } catch (error) {
      if (error instanceof Error && error.message.trim() !== "") {
        setDeleteResult({
          tone: "error",
          message: error.message,
        });
      } else {
        setDeleteResult({
          tone: "error",
          message: DELETE_REQUEST_ERROR_MESSAGE,
        });
      }
    } finally {
      deletingIsbnSetRef.current.delete(isbn);
      setDeletingByIsbn((currentValue) => {
        const nextValue = { ...currentValue };
        delete nextValue[isbn];
        return nextValue;
      });
    }
  };

  if (volumes.length === 0) {
    return null;
  }

  return (
    <section className={styles.volumeSection}>
      <h2 className={styles.sectionTitle}>登録済み巻</h2>
      {deleteResult !== null ? (
        <p
          className={
            deleteResult.tone === "success"
              ? styles.deleteSuccessMessage
              : styles.deleteErrorMessage
          }
          role={deleteResult.tone === "error" ? "alert" : "status"}
        >
          {deleteResult.message}
        </p>
      ) : null}
      <ul className={styles.volumeList}>
        {volumes.map((volume) => {
          const isDeleting = deletingByIsbn[volume.isbn] === true;
          const volumeLabel = formatVolumeLabel(volume.volume_number);

          return (
            <li className={styles.volumeListItem} key={volume.isbn}>
              <article className={styles.volumeCard}>
                <p className={styles.volumeNumber}>{volumeLabel}</p>
                <p className={styles.volumeMeta}>ISBN: {volume.isbn}</p>
                <p className={styles.volumeMeta}>
                  登録日時: {formatRegisteredAt(volume.registered_at)}
                </p>
                <div className={styles.volumeActions}>
                  <button
                    aria-label={`${volumeLabel}（ISBN: ${volume.isbn}）を削除`}
                    className={styles.volumeDeleteButton}
                    disabled={isDeleting}
                    onClick={() => {
                      void deleteVolume(volume);
                    }}
                    type="button"
                  >
                    {isDeleting ? "削除中..." : "削除"}
                  </button>
                </div>
              </article>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
