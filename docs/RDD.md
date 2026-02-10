# **漫画管理アプリ（蔵書目録）要件定義書（MVP・NDL Search版）**

## **1. 背景・目的**

### **1.1 背景**

物理漫画を所持していると、すでに持っている巻を忘れて **二重購入**が発生しやすい。巻数が増えるほど把握が難しく、購入前の確認コストが上がる。

### **1.2 目的**

**「登録されている＝持っている」** の単純なルールで、所持巻の有無を即時確認できる状態を作り、二重購入を防止する。

### **1.3 MVPのコア価値**

* 所持蔵書の可視化（作品単位で集約）  
* 所持内検索で即確認  
* 外部検索→所持判定→登録の導線  
* 作品詳細で未所持巻の確認と登録ができる  
* 重複登録防止と安全な削除

---

## 

## **2. 対象・非対象**

### **2.1 対象**

* **物理漫画（ISBN等の識別子がある書籍）**

### **2.2 非対象（MVP外）**

* Web漫画・電子書籍の所持管理  
* ユーザー認証、同期、複数端末共有  
* 読了/未読、購入予定などの状態管理

---

## **3. 技術前提（MVP）**

* Frontend: Next.js（React）+ TypeScript  
* Backend: FastAPI（Python）  
* DB: SQLite（Dockerは使わない）  
* 外部書誌: 国立国会図書館サーチ（NDL Search）  
* 書影データ: MVPでは画像バイナリを保持せず、URLのみ扱う  
* バーコードスキャン: ブラウザカメラ（例：html5-qrcode等）

---

## **4. 用語定義**

* **Series（作品）**：作品単位（タイトル、著者、出版社など）  
* **Volume（巻）**：巻単位（識別子＝ISBNを主キー相当として扱う）  
* **所持内検索**：DBに登録済み（所持済み）だけを検索する  
* **外部検索**：NDL Searchで書誌候補を検索する  
* **所持判定**：候補の識別子（ISBN）とDB照合で `owned` を判定する  
* **`owned`**：検索候補の所持判定値。`true` / `false` / `"unknown"` の3値を取る  
* **未登録巻候補**：作品詳細ページ上段に表示する「未所持の候補巻」

---

## 

## **5. 画面構成**

## **5.1 画面一覧（2タブ \+ 登録導線 \+ 作品詳細）**

* **タブ1：ライブラリ（メイン）**  
  * 所持Series一覧（代表表紙付き）  
  * 所持内検索（title OR author）  
  * ヘッダーに「登録」ボタン（ワンクリックでスキャン画面へ）  
  * Seriesクリックで作品詳細へ  
* **タブ2：検索（サブ）**  
  * 外部検索（NDL Search）  
  * 所持判定（所持済み/未所持/判定不可）  
  * 未所持の登録  
* **スキャン画面（登録画面）**  
  * バーコード読み取り→登録  
  * 最終手段の手入力（折りたたみ）  
* **作品詳細ページ**  
  * 未登録巻候補（上段）/登録済み巻（下段）の2段横スクロール  
  * 確認モーダルで登録  
  * 指定巻削除 / 全巻削除（物理削除）

---

## 

## **6. 機能要件**

## **6.1 ライブラリ（メイン）**

### **6.1.1 表示要件**

* Seriesカード一覧を表示する  
* **各Seriesカードは「所持している第1巻の表紙」を代表画像として表示する**  
  * 表紙が無い場合はプレースホルダ画像  
* 表示項目  
  * タイトル（必須）  
  * 著者（取得できる場合）  
  * 出版社（任意）  
* **ライブラリ画面では巻数情報を表示しない**（巻情報は作品詳細へ）

### **6.1.2 所持内検索**

* 対象：所持データ（DB）のSeries  
* 検索条件：`title OR author`

### **6.1.3 代表表紙（第1巻表紙）の決定ロジック**

優先順位：

1. `volume_number = 1` の巻が存在し `cover_url` がある場合はそれ  
2. 1巻が不明の場合は、当該Series内で `registered_at` が最も古い巻の `cover_url`  
3. `cover_url` が無い場合はプレースホルダ

---

## **6.2 登録（スキャン + 手入力）**

### **6.2.1 登録導線**

* ライブラリ画面のヘッダーに **「登録」ボタン**を配置（右上or左上に固定）  
* ワンクリックでスキャン画面へ遷移

### **6.2.2 スキャン登録**

* バーコード読み取り→識別子（ISBN）を抽出し正規化（前後空白除去、全角→半角、ハイフン除去）  
* 正規化後のISBNは半角数字13桁を必須とし、DBには「ハイフンなし13桁」のみ保存する  
* 登録結果（成功/登録済み/失敗）を表示  
* 連続スキャン対策  
  * 二重送信防止（処理中ロック）  
  * 同一識別子の短時間連打を無視（クールダウン）

### **6.2.3 手入力（最終手段）**

* スキャン/検索で取得できない場合の救済として提供  
* UIは折りたたみで、主導線にしない

---

## **6.3 検索タブ（外部検索）**

### **6.3.1 外部検索**

* 入力：キーワード（作品名/著者名など）  
* NDL Searchで検索し候補一覧を表示

### **6.3.2 結果表示**

* タイトル、著者（可能なら）、出版社（可能なら）、書影（可能なら）  
* 候補ごとに `owned` に応じた表示文言を固定で表示する

| `owned` | 条件 | 表示文言 |
|---|---|---|
| `true` | 同一ISBNがDBに存在する | `所持済み` |
| `false` | ISBNはあるがDBに存在しない | `未所持` |
| `"unknown"` | ISBNが欠損（`isbn = null`）で判定できない | `判定不可（ISBN不明）` |

### **6.3.3 登録**

* `owned = false` の候補のみ登録ボタンを表示する  
* `owned = true` / `owned = "unknown"` の候補は登録ボタンを表示しない  
* 登録後、該当候補の `owned` を `true` に更新し、表示文言を `所持済み` に切り替える

---

## **6.4 作品詳細ページ（Series詳細）**

### **6.4.1 目的**

* 作品単位で「未所持候補の確認→登録」「所持巻の管理（追加/削除）」を行う。

### **6.4.2 表示（必須）**

* 作品情報（タイトル必須、著者/出版社任意）  
* **2段横スクロール**  
  * 上段：未登録巻候補（未所持）  
  * 下段：登録済み巻（所持）  
* 登録済み巻が0の場合、下段は非表示でよい

### **6.4.3 書影がない場合の表示（採用）**

* 書影あり：表紙画像を表示  
* **書影なし：巻数を大きく表示するプレースホルダカード**を表示  
  * 例：「1巻」「2巻」  
  * 巻数不明の場合は「?巻」を許容

### **6.4.4 未登録候補→確認→登録（必須）**

* 上段の候補をクリックすると確認モーダル  
* 「登録する/しない」を選択  
* 登録後、上段から下段へ移動（UI更新）

### **6.4.5 削除（必須）**

* 指定巻削除（巻単位）  
* 全巻削除（作品単位）  
  * 実行前の確認ダイアログ必須  
  * **全巻削除は物理削除**（作品レコードも削除する）

---

## **6.5 未登録巻候補の抽出（NDL Search）**

### **6.5.1 方針**

* 候補抽出はベストエフォート  
* 誤判定リスクは「確認モーダル」で吸収する
* MVPでは「自動判定で完全一致を保証する」ことは目標にしない（過剰品質の実装に逸れない）

### **6.5.2 除外フィルタ（採用）**

未登録候補抽出時、タイトル等に以下の語を含む結果を除外する（拡張可）：

* 特装版  
* 電子版 / 電子書籍  
* Kindle / \[Kindle版\]  
* その他、形態違いを示す明確な語

### **6.5.3 重複排除（採用）**

* 候補一覧内で **同一の識別子（ISBN 13桁）** が複数ある場合は1件にまとめる

---

## 

## **7. データ要件（DB）**

## **7.1 テーブル**

### **Series（作品）**

* `id`（PK）  
* `title`（必須）  
* `author`（任意）  
* `publisher`（任意）  
* `created_at`

### **Volume（巻）**

* `isbn`（必須・ユニーク）  
* `series_id`（必須・FK）  
* `volume_number`（任意）  
* `cover_url`（任意）  
* `registered_at`

## **7.2 制約**

* `Volume.isbn` ユニーク（重複登録防止）  
* `Volume.isbn` は正規化済みの半角数字13桁のみ保存する  
* `Volume.cover_url` はURL文字列のみ保存し、画像バイナリ（BLOB/Base64/ファイル）は保存しない  
* `series_id` 外部キー（SQLiteのFK有効化が前提）

## **7.3 全巻削除時の扱い（採用）**

* 作品詳細での全巻削除は **Series/Volumeともに物理削除**  
* 削除済みステータス管理はMVP外

---

## 

## **8. API要件（概要）**

### **8.1 所持（DB）**

* `GET /api/library`（Series一覧。代表表紙URLを含む）  
* `GET /api/library?q=...`（title OR author）  
* `GET /api/series/{series_id}`（作品詳細：作品情報＋登録済み巻）  
* `POST /api/volumes`（登録：body `{isbn}`）  
* `DELETE /api/volumes/{isbn}`（指定巻削除）  
* `DELETE /api/series/{series_id}/volumes`（全巻削除＝物理削除）

#### **8.1.1 GET /api/library（ライブラリ一覧）**

フロントのライブラリ画面（所持Series一覧）で使用するエンドポイント。

**HTTPメソッド/パス**

* `GET /api/library`

**クエリパラメータ**

| パラメータ | 型 | 必須 | 説明 |
|---|---|---|---|
| `q` | string | 任意 | `title OR author` の部分一致検索キーワード |

`q` の扱いは以下で固定する。

* `q` 未指定、`q=`、空白のみ（例: `"   "`）は「検索なし」とみなし、全件を返す  
* 前後空白はトリムしてから検索する  
* 検索条件は `title LIKE %q% OR author LIKE %q%`（部分一致）  
* `author` が `null` のSeriesは、検索時に空文字として扱う（エラーにしない）

**レスポンス（200 OK）**

配列で返す。1要素が1Series。

| フィールド | 型 | `null` | 説明 |
|---|---|---|---|
| `id` | number | 不可 | Series ID |
| `title` | string | 不可 | 作品タイトル |
| `author` | string | 可 | 著者名 |
| `publisher` | string | 可 | 出版社名 |
| `representative_cover_url` | string | 可 | ライブラリカードで使う代表表紙URL |

並び順は以下で固定する。

* `created_at DESC`, `id DESC`（新しく作成されたSeriesが先頭）

`representative_cover_url` は以下優先順位で決定する。

1. `volume_number = 1` の巻で、`cover_url` が空でないもの  
2. 1が無い場合、同一Series内で `registered_at` が最古の巻の `cover_url`  
3. `cover_url` が1件も無い場合は `null`

**レスポンス例（検索なし）**

```json
[
  {
    "id": 12,
    "title": "葬送のフリーレン",
    "author": "山田鐘人",
    "publisher": "小学館",
    "representative_cover_url": "https://example.com/covers/frieren-1.jpg"
  },
  {
    "id": 11,
    "title": "作品B",
    "author": null,
    "publisher": "テスト出版社",
    "representative_cover_url": null
  }
]
```

**レスポンス例（`q` 指定あり）**

`GET /api/library?q=山田`

```json
[
  {
    "id": 12,
    "title": "葬送のフリーレン",
    "author": "山田鐘人",
    "publisher": "小学館",
    "representative_cover_url": "https://example.com/covers/frieren-1.jpg"
  }
]
```

**エラー**

* 4xx/5xx の形式は `docs/DEVELOPMENT_RULES.md` の「APIエラーレスポンス規約」に従う

#### **8.1.2 GET /api/series/{series_id}（作品詳細）**

フロントの作品詳細画面（登録済み巻表示）で使用するエンドポイント。

**HTTPメソッド/パス**

* `GET /api/series/{series_id}`

**パスパラメータ**

| パラメータ | 型 | 必須 | 説明 |
|---|---|---|---|
| `series_id` | number | 必須 | 取得対象のSeries ID |

**レスポンス（200 OK）**

作品情報と、配下の登録済み巻配列を返す。

| フィールド | 型 | `null` | 説明 |
|---|---|---|---|
| `id` | number | 不可 | Series ID |
| `title` | string | 不可 | 作品タイトル |
| `author` | string | 可 | 著者名 |
| `publisher` | string | 可 | 出版社名 |
| `volumes` | array | 不可 | 登録済み巻一覧（0件の場合は空配列 `[]`） |
| `volumes[].isbn` | string | 不可 | 正規化済みISBN（半角数字13桁） |
| `volumes[].volume_number` | number | 可 | 巻数（不明時は `null`） |
| `volumes[].cover_url` | string | 可 | 表紙URL（未取得時は `null`） |
| `volumes[].registered_at` | string | 不可 | 登録日時（ISO 8601） |

`volumes` の並び順は以下で固定する。

1. `volume_number` 昇順（`null` は末尾）  
2. 同巻数内は `registered_at` 昇順  
3. 同時刻は `isbn` 昇順

**レスポンス例（200 OK）**

```json
{
  "id": 12,
  "title": "葬送のフリーレン",
  "author": "山田鐘人",
  "publisher": "小学館",
  "volumes": [
    {
      "isbn": "9784088836440",
      "volume_number": 1,
      "cover_url": "https://example.com/covers/frieren-1.jpg",
      "registered_at": "2026-02-08T03:21:45Z"
    },
    {
      "isbn": "9784088836457",
      "volume_number": 2,
      "cover_url": "https://example.com/covers/frieren-2.jpg",
      "registered_at": "2026-02-09T03:21:45Z"
    },
    {
      "isbn": "9784088836990",
      "volume_number": null,
      "cover_url": null,
      "registered_at": "2026-02-10T03:21:45Z"
    }
  ]
}
```

**エラー**

* 4xx/5xx の形式は `docs/DEVELOPMENT_RULES.md` の「APIエラーレスポンス規約」に従う
* `series_id` が存在しない場合は `404`（`SERIES_NOT_FOUND`）を返す

#### **8.1.3 POST /api/volumes（巻登録）**

スキャン/手入力/検索結果から、ISBN指定で所持巻を1件登録するエンドポイント。

**HTTPメソッド/パス**

* `POST /api/volumes`

**リクエスト**

`Content-Type: application/json`

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `isbn` | string | 必須 | ISBN。入力時はハイフン付き・全角数字・前後空白を許容し、サーバー側で正規化する |

`isbn` は `docs/DEVELOPMENT_RULES.md` の「識別子（ISBN）正規化ルール」に従って正規化し、正規化後が半角数字13桁でない場合はエラーとする。

**リクエスト例**

```json
{
  "isbn": " 978-4-08-883644-0 "
}
```

**レスポンス（201 Created）**

| フィールド | 型 | `null` | 説明 |
|---|---|---|---|
| `series` | object | 不可 | 登録先Series情報 |
| `series.id` | number | 不可 | Series ID |
| `series.title` | string | 不可 | 作品タイトル |
| `series.author` | string | 可 | 著者名 |
| `series.publisher` | string | 可 | 出版社名 |
| `volume` | object | 不可 | 登録した巻情報 |
| `volume.isbn` | string | 不可 | 正規化済みISBN（半角数字13桁） |
| `volume.volume_number` | number | 可 | 巻数（取得できない場合は `null`） |
| `volume.cover_url` | string | 可 | 表紙URL（取得できない場合は `null`） |
| `volume.registered_at` | string | 不可 | 登録日時（ISO 8601） |

**レスポンス例（201 Created）**

```json
{
  "series": {
    "id": 12,
    "title": "葬送のフリーレン",
    "author": "山田鐘人",
    "publisher": "小学館"
  },
  "volume": {
    "isbn": "9784088836440",
    "volume_number": 1,
    "cover_url": "https://example.com/covers/frieren-1.jpg",
    "registered_at": "2026-02-08T03:21:45Z"
  }
}
```

**重複時レスポンス（409 Conflict）**

同一ISBN（正規化後）が既に `volume` テーブルに存在する場合は、新規登録せず `409` を返す。

```json
{
  "error": {
    "code": "VOLUME_ALREADY_EXISTS",
    "message": "Volume already exists",
    "details": {
      "isbn": "9784088836440",
      "seriesId": 12
    }
  }
}
```

`details.seriesId` を使い、フロントは既存作品詳細（`/api/series/{series_id}`）への誘導を実装できる。

#### **8.1.4 DELETE /api/volumes/{isbn}（指定巻削除）**

作品詳細画面の「登録済み巻」から、1冊だけ削除するエンドポイント。

**HTTPメソッド/パス**

* `DELETE /api/volumes/{isbn}`

**パスパラメータ**

| パラメータ | 型 | 必須 | 説明 |
|---|---|---|---|
| `isbn` | string | 必須 | 削除対象のISBN。ハイフン付き・全角数字・前後空白を許容し、サーバー側で正規化する |

`isbn` の正規化ルールは `POST /api/volumes` と同一で、`docs/DEVELOPMENT_RULES.md` の「識別子（ISBN）正規化ルール」に従う。

**レスポンス（200 OK）**

このエンドポイントは **Volumeのみ削除** し、Seriesレコードは削除しない。  
（Seriesごと削除したい場合は `DELETE /api/series/{series_id}/volumes` を使う）

| フィールド | 型 | `null` | 説明 |
|---|---|---|---|
| `deleted` | object | 不可 | 削除結果 |
| `deleted.isbn` | string | 不可 | 削除したVolumeの正規化済みISBN |
| `deleted.seriesId` | number | 不可 | 削除対象Volumeが属していたSeries ID |
| `deleted.remainingVolumeCount` | number | 不可 | 同Seriesに残っているVolume件数 |

**レスポンス例（200 OK）**

```json
{
  "deleted": {
    "isbn": "9784088836440",
    "seriesId": 12,
    "remainingVolumeCount": 3
  }
}
```

**対象なしレスポンス（404 Not Found）**

```json
{
  "error": {
    "code": "VOLUME_NOT_FOUND",
    "message": "Volume not found",
    "details": {
      "isbn": "9784088836440"
    }
  }
}
```

**エラー**

* `isbn` 正規化後が13桁でない場合は `400`（`INVALID_ISBN`）を返す
* 4xx/5xx の形式は `docs/DEVELOPMENT_RULES.md` の「APIエラーレスポンス規約」に従う

#### **8.1.5 DELETE /api/series/{series_id}/volumes（全巻削除）**

作品詳細画面の「全巻削除」操作で、対象Seriesと配下Volumeを物理削除するエンドポイント。

**HTTPメソッド/パス**

* `DELETE /api/series/{series_id}/volumes`

**パスパラメータ**

| パラメータ | 型 | 必須 | 説明 |
|---|---|---|---|
| `series_id` | number | 必須 | 削除対象のSeries ID |

**レスポンス（200 OK）**

| フィールド | 型 | `null` | 説明 |
|---|---|---|---|
| `deleted` | object | 不可 | 削除結果 |
| `deleted.seriesId` | number | 不可 | 削除したSeries ID |
| `deleted.deletedVolumeCount` | number | 不可 | 削除したVolume件数（0件の場合あり） |

**レスポンス例（200 OK）**

```json
{
  "deleted": {
    "seriesId": 12,
    "deletedVolumeCount": 8
  }
}
```

**対象なしレスポンス（404 Not Found）**

```json
{
  "error": {
    "code": "SERIES_NOT_FOUND",
    "message": "Series not found",
    "details": {
      "seriesId": 12
    }
  }
}
```

**エラー**

* 4xx/5xx の形式は `docs/DEVELOPMENT_RULES.md` の「APIエラーレスポンス規約」に従う

### **8.2 外部検索（NDL Search）**

* `GET /api/catalog/search?q=...&limit=...`（検索タブ用：候補＋所持判定）  
* `GET /api/series/{series_id}/candidates`（作品詳細用：未登録候補。フィルタ＋重複排除済み）

#### **8.2.1 GET /api/catalog/search（検索タブ候補取得）**

検索タブでキーワード検索し、NDL Search の候補一覧を取得するエンドポイント。  
候補ごとに `owned`（所持判定）を返す。

**HTTPメソッド/パス**

* `GET /api/catalog/search`

**クエリパラメータ**

| パラメータ | 型 | 必須 | 説明 |
|---|---|---|---|
| `q` | string | 必須 | 検索キーワード（作品名/著者名など） |
| `limit` | number | 任意 | 取得件数。`1`〜`100`。未指定時は `10` |

`q` と `limit` の扱いは以下で固定する。

* `q` は必須（未指定は `422`）  
* `q` が空文字または空白のみの場合は `400`（`INVALID_CATALOG_SEARCH_QUERY`）  
* `limit` が `1` 未満または `100` 超の場合は `422`

**リクエスト例**

`GET /api/catalog/search?q=葬送のフリーレン&limit=3`

**レスポンス（200 OK）**

配列で返す。1要素が1候補。  
並び順は NDL Search の応答順をそのまま使用する。

| フィールド | 型 | `null` | 説明 |
|---|---|---|---|
| `title` | string | 不可 | 候補タイトル（シリーズ名） |
| `author` | string | 可 | 著者名 |
| `publisher` | string | 可 | 出版社名 |
| `isbn` | string | 可 | ISBN-13（取得できない場合は `null`） |
| `volume_number` | number | 可 | 巻数（取得できない場合は `null`） |
| `cover_url` | string | 可 | 表紙URL（取得できない場合は `null`） |
| `owned` | boolean or string | 不可 | 所持判定。`true` / `false` / `"unknown"` |

`cover_url` は参照先URLを返すための値であり、画像バイナリはAPIレスポンスに含めない。

`owned` の判定ルールは以下で固定する。

1. `isbn = null` の場合は `owned = "unknown"`  
2. `isbn` があり、DB（`volume.isbn`）に同一値が存在する場合は `owned = true`  
3. `isbn` があり、DBに同一値が存在しない場合は `owned = false`

**レスポンス例（200 OK）**

```json
[
  {
    "title": "葬送のフリーレン",
    "author": "山田鐘人",
    "publisher": "小学館",
    "isbn": "9784098515762",
    "volume_number": 1,
    "cover_url": "https://example.com/covers/frieren-1.jpg",
    "owned": true
  },
  {
    "title": "葬送のフリーレン",
    "author": "山田鐘人",
    "publisher": "小学館",
    "isbn": "9784098515854",
    "volume_number": 2,
    "cover_url": "https://example.com/covers/frieren-2.jpg",
    "owned": false
  },
  {
    "title": "葬送のフリーレン",
    "author": "山田鐘人",
    "publisher": "小学館",
    "isbn": null,
    "volume_number": 3,
    "cover_url": null,
    "owned": "unknown"
  }
]
```

**エラー例（400 Bad Request）**

`q` が空文字または空白のみの場合。

```json
{
  "error": {
    "code": "INVALID_CATALOG_SEARCH_QUERY",
    "message": "Catalog search query is invalid",
    "details": {
      "reason": "q must not be empty"
    }
  }
}
```

**エラー例（422 Unprocessable Entity）**

`q` 未指定、または `limit` 範囲外の場合。

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "リクエストパラメータが不正です。",
    "details": {
      "fieldErrors": [
        {
          "field": "query.q",
          "reason": "Field required"
        }
      ]
    }
  }
}
```

**エラー例（504 Gateway Timeout）**

上流（NDL Search）がタイムアウトした場合。

```json
{
  "error": {
    "code": "NDL_API_TIMEOUT",
    "message": "NDL API request timed out",
    "details": {
      "upstream": "NDL Search",
      "externalFailure": true,
      "failureType": "timeout",
      "retryable": true,
      "timeoutSeconds": 10
    }
  }
}
```

#### **8.2.2 GET /api/catalog/lookup（識別子検索）**

識別子（ISBN）で NDL Search を検索し、最良候補1件を取得するエンドポイント。

**HTTPメソッド/パス**

* `GET /api/catalog/lookup`

**クエリパラメータ**

| パラメータ | 型 | 必須 | 説明 |
|---|---|---|---|
| `isbn` | string | 必須 | 検索対象のISBN。入力時は前後空白/全角数字/ハイフンを許容し、サーバー側で正規化する |

`isbn` は `docs/DEVELOPMENT_RULES.md` の「識別子（ISBN）正規化ルール」に従って正規化し、正規化後が半角数字13桁でない場合は `400`（`INVALID_ISBN`）とする。

**レスポンス（200 OK）**

検索結果の最良候補を1件返す。レスポンスDTOは `GET /api/catalog/search` と同一の `CatalogSearchCandidate` を使う。  
`owned` の定義・判定ルールも `8.2.1` と同一。

**レスポンス例（200 OK）**

```json
{
  "title": "葬送のフリーレン",
  "author": "山田鐘人",
  "publisher": "小学館",
  "isbn": "9784098515762",
  "volume_number": 1,
  "cover_url": "https://example.com/covers/frieren-1.jpg",
  "owned": false
}
```

**エラー例（404 Not Found）**

```json
{
  "error": {
    "code": "CATALOG_ITEM_NOT_FOUND",
    "message": "Catalog item not found",
    "details": {
      "isbn": "9784098515762",
      "upstream": "NDL Search",
      "externalFailure": false
    }
  }
}
```

#### **8.2.3 CatalogSearchCandidate DTO（共通）**

`/api/catalog/search` と `/api/catalog/lookup` は、同じ `CatalogSearchCandidate` DTO で返す。  
欠損可能な項目もキーは省略せず、必ず `null` で返す。

| フィールド | 型 | 必須 | 欠損時の扱い | UI/判定ロジックの扱い |
|---|---|---|---|---|
| `title` | string | 必須 | 欠損は許容しない | 候補表示の主キーとして扱う |
| `author` | string | 任意 | 取得できない場合は `null` | `null` は「著者不明」として表示可 |
| `publisher` | string | 任意 | 取得できない場合は `null` | `null` は「出版社不明」として表示可 |
| `isbn` | string | 任意 | 抽出できない場合は `null` | `null` の場合 `owned = "unknown"` として扱う（ISBN前提の登録処理は無効化） |
| `volume_number` | number | 任意 | 抽出できない場合は `null` | `null` は不明巻として扱う（例: `?巻`） |
| `cover_url` | string | 任意 | 書影情報が無い場合は `null` | `null` はプレースホルダ画像を表示 |
| `owned` | boolean or string | 必須 | 欠損は許容しない。`true` / `false` / `"unknown"` | 表示文言は `true=所持済み`、`false=未所持`、`"unknown"=判定不可（ISBN不明）` |

フロント実装時の型定義例（TypeScript）:

```ts
type Owned = true | false | "unknown";
```

`cover_url` は参照先URLを返すための値であり、画像バイナリはAPIレスポンスに含めない。

#### **8.2.4 GET /api/series/{series_id}/candidates（作品詳細: 未登録候補取得）**

作品詳細ページの上段（未登録巻候補）で使用するエンドポイント。  
レスポンスは **BookDTO 配列**で返し、サーバー側で未登録候補の抽出・除外フィルタ・重複排除を完了した状態を返す。

**HTTPメソッド/パス**

* `GET /api/series/{series_id}/candidates`

**パスパラメータ**

| パラメータ | 型 | 必須 | 説明 |
|---|---|---|---|
| `series_id` | number | 必須 | 取得対象のSeries ID |

**レスポンス（200 OK）**

* 配列で返す。1要素が1候補。型は `BookDTO`。  
* 候補抽出時に `6.5.2` の除外フィルタを適用済み。  
* 候補抽出時に `6.5.3` の重複排除（同一ISBNの1件化）を適用済み。  
* 既に `volume` テーブルに存在するISBNは除外済み（同一Series/他Seriesを問わず除外）。  
* 返却される候補はすべて「登録可能な候補」のみで、`isbn` は必ず13桁の正規化済み値。

| フィールド | 型 | `null` | 説明 |
|---|---|---|---|
| `title` | string | 不可 | 候補タイトル |
| `author` | string | 可 | 著者名 |
| `publisher` | string | 可 | 出版社名 |
| `isbn` | string | 不可 | ISBN-13（正規化済み、半角数字13桁） |
| `volume_number` | number | 可 | 巻数（取得できない場合は `null`） |
| `cover_url` | string | 可 | 表紙URL（取得できない場合は `null`） |

**並び順（固定）**

1. `volume_number` 昇順（`null` は末尾）  
2. 同巻数内は `isbn` 昇順

**レスポンス例（200 OK）**

```json
[
  {
    "title": "葬送のフリーレン",
    "author": "山田鐘人",
    "publisher": "小学館",
    "isbn": "9784098515762",
    "volume_number": 1,
    "cover_url": "https://example.com/covers/frieren-1.jpg"
  },
  {
    "title": "葬送のフリーレン",
    "author": "山田鐘人",
    "publisher": "小学館",
    "isbn": "9784098515854",
    "volume_number": 2,
    "cover_url": "https://example.com/covers/frieren-2.jpg"
  },
  {
    "title": "葬送のフリーレン",
    "author": "山田鐘人",
    "publisher": "小学館",
    "isbn": "9784098515922",
    "volume_number": null,
    "cover_url": null
  }
]
```

候補が存在しない場合は空配列 `[]` を返す。

**エラー**

* `series_id` が存在しない場合は `404`（`SERIES_NOT_FOUND`）  
* 4xx/5xx の形式は `docs/DEVELOPMENT_RULES.md` の「APIエラーレスポンス規約」に従う

#### **8.2.5 BookDTO（/api/series/{series_id}/candidates 用）**

`GET /api/series/{series_id}/candidates` は `BookDTO[]` で返す。  
`BookDTO` には `owned` を含めない（未登録候補のみ返すため）。

フロント実装時の型定義例（TypeScript）:

```ts
type BookDTO = {
  title: string;
  author: string | null;
  publisher: string | null;
  isbn: string;
  volume_number: number | null;
  cover_url: string | null;
};
```

### **エラー形式（統一）**

* エラー応答の正式仕様は `docs/DEVELOPMENT_RULES.md` の「APIエラーレスポンス規約」に従う  
* MVPでは以下のフォーマットを固定で採用する

```json
{
  "error": {
    "code": "SOME_ERROR_CODE",
    "message": "エラー内容を示すメッセージ",
    "details": {}
  }
}
```

### **8.3 最小テスト観点（health / library / series detail / register / delete）**

この節は、MVPで最低限維持するべきAPIテスト観点を定義する。  
レスポンス本文は「主要フィールドの期待値」を記載し、追加フィールドがあっても主要フィールドが一致していれば合格とする。

#### **8.3.1 health（`GET /health`）**

| ケースID | 前提 | リクエスト | 期待ステータス | 期待値（主要フィールド） |
|---|---|---|---|---|
| `HEALTH-01` | DB疎通が成功する | `GET /health` | `200` | `{"status":"ok","message":"API is running"}` |
| `HEALTH-02` | DB疎通チェックで例外が発生する | `GET /health` | `503` | `error.code = "SERVICE_UNAVAILABLE"`、`error.message = "Database connection failed"`、`error.details = {}` |

#### **8.3.2 library（`GET /api/library`）**

| ケースID | 前提 | リクエスト | 期待ステータス | 期待値（主要フィールド） |
|---|---|---|---|---|
| `LIBRARY-01` | Seriesが2件以上登録済み | `GET /api/library` | `200` | 登録済みSeriesが配列で返る。`title` は `created_at DESC, id DESC` の順。 |
| `LIBRARY-02` | `title` または `author` に一致するSeriesが存在する | `GET /api/library?q=<keyword>` | `200` | `title OR author` の部分一致に合致するSeriesのみ返る。 |
| `LIBRARY-03` | Seriesが複数件登録済み | `GET /api/library?q=` または `GET /api/library?q=   ` | `200` | 空文字・空白のみは検索なし扱いとなり、全件返る。 |
| `LIBRARY-04` | 同一Series内に複数Volumeがある | `GET /api/library` | `200` | `representative_cover_url` は「1巻の表紙 > 最古登録巻の表紙 > `null`」の優先順位で返る。 |

#### **8.3.3 series detail（`GET /api/series/{series_id}`）**

| ケースID | 前提 | リクエスト | 期待ステータス | 期待値（主要フィールド） |
|---|---|---|---|---|
| `SERIES-DETAIL-01` | 対象Seriesが存在し、Volumeが0件 | `GET /api/series/{series_id}` | `200` | `id/title/author/publisher` が返り、`volumes = []` |
| `SERIES-DETAIL-02` | 対象SeriesにVolumeが複数件ある | `GET /api/series/{series_id}` | `200` | `volumes` は `volume_number ASC（nullは末尾）` で返る。各要素は `isbn`（13桁）, `registered_at`（ISO 8601）を持つ。 |
| `SERIES-DETAIL-03` | 対象Seriesが存在しない | `GET /api/series/{series_id}` | `404` | `error.code = "SERIES_NOT_FOUND"`、`error.details.seriesId = {series_id}` |

#### **8.3.4 register（`POST /api/volumes`）**

| ケースID | 前提 | リクエスト | 期待ステータス | 期待値（主要フィールド） |
|---|---|---|---|---|
| `REGISTER-01` | NDLから書誌取得できる | `POST /api/volumes` (`{"isbn":" ９７８-... "}`) | `201` | `volume.isbn` は正規化済み13桁で返る。`series` と `volume.registered_at` が返る。 |
| `REGISTER-02` | 同一ISBNが既に登録済み | `POST /api/volumes` (`{"isbn":"978..."}`) | `409` | `error.code = "VOLUME_ALREADY_EXISTS"`、`error.message = "Volume already exists"` |
| `REGISTER-03` | 正規化後に13桁にならないISBN | `POST /api/volumes` (`{"isbn":"978-abc"}`) | `400` | `error.code = "INVALID_ISBN"`、`error.details.isbn` に入力値が入る。 |

#### **8.3.5 delete（`DELETE /api/volumes/{isbn}` / `DELETE /api/series/{series_id}/volumes`）**

| ケースID | 前提 | リクエスト | 期待ステータス | 期待値（主要フィールド） |
|---|---|---|---|---|
| `DELETE-01` | 対象ISBNが登録済み | `DELETE /api/volumes/{isbn}` | `200` | `deleted.isbn`（正規化済み）/`deleted.seriesId`/`deleted.remainingVolumeCount` が返る。 |
| `DELETE-02` | 対象ISBNが未登録 | `DELETE /api/volumes/{isbn}` | `404` | `error.code = "VOLUME_NOT_FOUND"`、`error.details.isbn = {isbn}` |
| `DELETE-03` | 正規化後に13桁にならないISBN | `DELETE /api/volumes/{isbn}` | `400` | `error.code = "INVALID_ISBN"`、`error.details.isbn` に入力値が入る。 |
| `DELETE-04` | 対象Seriesが存在し、Volumeが1件以上ある | `DELETE /api/series/{series_id}/volumes` | `200` | `deleted.seriesId` と `deleted.deletedVolumeCount` が返る。 |
| `DELETE-05` | 対象Seriesが存在しない | `DELETE /api/series/{series_id}/volumes` | `404` | `error.code = "SERIES_NOT_FOUND"`、`error.details.seriesId = {series_id}` |

---

## 

## **9. 非機能要件（MVP）**

* 数百巻規模で一覧・検索が体感遅くない  
* 外部検索はタイムアウトを設け、失敗時も画面が破綻しない  
* 重複登録・削除は安全側（確認/制約/エラー表示）で実装する

---

## **10. 完了定義（MVP Done）**

* ライブラリにSeriesが代表表紙付きで表示される（巻数は表示しない）  
* 所持内検索が title OR author で機能する  
* ヘッダー「登録」→スキャン→登録が成立する（成功/登録済み/失敗が分かる）  
* 検索タブで外部検索でき、所持判定が表示され、未所持を登録できる  
* 作品詳細で2段横スクロールが表示される（未登録/登録済み）  
* 未登録候補は確認モーダル経由で登録できる  
* 書影なしでも巻数プレースホルダで判別できる  
* 指定巻削除と全巻削除（物理削除）ができ、画面に反映される  
* 候補抽出で版違い除外と重複排除が効いている  
* データが永続化される（再起動後も保持）

---
