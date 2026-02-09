"use client";

import Link from "next/link";
import { type FormEvent, useState } from "react";
import styles from "./SearchTabPage.module.css";

export function SearchTabPage() {
  const [query, setQuery] = useState("");
  const [executedQuery, setExecutedQuery] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  const normalizedQuery = query.trim();

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (normalizedQuery === "") {
      setValidationError("キーワードを入力してください。");
      return;
    }

    setValidationError(null);
    setExecutedQuery(normalizedQuery);
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
                  if (validationError !== null) {
                    setValidationError(null);
                  }
                }}
                placeholder="作品名・著者名などを入力"
                type="text"
                value={query}
              />
              <button
                className={styles.searchButton}
                disabled={normalizedQuery === ""}
                type="submit"
              >
                検索
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
            <p className={styles.statusText}>
              {executedQuery === null
                ? "クエリを入力して検索を実行してください。"
                : `「${executedQuery}」で検索を実行しました。`}
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}
