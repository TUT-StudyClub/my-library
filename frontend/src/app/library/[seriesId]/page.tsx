import Link from "next/link";
import { notFound } from "next/navigation";
import styles from "./page.module.css";

type SeriesVolume = {
  isbn: string;
  volume_number: number | null;
  cover_url: string | null;
  registered_at: string;
};

type SeriesDetail = {
  id: number;
  title: string;
  author: string | null;
  publisher: string | null;
  volumes: SeriesVolume[];
};

type SeriesDetailPageProps = {
  params: {
    seriesId: string;
  };
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const DEFAULT_FETCH_ERROR_MESSAGE = "シリーズ詳細の取得に失敗しました。";

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

  return `${DEFAULT_FETCH_ERROR_MESSAGE} (status: ${statusCode})`;
}

function isSeriesVolume(value: unknown): value is SeriesVolume {
  return (
    typeof value === "object" &&
    value !== null &&
    "isbn" in value &&
    typeof value.isbn === "string" &&
    "volume_number" in value &&
    (typeof value.volume_number === "number" || value.volume_number === null) &&
    "cover_url" in value &&
    (typeof value.cover_url === "string" || value.cover_url === null) &&
    "registered_at" in value &&
    typeof value.registered_at === "string"
  );
}

function isSeriesDetail(value: unknown): value is SeriesDetail {
  return (
    typeof value === "object" &&
    value !== null &&
    "id" in value &&
    typeof value.id === "number" &&
    "title" in value &&
    typeof value.title === "string" &&
    "author" in value &&
    (typeof value.author === "string" || value.author === null) &&
    "publisher" in value &&
    (typeof value.publisher === "string" || value.publisher === null) &&
    "volumes" in value &&
    Array.isArray(value.volumes) &&
    value.volumes.every((volume) => isSeriesVolume(volume))
  );
}

function formatRegisteredAt(registeredAt: string): string {
  const parsedDate = new Date(registeredAt);
  if (Number.isNaN(parsedDate.getTime())) {
    return registeredAt;
  }

  return parsedDate.toLocaleString("ja-JP", { hour12: false });
}

async function fetchSeriesDetail(seriesId: string): Promise<SeriesDetail> {
  const requestUrl = new URL(`/api/series/${seriesId}`, API_BASE_URL);
  const response = await fetch(requestUrl.toString(), { cache: "no-store" });

  if (response.status === 404) {
    notFound();
  }

  if (!response.ok) {
    const errorPayload = (await response.json().catch(() => null)) as unknown;
    throw new Error(extractErrorMessage(errorPayload, response.status));
  }

  const payload = (await response.json()) as unknown;
  if (!isSeriesDetail(payload)) {
    throw new Error(DEFAULT_FETCH_ERROR_MESSAGE);
  }

  return payload;
}

export default async function SeriesDetailPage({ params }: SeriesDetailPageProps) {
  const normalizedSeriesId = params.seriesId.trim();
  const isValidSeriesId = /^[1-9][0-9]*$/.test(normalizedSeriesId);
  if (!isValidSeriesId) {
    notFound();
  }
  const seriesDetail = await fetchSeriesDetail(normalizedSeriesId);

  return (
    <main className={styles.page}>
      <div className={styles.container}>
        <p className={styles.backLinkWrapper}>
          <Link className={styles.backLink} href="/library">
            ライブラリへ戻る
          </Link>
        </p>

        <header className={styles.header}>
          <h1 className={styles.title}>{seriesDetail.title}</h1>
          <p className={styles.seriesId}>seriesId: {normalizedSeriesId}</p>
          <dl className={styles.seriesMetaList}>
            <div className={styles.seriesMetaRow}>
              <dt className={styles.seriesMetaLabel}>著者</dt>
              <dd className={styles.seriesMetaValue}>{seriesDetail.author ?? "不明"}</dd>
            </div>
            <div className={styles.seriesMetaRow}>
              <dt className={styles.seriesMetaLabel}>出版社</dt>
              <dd className={styles.seriesMetaValue}>{seriesDetail.publisher ?? "不明"}</dd>
            </div>
          </dl>
        </header>

        <section className={styles.volumeSection}>
          <h2 className={styles.sectionTitle}>登録済み巻</h2>
          {seriesDetail.volumes.length === 0 ? (
            <div aria-live="polite" className={styles.placeholderPanel} role="status">
              <p className={styles.placeholderText}>登録済みの巻はありません。</p>
            </div>
          ) : (
            <ul className={styles.volumeList}>
              {seriesDetail.volumes.map((volume) => (
                <li className={styles.volumeListItem} key={volume.isbn}>
                  <article className={styles.volumeCard}>
                    <p className={styles.volumeNumber}>
                      {volume.volume_number === null ? "巻数不明" : `${volume.volume_number}巻`}
                    </p>
                    <p className={styles.volumeMeta}>ISBN: {volume.isbn}</p>
                    <p className={styles.volumeMeta}>
                      登録日時: {formatRegisteredAt(volume.registered_at)}
                    </p>
                  </article>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </main>
  );
}
