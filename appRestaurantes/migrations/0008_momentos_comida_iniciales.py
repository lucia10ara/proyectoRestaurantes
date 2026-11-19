from django.db import migrations

#los cinco tipos de comida por los que se puede filtrar (datos fijos, se crean una sola vez)
MOMENTOS = [('desayuno', 'Desayuno', 1), ('brunch', 'Brunch', 2), ('comida', 'Comida', 3), ('merienda', 'Merienda', 4), ('cena', 'Cena', 5)]


def crear(apps, schema_editor):
    MomentoComida = apps.get_model('appRestaurantes', 'MomentoComida')
    for clave, nombre, orden in MOMENTOS:
        MomentoComida.objects.get_or_create(clave=clave, defaults={'nombre': nombre, 'orden': orden})
    #al añadir fecha_alta, Django pone "ahora" a todos los restaurantes que ya existían. No es verdad
    #(no sabemos cuándo se añadieron), así que la dejamos vacía: solo la tendrán los que se añadan desde hoy
    apps.get_model('appRestaurantes', 'Restaurante').objects.update(fecha_alta=None)


def borrar(apps, schema_editor):
    apps.get_model('appRestaurantes', 'MomentoComida').objects.filter(clave__in=[m[0] for m in MOMENTOS]).delete()


class Migration(migrations.Migration):
    dependencies = [('appRestaurantes', '0007_base_guardados_visitas_y_datos')]
    operations = [migrations.RunPython(crear, borrar)]
