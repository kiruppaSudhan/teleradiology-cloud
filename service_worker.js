const CACHE_NAME = "telerad-v1";
const URLS_TO_CACHE = [
  "/",
  "/dashboard",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  "/manifest.json"
];

self.addEventListener("install", function(event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function(cache) {
      return cache.addAll(URLS_TO_CACHE);
    })
  );
});

self.addEventListener("fetch", function(event) {
  event.respondWith(
    caches.match(event.request).then(function(response) {
      return response || fetch(event.request);
    })
  );
});