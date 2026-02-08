import styles from "./LibraryTabPage.module.css";

const placeholderSeries = [
  {
    id: 1,
    title: "作品タイトル（仮）",
    author: "著者名（仮）",
  },
  {
    id: 2,
    title: "作品タイトル（仮）",
    author: "著者名（仮）",
  },
  {
    id: 3,
    title: "作品タイトル（仮）",
    author: "著者名（仮）",
  },
];

export function LibraryTabPage() {
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
          <div className={styles.seriesGrid}>
            {placeholderSeries.map((series) => (
              <article className={styles.seriesCard} key={series.id}>
                <h3 className={styles.seriesTitle}>{series.title}</h3>
                <p className={styles.seriesMeta}>{series.author}</p>
              </article>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
