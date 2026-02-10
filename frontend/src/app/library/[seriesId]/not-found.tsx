import Link from "next/link";
import styles from "./page.module.css";

export default function SeriesDetailNotFoundPage() {
  return (
    <main className={styles.page}>
      <div className={styles.container}>
        <header className={styles.header}>
          <h1 className={styles.title}>シリーズ詳細</h1>
          <p className={styles.seriesId}>状態: 404 Not Found</p>
        </header>

        <section aria-live="polite" className={styles.errorPanel} role="status">
          <p className={styles.errorText}>指定されたシリーズが見つかりません。</p>
          <p className={styles.backLinkWrapper}>
            <Link className={styles.backLink} href="/library">
              ライブラリへ戻る
            </Link>
          </p>
        </section>
      </div>
    </main>
  );
}
