// Mapa de restaurantes (Leaflet + OpenStreetMap).
// 1) pide la zona que ocupan los resultados para encuadrar el mapa; 2) cada vez que se mueve, pide los puntos de la zona visible.
// Los filtros son los de la URL de la página. Los textos de los restaurantes se ponen con textContent (nunca como HTML).
(function () {
    var caja = document.getElementById('mapa');
    if (!caja || !window.L) return;

    var estado = document.getElementById('mapa-estado');
    var urlDatos = caja.dataset.url;
    var focoId = caja.dataset.foco ? Number(caja.dataset.foco) : null;

    // filtros de la página (sin el parámetro foco, que solo sirve para el primer encuadre)
    var filtros = new URLSearchParams(window.location.search);
    filtros.delete('foco');
    filtros.delete('page');

    var mapa = L.map(caja).setView([40.2, -3.7], 6);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        referrerPolicy: 'strict-origin-when-cross-origin',  // OpenStreetMap exige Referer; Django por defecto no lo manda a otros dominios
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    }).addTo(mapa);

    var grupo = L.markerClusterGroup({ showCoverageOnHover: false, maxClusterRadius: 45 });
    mapa.addLayer(grupo);

    var marcadores = {};       // id del restaurante -> marcador (para abrir el del foco)
    var peticion = 0;          // número de la última petición: las respuestas antiguas se descartan
    var temporizador = null;

    function texto(tag, clase, contenido) {
        var e = document.createElement(tag);
        if (clase) e.className = clase;
        e.textContent = contenido;
        return e;
    }

    function ventana(r) {
        var d = document.createElement('div');
        d.className = 'mapa-ficha';
        var titulo = document.createElement('a');
        titulo.href = r.url;
        titulo.className = 'mapa-ficha-titulo';
        titulo.textContent = r.nombre;
        d.appendChild(titulo);
        d.appendChild(texto('div', 'meta', r.cocina + ' · ' + r.ciudad));
        if (r.direccion) d.appendChild(texto('div', 'meta', r.direccion));
        d.appendChild(texto('div', 'mapa-ficha-nota',
            r.media !== null ? '★ ' + r.media.toFixed(1).replace('.', ',') + ' (' + r.resenas + ' reseña' + (r.resenas === 1 ? '' : 's') + ')'
                             : 'Todavía sin reseñas'));
        var como = document.createElement('a');
        como.href = 'https://www.openstreetmap.org/directions?to=' + r.lat + '%2C' + r.lon;
        como.target = '_blank';
        como.rel = 'noopener';
        como.textContent = 'Cómo llegar';
        d.appendChild(como);
        return d;
    }

    function pintar(datos) {
        grupo.clearLayers();
        marcadores = {};
        datos.restaurantes.forEach(function (r) {
            var m = L.circleMarker([r.lat, r.lon], {
                radius: 8, weight: 2, color: '#3A2418', fillColor: '#D2BBA0', fillOpacity: 0.95
            });
            m.bindPopup(function () { return ventana(r); });
            marcadores[r.id] = m;
            grupo.addLayer(m);
        });
        var n = datos.restaurantes.length;
        if (datos.total === 0) {
            estado.textContent = 'No hay restaurantes con ubicación en esta zona.';
        } else if (datos.total > n) {
            estado.textContent = 'Se enseñan ' + n + ' de ' + datos.total.toLocaleString('es-ES') + ' restaurantes de esta zona. Acerca el mapa para ver los demás.';
        } else {
            estado.textContent = datos.total.toLocaleString('es-ES') + ' restaurante' + (datos.total === 1 ? '' : 's') + ' en esta zona.';
        }
    }

    function cargar() {
        var b = mapa.getBounds();
        var p = new URLSearchParams(filtros);
        p.set('sur', b.getSouth());
        p.set('norte', b.getNorth());
        p.set('oeste', b.getWest());
        p.set('este', b.getEast());
        var esta = ++peticion;
        estado.textContent = 'Buscando…';
        return fetch(urlDatos + '?' + p.toString())
            .then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
            .then(function (datos) {
                if (esta !== peticion) return;  // ya se pidió otra zona
                pintar(datos);
                if (focoId && marcadores[focoId]) {
                    var m = marcadores[focoId];
                    focoId = null;
                    grupo.zoomToShowLayer(m, function () { m.openPopup(); });
                }
            })
            .catch(function () {
                if (esta === peticion) estado.textContent = 'No se pudieron cargar los restaurantes. Inténtalo de nuevo.';
            });
    }

    mapa.on('moveend', function () {
        clearTimeout(temporizador);
        temporizador = setTimeout(cargar, 250);  // espera a que termine de moverse
    });

    // primer encuadre: el restaurante enfocado, o la zona que ocupan los resultados
    var inicial = new URLSearchParams(window.location.search);
    inicial.delete('page');
    inicial.set('inicial', '1');
    fetch(urlDatos + '?' + inicial.toString())
        .then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
        .then(function (d) {
            if (d.foco) mapa.setView([d.foco.lat, d.foco.lon], 17);
            else if (d.zona) mapa.fitBounds(d.zona, { padding: [30, 30] });
            else { estado.textContent = 'Ningún restaurante con ubicación cumple esos filtros.'; return; }
            cargar();  // por si el encuadre no cambió y no se dispara moveend
        })
        .catch(function () { estado.textContent = 'No se pudo cargar el mapa. Inténtalo de nuevo.'; });

    // "Cerca de mí": la ubicación se pide solo al pulsar el botón y no se guarda en ningún sitio
    var boton = document.getElementById('mapa-cerca');
    var yo = null;
    boton.addEventListener('click', function () {
        if (!navigator.geolocation) { estado.textContent = 'Tu navegador no permite saber dónde estás.'; return; }
        estado.textContent = 'Buscando tu ubicación…';
        navigator.geolocation.getCurrentPosition(function (pos) {
            var punto = [pos.coords.latitude, pos.coords.longitude];
            if (yo) yo.remove();
            yo = L.circle(punto, { radius: Math.max(pos.coords.accuracy, 30), color: '#3A2418', weight: 1, fillOpacity: 0.12 }).addTo(mapa);
            yo.bindTooltip('Estás aquí');
            mapa.setView(punto, 15);
        }, function (error) {
            estado.textContent = error.code === 1
                ? 'No has dado permiso para usar tu ubicación. Puedes seguir moviendo el mapa a mano.'
                : 'No se pudo saber tu ubicación.';
        }, { timeout: 10000 });
    });
})();
