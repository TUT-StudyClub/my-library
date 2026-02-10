"use client";

import Link from "next/link";
import { useEffect } from "react";
import styles from "./page.module.css";

type SeriesDetailErrorPageProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

export default function SeriesDetailErrorPage({ error, reset }: SeriesDetailErrorPageProps) {
  const normalizedErrorMessage = error.message.trim();
  const hasErrorDetail = normalizedErrorMessage !== "";

  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className={styles.page}>
      <div className={styles.container}>
        <header className={styles.header}>
          <h1 className={styles.title}>シリーズ詳細</h1>
          <p className={styles.seriesId}>状態: 取得失敗</p>
        </header>

        <section aria-live="assertive" className={styles.errorPanel} role="alert">
          <p className={styles.errorText}>
            シリーズ詳細の取得に失敗しました。時間をおいて再試行してください。
          </p>
          {hasErrorDetail && <p className={styles.errorDetail}>詳細: {normalizedErrorMessage}</p>}
          <div className={styles.errorActions}>
            <button className={styles.retryButton} onClick={reset} type="button">
              再試行
            </button>
            <Link className={styles.backLink} href="/library">
              ライブラリへ戻る
            </Link>
          </div>
        </section>
      </div>
    </main>
  );
}
