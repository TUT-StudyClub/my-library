"use client";

import { useEffect, useState } from "react";
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

  useEffect(() => {
    let isCancelled = false;

    const fetchLibrary = async () => {
      setIsLoading(true);
      setErrorMessage(null);

      try {
        const response = await fetch(`${API_BASE_URL}/api/library`);
        if (!response.ok) {
          const errorPayload = (await response.json().catch(() => null)) as unknown;
          throw new Error(extractErrorMessage(errorPayload, response.status));
        }

        const payload = (await response.json()) as unknown;
        if (!Array.isArray(payload)) {
          throw new Error(DEFAULT_ERROR_MESSAGE);
        }

        if (!isCancelled) {
          setSeriesList(payload as LibrarySeries[]);
        }
      } catch (error) {
        if (!isCancelled) {
          setSeriesList([]);
          if (error instanceof Error && error.message.trim() !== "") {
            setErrorMessage(error.message);
          } else {
            setErrorMessage(DEFAULT_ERROR_MESSAGE);
          }
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    };

    void fetchLibrary();

    return () => {
      isCancelled = true;
    };
  }, []);

  return (
    <main className={styles.page}>
      <div className={styles.container}>
        <header className={styles.header}>
          <h1 className={styles.title}>ライブラリ</h1>
          <button type="button" className={styles.registerButton}>
            登録
          </button>
        </header>

        <nav aria-label="メインタブ" className={styles.tabs}>
          <span className={`${styles.tab} ${styles.tabActive}`}>ライブラリ</span>
          <span className={`${styles.tab} ${styles.tabInactive}`}>検索</span>
        </nav>

        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>所持内検索</h2>
          <input
            aria-label="所持内検索"
            className={styles.searchInput}
            placeholder="タイトル・著者で検索（未実装）"
            type="text"
          />
        </section>

        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>シリーズ一覧</h2>
          {isLoading && <p className={styles.statusText}>読み込み中...</p>}
          {!isLoading && errorMessage !== null && (
            <p className={styles.errorText}>{errorMessage}</p>
          )}
          {!isLoading && errorMessage === null && seriesList.length === 0 && (
            <p className={styles.statusText}>シリーズが登録されていません。</p>
          )}
          {!isLoading && errorMessage === null && seriesList.length > 0 && (
            <div className={styles.seriesGrid}>
              {seriesList.map((series) => (
                <article className={styles.seriesCard} key={series.id}>
                  <h3 className={styles.seriesTitle}>{series.title}</h3>
                  <p className={styles.seriesMeta}>
                    著者: {series.author ?? "未設定"}
                    <br />
                    出版社: {series.publisher ?? "未設定"}
                  </p>
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
