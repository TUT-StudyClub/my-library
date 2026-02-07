# AGENTS.md

このファイルは、このリポジトリで作業する人間/AIエージェント向けの実務ガイドです。  
目的は「迷わず同じ基準で実装・検証・提出できる状態」を作ることです。

## 1. プロジェクト概要

- プロジェクト名: `my-library`
- 目的: 所持しているマンガを管理・検索し、購入の重複を防ぐ
- 構成:
  - `frontend/`: Next.js (TypeScript)
  - `backend/`: FastAPI (Python)
  - `docs/`: 要件・開発ルール

## 2. 技術スタック

- Frontend: Next.js 14 / React 18 / TypeScript
- Backend: FastAPI / Python 3.9+ / uvicorn / uv
- DB: SQLite
- 外部API: NDL Search (`https://ndlsearch.ndl.go.jp/api/opensearch`)

## 3. 主要ディレクトリと責務

- `frontend/src/app/`: 画面実装
- `backend/src/main.py`: FastAPIエントリポイント
- `backend/src/config.py`: DBパス解決
- `backend/src/db.py`: DB接続・初期化・疎通確認
- `backend/tests/`: backendテスト
- `docs/RDD.md`: プロダクト要件
- `docs/DEVELOPMENT_RULES.md`: 開発の最小ルール

## 4. 環境変数

### Frontend (`frontend/.env`)

- `NEXT_PUBLIC_API_BASE_URL` (default: `http://localhost:8000`)

### Backend (`backend/.env`)

- `NDL_API_BASE_URL` (default: `https://ndlsearch.ndl.go.jp/api/opensearch`)
- `ALLOWED_ORIGINS` (default: `http://localhost:3000`)
- `DB_PATH` (optional)
  - 未設定時: `backend/data/library.db` を使用
  - 相対パス指定時: `backend` ディレクトリ基準で解決
  - `~` は展開される

## 5. SQLite運用ルール（重要）

- DBファイルのデフォルト配置: `backend/data/library.db`
- backend起動時に以下を自動実行:
  - DBファイル作成（必要時）
  - 最小スキーマ作成（`series`, `volume`）
  - インデックス作成（`idx_series_title`, `idx_series_author`, `idx_volume_series_id`）
  - `PRAGMA foreign_keys = ON`
- `/health` はDB疎通チェックを実行し、失敗時は `503` を返す
- DB実ファイルはコミットしない（`backend/.gitignore` で除外）

## 6. セットアップ

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

### Backend

```bash
cd backend
uv sync --extra dev
cp .env.example .env
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

## 7. 日常コマンド

リポジトリルートで実行:

```bash
make check
```

`make check` は以下を順に実行:

1. lint（frontend + backend）
2. format-check（frontend + backend）
3. typecheck（frontend + backend）

個別実行:

```bash
make lint
make format
make format-check
make typecheck
```

## 8. コーディング規約

`docs/DEVELOPMENT_RULES.md` を優先し、最低限以下を守る:

- フォーマッタ/Lintを実行してから提出
- importは自動整形に従う
- 改行コードはLF
- 変更は最小限にし、無関係な整形を避ける
- コメントと docstring は日本語で記述する
- 命名:
  - 変数/関数: `lowerCamelCase`
  - 型/コンポーネント: `PascalCase`
  - 定数: `UPPER_SNAKE_CASE`

## 9. 実装時の作業方針

- 1PR = 1目的を維持する
- 既存設計を壊す大きな変更は、事前に合意を取る
- 仕様判断が必要なら `docs/RDD.md` を基準にする
- backend変更時は、可能な限り `backend/tests/` にテストを追加/更新する

## 10. 変更前後のチェックリスト

変更前:

1. 関連仕様を確認 (`README.md`, `docs/RDD.md`, `docs/DEVELOPMENT_RULES.md`)
2. 影響範囲（frontend/backend/docs）を明確化

変更後:

1. `make check` が通る
2. 追加した環境変数や運用ルールをドキュメントへ反映
3. DB関連変更時は `DB_PATH` 未設定時の挙動を壊していないことを確認
