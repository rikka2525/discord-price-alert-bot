# Discord Price Alert Bot

暗号資産の価格を定期的に確認し、指定価格に到達したらDiscordへ通知するポートフォリオ用Botです。

ユーザーがスラッシュコマンドで通知条件を登録すると、BotがCoinGecko APIから価格を取得して監視します。条件到達後はメンション付きで通知し、通知済みの条件を自動削除します。

## できること

| コマンド | 内容 |
| --- | --- |
| `/register` | 銘柄・目標価格・上昇/下落条件を登録 |
| `/list` | 自分が登録した通知を一覧表示 |
| `/delete` | 通知番号を指定して削除 |
| `/price` | 指定銘柄の現在価格をその場で確認 |

そのほか、SQLiteへの設定保存、一定間隔での自動確認、API障害時のリトライ、ユーザーごとのアクセス制御、`.env`によるトークン管理、ログ出力、ユニットテストに対応しています。

## 利用イメージ

![登録・一覧・自動通知のデモ](docs/demo.svg)

画像は2026年9月4日に確認した実際の応答をもとに、個人情報を除いて再現したものです。価格は動作確認時の値であり、現在価格ではありません。

```text
/register coin_id:bitcoin target_price:100000 direction:目標価格以上

Bot:
通知 #1 を登録しました。
bitcoin が $100,000.00 以上
現在価格: $96,500.00
```

条件に到達すると、登録したチャンネルへ次のように通知します。

```text
🔔 @user 価格アラート
bitcoin が $100,120.50 になりました。
設定条件: $100,000.00 以上
```

## 使用技術

- Python 3.11+
- discord.py 2.x
- aiohttp / REST API
- SQLite
- CoinGecko API
- unittest

## セットアップ

### 1. Discord Botを作成

1. [Discord Developer Portal](https://discord.com/developers/applications)でApplicationを作成します。
2. `Bot`画面からBotを追加し、トークンを取得します。
3. `OAuth2 > URL Generator`で `bot` と `applications.commands` を選択します。
4. Bot権限で `View Channels` と `Send Messages` を選び、生成されたURLからサーバーへ招待します。

このBotはメッセージ本文を読む必要がないため、Message Content Intentは不要です。

### 2. Python環境を準備

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

macOS / Linuxの場合:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### 3. 環境変数を設定

`.env.example`をコピーして`.env`を作り、Discord Botのトークンを設定します。

```env
DISCORD_TOKEN=取得したBotトークン
CHECK_INTERVAL_MINUTES=5
DATABASE_PATH=alerts.db
LOG_LEVEL=INFO
```

`.env`とSQLiteファイルは`.gitignore`で除外しています。ただし、すでにGitで追跡しているファイルや手動アップロードには効かないため、公開前に必ず対象を確認してください。トークンはREADMEや画像にも載せないでください。

### 4. 起動

```powershell
python bot.py
```

起動後、Discordサーバーでスラッシュコマンドが使えるようになります。グローバルコマンドの反映には時間がかかる場合があります。

## 銘柄IDについて

`coin_id`にはティッカーではなくCoinGeckoのIDを指定します。例: Bitcoinは`bitcoin`、Ethereumは`ethereum`、Solanaは`solana`です。

## テスト

```powershell
python -m unittest discover -s tests -v
```

データベースの登録・一覧・削除・権限制御と、価格条件の判定を外部APIやDiscord接続なしで確認できます。

### 実動作の確認結果

2026年9月4日、Windows環境・Python 3.12・テスト用Discordサーバーで確認しました。

| 項目 | 結果 |
| --- | --- |
| `/price` から外部APIの価格を取得 | 成功 |
| `/register` で登録し `/list` に表示 | 成功 |
| 定期チェックによるメンション付き通知 | 成功 |
| 通知後に対象条件を自動削除 | 成功 |
| `/delete` による手動削除 | 成功 |
| 存在しない通知番号への案内 | 成功 |
| Bot再起動後も通知 #3 の設定を保持 | 成功 |
| 自動テスト | 5件成功 |

API障害・レート制限・権限不足の実環境での強制発生テスト、長期連続稼働、大量登録の負荷テストは未実施です。

### デモを再現する手順

1. `/price coin_id:bitcoin` で価格取得を確認します。
2. `/register` で `bitcoin`、目標価格 `1`、`目標価格以上` を登録します。
3. `/list` で一覧を確認します。
4. 次の定期チェックを待ちます（既定は5分間隔。API障害時などは遅れる場合があります）。
5. 通知後の `/list` が空になることを確認します。
6. `bitcoin`、目標価格 `1`、`目標価格以下` を登録し、Botを停止・再起動して `/list` に残ることを確認します。
7. 表示された番号を `/delete` に指定し、テスト用の登録を削除します。

これは通知テストであり、売買注文は一切行いません。

## 構成

```text
discord-price-alert-bot/
├── bot.py                 # Discordコマンドと定期処理
├── api_client.py          # CoinGecko API通信とリトライ
├── database.py            # SQLite操作
├── logic.py               # 価格到達の判定ロジック
├── config.py              # 環境変数の読み込み
├── docs/demo.svg          # 個人情報を除いたデモ画像
├── tests/
│   ├── test_bot_logic.py
│   └── test_database.py
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## 設計上のポイント

- Discordの処理を止めないよう、SQLite操作は別スレッドで実行しています。
- 登録銘柄をまとめて取得し、APIへのリクエスト数を抑えています。
- レート制限や一時障害では、待ち時間を延ばしながら最大3回再試行します。
- 削除時はサーバーIDとユーザーIDを照合し、本人の登録だけを操作します。
- 一度通知した条件は削除し、同じ通知が繰り返されないようにしています。

## 発展例

案件要件に応じて、管理者向けコマンド、Web管理画面、複数通貨、通知履歴、Docker化、クラウドへの常時稼働などを追加できます。

## 注意事項

- Botのプロセスが動いている間だけ監視します。PC停止・スリープ中は通知できません。
- 小規模・単一プロセスでのデモ利用を想定しています。
- 通知送信とDB削除は一つの処理として保証されていないため、その間に停止すると再通知される可能性があります。
- 通知先の削除や権限不足により送信できない場合は登録を保持し、ログを出力します。
- 大量登録向けの一覧分割や登録数制限は未実装です。

このリポジトリは技術デモです。取得価格の正確性・リアルタイム性を保証するものではなく、投資判断を目的としていません。CoinGecko APIの利用条件とレート制限に従って使用してください。
