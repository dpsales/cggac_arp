from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter(name='moeda_br')
def moeda_br(value):
    """Formata numero em padrao brasileiro: 1.234.567,89."""
    if value in (None, ''):
        return '0,00'

    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return value

    formatted = f"{number:,.2f}"
    return formatted.replace(',', 'X').replace('.', ',').replace('X', '.')
