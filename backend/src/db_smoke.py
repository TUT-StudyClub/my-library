import argparse
import json
import time
from pathlib import Path
from typing import Any, Optional

from src.db import connect, initialize_database


def generate_sample_isbn() -> str:
    """重複しづらい13桁ISBN文字列を生成する."""
    return str(int(time.time() * 1000)).zfill(13)[-13:]


def run_register_and_fetch_smoke(log_path: Optional[Path] = None) -> dict[str, Any]:
    """Series/Volumeの登録と取得を最小構成で確認する."""
    initialize_database()

    sample_isbn = generate_sample_isbn()
    sample_title = f"スモーク確認作品-{sample_isbn[-6:]}"

    with connect() as connection:
        cursor = connection.execute(
            "INSERT INTO series (title, author, publisher) VALUES (?, ?, ?);",
            (sample_title, "スモーク著者", "スモーク出版社"),
        )
        series_id = cursor.lastrowid
        connection.execute(
            "INSERT INTO volume (isbn, series_id, volume_number, cover_url) VALUES (?, ?, ?, ?);",
            (sample_isbn, series_id, 1, "https://example.com/smoke-cover.jpg"),
        )
        row = connection.execute(
            """
            SELECT s.id, s.title, v.isbn, v.volume_number
            FROM series s
            JOIN volume v ON v.series_id = s.id
            WHERE v.isbn = ?;
            """,
            (sample_isbn,),
        ).fetchone()

    if row is None:
        raise RuntimeError("登録した巻を取得できませんでした。")

    result = {
        "status": "ok",
        "series": {"id": row[0], "title": row[1]},
        "volume": {"isbn": row[2], "volumeNumber": row[3]},
    }

    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    return result


def parse_args() -> argparse.Namespace:
    """CLI引数を読み取る."""
    parser = argparse.ArgumentParser(
        description="Series/Volume の登録→取得を確認するスモークコマンド"
    )
    parser.add_argument(
        "--log-path", type=Path, default=None, help="結果JSONを書き出すファイルパス"
    )
    return parser.parse_args()


def main() -> None:
    """スモーク処理を実行して結果を出力する."""
    args = parse_args()
    result = run_register_and_fetch_smoke(log_path=args.log_path)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.log_path is not None:
        print(f"log saved: {args.log_path}")


if __name__ == "__main__":
    main()
