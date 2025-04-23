import streamlit as st
import hashlib
import sqlite3
import pandas as pd
import threading

# データベースファイル名
DB_FILE = 'app.db'

# ロックオブジェクトを作成
db_lock = threading.Lock()

@st.cache_resource()  # キャッシュを有効化
def get_db_connection():
# データベース接続をキャッシュする関数
    return sqlite3.connect(DB_FILE, check_same_thread=False)

# データベース操作関数
def execute_sql(sql, params=()):
    with db_lock:
      conn = get_db_connection()
      c = conn.cursor()
      c.execute(sql, params)
      conn.commit()
      result= c.fetchall()  # 結果を取得取得
      return result  # 結果を返す
      conn.close()  # 接続を閉じる閉じる


# テーブル作成とインデックス追加
execute_sql('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
''')
execute_sql('''
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        project_name TEXT NOT NULL,
        checked INTEGER NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
''')
execute_sql("CREATE INDEX IF NOT EXISTS idx_username ON users (username)")



# ハッシュ関数
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


# ユーザー登録
def register():
    st.title("ユーザー登録")
    new_username = st.text_input("新しいユーザー名")
    new_password = st.text_input("新しいパスワード", type="password")
    confirm_password = st.text_input("パスワード確認", type="password")

    if st.button("登録"):
        if new_password != confirm_password:
            st.error("パスワードが一致しません。")
        else:
            hashed_password = hash_password(new_password)
            with db_lock:
                try:
                    execute_sql("INSERT INTO users (username, password) VALUES (?, ?)", (new_username, hashed_password))
                    st.success("登録が完了しました！ログインしてください。")
                    st.session_state.register_success = True  # 登録成功フラグを設定
                    st.rerun()  # ログイン画面に遷移

                except sqlite3.IntegrityError:
                    st.error("このユーザー名は既に使用されています。")

@st.cache_data()  # キャッシュを有効化
def fetch_user(username, hashed_password):
     return execute_sql("SELECT * FROM users WHERE username = ? AND password = ?", (username, hashed_password))



# ログイン画面
def login():
    st.title("ログイン")
    if 'register_success' in st.session_state and st.session_state.register_success:
        st.success("登録が完了しました！ログインしてください。")
        del st.session_state.register_success
    username = st.text_input("ユーザー名")
    password = st.text_input("パスワード", type="password")

    if st.button("ログイン"):
        hashed_password = hash_password(password)
        user = fetch_user(username, hashed_password) # キャッシュされた関数を使用

        if user:
            st.session_state.user_id = user[0][0]
            st.session_state['logged_in'] = True # ログイン状態をセッション状態に保存
            st.success("ログインに成功しました！")
            st.rerun()  # メイン画面に遷移

        else:
            st.error("ユーザー名またはパスワードが間違っています。")

    if st.button("新規登録"):
        st.session_state.new_user = True
        st.rerun()  # 登録画面に遷移


def update_projects_view(user_id, projects):
    """案件の表示を更新する関数"""
    checked_count = 0
    project_data = []
    project_checks = {}

    for project_name, description in projects.items():
        col1, col2 = st.columns([1, 3])
        with col1:
            with db_lock:
                result = execute_sql("SELECT checked FROM projects WHERE user_id = ? AND project_name = ?", (user_id, project_name))
                checked = result[0][0] if result else 0 # タプルのリストから値を取り出す

            project_checks[project_name] = st.checkbox("", key=project_name, value=(checked == 1))

            if checked:
                st.markdown(f"<span style='color:green;'>● {project_name}</span>", unsafe_allow_html=True)
                checked_count += 1
            else:
                st.markdown(f"<span style='color:red;'>● {project_name}</span>", unsafe_allow_html=True)

            project_data.append([project_name, "〇" if checked else "×"])

        with col2:
            st.write(description)

    df_projects = pd.DataFrame(project_data, columns=["案件名", "登録状況"])
    st.table(df_projects)

    return checked_count, project_checks




# メイン画面
def main():
    if 'new_user' in st.session_state and st.session_state.new_user:  # 新規登録からの遷移時
        register()
        if 'register_success' in st.session_state and st.session_state.register_success:
            del st.session_state.new_user # new_userフラグを削除
            del st.session_state.register_success


    elif 'user_id' not in st.session_state:  # 未ログイン時
        login()
    else: # ログイン済み
        st.title("案件一覧")
        user_id = st.session_state.user_id
        with db_lock:
            result = execute_sql("SELECT username FROM users WHERE id = ?", (user_id,))
            username = result[0][0] if result else None
        if username:
          st.write(f"ようこそ、{username}さん！")
        else:
          st.error("ユーザ情報が取得できませんでした")

        projects = {
            "案件１": "１５年のトーク",
            "案件２": "１０年のトーク"
        }


        checked_count, project_checks = update_projects_view(user_id, projects)

        if st.button("登録"):
            with db_lock:
                for project_name, checked_state in project_checks.items():
                    execute_sql("INSERT OR REPLACE INTO projects (user_id, project_name, checked) VALUES (?, ?, ?)",
                              (user_id, project_name, 1 if checked_state else 0))


            st.success("登録完了しました！")

            checked_count, project_checks = update_projects_view(user_id, projects)



# アプリ実行
if __name__ == "__main__":
    main()

