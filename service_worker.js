const CACHE_NAME = "teleradiology-v2";

// Only cache these static assets
const STATIC_ASSETS = [
  "/",
  "/login_page",
  "/manifest.json"
];

// Install - cache only static assets
self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

// Activate - delete old caches
self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Fetch - NEVER cache POST requests or dynamic routes
self.addEventListener("fetch", event => {
  const url = new URL(event.request.url);

  // Always go to network for POST requests (form submissions)
  if (event.request.method !== "GET") {
    event.respondWith(fetch(event.request));
    return;
  }

  // Always go to network for these dynamic routes
  const dynamicRoutes = [
    "/dashboard", "/add_patient", "/delete_patient",
    "/view", "/upload_scan", "/login", "/logout",
    "/register", "/image", "/save_annotation",
    "/machines", "/machine_chat", "/download"
  ];

  const isDynamic = dynamicRoutes.some(r => url.pathname.startsWith(r));

  if (isDynamic) {
    // Network only - never cache
    event.respondWith(fetch(event.request));
    return;
  }

  // For static assets - cache first, then network
  event.respondWith(
    caches.match(event.request).then(cached => cached || fetch(event.request))
  );
});
