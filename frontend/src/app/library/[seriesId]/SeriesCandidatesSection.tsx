"use client";

import Image, { type ImageLoaderProps } from "next/image";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { publishLibraryRefreshSignal } from "@/lib/libraryRefreshSignal";
import { publishSeriesVolumeRegistered, type SeriesVolume } from "@/lib/seriesVolumeSignal";
import styles from "./page.module.css";

type SeriesCandidate = {
  title: string;
  author: string | null;
  publisher: string | null;
  isbn: string;
  volume_number: number | null;
  cover_url: string | null;
};

type SeriesCandidatesSectionProps = {
  seriesId: string;
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const DEFAULT_FETCH_ERROR_MESSAGE = "未登録候補の取得に失敗しました。";
const DEFAULT_REGISTER_ERROR_MESSAGE = "候補の登録に失敗しました。";
const REGISTER_REQUEST_ERROR_MESSAGE = "登録リクエストの送信に失敗しました。";
const REGISTER_RESULT_TOAST_DURATION_MILLISECONDS = 5000;

type RegisterResultToast = {
  id: number;
  tone: "success" | "info" | "error";
  message: string;
};

type CandidateCoverProps = {
  title: string;
  coverUrl: string | null;
  volumeNumber: number | null;
};

function passthroughImageLoader({ src }: ImageLoaderProps): string {
  return src;
}

function normalizeCoverUrl(coverUrl: string | null): string | null {
  const trimmedCoverUrl = coverUrl?.trim() ?? "";
  if (trimmedCoverUrl === "") {
    return null;
  }

  try {
    const parsedCoverUrl = new URL(trimmedCoverUrl);
    if (parsedCoverUrl.protocol !== "http:" && parsedCoverUrl.protocol !== "https:") {
      return null;
    }

    return parsedCoverUrl.toString();
  } catch {
    return null;
  }
}

function formatVolumeNumber(volumeNumber: number | null): string {
  return volumeNumber === null ? "巻数不明" : `${volumeNumber}巻`;
}

function CandidateCover({ title, coverUrl, volumeNumber }: CandidateCoverProps) {
  const normalizedCoverUrl = normalizeCoverUrl(coverUrl);
  const [isImageLoadFailed, setIsImageLoadFailed] = useState(false);

  useEffect(() => {
    setIsImageLoadFailed(false);
  }, [normalizedCoverUrl]);

  const coverImageUrl =
    normalizedCoverUrl !== null && !isImageLoadFailed ? normalizedCoverUrl : null;
  const volumeLabel = formatVolumeNumber(volumeNumber);

  return (
    <div className={styles.candidateCoverArea}>
      {coverImageUrl !== null ? (
        <Image
          alt={`${title} ${volumeLabel} の表紙`}
          className={styles.candidateCoverImage}
          fill
          loader={passthroughImageLoader}
          onError={() => {
            setIsImageLoadFailed(true);
          }}
          sizes="(max-width: 640px) 72vw, 240px"
          src={coverImageUrl}
          unoptimized
        />
      ) : (
        <div aria-hidden="true" className={styles.candidateCoverPlaceholder}>
          <span className={styles.candidateCoverPlaceholderVolume}>{volumeLabel}</span>
          <span className={styles.candidateCoverPlaceholderText}>表紙なし</span>
        </div>
      )}
    </div>
  );
}

function extractErrorMessage(errorPayload: unknown, statusCode: number): string {
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

  return `${DEFAULT_FETCH_ERROR_MESSAGE} (status: ${statusCode})`;
}

function normalizeErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim() !== "") {
    return error.message;
  }

  return DEFAULT_FETCH_ERROR_MESSAGE;
}

function extractRegisterErrorMessage(errorPayload: unknown, statusCode: number): string {
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

  return `${DEFAULT_REGISTER_ERROR_MESSAGE} (status: ${statusCode})`;
}

function extractRegisterErrorCode(errorPayload: unknown): string | null {
  if (
    typeof errorPayload === "object" &&
    errorPayload !== null &&
    "error" in errorPayload &&
    typeof errorPayload.error === "object" &&
    errorPayload.error !== null &&
    "code" in errorPayload.error &&
    typeof errorPayload.error.code === "string"
  ) {
    const errorCode = errorPayload.error.code.trim();
    if (errorCode !== "") {
      return errorCode;
    }
  }

  return null;
}

function extractRegisteredIsbn(payload: unknown): string | null {
  if (
    typeof payload === "object" &&
    payload !== null &&
    "volume" in payload &&
    typeof payload.volume === "object" &&
    payload.volume !== null &&
    "isbn" in payload.volume &&
    typeof payload.volume.isbn === "string"
  ) {
    const normalizedIsbn = payload.volume.isbn.trim();
    if (normalizedIsbn !== "") {
      return normalizedIsbn;
    }
  }

  return null;
}

function extractRegisteredSeriesId(payload: unknown): string | null {
  if (
    typeof payload === "object" &&
    payload !== null &&
    "series" in payload &&
    typeof payload.series === "object" &&
    payload.series !== null &&
    "id" in payload.series &&
    typeof payload.series.id === "number"
  ) {
    return payload.series.id.toString();
  }

  return null;
}

function extractRegisteredVolume(payload: unknown): SeriesVolume | null {
  if (
    typeof payload !== "object" ||
    payload === null ||
    !("volume" in payload) ||
    typeof payload.volume !== "object" ||
    payload.volume === null ||
    !("isbn" in payload.volume) ||
    typeof payload.volume.isbn !== "string" ||
    !("volume_number" in payload.volume) ||
    (typeof payload.volume.volume_number !== "number" && payload.volume.volume_number !== null) ||
    !("cover_url" in payload.volume) ||
    (typeof payload.volume.cover_url !== "string" && payload.volume.cover_url !== null) ||
    !("registered_at" in payload.volume) ||
    typeof payload.volume.registered_at !== "string"
  ) {
    return null;
  }

  const normalizedIsbn = payload.volume.isbn.trim();
  if (normalizedIsbn === "") {
    return null;
  }

  const normalizedRegisteredAt = payload.volume.registered_at.trim();
  if (normalizedRegisteredAt === "") {
    return null;
  }

  return {
    isbn: normalizedIsbn,
    volume_number: payload.volume.volume_number,
    cover_url: payload.volume.cover_url,
    registered_at: normalizedRegisteredAt,
  };
}

function isSeriesCandidate(value: unknown): value is SeriesCandidate {
  return (
    typeof value === "object" &&
    value !== null &&
    "title" in value &&
    typeof value.title === "string" &&
    "author" in value &&
    (typeof value.author === "string" || value.author === null) &&
    "publisher" in value &&
    (typeof value.publisher === "string" || value.publisher === null) &&
    "isbn" in value &&
    typeof value.isbn === "string" &&
    "volume_number" in value &&
    (typeof value.volume_number === "number" || value.volume_number === null) &&
    "cover_url" in value &&
    (typeof value.cover_url === "string" || value.cover_url === null)
  );
}

function pickPreferredSeriesCandidate(
  existingCandidate: SeriesCandidate,
  incomingCandidate: SeriesCandidate
): SeriesCandidate {
  if (existingCandidate.volume_number === null && incomingCandidate.volume_number !== null) {
    return incomingCandidate;
  }

  if (
    existingCandidate.volume_number !== null &&
    incomingCandidate.volume_number !== null &&
    incomingCandidate.volume_number < existingCandidate.volume_number
  ) {
    return incomingCandidate;
  }

  if (existingCandidate.cover_url === null && incomingCandidate.cover_url !== null) {
    return incomingCandidate;
  }

  return existingCandidate;
}

function mergeCandidatesByIsbn(candidates: SeriesCandidate[]): SeriesCandidate[] {
  const mergedCandidatesByIsbn = new Map<string, SeriesCandidate>();

  for (const candidate of candidates) {
    const existingCandidate = mergedCandidatesByIsbn.get(candidate.isbn);
    if (existingCandidate === undefined) {
      mergedCandidatesByIsbn.set(candidate.isbn, candidate);
      continue;
    }

    mergedCandidatesByIsbn.set(
      candidate.isbn,
      pickPreferredSeriesCandidate(existingCandidate, candidate)
    );
  }

  return Array.from(mergedCandidatesByIsbn.values());
}

export function SeriesCandidatesSection({ seriesId }: SeriesCandidatesSectionProps) {
  const router = useRouter();
  const [candidates, setCandidates] = useState<SeriesCandidate[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [selectedCandidate, setSelectedCandidate] = useState<SeriesCandidate | null>(null);
  const [isSubmittingRegister, setIsSubmittingRegister] = useState(false);
  const [registerResultToast, setRegisterResultToast] = useState<RegisterResultToast | null>(null);

  useEffect(() => {
    const abortController = new AbortController();
    let isDisposed = false;

    const fetchCandidates = async () => {
      setIsLoading(true);
      setErrorMessage(null);
      setSelectedCandidate(null);

      try {
        const requestUrl = new URL(`/api/series/${seriesId}/candidates`, API_BASE_URL);
        const response = await fetch(requestUrl.toString(), {
          cache: "no-store",
          signal: abortController.signal,
        });
        if (!response.ok) {
          const errorPayload = (await response.json().catch(() => null)) as unknown;
          throw new Error(extractErrorMessage(errorPayload, response.status));
        }

        const payload = (await response.json()) as unknown;
        if (!Array.isArray(payload) || !payload.every(isSeriesCandidate)) {
          throw new Error(DEFAULT_FETCH_ERROR_MESSAGE);
        }

        if (isDisposed || abortController.signal.aborted) {
          return;
        }

        setCandidates(mergeCandidatesByIsbn(payload));
      } catch (error) {
        if (isDisposed || abortController.signal.aborted) {
          return;
        }

        setCandidates([]);
        setErrorMessage(normalizeErrorMessage(error));
      } finally {
        if (!isDisposed && !abortController.signal.aborted) {
          setIsLoading(false);
        }
      }
    };

    void fetchCandidates();

    return () => {
      isDisposed = true;
      abortController.abort();
    };
  }, [reloadKey, seriesId]);

  useEffect(() => {
    if (selectedCandidate === null) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !isSubmittingRegister) {
        setSelectedCandidate(null);
      }
    };

    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isSubmittingRegister, selectedCandidate]);

  useEffect(() => {
    if (registerResultToast === null) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      setRegisterResultToast((currentToast) => {
        if (currentToast === null || currentToast.id !== registerResultToast.id) {
          return currentToast;
        }

        return null;
      });
    }, REGISTER_RESULT_TOAST_DURATION_MILLISECONDS);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [registerResultToast]);

  const showRegisterResultToast = (tone: RegisterResultToast["tone"], message: string) => {
    setRegisterResultToast({
      id: Date.now(),
      tone,
      message,
    });
  };

  const closeCandidateModal = () => {
    if (isSubmittingRegister) {
      return;
    }

    setSelectedCandidate(null);
  };

  const registerCandidate = async () => {
    if (selectedCandidate === null || isSubmittingRegister) {
      return;
    }

    const targetCandidate = selectedCandidate;
    setIsSubmittingRegister(true);

    try {
      const response = await fetch(new URL("/api/volumes", API_BASE_URL).toString(), {
        body: JSON.stringify({
          isbn: targetCandidate.isbn,
        }),
        headers: {
          "Content-Type": "application/json",
        },
        method: "POST",
      });

      if (!response.ok) {
        const errorPayload = (await response.json().catch(() => null)) as unknown;
        const registerErrorCode = extractRegisterErrorCode(errorPayload);

        if (response.status === 409 && registerErrorCode === "VOLUME_ALREADY_EXISTS") {
          showRegisterResultToast("info", `ISBN: ${targetCandidate.isbn} は既に登録済みです。`);
          setCandidates((currentCandidates) =>
            currentCandidates.filter((candidate) => candidate.isbn !== targetCandidate.isbn)
          );
          setSelectedCandidate(null);
          setReloadKey((currentValue) => currentValue + 1);
          router.refresh();
          return;
        }

        showRegisterResultToast(
          "error",
          extractRegisterErrorMessage(errorPayload, response.status)
        );
        return;
      }

      const successPayload = (await response.json().catch(() => null)) as unknown;
      const registeredIsbn = extractRegisteredIsbn(successPayload) ?? targetCandidate.isbn;
      const registeredSeriesId = extractRegisteredSeriesId(successPayload);
      const registeredVolume = extractRegisteredVolume(successPayload);
      showRegisterResultToast("success", `登録しました（ISBN: ${registeredIsbn}）。`);
      setCandidates((currentCandidates) =>
        currentCandidates.filter((candidate) => candidate.isbn !== targetCandidate.isbn)
      );
      setSelectedCandidate(null);
      setReloadKey((currentValue) => currentValue + 1);
      if (registeredSeriesId === seriesId && registeredVolume !== null) {
        publishSeriesVolumeRegistered({
          seriesId: registeredSeriesId,
          volume: registeredVolume,
        });
      }
      publishLibraryRefreshSignal();
      router.refresh();
    } catch {
      showRegisterResultToast("error", REGISTER_REQUEST_ERROR_MESSAGE);
    } finally {
      setIsSubmittingRegister(false);
    }
  };

  if (isLoading) {
    return (
      <section className={styles.volumeSection}>
        <h2 className={styles.sectionTitle}>未登録候補</h2>
        <div aria-live="polite" className={styles.loadingPanel} role="status">
          <p className={styles.loadingText}>未登録候補を取得しています。</p>
        </div>
      </section>
    );
  }

  if (errorMessage !== null) {
    return (
      <section className={styles.volumeSection}>
        <h2 className={styles.sectionTitle}>未登録候補</h2>
        <div aria-live="assertive" className={styles.errorPanel} role="alert">
          <p className={styles.errorText}>未登録候補の取得に失敗しました。</p>
          <p className={styles.errorDetail}>詳細: {errorMessage}</p>
          <div className={styles.errorActions}>
            <button
              className={styles.retryButton}
              onClick={() => {
                setReloadKey((currentValue) => currentValue + 1);
              }}
              type="button"
            >
              再試行
            </button>
          </div>
        </div>
      </section>
    );
  }

  if (candidates.length === 0) {
    return (
      <section className={styles.volumeSection}>
        <h2 className={styles.sectionTitle}>未登録候補</h2>
        <div aria-live="polite" className={styles.placeholderPanel} role="status">
          <p className={styles.placeholderText}>未登録候補はありません。</p>
        </div>
        {registerResultToast !== null ? (
          <div
            aria-live={registerResultToast.tone === "error" ? "assertive" : "polite"}
            className={`${styles.registerResultToast} ${
              registerResultToast.tone === "success"
                ? styles.registerResultToastSuccess
                : registerResultToast.tone === "info"
                  ? styles.registerResultToastInfo
                  : styles.registerResultToastError
            }`}
            role={registerResultToast.tone === "error" ? "alert" : "status"}
          >
            <p className={styles.registerResultToastTitle}>
              {registerResultToast.tone === "success"
                ? "登録成功"
                : registerResultToast.tone === "info"
                  ? "登録済み"
                  : "登録失敗"}
            </p>
            <p className={styles.registerResultToastMessage}>{registerResultToast.message}</p>
            <button
              className={styles.registerResultToastCloseButton}
              onClick={() => {
                setRegisterResultToast(null);
              }}
              type="button"
            >
              閉じる
            </button>
          </div>
        ) : null}
      </section>
    );
  }

  return (
    <section className={styles.volumeSection}>
      <h2 className={styles.sectionTitle}>未登録候補</h2>
      <ul className={styles.candidateList}>
        {candidates.map((candidate) => (
          <li className={styles.candidateListItem} key={candidate.isbn}>
            <article
              className={`${styles.volumeCard} ${styles.candidateCardInteractive}`}
              onClick={() => {
                setSelectedCandidate(candidate);
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  setSelectedCandidate(candidate);
                }
              }}
              role="button"
              tabIndex={0}
            >
              <CandidateCover
                coverUrl={candidate.cover_url}
                title={candidate.title}
                volumeNumber={candidate.volume_number}
              />
              <h3 className={styles.candidateTitle}>{candidate.title}</h3>
              <p className={styles.volumeNumber}>{formatVolumeNumber(candidate.volume_number)}</p>
              <dl className={styles.candidateMetaList}>
                <div className={styles.candidateMetaRow}>
                  <dt className={styles.candidateMetaLabel}>著者</dt>
                  <dd className={styles.candidateMetaValue}>{candidate.author ?? "不明"}</dd>
                </div>
                <div className={styles.candidateMetaRow}>
                  <dt className={styles.candidateMetaLabel}>出版社</dt>
                  <dd className={styles.candidateMetaValue}>{candidate.publisher ?? "不明"}</dd>
                </div>
              </dl>
              <p className={styles.volumeMeta}>ISBN: {candidate.isbn}</p>
            </article>
          </li>
        ))}
      </ul>

      {selectedCandidate !== null ? (
        <div
          className={styles.candidateModalOverlay}
          onClick={() => {
            closeCandidateModal();
          }}
          role="presentation"
        >
          <div
            aria-labelledby={`candidate-detail-title-${selectedCandidate.isbn}`}
            aria-modal="true"
            className={styles.candidateModal}
            onClick={(event) => {
              event.stopPropagation();
            }}
            role="dialog"
          >
            <header className={styles.candidateModalHeader}>
              <h3
                className={styles.candidateModalTitle}
                id={`candidate-detail-title-${selectedCandidate.isbn}`}
              >
                候補詳細
              </h3>
            </header>
            <dl className={styles.candidateModalMetaList}>
              <div className={styles.candidateModalMetaRow}>
                <dt className={styles.candidateModalMetaLabel}>タイトル</dt>
                <dd className={styles.candidateModalMetaValue}>{selectedCandidate.title}</dd>
              </div>
              <div className={styles.candidateModalMetaRow}>
                <dt className={styles.candidateModalMetaLabel}>著者</dt>
                <dd className={styles.candidateModalMetaValue}>
                  {selectedCandidate.author ?? "不明"}
                </dd>
              </div>
              <div className={styles.candidateModalMetaRow}>
                <dt className={styles.candidateModalMetaLabel}>出版社</dt>
                <dd className={styles.candidateModalMetaValue}>
                  {selectedCandidate.publisher ?? "不明"}
                </dd>
              </div>
              <div className={styles.candidateModalMetaRow}>
                <dt className={styles.candidateModalMetaLabel}>巻数</dt>
                <dd className={styles.candidateModalMetaValue}>
                  {formatVolumeNumber(selectedCandidate.volume_number)}
                </dd>
              </div>
              <div className={styles.candidateModalMetaRow}>
                <dt className={styles.candidateModalMetaLabel}>ISBN</dt>
                <dd className={styles.candidateModalMetaValue}>{selectedCandidate.isbn}</dd>
              </div>
              <div className={styles.candidateModalMetaRow}>
                <dt className={styles.candidateModalMetaLabel}>表紙URL</dt>
                <dd className={styles.candidateModalMetaValue}>
                  {selectedCandidate.cover_url === null ? (
                    "不明"
                  ) : (
                    <a
                      className={styles.candidateModalCoverLink}
                      href={selectedCandidate.cover_url}
                      rel="noopener noreferrer"
                      target="_blank"
                    >
                      {selectedCandidate.cover_url}
                    </a>
                  )}
                </dd>
              </div>
            </dl>
            <p className={styles.candidateModalDescription}>この候補を登録しますか？</p>
            <div className={styles.candidateModalActions}>
              <button
                className={styles.candidateModalSubmitButton}
                onClick={() => {
                  void registerCandidate();
                }}
                type="button"
                disabled={isSubmittingRegister}
              >
                {isSubmittingRegister ? "登録中..." : "登録する"}
              </button>
              <button
                className={styles.candidateModalCancelButton}
                onClick={() => {
                  closeCandidateModal();
                }}
                type="button"
                disabled={isSubmittingRegister}
              >
                しない
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {registerResultToast !== null ? (
        <div
          aria-live={registerResultToast.tone === "error" ? "assertive" : "polite"}
          className={`${styles.registerResultToast} ${
            registerResultToast.tone === "success"
              ? styles.registerResultToastSuccess
              : registerResultToast.tone === "info"
                ? styles.registerResultToastInfo
                : styles.registerResultToastError
          }`}
          role={registerResultToast.tone === "error" ? "alert" : "status"}
        >
          <p className={styles.registerResultToastTitle}>
            {registerResultToast.tone === "success"
              ? "登録成功"
              : registerResultToast.tone === "info"
                ? "登録済み"
                : "登録失敗"}
          </p>
          <p className={styles.registerResultToastMessage}>{registerResultToast.message}</p>
          <button
            className={styles.registerResultToastCloseButton}
            onClick={() => {
              setRegisterResultToast(null);
            }}
            type="button"
          >
            閉じる
          </button>
        </div>
      ) : null}
    </section>
  );
}
