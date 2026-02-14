"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { consumeLibraryRefreshSignal } from "@/lib/libraryRefreshSignal";
import { LibrarySeriesCard } from "./LibrarySeriesCard";
import styles from "./LibraryTabPage.module.css";

type LibrarySeries = {
  id: number;
  title: string;
  author: string | null;
  publisher: string | null;
  representative_cover_url: string | null;
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const DEFAULT_ERROR_MESSAGE = "ライブラリの取得に失敗しました。";
// 入力停止後300ms待って検索し、タイプ中の過剰リクエストを抑える。
const SEARCH_DEBOUNCE_MS = 300;

function isNullableString(value: unknown): value is string | null {
  return typeof value === "string" || value === null;
}

function isLibrarySeries(value: unknown): value is LibrarySeries {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const candidate = value as Record<string, unknown>;

  return (
    Number.isInteger(candidate.id) &&
    typeof candidate.id === "number" &&
    candidate.id > 0 &&
    typeof candidate.title === "string" &&
    candidate.title.trim() !== "" &&
    isNullableString(candidate.author) &&
    isNullableString(candidate.publisher) &&
    isNullableString(candidate.representative_cover_url)
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

  return `${DEFAULT_ERROR_MESSAGE} (status: ${statusCode})`;
}

export function LibraryTabPage() {
  const [seriesList, setSeriesList] = useState<LibrarySeries[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [searchKeyword, setSearchKeyword] = useState("");
  const [debouncedSearchKeyword, setDebouncedSearchKeyword] = useState("");
  const normalizedSearchKeyword = debouncedSearchKeyword.trim();

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      setDebouncedSearchKeyword(searchKeyword);
    }, SEARCH_DEBOUNCE_MS);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [searchKeyword]);

  useEffect(() => {
    const abortController = new AbortController();

    const fetchLibrary = async () => {
      setIsLoading(true);
      setErrorMessage(null);

      try {
        const requestUrl = new URL("/api/library", API_BASE_URL);
        if (normalizedSearchKeyword !== "") {
          requestUrl.searchParams.set("q", normalizedSearchKeyword);
        }

        const response = await fetch(requestUrl.toString(), { signal: abortController.signal });
        if (!response.ok) {
          const errorPayload = (await response.json().catch(() => null)) as unknown;
          throw new Error(extractErrorMessage(errorPayload, response.status));
        }

        const payload = (await response.json()) as unknown;
        if (!Array.isArray(payload) || !payload.every(isLibrarySeries)) {
          throw new Error(DEFAULT_ERROR_MESSAGE);
        }

        if (!abortController.signal.aborted) {
          setSeriesList(payload);
        }
      } catch (error) {
        if (abortController.signal.aborted) {
          return;
        }

        setSeriesList([]);
        if (error instanceof Error && error.message.trim() !== "") {
          setErrorMessage(error.message);
        } else {
          setErrorMessage(DEFAULT_ERROR_MESSAGE);
        }
      } finally {
        if (!abortController.signal.aborted) {
          setIsLoading(false);
        }
      }
    };

    void fetchLibrary();

    return () => {
      abortController.abort();
    };
  }, [normalizedSearchKeyword, reloadKey]);

  const reloadLibrary = useCallback(() => {
    setReloadKey((currentValue) => currentValue + 1);
  }, []);

  useEffect(() => {
    const refreshLibraryIfNeeded = () => {
      if (consumeLibraryRefreshSignal()) {
        reloadLibrary();
      }
    };

    refreshLibraryIfNeeded();
    window.addEventListener("focus", refreshLibraryIfNeeded);
    window.addEventListener("pageshow", refreshLibraryIfNeeded);

    return () => {
      window.removeEventListener("focus", refreshLibraryIfNeeded);
      window.removeEventListener("pageshow", refreshLibraryIfNeeded);
    };
  }, [reloadLibrary]);

  return (
    <main className={styles.page}>
      <div className={styles.container}>
        <header className={styles.header}>
          <h1 className={styles.title}>ライブラリ</h1>
          <Link className={styles.registerButton} href="/library/register">
            登録
          </Link>
        </header>

        <section className={`${styles.section} ${styles.searchSection}`}>
          <label className={styles.searchLabel} htmlFor="librarySearchInput">
            所持内検索
          </label>
          <input
            aria-label="所持内検索"
            className={styles.searchInput}
            id="librarySearchInput"
            onChange={(event) => {
              setSearchKeyword(event.target.value);
            }}
            placeholder="タイトル・著者で検索"
            type="text"
            value={searchKeyword}
          />
        </section>

        <nav aria-label="メインタブ" className={styles.tabs}>
          <span className={`${styles.tab} ${styles.tabActive}`}>ライブラリ</span>
          <Link className={`${styles.tab} ${styles.tabInactive}`} href="/search">
            検索
          </Link>
        </nav>

        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>シリーズ一覧</h2>
          <div className={styles.seriesContent}>
            {isLoading && (
              <div aria-live="polite" className={styles.statePanel} role="status">
                <p className={styles.statusText}>読み込み中...</p>
              </div>
            )}
            {!isLoading && errorMessage !== null && (
              <div aria-live="polite" className={styles.statePanel} role="status">
                <p className={styles.errorText}>{errorMessage}</p>
                <button className={styles.retryButton} onClick={reloadLibrary} type="button">
                  再試行
                </button>
              </div>
            )}
            {!isLoading && errorMessage === null && seriesList.length === 0 && (
              <div aria-live="polite" className={styles.statePanel} role="status">
                <p className={styles.statusText}>
                  {normalizedSearchKeyword === ""
                    ? "シリーズが登録されていません。"
                    : "検索条件に一致するシリーズがありません。"}
                </p>
              </div>
            )}
            {!isLoading && errorMessage === null && seriesList.length > 0 && (
              <div className={styles.seriesGrid}>
                {seriesList.map((series) => (
                  <LibrarySeriesCard
                    detailPageUrl={`/library/${series.id}`}
                    key={series.id}
                    representativeCoverUrl={series.representative_cover_url}
                    title={series.title}
                  />
                ))}
              </div>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
