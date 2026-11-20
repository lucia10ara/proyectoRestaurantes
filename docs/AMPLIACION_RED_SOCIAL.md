# Ampliación «red social» de Restaurantes de España

Documento de referencia de las 13 funcionalidades añadidas a la aplicación en los bloques 0 a 8. Pensado para quien
tenga que mantener, defender o ampliar el proyecto.

## 1. Las 13 funcionalidades y dónde están

| # | Funcionalidad | Dirección | Quién la ve | Bloque |
|---|---|---|---|---|
| 1 | Mapa de restaurantes (con filtros, grupos de puntos y «Cerca de mí») | `/mapa/` | Todos | 2 |
| 2 | Amigos que han estado / recomiendan / lo tienen guardado | Ficha del restaurante | Con sesión | 1 |
| 3 | Recomendaciones «Para ti» (con el motivo de cada una) | `/descubre/para-ti/` | Con sesión | 7 |
| 4 | Planes entre amigos (invitar, responder, cancelar) | `/planes/` | Creador e invitados | 4 |
| 5 | Colecciones (públicas o privadas) | `/perfiles/<id>/colecciones/` | Según visibilidad | 3 |
| 6 | Historias de 24 horas | Tira del inicio, `/historias/<id>/` | Autor y sus seguidores | 5 |
| 7 | Diario | `/diario/` | Solo su dueño | 6 |
| 8 | Novedades y joyas ocultas | `/descubre/novedades/`, `/descubre/joyas/` | Todos | 7 |
| 9 | Filtros avanzados | Lista, Explorar, Mapa, Descubre | Todos | 1 |
| 10 | Reseñas por categorías (comida, servicio, ambiente, calidad-precio) | Al reseñar y en la ficha | Todos | 1 |
| 11 | Pasaporte de sellos | `/diario/pasaporte/` | Solo su dueño | 6 |
| 12 | Ruleta | `/descubre/ruleta/` | Todos | 7 |
| 13 | Retos | `/diario/retos/` | Solo su dueño | 6 |

Además: avisos (notificaciones) en `/avisos/` y guardados («Guardar para ir») desde el bloque 0.

## 2. Reglas que se han respetado en todo el proyecto

- **Visita confirmada.** Solo la crea la propia persona, con el botón «He estado aquí» (con fecha) o la casilla «Estuve aquí»
  al reseñar. Guardar, mirar, subir una foto o ir a un plan **no** cuentan. De las visitas salen el diario, el pasaporte,
  los retos, «amigos que han estado» y el filtro «Donde aún no he estado».
- **Lo desconocido no se enseña como confirmado.** Los datos de un restaurante que no se conocen (precio, terraza, menú…)
  están vacíos (`null`), y los filtros solo devuelven los que tienen ese dato confirmado.
- **Privacidad.** Lo privado responde 404 (no «prohibido») a quien no puede verlo, para no revelar que existe:
  colecciones privadas, planes ajenos e historias de gente a la que no se sigue.
- **Diseño.** Paleta marrón y beige. Las variables CSS se llaman `--azulejo`/`--azafran` por historia, pero valen marrón y arena.
- **Amigos** = seguimiento mutuo. Solo se puede invitar a planes a amigos.

## 3. Modelos nuevos (migraciones 0007 a 0012)

| Modelo | Para qué |
|---|---|
| `MomentoComida` | Desayuno, brunch, comida, cena, merienda (filtro) |
| `Guardado` | Restaurante pendiente de visitar |
| `Visita` | Visita confirmada (única por persona, restaurante y día) |
| `Coleccion`, `ElementoColeccion` | Lista temática con nota personal por restaurante |
| `Notificacion` | Aviso con texto y enlace ya escritos |
| `Plan`, `Invitacion` | Quedada y respuesta de cada invitado |
| `Historia` | Imagen con caducidad a las 24 h; `vista_por` guarda quién la vio |

Campos nuevos: notas por categoría en `Resena`; latitud, longitud, precio, terraza, menú del día, vegetariano, vegano,
grupos, accesible y `fecha_alta` en `Restaurante`.

## 4. Organización del código

- `views.py` (lectura pública), `views_social.py` (publicar y moderar), y un módulo por bloque: `views_colecciones.py`,
  `views_planes.py`, `views_historias.py`, `views_avisos.py`, `views_diario.py`, `views_descubre.py`.
- `filtros.py`: **un único sitio** donde se aplican los filtros; lo usan la lista, Explorar, el mapa, Novedades, Joyas y la ruleta.
- `recomendaciones.py` y `logros.py`: la lógica de «Para ti», joyas, pasaporte y retos, separada de las vistas.
- `notificaciones.py`: `notificar()` y el contador de avisos del menú (context processor).
- `static/js/mapa.js` y `static/vendor/`: el mapa usa Leaflet incluido en el proyecto (no depende de ningún CDN).

## 5. Cómo funciona lo menos obvio

- **Mapa.** La página pide por AJAX (`/mapa/datos/`) solo los restaurantes de la zona visible, con un máximo de 400, y avisa
  si hay más. Los nombres se pintan con `textContent` (nunca como HTML). OpenStreetMap exige el encabezado Referer, por eso
  `mapa.js` fija `referrerPolicy`. La ubicación del usuario solo se pide al pulsar «Cerca de mí» y no se guarda.
- **Historias.** Dejan de verse solas a las 24 h (la consulta filtra por `caduca`). Para liberar los archivos hay que ejecutar
  `python manage.py limpiar_historias`, a mano o programado cada día. Máximo 10 activas por persona.
- **Para ti.** Suma puntos por lo que recomiendan (4 o 5 estrellas) las personas a las que sigues, por la cocina que te gusta
  en tu ciudad y por la nota. Nunca incluye lo ya visitado, guardado o reseñado, respeta «con niños» y «con perro», y excluye
  los mal valorados. Si no hay nada que cruzar, enseña los mejor valorados de tu ciudad.
- **Joyas.** Media de 4,5 o más con entre 2 y 10 reseñas (una sola reseña no basta).
- **Novedades.** Solo cuentan los restaurantes con `fecha_alta`; los importados antes de que existiera ese dato la tienen
  vacía a propósito, porque no sabemos cuándo se añadieron.
- **Ruleta.** Exige acotar por comunidad o ciudad, elige por posición aleatoria (sin ordenar los 62.000 restaurantes) y no
  repite el que acaba de salir.

## 5 bis. Seguridad y rendimiento

- Todo lo que modifica datos exige sesión y método POST (con protección CSRF); editar o borrar exige ser el dueño o la
  administradora. Hay tests de permisos para colecciones, planes, historias y avisos.
- Las redirecciones con `next` solo aceptan direcciones de esta misma web.
- Las imágenes subidas pasan por Pillow y tienen un límite de 5 MB (fotos e historias).
- `RendimientoTests` comprueba que ninguna página hace más consultas a la base de datos cuanto más contenido tiene
  (evita el problema N+1). Con ello se corrigió que cada tarjeta de restaurante hiciera una consulta para su foto.
- **Antes de publicar en un servidor real** (`python manage.py check --deploy` lo avisa): poner `DEBUG = False`, rellenar
  `ALLOWED_HOSTS`, cambiar `SECRET_KEY` por una clave larga y secreta (la actual es de desarrollo y está en el repositorio),
  y activar las cookies seguras y HTTPS.

## 6. Pruebas y datos

- `python manage.py test appRestaurantes` ejecuta las 91 pruebas automáticas, con una base de datos temporal.
- Antes de cada migración se hizo una copia de la base de datos (`db_copia_antes_bloqueN.sqlite3`, fuera de git).
- Datos reales: 62.962 restaurantes importados, de los que 62.636 tienen coordenadas y salen en el mapa (a 20 nov 2026); ninguno tiene todavía precio y unos 8.400 tienen el dato de terraza.

## 7. Límites conocidos

- Los restaurantes sin coordenadas no salen en el mapa hasta que se les ponga ubicación (la administradora puede hacerlo).
- Los planes no se pueden editar: se cancelan y se crea otro.
- No hay avisos por «me gusta» (decisión para no saturar); sí por seguidor, comentario y planes.
- El diario, el pasaporte y los retos son personales: no hay versión pública.
