# Restaurantes de España (proyecto de Ingeniería Web)

Red social de restaurantes hecha con Django: reseñas, fotos, mapa, colecciones, planes con amigos, historias de 24 horas,
diario, pasaporte, retos y recomendaciones.

## Arrancar el proyecto

```
pip install django pillow
python manage.py migrate
python manage.py runserver
```

Después se abre http://127.0.0.1:8000/. La administración está en `/admin/`.

## Pruebas

```
python manage.py test appRestaurantes
```

Usan una base de datos temporal; no tocan `db.sqlite3`.

## Documentación

Qué hace cada funcionalidad, las reglas del proyecto, los modelos y los límites conocidos: `docs/AMPLIACION_RED_SOCIAL.md`.
