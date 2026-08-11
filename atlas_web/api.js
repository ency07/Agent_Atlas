/**
 * Atlas API — Wrapper fino entre la UI y opencode serve.
 *
 * Encapsula todas las llamadas HTTP a opencode serve en un solo módulo.
 * Si el server cambia de versión o migramos a ventana nativa/terminal,
 * solo se toca este archivo (nunca la lógica de la UI).
 *
 * Uso:
 *   <script src="api.js"></script>
 *   const info = await AtlasAPI.health();
 *   const session = await AtlasAPI.createSession();
 *
 * Endpoints cubiertos:
 *   /config          → estado del server
 *   /session         → crear/listar sesiones
 *   /session/:id     → detalle de sesión
 */
const AtlasAPI = (() => {
    let _base = '';

    function _url(path) {
        return `${_base}${path}`;
    }

    async function _fetch(path, opts = {}) {
        const resp = await fetch(_url(path), {
            headers: { 'Content-Type': 'application/json', ...opts.headers },
            ...opts,
        });
        if (!resp.ok) throw new Error(`AtlasAPI ${resp.status}: ${resp.statusText}`);
        return resp.json();
    }

    return {
        /**
         * Inicializa el wrapper con la base URL del server.
         * Si no se llama, usa la misma origin del browser.
         */
        init(baseUrl) {
            _base = baseUrl || '';
        },

        /** Estado del server (config, modelo activo). */
        async config() {
            return _fetch('/config');
        },

        /** Crear una nueva sesión de chat. */
        async createSession() {
            return _fetch('/session', { method: 'POST', body: '{}' });
        },

        /** Listar sesiones recientes. */
        async sessions() {
            return _fetch('/sessions');
        },

        /** Detalle de una sesión. */
        async session(id) {
            return _fetch(`/session/${id}`);
        },

        /**
         * Enviar un mensaje a una sesión.
         * @param {string} sessionId
         * @param {string} text
         */
        async sendMessage(sessionId, text) {
            return _fetch(`/session/${sessionId}/message`, {
                method: 'POST',
                body: JSON.stringify({ parts: [{ type: 'text', text }] }),
            });
        },

        /** URL directa a una sesión (para navegación). */
        sessionUrl(port, sessionId) {
            const b64 = btoa(`http://127.0.0.1:${port}`).replace(/=/g, '');
            return `http://127.0.0.1:${port}/server/${b64}/session/${sessionId}`;
        },
    };
})();

if (typeof module !== 'undefined') module.exports = AtlasAPI;
