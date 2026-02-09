"use client";

import Link from "next/link";
import { type FormEvent, useState } from "react";
import styles from "./SearchTabPage.module.css";

type CatalogSearchCandidate = {
  title: string;
  author: string | null;
  publisher: string | null;
  isbn: string | null;
  volume_number: number | null;
  cover_url: string | null;
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const DEFAULT_SEARCH_ERROR_MESSAGE = "検索に失敗しました。";
const SEARCH_LIMIT = 20;

function extractSearchErrorMessage(errorPayload: unknown, statusCode: number): string {
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

  return `${DEFAULT_SEARCH_ERROR_MESSAGE} (status: ${statusCode})`;
}

export function SearchTabPage() {
  const [query, setQuery] = useState("");
  const [executedQuery, setExecutedQuery] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<CatalogSearchCandidate[]>([]);

  const normalizedQuery = query.trim();

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (normalizedQuery === "") {
      setValidationError("キーワードを入力してください。");
      return;
    }

    setValidationError(null);
    setExecutedQuery(normalizedQuery);

    setIsLoading(true);
    setErrorMessage(null);

    try {
      const requestUrl = new URL("/api/catalog/search", API_BASE_URL);
      requestUrl.searchParams.set("q", normalizedQuery);
      requestUrl.searchParams.set("limit", String(SEARCH_LIMIT));

      const response = await fetch(requestUrl.toString());
      if (!response.ok) {
        const errorPayload = (await response.json().catch(() => null)) as unknown;
        throw new Error(extractSearchErrorMessage(errorPayload, response.status));
      }

      const payload = (await response.json()) as unknown;
      if (!Array.isArray(payload)) {
        throw new Error(DEFAULT_SEARCH_ERROR_MESSAGE);
      }

      setCandidates(payload as CatalogSearchCandidate[]);
    } catch (error) {
      setCandidates([]);
      if (error instanceof Error && error.message.trim() !== "") {
        setErrorMessage(error.message);
      } else {
        setErrorMessage(DEFAULT_SEARCH_ERROR_MESSAGE);
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className={styles.page}>
      <div className={styles.container}>
        <header className={styles.header}>
          <h1 className={styles.title}>検索</h1>
        </header>

        <nav aria-label="メインタブ" className={styles.tabs}>
          <Link className={`${styles.tab} ${styles.tabInactive}`} href="/library">
            ライブラリ
          </Link>
          <span className={`${styles.tab} ${styles.tabActive}`}>検索</span>
        </nav>

        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>外部検索</h2>
          <form className={styles.searchForm} onSubmit={handleSubmit}>
            <label className={styles.searchLabel} htmlFor="catalogSearchInput">
              キーワード
            </label>
            <div className={styles.searchRow}>
              <input
                aria-label="外部検索キーワード"
                className={styles.searchInput}
                id="catalogSearchInput"
                onChange={(event) => {
                  setQuery(event.target.value);
                  if (validationError !== null || errorMessage !== null) {
                    setValidationError(null);
                    setErrorMessage(null);
                  }
                }}
                placeholder="作品名・著者名などを入力"
                type="text"
                value={query}
              />
              <button
                className={styles.searchButton}
                disabled={normalizedQuery === "" || isLoading}
                type="submit"
              >
                {isLoading ? "検索中..." : "検索"}
              </button>
            </div>
          </form>
          <p className={styles.helperText}>Enter キーでも実行できます。</p>
          {validationError !== null && (
            <p aria-live="polite" className={styles.errorText} role="alert">
              {validationError}
            </p>
          )}
        </section>

        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>検索結果</h2>
          <div aria-live="polite" className={styles.statePanel}>
            {isLoading && <p className={styles.statusText}>検索中...</p>}
            {!isLoading && errorMessage !== null && (
              <p className={styles.errorText}>{errorMessage}</p>
            )}
            {!isLoading && errorMessage === null && executedQuery === null && (
              <p className={styles.statusText}>クエリを入力して検索を実行してください。</p>
            )}
            {!isLoading &&
              errorMessage === null &&
              executedQuery !== null &&
              candidates.length === 0 && (
                <p className={styles.statusText}>
                  「{executedQuery}」に一致する候補は見つかりませんでした。
                </p>
              )}
            {!isLoading && errorMessage === null && candidates.length > 0 && (
              <ul className={styles.resultList}>
                {candidates.map((candidate, index) => (
                  <li className={styles.resultItem} key={`${candidate.isbn ?? "unknown"}-${index}`}>
                    <p className={styles.resultTitle}>{candidate.title}</p>
                    <p className={styles.resultMeta}>
                      著者: {candidate.author ?? "不明"} / 出版社: {candidate.publisher ?? "不明"} /
                      ISBN:
                      {candidate.isbn ?? "不明"} / 巻数: {candidate.volume_number ?? "不明"}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
