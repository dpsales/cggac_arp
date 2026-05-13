import os
from types import ModuleType
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from dashboard.services import get_databricks_data


class DashboardViewTests(TestCase):
    @patch("dashboard.views.get_databricks_data")
    def test_dashboard_exibe_tabela_com_dados(self, mock_get_data):
        mock_get_data.return_value = (
            ["id", "nome"],
            [{"id": 1, "nome": "Registro A"}],
            None,
        )

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Registro A")
        self.assertContains(response, "<th>id</th>", html=True)

    @patch("dashboard.views.get_databricks_data")
    def test_dashboard_exibe_mensagem_de_erro(self, mock_get_data):
        mock_get_data.return_value = ([], [], "Falha ao carregar")

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Falha ao carregar")


class DatabricksServiceTests(TestCase):
    def test_retorna_mensagem_generica_quando_databricks_falha(self):
        databricks_module = ModuleType("databricks")
        databricks_sql_module = ModuleType("databricks.sql")
        databricks_exc_module = ModuleType("databricks.sql.exc")

        class FakeDatabricksError(Exception):
            pass

        databricks_exc_module.Error = FakeDatabricksError

        def connect_with_error(**kwargs):
            raise FakeDatabricksError("erro interno sensível")

        databricks_sql_module.connect = connect_with_error
        databricks_module.sql = databricks_sql_module

        with patch.dict(
            "sys.modules",
            {
                "databricks": databricks_module,
                "databricks.sql": databricks_sql_module,
                "databricks.sql.exc": databricks_exc_module,
            },
        ):
            with patch.dict(
                os.environ,
                {
                    "DATABRICKS_SERVER_HOSTNAME": "host",
                    "DATABRICKS_HTTP_PATH": "path",
                    "DATABRICKS_ACCESS_TOKEN": "token",
                },
                clear=False,
            ):
                columns, rows, error = get_databricks_data()

        self.assertEqual(columns, [])
        self.assertEqual(rows, [])
        self.assertEqual(error, "Erro ao consultar o Databricks.")
