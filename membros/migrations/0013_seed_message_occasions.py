from django.db import migrations

# (nome, mês, dia fixo, domingo do mês, orientação para a IA)
OCCASIONS = [
    ("Ano Novo", 1, 1, None, "Mensagem de esperança e renovação para o novo ano."),
    ("Dia Internacional da Mulher", 3, 8, None, "Honrar e valorizar as mulheres da igreja."),
    ("Dia das Mães", 5, None, 2, "Homenagem às mães, com gratidão pelo amor e pelas orações."),
    ("Dia dos Namorados", 6, 12, None, "Mensagem sobre amor e compromisso à luz da Palavra."),
    ("Dia dos Pais", 8, None, 2, "Homenagem aos pais, com gratidão pelo exemplo e cuidado."),
    ("Dia do Pastor", 10, None, 2, "Gratidão ao pastor e à sua família; as palavras são dirigidas à pessoa que recebe."),
    ("Dia das Crianças", 10, 12, None, "Mensagem carinhosa sobre o valor das crianças para Deus."),
    ("Dia da Bíblia", 12, None, 2, "Valorizar a Palavra de Deus."),
    ("Natal", 12, 25, None, "Celebrar o nascimento de Jesus."),
]


def seed(apps, schema_editor):
    MessageOccasion = apps.get_model("membros", "MessageOccasion")
    for name, month, day, nth, guidance in OCCASIONS:
        MessageOccasion.objects.get_or_create(
            name=name, month=month, day=day, defaults={"nth_sunday": nth, "ai_guidance": guidance},
        )


class Migration(migrations.Migration):

    dependencies = [
        ("membros", "0012_messageoccasion_movable"),
    ]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
