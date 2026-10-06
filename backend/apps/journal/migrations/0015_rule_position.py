from django.db import migrations, models


def initialize_positions(apps, schema_editor):
    Rule = apps.get_model("journal", "Rule")

    for index, rule in enumerate(Rule.objects.order_by("id")):
        rule.position = index
        rule.save(update_fields=["position"])


class Migration(migrations.Migration):
    dependencies = [("journal", "0014_brokersync")]
    operations = [
        migrations.AddField("rule", "position", models.PositiveIntegerField(default=0)),
        migrations.RunPython(initialize_positions, migrations.RunPython.noop),
        migrations.AlterModelOptions("rule", {"ordering": ["position", "id"]}),
    ]
