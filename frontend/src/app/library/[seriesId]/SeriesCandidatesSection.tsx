"use client";

import { useEffect, useState } from "react";
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
  const [candidates, setCandidates] = useState<SeriesCandidate[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const abortController = new AbortController();
    let isDisposed = false;

    const fetchCandidates = async () => {
      setIsLoading(true);
      setErrorMessage(null);

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
      </section>
    );
  }

  return (
    <section className={styles.volumeSection}>
      <h2 className={styles.sectionTitle}>未登録候補</h2>
      <ul className={styles.candidateList}>
        {candidates.map((candidate) => (
          <li className={styles.candidateListItem} key={candidate.isbn}>
            <article className={styles.volumeCard}>
              <h3 className={styles.candidateTitle}>{candidate.title}</h3>
              <p className={styles.volumeNumber}>
                {candidate.volume_number === null ? "巻数不明" : `${candidate.volume_number}巻`}
              </p>
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
    </section>
  );
}
