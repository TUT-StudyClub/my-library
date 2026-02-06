# my-library

## 目的

所持しているマンガを管理・検索し、購入の重複を防ぐため

## 技術スタック

### Frontend
- Next.js 14
- TypeScript
- React 18

### Backend
- FastAPI
- Python 3.9+
- uvicorn
- uv

### その他
- API:国立国会図書館サーチ （マンガ情報取得）

## 構成

```
my-library-main/
├── frontend/     # Next.js (TypeScript) フロントエンド
├── backend/      # FastAPI バックエンド
├── docs/         # 開発ルール/運用ドキュメント
└── README.md
```

### ポート設定
- Frontend: `3000`
- Backend: `8000`

### 環境変数

#### Frontend (.env)
| 変数名 | 説明 | デフォルト値 |
|--------|------|--------------|
| NEXT_PUBLIC_API_BASE_URL | バックエンドAPIのベースURL | http://localhost:8000 |

#### Backend (.env)
| 変数名 | 説明 | デフォルト値 |
|--------|------|--------------|
| NDL_API_BASE_URL | NDL Search API URL | https://ndlsearch.ndl.go.jp/api/opensearch |
| ALLOWED_ORIGINS | CORS許可オリジン | http://localhost:3000 |


### クイックスタート

1. Backendを起動 (ポート8000)
```bash
cd backend
uv sync
cp .env.example .env
uv run uvicorn src.main:app --reload --port 8000
```

2. Frontendを起動 (ポート3000)
```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

3. ブラウザで http://localhost:3000 にアクセス

### ルートからの共通コマンド

フロント/バックを一括で実行できます。

```bash
make lint
make format
make format-check
make typecheck
```

### 開発ルール / PR運用

最低限の共通ルールは [docs/DEVELOPMENT_RULES.md](docs/DEVELOPMENT_RULES.md) を参照してください。

#### 起動手順

### Frontend (Next.js)

#### 必要な環境
- Node.js 18.x 以上
- npm 9.x 以上

#### セットアップ(frontend)

1. frontendディレクトリに移動
```bash
cd frontend
```

2. 依存パッケージをインストール
```bash
npm install
```

3. 環境変数を設定
```bash
# .env.exampleをコピーして.envを作成
cp .env.example .env

# .envファイルを編集して必要な値を設定
# NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

開発サーバーを起動:
```bash
npm run dev
```

起動後、ブラウザで http://localhost:3000 にアクセスしてページを確認できます。

#### ビルド
```bash
npm run build
npm start
```

### Backend (FastAPI)

#### 必要な環境
- Python 3.9 以上
- uv (高速Pythonパッケージマネージャー)

#### セットアップ(backend)

1. uvをインストール（未インストールの場合）
```bash
# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. backendディレクトリに移動
```bash
cd backend
```

3. 依存パッケージをインストール
```bash
uv sync
```

4. 環境変数を設定
```bash
# .env.exampleをコピーして.envを作成
cp .env.example .env

# .envファイルを編集して必要な値を設定
# NDL_API_BASE_URL=https://ndlsearch.ndl.go.jp/api/opensearch
# ALLOWED_ORIGINS=http://localhost:3000
```

開発サーバーを起動:
```bash
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

起動後、以下のエンドポイントが利用可能:
- API: http://localhost:8000
- ヘルスチェック: http://localhost:8000/health
- API ドキュメント: http://localhost:8000/docs

## コード品質管理

### Lint・Format確認手順

本プロジェクトではコード品質を保つため、lintとformatを導入。

#### Frontend (Next.js/TypeScript)

**使用ツール**: ESLint + Prettier

##### Lintチェック
```bash
cd frontend
npm run lint
```
- 合格: ` No ESLint warnings or errors`
- エラー: 問題箇所と修正方法が表示される

##### Formatチェック（確認のみ）
```bash
cd frontend
npm run format:check
```
-  合格: `All matched files use Prettier code style!`
-  エラー: フォーマットが必要なファイルが表示される

##### Format適用（自動修正）
```bash
cd frontend
npm run format
```
- エラーが出た場合のみ実行してコードを自動整形

#### Backend (Python/FastAPI)

**使用ツール**: ruff (lint) + black (format)

##### Lintチェック
```bash
cd backend
uv run ruff check .
```
-  合格: `All checks passed!`
-  エラー: 問題箇所が表示される

##### Lint自動修正
```bash
cd backend
uv run ruff check . --fix
```
- 自動修正可能なlintエラーを修正

##### Formatチェック（確認のみ）
```bash
cd backend
uv run black --check .
```
-  合格: `All done! `
-  エラー: `X files would be reformatted`

##### Format適用（自動修正）
```bash
cd backend
uv run black .
```
- エラーが出た場合のみ実行してコードを自動整形

### コミット前の確認（推奨）

コミット前に必ず以下を実行してください:

```bash
# Frontend確認
cd frontend
npm run lint
npm run format:check

# Backend確認
cd backend
uv run ruff check .
uv run black --check .
```

## 開発フロー
1. `feature/` でブランチを切って作業する。
2. 作業が完了したらPRを作成する。
3. Approveを2件取得する。
4. `main` へmergeする。

## ルール
- `main` への直接pushは禁止。
- `feature/` ブランチ運用を徹底する。
- レビュー必須（Approve 2件）。
