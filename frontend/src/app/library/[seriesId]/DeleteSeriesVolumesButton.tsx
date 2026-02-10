"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { publishLibraryRefreshSignal } from "@/lib/libraryRefreshSignal";
import styles from "./page.module.css";

type DeleteSeriesVolumesButtonProps = {
  seriesId: string;
  seriesTitle: string;
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const DEFAULT_DELETE_ERROR_MESSAGE = "全巻削除に失敗しました。";
const DELETE_REQUEST_ERROR_MESSAGE = "削除リクエストの送信に失敗しました。";

function extractDeleteErrorMessage(errorPayload: unknown, statusCode: number): string {
  if (
    typeof errorPayload === "object" &&
    errorPayload !== null &&
    "error" in errorPayload &&
    typeof errorPayload.error === "object" &&
    errorPayload.error !== null &&
    "message" in errorPayload.error &&
    typeof errorPayload.error.message === "string"
  ) {
    const message = errorPayload.error.message.trim();
    if (message !== "") {
      return message;
    }
  }

  return `${DEFAULT_DELETE_ERROR_MESSAGE} (status: ${statusCode})`;
}

export function DeleteSeriesVolumesButton({
  seriesId,
  seriesTitle,
}: DeleteSeriesVolumesButtonProps) {
  const router = useRouter();
  const [isDeleting, setIsDeleting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const isDeletingRef = useRef(false);

  const deleteAllVolumes = async () => {
    if (isDeletingRef.current) {
      return;
    }
    isDeletingRef.current = true;

    const targetSeriesTitle = seriesTitle.trim() === "" ? "この作品" : seriesTitle.trim();
    const shouldDelete = window.confirm(
      `「${targetSeriesTitle}」の登録済み巻をすべて削除します。よろしいですか？`
    );
    if (!shouldDelete) {
      isDeletingRef.current = false;
      return;
    }

    setIsDeleting(true);
    setErrorMessage(null);

    try {
      const requestUrl = new URL(`/api/series/${seriesId}/volumes`, API_BASE_URL);
      const response = await fetch(requestUrl.toString(), {
        method: "DELETE",
      });

      if (!response.ok) {
        const errorPayload = (await response.json().catch(() => null)) as unknown;
        throw new Error(extractDeleteErrorMessage(errorPayload, response.status));
      }

      publishLibraryRefreshSignal();
      router.replace("/library");
      router.refresh();
    } catch (error) {
      if (error instanceof Error && error.message.trim() !== "") {
        setErrorMessage(error.message);
      } else {
        setErrorMessage(DELETE_REQUEST_ERROR_MESSAGE);
      }
    } finally {
      isDeletingRef.current = false;
      setIsDeleting(false);
    }
  };

  return (
    <div className={styles.seriesDangerZone}>
      <button
        className={styles.deleteSeriesButton}
        disabled={isDeleting}
        onClick={() => {
          void deleteAllVolumes();
        }}
        type="button"
      >
        {isDeleting ? "削除中..." : "全巻削除"}
      </button>
      {errorMessage !== null ? (
        <p className={styles.seriesDeleteErrorMessage} role="alert">
          {errorMessage}
        </p>
      ) : null}
    </div>
  );
}
