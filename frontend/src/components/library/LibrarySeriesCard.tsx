import Image, { type ImageLoaderProps } from "next/image";
import { useEffect, useState } from "react";
import styles from "./LibrarySeriesCard.module.css";

type LibrarySeriesCardProps = {
  title: string;
  representativeCoverUrl: string | null;
};

function passthroughImageLoader({ src }: ImageLoaderProps): string {
  return src;
}

function normalizeCoverUrl(representativeCoverUrl: string | null): string | null {
  const trimmedCoverUrl = representativeCoverUrl?.trim() ?? "";
  if (trimmedCoverUrl === "") {
    return null;
  }

  try {
    const parsedCoverUrl = new URL(trimmedCoverUrl);
    if (parsedCoverUrl.protocol !== "http:" && parsedCoverUrl.protocol !== "https:") {
      return null;
    }

    return parsedCoverUrl.toString();
  } catch {
    return null;
  }
}

export function LibrarySeriesCard({ title, representativeCoverUrl }: LibrarySeriesCardProps) {
  const normalizedCoverUrl = normalizeCoverUrl(representativeCoverUrl);
  const [isImageLoadFailed, setIsImageLoadFailed] = useState(false);
  const hasCoverImage = normalizedCoverUrl !== null && !isImageLoadFailed;

  useEffect(() => {
    setIsImageLoadFailed(false);
  }, [normalizedCoverUrl]);

  return (
    <article className={styles.card}>
      <div className={styles.coverArea}>
        {hasCoverImage ? (
          <Image
            alt={`${title} の代表表紙`}
            className={styles.coverImage}
            fill
            loader={passthroughImageLoader}
            onError={() => {
              setIsImageLoadFailed(true);
            }}
            sizes="(max-width: 640px) 45vw, (max-width: 1080px) 30vw, 220px"
            src={normalizedCoverUrl}
            unoptimized
          />
        ) : (
          <div aria-hidden="true" className={styles.coverPlaceholder}>
            <div className={styles.placeholderIcon}>
              <span className={styles.placeholderBook} />
              <span className={styles.placeholderBookSpine} />
            </div>
            <span className={styles.placeholderText}>表紙なし</span>
          </div>
        )}
      </div>
      <h3 className={styles.title}>{title}</h3>
    </article>
  );
}
