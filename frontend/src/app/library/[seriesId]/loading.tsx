import styles from "./page.module.css";

export default function SeriesDetailLoadingPage() {
  return (
    <main className={styles.page}>
      <div className={styles.container}>
        <header className={styles.header}>
          <h1 className={styles.title}>シリーズ詳細</h1>
          <p className={styles.seriesId}>読み込み中...</p>
        </header>

        <section aria-live="polite" className={styles.loadingPanel} role="status">
          <p className={styles.loadingText}>詳細情報を取得しています...</p>
        </section>
      </div>
    </main>
  );
}
