/* ============================================================
   ARGO — service worker minimale (companion mobile / PWA)
   Strategia:
     - shell (/, index, flotta, manifest): cache-first, con
       aggiornamento in background.
     - API (richieste POST o percorsi dinamici): sempre rete,
       mai cache, così i dati restano reali e freschi.
   Degrada con grazia: se la rete manca, prova la cache; se
   anche quella manca, lascia fallire la richiesta senza rompere.
   ============================================================ */

const CACHE = "argo-shell-v1";

// Shell statica da precaricare. Solo file che esistono di sicuro.
const SHELL = [
  "/",
  "/index.html",
  "/manifest.webmanifest"
];

self.addEventListener("install", (event) => {
  // Precarica la shell; ignora i singoli fallimenti per non bloccare l'install.
  event.waitUntil(
    caches.open(CACHE).then((cache) =>
      Promise.allSettled(SHELL.map((u) => cache.add(u)))
    ).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  // Pulisce le cache vecchie e prende subito il controllo.
  event.waitUntil(
    caches.keys().then((chiavi) =>
      Promise.all(chiavi.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// Percorsi che sono "shell" (HTML/PWA), da servire cache-first.
function isShell(url) {
  const p = url.pathname;
  return p === "/" ||
         p === "/index.html" ||
         p === "/flotta.html" ||
         p === "/flotta/console" ||
         p === "/manifest.webmanifest";
}

self.addEventListener("fetch", (event) => {
  const req = event.request;

  // Solo GET viene gestito; le POST (chat, voce, conferma…) vanno sempre in rete.
  if (req.method !== "GET") return;

  const url = new URL(req.url);

  // Solo stessa origine: non intercettiamo risorse esterne.
  if (url.origin !== self.location.origin) return;

  if (isShell(url)) {
    // Cache-first con refresh in background.
    event.respondWith(
      caches.match(req).then((cached) => {
        const rete = fetch(req).then((resp) => {
          if (resp && resp.ok) {
            const copia = resp.clone();
            caches.open(CACHE).then((c) => c.put(req, copia));
          }
          return resp;
        }).catch(() => cached);
        return cached || rete;
      })
    );
    return;
  }

  // Tutto il resto (API: /stato, /eventi, /flotta, /dashboard, …):
  // sempre rete, niente cache, dati reali e freschi.
  event.respondWith(fetch(req));
});
