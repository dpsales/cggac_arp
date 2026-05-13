import os


def get_databricks_data():
    try:
        from databricks import sql
    except ImportError:
        return [], [], "Dependência 'databricks-sql-connector' não instalada."

    query = os.getenv("DATABRICKS_QUERY", "SELECT 1 AS exemplo")
    config = {
        "server_hostname": os.getenv("DATABRICKS_SERVER_HOSTNAME"),
        "http_path": os.getenv("DATABRICKS_HTTP_PATH"),
        "access_token": os.getenv("DATABRICKS_ACCESS_TOKEN"),
    }

    missing = [key for key, value in config.items() if not value]
    if missing:
        return [], [], f"Configuração ausente: {', '.join(missing)}"

    try:
        with sql.connect(**config) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                columns = [column[0] for column in cursor.description or []]
                rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return columns, rows, None
    except Exception as error:  # pragma: no cover
        return [], [], f"Erro ao consultar o Databricks: {error}"
