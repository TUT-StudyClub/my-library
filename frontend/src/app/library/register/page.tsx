import Link from "next/link";
import styles from "./page.module.css";

export default function RegisterPage() {
  return (
    <main className={styles.page}>
      <div className={styles.container}>
        <p className={styles.backLinkWrapper}>
          <Link className={styles.backLink} href="/library">
            ライブラリへ戻る
          </Link>
        </p>

        <header className={styles.header}>
          <h1 className={styles.title}>登録</h1>
          <p className={styles.description}>スキャン画面は次の実装で追加予定です。</p>
        </header>

        <section aria-live="polite" className={styles.placeholderPanel}>
          <p className={styles.placeholderText}>登録機能を準備しています...</p>
        </section>
      </div>
    </main>
  );
}
