// AgendaVue: SPA de agenda de contactos (Vue 2)
var CLAVE = 'agendaVue.contactos';

function cargar() {
    try {
        var d = JSON.parse(localStorage.getItem(CLAVE));
        if (Array.isArray(d)) return d;
    } catch (e) {}
    return [{ id: 1, nombre: 'John Doe', email: 'john.doe@deusto.es', telefono: '555555555' }];
}

new Vue({
    el: '#app',
    data: {
        contactos: cargar(),
        nuevo: { nombre: '', email: '', telefono: '' },
        errores: { nombre: '', email: '', telefono: '' },
        busqueda: '',
        mensaje: ''
    },
    computed: {
        filtrados: function () {
            var q = this.busqueda.toLowerCase();
            return this.contactos.filter(function (c) {
                return (c.nombre + ' ' + c.email + ' ' + c.telefono).toLowerCase().indexOf(q) !== -1;
            });
        }
    },
    watch: {
        contactos: {
            deep: true,
            immediate: true,
            handler: function (lista) {
                try { localStorage.setItem(CLAVE, JSON.stringify(lista)); } catch (e) {}
                this.actualizarJsonLd();
            }
        }
    },
    methods: {
        validar: function () {
            var n = this.nuevo, e = this.errores;
            e.nombre = n.nombre ? '' : 'El nombre es obligatorio.';
            e.email = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(n.email) ? '' : 'Introduce un email válido.';
            e.telefono = /^\+?[0-9 ]{9,15}$/.test(n.telefono) ? '' : 'Introduce un teléfono válido (9-15 dígitos).';
            return !e.nombre && !e.email && !e.telefono;
        },
        anadir: function () {
            this.mensaje = '';
            if (!this.validar()) return;
            var id = this.contactos.reduce(function (m, c) { return Math.max(m, c.id); }, 0) + 1;
            this.contactos.push({ id: id, nombre: this.nuevo.nombre, email: this.nuevo.email, telefono: this.nuevo.telefono });
            this.mensaje = 'Contacto "' + this.nuevo.nombre + '" añadido.';
            this.nuevo = { nombre: '', email: '', telefono: '' };
            $('.floating-label-form-group').removeClass('floating-label-form-group-with-value');
        },
        borrar: function (c) {
            if (confirm('¿Borrar a ' + c.nombre + '?')) {
                this.contactos = this.contactos.filter(function (x) { return x.id !== c.id; });
            }
        },
        // JSON-LD: datos estructurados generados a partir de los contactos
        actualizarJsonLd: function () {
            var el = document.getElementById('jsonld');
            if (!el) return;
            el.textContent = JSON.stringify({
                '@context': 'https://schema.org',
                '@type': 'ItemList',
                name: 'Agenda de contactos',
                numberOfItems: this.contactos.length,
                itemListElement: this.contactos.map(function (c, i) {
                    return {
                        '@type': 'ListItem',
                        position: i + 1,
                        item: { '@type': 'Person', name: c.nombre, email: c.email, telephone: c.telefono }
                    };
                })
            });
        }
    }
});
