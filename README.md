# ライブスケジュール文字列検索 Webアプリ

## Streamlit Community Cloudへの公開
1. GitHubで新しいリポジトリ `live-schedule-search` を作成します。
2. このフォルダーの `app.py` と `requirements.txt` をリポジトリの直下にアップロードします。READMEも任意でアップロードできます。
3. https://share.streamlit.io/ を開き、GitHubアカウントでサインインします。
4. **Create app** → **Yup, I have an app** を選びます。
5. Repositoryに `あなたのGitHub名/live-schedule-search`、Branchに `main`、Main file pathに `app.py` を指定します。
6. **Deploy** を押します。デプロイ完了後に `https://....streamlit.app` のURLが発行されます。
7. URLを利用者に共有します。

## 注意事項
- GitHubとStreamlit Community Cloudのアカウントが必要です。こちらから利用者のアカウントにログインして公開URLを発行することはできません。
- 公開設定にするとURLを知る人が利用できます。公開アプリでは、検索リクエストがこのアプリのホスティング環境から対象サイトに送信されます。
- 対象サイトのHTML構造・文字コード・クラウド環境からのアクセス可否は未検証です。公開後、まず数日だけ検索して確認してください。
- Streamlit Community Cloudは無料で利用できるプランがありますが、利用制限や提供条件は変更される場合があります。
