import Link from "next/link";

type SeriesDetailPageProps = {
  params: {
    seriesId: string;
  };
};

export default function SeriesDetailPage({ params }: SeriesDetailPageProps) {
  return (
    <main>
      <p>
        <Link href="/library">ライブラリへ戻る</Link>
      </p>
      <h1>シリーズ詳細</h1>
      <p>seriesId: {params.seriesId}</p>
    </main>
  );
}
