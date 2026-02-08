import Image, { type ImageLoaderProps } from "next/image";
import styles from "./LibrarySeriesCard.module.css";

type LibrarySeriesCardProps = {
  title: string;
  representativeCoverUrl: string | null;
};

function passthroughImageLoader({ src }: ImageLoaderProps): string {
  return src;
}

export function LibrarySeriesCard({ title, representativeCoverUrl }: LibrarySeriesCardProps) {
  const normalizedCoverUrl = representativeCoverUrl?.trim() ?? "";
  const hasCoverImage = normalizedCoverUrl !== "";

  return (
    <article className={styles.card}>
      <div className={styles.coverArea}>
        {hasCoverImage ? (
          <Image
            alt={`${title} の代表表紙`}
            className={styles.coverImage}
            fill
            loader={passthroughImageLoader}
            sizes="(max-width: 640px) 45vw, (max-width: 1080px) 30vw, 220px"
            src={normalizedCoverUrl}
            unoptimized
          />
        ) : (
          <div aria-hidden="true" className={styles.coverPlaceholder}>
            <span className={styles.placeholderText}>画像なし</span>
          </div>
        )}
      </div>
      <h3 className={styles.title}>{title}</h3>
    </article>
  );
}
