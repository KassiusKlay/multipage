mkdir -p ~/.streamlit/

echo "
[server]\n
headless = true\n
port = $PORT\n
enableCORS = false\n
\n
" > ~/.streamlit/config.toml


echo "
[postgres]\n
host = $DB_HOST\n
port = $DB_PORT\n
dbname = $DB_NAME\n
user = $DB_USER\n
password = $DB_PSWD\n
\n
" > ~/.streamlit/secrets.toml
