# 開発の共通ルール

## コーディング最小ルール
- フォーマッタ・Lintは必ず実行してからPRを出す（ローカル/CI両方）。
- importは自動整形に従う（手動で並べ替えない）。
- 改行コードはLFで統一（設定済み）。
- 変更は最小限・目的と関係ない整形は避ける。

## 命名
- 変数/関数: lowerCamelCase
- 型/コンポーネント: PascalCase
- 定数: UPPER_SNAKE_CASE

## 識別子（ISBN）正規化ルール
- 対象: `Volume.isbn` として保存する値。
- 保存前に必ず以下の順で正規化する。
  1. 前後の空白を除去する。
  2. 全角数字を半角数字へ変換する。
  3. ハイフン（`-`）を除去する。
- 正規化後の値が `^[0-9]{13}$`（半角数字13桁）でない場合は保存しない。
- DBには「半角数字13桁・ハイフンなし」のみを保存する。
- 例:
  - 入力: `978-4-08-883644-0`
  - 保存値: `9784088836440`

## APIエラーレスポンス規約
- 対象: backend が返すすべての `4xx` / `5xx` レスポンス。
- レスポンス形式は必ず以下に統一する。

```json
{
  "error": {
    "code": "SOME_ERROR_CODE",
    "message": "エラー内容を示すメッセージ",
    "details": {}
  }
}
```

- `error.code`
  - クライアント分岐に使う機械可読な識別子。
  - `UPPER_SNAKE_CASE` で固定し、文言変更で値を変えない。
  - 命名は `ドメイン_原因`（例: `SERIES_NOT_FOUND`, `NDL_API_UNAVAILABLE`）を基本とする。
- `error.message`
  - 人が読むための説明。
  - 表示向け文言として扱い、クライアント側の分岐条件には使わない。
- `error.details`
  - 追加情報を入れるオブジェクト。
  - 追加情報がない場合も `{}` を返し、`null` やキー省略はしない。
  - キー名は `lowerCamelCase` で統一する。
- HTTPステータスと `error.code` は常に整合させる（例: `404` + `SERIES_NOT_FOUND`）。

### エラーJSON例

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "リクエストパラメータが不正です。",
    "details": {
      "fieldErrors": [
        {
          "field": "title",
          "reason": "required"
        }
      ]
    }
  }
}
```

```json
{
  "error": {
    "code": "SERIES_NOT_FOUND",
    "message": "指定されたシリーズが見つかりません。",
    "details": {
      "seriesId": 123
    }
  }
}
```

```json
{
  "error": {
    "code": "NDL_API_UNAVAILABLE",
    "message": "外部書誌サービスに接続できませんでした。",
    "details": {
      "upstream": "NDL Search",
      "retryable": true
    }
  }
}
```

## PR運用の最小ルール
- 1PR = 1目的（小さく出す）
- PR本文に「目的」「変更概要」「動作確認」「影響範囲」を必ず記載
- CI（lint/format-check）が通っていることがレビュー前提
- 大きな変更は事前にIssueで合意
