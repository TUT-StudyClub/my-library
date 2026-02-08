import Link from "next/link";
import styles from "./page.module.css";

type SeriesDetailPageProps = {
  params: {
    seriesId: string;
  };
};

export default function SeriesDetailPage({ params }: SeriesDetailPageProps) {
  const normalizedSeriesId = params.seriesId.trim();

  return (
    <main className={styles.page}>
      <div className={styles.container}>
        <p className={styles.backLinkWrapper}>
          <Link className={styles.backLink} href="/library">
            ライブラリへ戻る
          </Link>
        </p>

        <header className={styles.header}>
          <h1 className={styles.title}>シリーズ詳細（仮表示）</h1>
          <p className={styles.seriesId}>seriesId: {normalizedSeriesId}</p>
        </header>

        <section aria-live="polite" className={styles.placeholderPanel}>
          <p className={styles.placeholderText}>詳細ページの本実装は次のEpicで対応予定です。</p>
        </section>
      </div>
    </main>
  );
}
