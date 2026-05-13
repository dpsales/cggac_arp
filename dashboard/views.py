from django.shortcuts import render

from dashboard.services import get_databricks_data


def dashboard_view(request):
    columns, rows, error = get_databricks_data()
    return render(
        request,
        "dashboard/index.html",
        {"columns": columns, "rows": rows, "error": error},
    )
