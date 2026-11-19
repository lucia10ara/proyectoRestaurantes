// Selección en dos pasos: al elegir una comunidad autónoma se rellena el desplegable de ciudades con las de esa comunidad.
// Cada <select> de comunidad lleva data-ciudades="id del select de ciudades" y data-url="dirección que devuelve las ciudades".
document.querySelectorAll('select[data-ciudades]').forEach(function (comunidad) {
    var ciudad = document.getElementById(comunidad.dataset.ciudades);
    if (!ciudad) return;
    var todas = ciudad.options[0] ? ciudad.options[0].text : '';

    comunidad.addEventListener('change', function () {
        ciudad.innerHTML = '';
        if (!comunidad.value) {
            ciudad.add(new Option(todas, ''));
            return;
        }
        ciudad.add(new Option('Cargando…', ''));
        fetch(comunidad.dataset.url + '?comunidad=' + encodeURIComponent(comunidad.value))
            .then(function (r) { return r.json(); })
            .then(function (datos) {
                ciudad.innerHTML = '';
                ciudad.add(new Option(ciudad.dataset.vacio || 'Todas las ciudades', ''));
                datos.forEach(function (c) { ciudad.add(new Option(c.nombre, c.id)); });
            })
            .catch(function () {
                ciudad.innerHTML = '';
                ciudad.add(new Option('No se pudieron cargar las ciudades', ''));
            });
    });
});
