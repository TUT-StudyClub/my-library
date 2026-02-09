"use client";

import Link from "next/link";
import { type FormEvent, useState } from "react";
import styles from "./SearchTabPage.module.css";

type CatalogSearchCandidate = {
  owned: true | false | "unknown";
  title: string;
  author: string | null;
  publisher: string | null;
  isbn: string | null;
  volume_number: number | null;
  cover_url: string | null;
};

type SearchResultStatus = "idle" | "loading" | "error" | "empty" | "success";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const DEFAULT_SEARCH_ERROR_MESSAGE = "検索に失敗しました。";
const SEARCH_LIMIT = 20;

function getOwnedLabel(owned: CatalogSearchCandidate["owned"]): string {
  if (owned === true) {
    return "所持済み";
  }

  if (owned === false) {
    return "未所持";
  }

  return "判定不可（ISBN不明）";
}

function getCandidateOwnedLabel(candidate: CatalogSearchCandidate): string {
  if (candidate.isbn === null) {
    return "判定不可（ISBN不明）";
  }

  return getOwnedLabel(candidate.owned);
}

function getRegistrationAvailabilityLabel(candidate: CatalogSearchCandidate): string {
  if (candidate.isbn === null) {
    return "ISBNがないため、この候補は登録できません。";
  }

  if (candidate.owned === false) {
    return "未所持のため登録できます。";
  }

  return "ISBNあり";
}

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
  const displayedQuery = executedQuery ?? "";

  let searchResultStatus: SearchResultStatus = "idle";
  if (isLoading) {
    searchResultStatus = "loading";
  } else if (errorMessage !== null) {
    searchResultStatus = "error";
  } else if (executedQuery === null) {
    searchResultStatus = "idle";
  } else if (candidates.length === 0) {
    searchResultStatus = "empty";
  } else {
    searchResultStatus = "success";
  }

  const statePanelClassName =
    searchResultStatus === "success"
      ? `${styles.statePanel} ${styles.statePanelList}`
      : searchResultStatus === "loading"
        ? `${styles.statePanel} ${styles.statePanelLoading}`
        : searchResultStatus === "empty"
          ? `${styles.statePanel} ${styles.statePanelEmpty}`
          : searchResultStatus === "error"
            ? `${styles.statePanel} ${styles.statePanelError}`
            : `${styles.statePanel} ${styles.statePanelIdle}`;

  const executeSearch = async (searchQuery: string) => {
    setExecutedQuery(searchQuery);
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const requestUrl = new URL("/api/catalog/search", API_BASE_URL);
      requestUrl.searchParams.set("q", searchQuery);
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

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (normalizedQuery === "") {
      setValidationError("キーワードを入力してください。");
      return;
    }

    setValidationError(null);
    void executeSearch(normalizedQuery);
  };

  const handleRetry = () => {
    if (executedQuery === null || isLoading) {
      return;
    }

    void executeSearch(executedQuery);
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
          <div aria-live="polite" className={statePanelClassName}>
            {searchResultStatus === "success" && (
              <>
                <p className={styles.resultSummary}>
                  「{displayedQuery}」の検索結果: {candidates.length} 件
                </p>
                <ul className={styles.resultList}>
                  {candidates.map((candidate, index) => {
                    const registerPageUrl =
                      candidate.owned === false && candidate.isbn !== null
                        ? `/library/register?isbn=${encodeURIComponent(candidate.isbn)}`
                        : null;

                    return (
                      <li
                        className={styles.resultItem}
                        key={`${candidate.isbn ?? "unknown"}-${index}`}
                      >
                        <p className={styles.resultTitle}>{candidate.title}</p>
                        <p className={styles.statusText}>
                          所持判定: {getCandidateOwnedLabel(candidate)}
                        </p>
                        <p className={styles.statusDetail}>
                          {getRegistrationAvailabilityLabel(candidate)}
                        </p>
                        {registerPageUrl !== null && (
                          <p className={styles.registerActionRow}>
                            <Link className={styles.registerActionButton} href={registerPageUrl}>
                              登録を開始
                            </Link>
                          </p>
                        )}
                        <p className={styles.resultMeta}>
                          著者: {candidate.author ?? "不明"} / 出版社:{" "}
                          {candidate.publisher ?? "不明"} / ISBN: {candidate.isbn ?? "不明"} / 巻数:{" "}
                          {candidate.volume_number ?? "不明"}
                        </p>
                      </li>
                    );
                  })}
                </ul>
              </>
            )}

            {searchResultStatus === "idle" && (
              <div className={styles.stateContent}>
                <p className={styles.stateTitle}>検索待機中</p>
                <p className={styles.stateDescription}>
                  キーワードを入力して「検索」を押すか、Enter キーで実行してください。
                </p>
              </div>
            )}

            {searchResultStatus === "loading" && (
              <div className={styles.stateContent}>
                <p className={styles.stateTitle}>検索中...</p>
                <p className={styles.stateDescription}>NDL Search から候補を取得しています。</p>
              </div>
            )}

            {searchResultStatus === "empty" && (
              <div className={styles.stateContent}>
                <p className={styles.stateTitle}>候補が見つかりませんでした</p>
                <p className={styles.stateDescription}>
                  「{displayedQuery}」に一致する候補は0件でした。別のキーワードでお試しください。
                </p>
              </div>
            )}

            {searchResultStatus === "error" && (
              <div className={styles.stateContent}>
                <p className={styles.stateTitle}>取得に失敗しました</p>
                <p className={`${styles.stateDescription} ${styles.stateDescriptionError}`}>
                  {errorMessage ?? DEFAULT_SEARCH_ERROR_MESSAGE}
                </p>
                <button className={styles.retryButton} onClick={handleRetry} type="button">
                  再試行
                </button>
              </div>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
