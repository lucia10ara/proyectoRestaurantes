// Doble clic sobre la foto de una publicación = me gusta (como en Instagram).
// Cada foto va dentro de un .post-media con data-like-url (a dónde enviar el me gusta) y data-like-id.
// El doble clic solo da me gusta: para quitarlo se usa el botón del corazón.

function leerCookie(nombre) {
    var trozos = ('; ' + document.cookie).split('; ' + nombre + '=');
    return trozos.length === 2 ? trozos.pop().split(';').shift() : '';
}

document.addEventListener('dblclick', function (evento) {
    var foto = evento.target.closest('.post-media');
    if (!foto) return;
    evento.preventDefault();

    // sin sesión no se puede dar me gusta: se lleva a iniciar sesión
    if (!foto.dataset.auth) {
        window.location = foto.dataset.loginUrl;
        return;
    }

    // corazón que aparece sobre la foto (se quita y se pone la clase para poder repetir la animación)
    var corazon = foto.querySelector('.corazon');
    if (corazon) {
        corazon.classList.remove('late');
        void corazon.offsetWidth;
        corazon.classList.add('late');
    }

    var datos = new FormData();
    datos.append('solo_like', '1');
    fetch(foto.dataset.likeUrl, {
        method: 'POST',
        body: datos,
        credentials: 'same-origin',
        headers: { 'X-CSRFToken': leerCookie('csrftoken'), 'X-Requested-With': 'XMLHttpRequest' }
    })
        .then(function (r) { return r.json(); })
        .then(function (respuesta) {
            // se actualiza el botón del corazón de esa publicación sin recargar la página
            document.querySelectorAll('[data-like-boton="' + foto.dataset.likeId + '"]').forEach(function (boton) {
                boton.textContent = '♥ ' + respuesta.total;
                boton.classList.add('activo');
            });
        })
        .catch(function () { /* si falla la red no pasa nada: el botón del corazón sigue funcionando */ });
});
