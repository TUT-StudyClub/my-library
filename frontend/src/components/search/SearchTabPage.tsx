"use client";

import Link from "next/link";
import { type FormEvent, useRef, useState } from "react";
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
type RegisterFeedbackTone = "success" | "info" | "error";
type RegisterFeedback = {
  tone: RegisterFeedbackTone;
  title: string;
  message: string;
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const DEFAULT_SEARCH_ERROR_MESSAGE = "検索に失敗しました。";
const DEFAULT_REGISTER_ERROR_MESSAGE = "登録に失敗しました。";
const REGISTER_REQUEST_ERROR_MESSAGE = "登録リクエストの送信に失敗しました。";
const REGISTER_SUCCESS_MESSAGE = "登録完了";
const REGISTER_ALREADY_EXISTS_MESSAGE = "このISBNは既に登録済みです。";
const REGISTER_RESULT_SUCCESS_TITLE = "登録結果: 成功";
const REGISTER_RESULT_ALREADY_EXISTS_TITLE = "登録結果: 登録済み";
const REGISTER_RESULT_FAILURE_TITLE = "登録結果: 失敗";
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

  if (candidate.owned === true) {
    return "所持済みのため登録不要です。";
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
    const code = errorPayload.error.code.trim();
    if (code !== "") {
      return code;
    }
  }

  return null;
}

function extractRegisterConflictIsbn(errorPayload: unknown): string | null {
  if (
    typeof errorPayload === "object" &&
    errorPayload !== null &&
    "error" in errorPayload &&
    typeof errorPayload.error === "object" &&
    errorPayload.error !== null &&
    "details" in errorPayload.error &&
    typeof errorPayload.error.details === "object" &&
    errorPayload.error.details !== null &&
    "isbn" in errorPayload.error.details &&
    typeof errorPayload.error.details.isbn === "string"
  ) {
    const isbn = errorPayload.error.details.isbn.trim();
    if (isbn !== "") {
      return isbn;
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
    const isbn = payload.volume.isbn.trim();
    if (isbn !== "") {
      return isbn;
    }
  }

  return null;
}

function extractRegisteredSeriesTitle(payload: unknown): string | null {
  if (
    typeof payload === "object" &&
    payload !== null &&
    "series" in payload &&
    typeof payload.series === "object" &&
    payload.series !== null &&
    "title" in payload.series &&
    typeof payload.series.title === "string"
  ) {
    const title = payload.series.title.trim();
    if (title !== "") {
      return title;
    }
  }

  return null;
}

function getCandidateKey(candidate: CatalogSearchCandidate, index: number): string {
  return `${candidate.isbn ?? "unknown"}-${index}`;
}

function markCandidatesOwnedByIsbn(
  currentCandidates: CatalogSearchCandidate[],
  targetCandidateKey: string,
  requestedIsbn: string,
  matchedIsbn: string | null
): CatalogSearchCandidate[] {
  return currentCandidates.map((currentCandidate, currentIndex) => {
    const currentCandidateKey = getCandidateKey(currentCandidate, currentIndex);
    if (currentCandidateKey === targetCandidateKey) {
      return {
        ...currentCandidate,
        owned: true,
      };
    }

    if (
      currentCandidate.isbn === requestedIsbn ||
      (matchedIsbn !== null && currentCandidate.isbn === matchedIsbn)
    ) {
      return {
        ...currentCandidate,
        owned: true,
      };
    }

    return currentCandidate;
  });
}

export function SearchTabPage() {
  const [query, setQuery] = useState("");
  const [executedQuery, setExecutedQuery] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<CatalogSearchCandidate[]>([]);
  const [registeringCandidateKey, setRegisteringCandidateKey] = useState<string | null>(null);
  const [registerFeedbackByCandidateKey, setRegisterFeedbackByCandidateKey] = useState<
    Record<string, RegisterFeedback>
  >({});
  const isRegisteringRef = useRef(false);

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
    setRegisteringCandidateKey(null);
    setRegisterFeedbackByCandidateKey({});

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

  const registerCandidate = async (candidate: CatalogSearchCandidate, candidateKey: string) => {
    if (
      candidate.owned !== false ||
      candidate.isbn === null ||
      registeringCandidateKey !== null ||
      isRegisteringRef.current
    ) {
      return;
    }

    const requestIsbn = candidate.isbn;
    isRegisteringRef.current = true;
    setRegisteringCandidateKey(candidateKey);
    setRegisterFeedbackByCandidateKey((currentValue) => {
      const nextValue = { ...currentValue };
      delete nextValue[candidateKey];
      return nextValue;
    });

    try {
      const response = await fetch(new URL("/api/volumes", API_BASE_URL).toString(), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          isbn: requestIsbn,
        }),
      });

      if (!response.ok) {
        const errorPayload = (await response.json().catch(() => null)) as unknown;
        const registerErrorCode = extractRegisterErrorCode(errorPayload);
        if (response.status === 409 && registerErrorCode === "VOLUME_ALREADY_EXISTS") {
          const conflictIsbn = extractRegisterConflictIsbn(errorPayload);
          setCandidates((currentCandidates) =>
            markCandidatesOwnedByIsbn(currentCandidates, candidateKey, requestIsbn, conflictIsbn)
          );
          setRegisterFeedbackByCandidateKey((currentValue) => ({
            ...currentValue,
            [candidateKey]: {
              tone: "info",
              title: REGISTER_RESULT_ALREADY_EXISTS_TITLE,
              message: REGISTER_ALREADY_EXISTS_MESSAGE,
            },
          }));
          return;
        }

        setRegisterFeedbackByCandidateKey((currentValue) => ({
          ...currentValue,
          [candidateKey]: {
            tone: "error",
            title: REGISTER_RESULT_FAILURE_TITLE,
            message: extractRegisterErrorMessage(errorPayload, response.status),
          },
        }));
        return;
      }

      const successPayload = (await response.json().catch(() => null)) as unknown;
      const registeredIsbn = extractRegisteredIsbn(successPayload) ?? requestIsbn;
      const registeredSeriesTitle = extractRegisteredSeriesTitle(successPayload);
      const successMessage =
        registeredSeriesTitle === null
          ? `${REGISTER_SUCCESS_MESSAGE}（ISBN: ${registeredIsbn}）`
          : `${REGISTER_SUCCESS_MESSAGE}（${registeredSeriesTitle} / ISBN: ${registeredIsbn}）`;

      setCandidates((currentCandidates) =>
        markCandidatesOwnedByIsbn(currentCandidates, candidateKey, requestIsbn, registeredIsbn)
      );
      setRegisterFeedbackByCandidateKey((currentValue) => ({
        ...currentValue,
        [candidateKey]: {
          tone: "success",
          title: REGISTER_RESULT_SUCCESS_TITLE,
          message: successMessage,
        },
      }));
    } catch {
      setRegisterFeedbackByCandidateKey((currentValue) => ({
        ...currentValue,
        [candidateKey]: {
          tone: "error",
          title: REGISTER_RESULT_FAILURE_TITLE,
          message: REGISTER_REQUEST_ERROR_MESSAGE,
        },
      }));
    } finally {
      isRegisteringRef.current = false;
      setRegisteringCandidateKey((currentValue) =>
        currentValue === candidateKey ? null : currentValue
      );
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
          <div aria-live="polite" className={statePanelClassName}>
            {searchResultStatus === "success" && (
              <>
                <p className={styles.resultSummary}>
                  「{displayedQuery}」の検索結果: {candidates.length} 件
                </p>
                <ul className={styles.resultList}>
                  {candidates.map((candidate, index) => {
                    const candidateKey = getCandidateKey(candidate, index);
                    const canRegisterCandidate =
                      candidate.owned === false && candidate.isbn !== null;
                    const registerFeedback = registerFeedbackByCandidateKey[candidateKey];
                    const registerFeedbackClassName =
                      registerFeedback === undefined
                        ? null
                        : registerFeedback.tone === "success"
                          ? `${styles.registerFeedbackPanel} ${styles.registerFeedbackSuccess}`
                          : registerFeedback.tone === "info"
                            ? `${styles.registerFeedbackPanel} ${styles.registerFeedbackInfo}`
                            : `${styles.registerFeedbackPanel} ${styles.registerFeedbackError}`;

                    return (
                      <li className={styles.resultItem} key={candidateKey}>
                        <p className={styles.resultTitle}>{candidate.title}</p>
                        <p className={styles.statusText}>
                          所持判定: {getCandidateOwnedLabel(candidate)}
                        </p>
                        <p className={styles.statusDetail}>
                          {getRegistrationAvailabilityLabel(candidate)}
                        </p>
                        {canRegisterCandidate && (
                          <p className={styles.registerActionRow}>
                            <button
                              className={styles.registerActionButton}
                              disabled={registeringCandidateKey !== null}
                              onClick={() => {
                                void registerCandidate(candidate, candidateKey);
                              }}
                              type="button"
                            >
                              {registeringCandidateKey === candidateKey ? "登録中..." : "登録する"}
                            </button>
                          </p>
                        )}
                        {registerFeedbackClassName !== null && (
                          <div
                            aria-live="polite"
                            className={registerFeedbackClassName}
                            role={registerFeedback?.tone === "error" ? "alert" : "status"}
                          >
                            <p className={styles.registerFeedbackTitle}>{registerFeedback.title}</p>
                            <p className={styles.registerFeedbackMessage}>
                              {registerFeedback.message}
                            </p>
                          </div>
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
