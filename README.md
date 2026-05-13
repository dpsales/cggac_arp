# cggac_arp

Dashboard Django para exibir dados consultados no Databricks.

## Como executar

1. Instale as dependências:

```bash
pip install -r requirements.txt
```

2. Configure as variáveis de ambiente:

```bash
export DATABRICKS_SERVER_HOSTNAME="<seu-host>.databricks.com"
export DATABRICKS_HTTP_PATH="/sql/1.0/warehouses/<warehouse-id>"
export DATABRICKS_ACCESS_TOKEN="<token>"
export DATABRICKS_QUERY="SELECT * FROM sua_tabela LIMIT 100"
export DJANGO_DEBUG="True"
export DJANGO_SECRET_KEY="<chave-secreta-django>"
export DJANGO_ALLOWED_HOSTS="127.0.0.1,localhost"
```

3. Rode o servidor:

```bash
python manage.py runserver
```

4. Acesse:

http://127.0.0.1:8000/
