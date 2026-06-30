# Hello Weekly 3 — 完全組み立てガイド
iOS Shortcuts × Gemini 2.5 Flash 日本語音声アシスタント  
対応iOS: iOS 26.5 / Gemini 2.5 Flash / 2026-06-27 設計 / 2026-06-30 更新

---

## はじめに

このガイドは iOS Shortcuts で動く日本語音声アシスタントを **ゼロから** 組み立てる手順書です。  
コピペが必要なのは **④ 本文JSON** と **⑤ エンドポイントURL** の 2か所のみです。

### 機能概要

| 発話例 | 動作 |
|--------|------|
| 「明日14時に歯医者を追加して」 | Calendarイベント作成 |
| 「牛乳を買うリマインダーを追加」 | Reminders追加 |
| 「今日の感想をメモしておいて」 | Notes新規作成 |
| 「最新のiPhoneを検索して」 | Safariでグーグル検索 |

### Hello Weekly 2 からの主な改善点

| 項目 | Hello Weekly 2 | Hello Weekly 3 |
|------|---------------|----------------|
| レスポンス解析 | 解析チェーン6連発 | ドット記法1発 `candidates.1.content.parts.1.text` |
| JSON品質 | 表記ゆれあり | `responseMimeType` + `responseSchema`（enum制約）で根絶 |
| 応答速度 | thinking ON（遅延あり） | `thinkingBudget:0` で遅延カット |
| 変数バインド | 分岐後にバインド | 辞書化直後に6変数を一括バインド（誤バインド防止） |
| リトライ | なし | 全体を「リピート3回」で包み自動リトライ |
| モデル | gemini-2.0-flash | gemini-2.5-flash |

---

## 第1章 準備

### 1-1. APIキー取得

1. [Google AI Studio](https://aistudio.google.com/) にアクセス
2. 「Get API key」→「Create API key」
3. キーをコピーしてメモアプリに一時保存（ショートカット完成後は削除）

> ⚠️ 旧キーがスクリーンショットに写った場合は必ず新規作成してください。

### 1-2. 無料枠の確認

- Gemini 2.5 Flash: 約10 RPM・250回/日（2026年6月時点）
- 正確な制限: AI Studio → 自アカウントの Rate Limits タブで確認
- 音声アシスタント用途なら無料枠で十分運用可能

### 1-3. ショートカット新規作成

1. Shortcuts アプリを開く
2. 右上「＋」をタップ → 新規ショートカット
3. 名前を「アシスタント」など任意の名前に設定

---

## 第2章 全体構造

### リトライ・ループ設計

全体を **「リピート3回（Repeat）」** で包みます。  
Gemini が `unknown` を返した場合、自動で最大3回リトライします。  
成功ルートの末尾に「ショートカットを停止（Stop Shortcut）」を置くことで **break** として機能します。

```
┌──────────────────────────────────────────────┐
│ Repeat 3 times                               │
│  ┌────────────────────────────────────────┐  │
│  │ Block A: 音声取得・プロンプト構築      │  │
│  │ Block B: Gemini API 呼び出し           │  │
│  │ Block C: レスポンス解析・6変数バインド │  │
│  │ Block D: operation で4分岐             │  │
│  │   ├─ create_calendar → 作成→読上→Stop │  │
│  │   ├─ create_reminder → 作成→読上→Stop │  │
│  │   ├─ create_note     → 作成→読上→Stop │  │
│  │   ├─ web_search      → 検索→読上→Stop │  │
│  │   └─ unknown         → 次のRepeatへ   │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
↓（3回ともunknownの場合）
「コマンドを認識できませんでした」音声出力
```

---

## 第3章 ブロックA：入力部

> ⚠️ 以降のすべてのアクションは **Repeatブロックの内側** に配置します。

### A-1. Repeatブロックの追加

1. アクション検索: `repeat` または「繰り返す」
2. **「Repeat」**（回数指定型）を追加
3. 回数を **3** に設定

### A-2. 音声入力の取得

1. アクション検索: `dictate` または「音声入力」
2. **「テキストを音声入力（Dictate Text）」** を追加
3. 設定:
   - 言語: **日本語**
   - 停止: **ポーズ後** または **タップ後**（好みで）

### A-3. voice_input 変数に保存

1. アクション: **「変数を設定（Set Variable）」**
2. 変数名: `voice_input`
3. 値: 前の「テキストを音声入力」の結果

### A-4. 現在の日時を取得

1. アクション検索: `current date` または「現在の日付」
2. **「現在の日付（Current Date）」** を追加
3. 変数名: `current_date`

### A-5. プロンプトの構築

1. アクション: **「テキスト（Text）」** を追加
2. 以下の内容を入力（変数は長押し→「変数を挿入」）:

```
以下の日本語コマンドを解析し、JSONで返答してください。

コマンド: [voice_input]
現在日時: [current_date]

注意事項:
- datetime は ISO 8601形式（例: 2026-07-01T15:00:00）
- 時刻が不明な場合は空文字 ""
- result_message は「〇〇をカレンダーに追加しました」のような日本語の完結文
```

3. 変数名: `prompt_text`

---

## 第4章 ブロックB：API呼び出し

> **コピペ箇所は④と⑤の2か所のみです。**

### B-1. URLアクションの追加

1. アクション検索: `url`
2. **「URL」** アクション（URLを保持するだけのアクション）を追加

### ⑤ エンドポイントURL（コピペその1 — B-1に貼り付け）

```
https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=YOUR_API_KEY
```

> `YOUR_API_KEY` を第1章で取得したキーに書き換える

### B-2. URLの内容を取得アクション

1. アクション検索: `get contents of url` または「URLの内容を取得」
2. **「URLの内容を取得（Get Contents of URL）」** を追加
3. URL: 前のステップのURL変数
4. **「詳細を表示（Show Details）」** をタップして展開
5. 設定:
   - メソッド: **POST**
   - ヘッダー: `Content-Type` = `application/json`
   - リクエスト本文: **JSON**（"テキスト"ではなく"JSON"を選択）

### ④ 本文JSON（コピペその2 — B-2のリクエスト本文に貼り付け）

```json
{"contents":[{"parts":[{"text":"[prompt_text変数]"}]}],"generationConfig":{"responseMimeType":"application/json","responseSchema":{"type":"object","properties":{"operation":{"type":"string","enum":["create_calendar","create_reminder","create_note","web_search","unknown"]},"app":{"type":"string","enum":["calendar","reminders","notes","safari","unknown"]},"title":{"type":"string"},"datetime":{"type":"string"},"end_datetime":{"type":"string"},"result_message":{"type":"string"}},"required":["operation","app","title","datetime","end_datetime","result_message"]},"thinkingConfig":{"thinkingBudget":0}}}
```

見やすい形式（確認用・ショートカットには上記の1行版を使用）:

```json
{
  "contents": [
    {
      "parts": [
        { "text": "[prompt_text変数]" }
      ]
    }
  ],
  "generationConfig": {
    "responseMimeType": "application/json",
    "responseSchema": {
      "type": "object",
      "properties": {
        "operation": {
          "type": "string",
          "enum": ["create_calendar", "create_reminder", "create_note", "web_search", "unknown"]
        },
        "app": {
          "type": "string",
          "enum": ["calendar", "reminders", "notes", "safari", "unknown"]
        },
        "title":          { "type": "string" },
        "datetime":       { "type": "string" },
        "end_datetime":   { "type": "string" },
        "result_message": { "type": "string" }
      },
      "required": ["operation", "app", "title", "datetime", "end_datetime", "result_message"]
    },
    "thinkingConfig": { "thinkingBudget": 0 }
  }
}
```

> ⚠️ `"[prompt_text変数]"` の箇所は貼り付け後に長押し→「変数を挿入」で `prompt_text` トークンに置き換えること

### B-3. レスポンスを変数に保存

1. 「URLの内容を取得」の結果を変数に設定
2. 変数名: `api_response`

---

## ✅ チェックポイント 1（Block B まで完成後にテスト）

▶ を押して実行し、以下を確認:

- [ ] 音声入力ダイアログが起動する
- [ ] APIが呼ばれてレスポンスが返る（エラーにならない）
- [ ] `api_response` に JSON 文字列が格納されている

エラーが出た場合 → 末尾のトラブルシュート表を参照

---

## 第5章 ブロックC：レスポンス解析

### Gemini APIレスポンスの構造

```json
{
  "candidates": [
    {
      "content": {
        "parts": [
          {
            "text": "{\"operation\":\"create_calendar\", ...}"
          }
        ]
      }
    }
  ]
}
```

### C-1. ドット記法でテキストを取り出す

> ⚠️ iOS Shortcuts の配列インデックスは **1始まり** です。

1. アクション: **「辞書の値を取得（Get Dictionary Value）」**
2. 辞書: `api_response`
3. キー: `candidates.1.content.parts.1.text`
4. 変数名: `response_json_text`

### C-2. JSON文字列をパース

1. アクション: **「テキストから辞書を取得（Get Dictionary from Input）」** または **「辞書を取得」**
2. 入力: `response_json_text`
3. 変数名: `response_dict`

### C-3. 6変数を一括バインド（⚠️ if分岐の前に必ず実施）

以下の6変数を **すべてこの位置（Ifの前）** でバインドします。  
Hello Weekly 2 の教訓: 分岐後バインドだと誤バインド事故が発生するため。

| 変数名 | 辞書のキー | 内容 |
|--------|-----------|------|
| `v_operation` | `operation` | 操作種別（create_calendar など） |
| `v_app` | `app` | 対象アプリ（calendar など） |
| `v_title` | `title` | イベント・タスク・メモのタイトル |
| `v_datetime` | `datetime` | 開始日時（ISO 8601） |
| `v_end_datetime` | `end_datetime` | 終了日時（ISO 8601） |
| `v_result_message` | `result_message` | Siriに読み上げさせるメッセージ |

各変数の追加手順（6回繰り返す）:
1. アクション: **「辞書の値を取得」**
2. 辞書: `response_dict`
3. キー: 上表の「辞書のキー」
4. 変数を設定: 上表の「変数名」

---

## 第6章 ブロックD：分岐・実行

`v_operation` の値で4分岐します。

### D-1. 最初の If

1. アクション: **「If」** を追加
2. 条件: `v_operation` **次と等しい（is）** → `create_calendar`

### D-2. create_calendar ブランチ（Ifの内側）

1. **「カレンダーイベントを追加（Add New Event）」**
   - タイトル: `v_title`
   - 開始日時: `v_datetime`
   - 終了日時: `v_end_datetime`（空の場合は開始+1時間が自動設定）
   - カレンダー: デフォルト
2. **「テキストを読み上げ（Speak Text）」** → `v_result_message`
3. **「ショートカットを停止（Stop Shortcut）」** ← ループ break

### D-3. Otherwise If: create_reminder

「Otherwise」ブロックの先頭に **「If」** を追加:
- 条件: `v_operation` **次と等しい** → `create_reminder`

内側:
1. **「リマインダーを追加（Add New Reminder）」**
   - タイトル: `v_title`
   - 期日: `v_datetime`（空の場合は期日なし）
2. **「テキストを読み上げ」** → `v_result_message`
3. **「ショートカットを停止」**

### D-4. Otherwise If: create_note

条件: `v_operation` **次と等しい** → `create_note`

内側:
1. **「テキスト」** → `v_title` + 改行 + `v_result_message` → 変数: `note_body`
2. **「メモを作成（Create Note）」** → テキスト: `note_body`
3. **「テキストを読み上げ」** → `v_result_message`
4. **「ショートカットを停止」**

### D-5. Otherwise If: web_search

条件: `v_operation` **次と等しい** → `web_search`

内側:
1. **「テキスト」** → `https://www.google.com/search?q=` + `v_title` → 変数: `search_url`
2. **「URLを開く（Open URLs）」** → `search_url`
3. **「テキストを読み上げ」** → `v_result_message`
4. **「ショートカットを停止」**

### D-6. Otherwise（unknown の場合）

何もアクションを追加しない → Repeat の次のイテレーションへ自動的に進む

### D-7. Repeat ブロックの外側（3回ともunknownの場合）

Repeat ブロックを閉じた後（外側）に追加:
1. **「テキストを読み上げ」**
   - テキスト: 「コマンドを認識できませんでした。もう一度お試しください。」

---

## ✅ チェックポイント 2：総合テスト

以下のコマンドを順番に試す:

| テストコマンド | 期待する動作 |
|----------------|-------------|
| 「明日14時に歯医者を追加して」 | Calendarに「歯医者」が作成される |
| 「牛乳を買うリマインダーを追加」 | Remindersに「牛乳を買う」が追加される |
| 「今日感じたことをメモしておいて」 | Notesに新規メモが作成される |
| 「最新のiPhoneを検索して」 | Safariでグーグル検索が開く |
| 「xyzzy」（意味不明な発話） | 3回後に「認識できませんでした」 |

---

## 第7章 完成・ショートカット設定

### 7-1. ショートカット名・アイコン

- 名前: 「アシスタント」（Siriで呼び出す名前になる）
- アイコン・カラーは任意で設定

### 7-2. Siriへの登録

1. ショートカット設定（...）→「Siriに追加」
2. フレーズを録音:「ねえ Siri、アシスタント」
3. または好みのフレーズで登録

### 7-3. ウィジェット・アクションボタン

- **ホーム画面ウィジェット**: ホーム長押し → ウィジェット追加 → Shortcuts
- **アクションボタン**（iPhone 15 Pro以降）: 設定 → アクションボタン → ショートカット

---

## 拡張メニュー（組み立て完了後に実装）

### E1. 予定の読み上げ + AI要約（read_calendar）

responseSchema の enum に `"read_calendar"` を追加し、D分岐に追加:
- 「今日の予定を教えて」などに対応
- Shortcuts の「カレンダーイベントを検索」で予定を取得
- 取得した予定リストを Gemini に渡して自然言語要約を生成
- Speak Text で読み上げ

### E2. Web検索 + AI要約（クエリ最適化）

現状はタイトルをそのまま検索URL に使用している。  
改善案: Gemini にクエリ最適化させてから検索。  
prompt_text に「検索クエリを最適化して title フィールドに入れてください」を追加。

### E3. 削除実装（delete_calendar / delete_reminder）

enum に `"delete_calendar"`, `"delete_reminder"` を追加:
- 「〇〇の予定を削除して」に対応
- 該当イベントを Shortcuts で検索し、確認ダイアログ後に削除

> ⚠️ 削除は「本当に削除しますか？」の確認ダイアログを必ず入れること

### E4. 編集実装（edit_calendar / edit_note）

enum に `"edit_calendar"`, `"edit_note"` を追加:
- 「〇〇の予定を〇〇に変更して」に対応
- 既存イベントの検索（Shortcuts の「カレンダーイベントを検索」）が必要

### E5. 天気・タイマー

- **天気**:「今日の天気は？」→ Shortcuts の「現在の天気状況を取得」アクションを使用（Gemini 不要）
- **タイマー**:「〇分のタイマーをセット」→「タイマーを開始（Start Timer）」アクションを使用  
  datetime フィールドに分数を返すようプロンプトを修正

---

## トラブルシュート表

| 症状 | 原因 | 対処 |
|------|------|------|
| APIエラー 400 | JSONの形式が不正 | ④本文JSONを再コピペ。prompt_text変数が正しく挿入されているか確認 |
| APIエラー 403 | APIキーが無効 | AI StudioでAPIキーを再生成 |
| APIエラー 429 | レート制限超過 | しばらく待つ。無料枠（250回/日）に達した可能性あり |
| 変数が空になる | バインド順序が間違い | C-3の6変数バインドを If の前に移動 |
| 配列エラー | インデックスが0始まりになっている | `candidates.1`（1始まり）に修正 |
| unknownばかり返る | プロンプトの指示が不明確 | A-5のプロンプトにコマンド例を追加 |
| JSON解析エラー | thinkingが有効になっている | `thinkingBudget:0` を確認 |
| Siriが反応しない | フレーズ登録が未完了 | 7-2を再実行 |

---

## 技術メモ

```
配列インデックス : iOS Shortcuts は 1始まり
                  → candidates.1.content.parts.1.text

変数バインド順序 : 6変数は if 分岐の前に実施（誤バインド防止）

thinkingBudget  : Gemini 2.5 Flash はデフォルト ON
                  → thinkingBudget:0 は必須（遅延防止）

responseSchema  : enum 制約で operation/app の表記ゆれを根絶
                  required で全6フィールドを強制出力

リトライ設計    : Repeat 3 = 最大3回リトライ
                  成功時は Stop Shortcut でループを抜ける（break相当）

.shortcut方式   : plistlib での構造生成は可能だが
                  iOS バージョンによりアクション識別子が変わるリスクあり
                  → 手動組み立て（このガイド方式）を推奨
```

---

*Hello Weekly 3 / iOS 26.5 対応 / Gemini 2.5 Flash / 設計: 2026-06-27 / 更新: 2026-06-30*
