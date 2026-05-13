from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch


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
