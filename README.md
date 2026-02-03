# my-library

## 目的

所持しているマンガを管理・検索するアプリケーション

## 技術スタック

### Frontend
- Next.js 14
- TypeScript
- React 18

### Backend
- FastAPI
- Python 3.9+
- uvicorn
- uv (パッケージマネージャー)

### その他
- 楽天Books API（マンガ情報取得）

## 構成

```
my-library-main/
├── frontend/     # Next.js (TypeScript) フロントエンド
├── backend/      # FastAPI バックエンド
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
| RAKUTEN_APP_ID | 楽天APIアプリケーションID | - |
| RAKUTEN_API_BASE_URL | 楽天Books API URL | https://app.rakuten.co.jp/services/api/BooksBook/Search/20170404 |
| ALLOWED_ORIGINS | CORS許可オリジン | http://localhost:3000 |

## 起動手順

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

#### 起動方法

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
# RAKUTEN_APP_ID=your_rakuten_application_id_here
# RAKUTEN_API_BASE_URL=https://app.rakuten.co.jp/services/api/BooksBook/Search/20170404
# ALLOWED_ORIGINS=http://localhost:3000
```

#### 起動方法

開発サーバーを起動:
```bash
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

起動後、以下のエンドポイントが利用可能:
- API: http://localhost:8000
- ヘルスチェック: http://localhost:8000/health
- API ドキュメント: http://localhost:8000/docs

### クイックスタート

1. Backendを起動 (ポート8000)
```bash
cd backend
uv sync
cp .env.example .env
uv run uvicorn main:app --reload --port 8000
```

2. Frontendを起動 (ポート3000)
```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

3. ブラウザで http://localhost:3000 にアクセス