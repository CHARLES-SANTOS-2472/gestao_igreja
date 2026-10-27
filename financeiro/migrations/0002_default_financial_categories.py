from django.db import migrations


DEFAULT_CATEGORIES = (
    ("income", "Dízimos"),
    ("income", "Ofertas"),
    ("income", "Doações"),
    ("income", "Outras receitas"),
    ("expense", "Despesas administrativas"),
    ("expense", "Água, energia e serviços"),
    ("expense", "Manutenção"),
    ("expense", "Missões"),
    ("expense", "Ação social"),
    ("expense", "Materiais e equipamentos"),
    ("expense", "Outras despesas"),
)


def create_default_categories(apps, schema_editor):
    category_model = apps.get_model("financeiro", "FinancialCategory")
    category_model.objects.using(schema_editor.connection.alias).bulk_create(
        [
            category_model(kind=kind, name=name)
            for kind, name in DEFAULT_CATEGORIES
        ],
        ignore_conflicts=True,
    )


def remove_default_categories(apps, schema_editor):
    category_model = apps.get_model("financeiro", "FinancialCategory")
    for kind, name in DEFAULT_CATEGORIES:
        category_model.objects.using(schema_editor.connection.alias).filter(
            kind=kind, name=name, transactions__isnull=True
        ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("financeiro", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            create_default_categories,
            reverse_code=remove_default_categories,
        ),
    ]
