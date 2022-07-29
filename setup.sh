mkdir -p ~/.streamlit

printf "
[server]
headless = true
port = $PORT
enableCORS = false
" > ~/.streamlit/config.toml


printf "
joaocassis = $PSWD

[postgres]
host = $DB_HOST
port = $DB_PORT
dbname = $DB_NAME
user = $DB_USER
password = $DB_PSWD
" > ~/.streamlit/secrets.toml
