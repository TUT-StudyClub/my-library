import Link from "next/link";
import styles from "./SearchTabPage.module.css";

export function SearchTabPage() {
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
          <label className={styles.searchLabel} htmlFor="catalogSearchInput">
            キーワード
          </label>
          <div className={styles.searchRow}>
            <input
              aria-label="外部検索キーワード"
              className={styles.searchInput}
              id="catalogSearchInput"
              placeholder="作品名・著者名などを入力"
              type="text"
            />
            <button className={styles.searchButton} disabled type="button">
              検索
            </button>
          </div>
          <p className={styles.helperText}>検索処理は次の実装で追加予定です。</p>
        </section>

        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>検索結果</h2>
          <div aria-live="polite" className={styles.statePanel}>
            <p className={styles.statusText}>検索結果の表示エリア</p>
          </div>
        </section>
      </div>
    </main>
  );
}
