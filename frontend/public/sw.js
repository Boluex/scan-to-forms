/* One service worker for the offline shell and FCM data messages. */
const CACHE = "scanforms-static-v1";
const SHELL = ["/offline.html", "/icon-192.png", "/icon-512.png"];
self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)));
});
self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(
        keys
          .filter((key) => key.startsWith("scanforms-") && key !== CACHE)
          .map((key) => caches.delete(key)),
      );
      await self.clients.claim();
    })(),
  );
});
self.addEventListener("fetch", (event) => {
  const request = event.request,
    url = new URL(request.url);
  if (
    request.method !== "GET" ||
    url.origin !== self.location.origin ||
    request.headers.has("Authorization")
  )
    return;
  // Never cache API responses, RSC payloads, account HTML, uploads or downloads.
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() => caches.match("/offline.html")),
    );
    return;
  }
  const immutableAsset =
    url.pathname.startsWith("/_next/static/") &&
    /[a-f0-9]{8,}\.(?:js|css|woff2?)$/.test(url.pathname);
  const staticAsset = SHELL.includes(url.pathname) || immutableAsset;
  if (!staticAsset) return;
  event.respondWith(
    (async () => {
      const cache = await caches.open(CACHE);
      const cached = await cache.match(request);
      if (cached) return cached;
      const response = await fetch(request);
      if (response.ok && response.type === "basic") {
        await cache.put(request, response.clone());
        const keys = await cache.keys();
        const assets = keys.filter(
          (key) => !SHELL.includes(new URL(key.url).pathname),
        );
        if (assets.length > 100) await cache.delete(assets[0]);
      }
      return response;
    })(),
  );
});
self.addEventListener("push", (event) => {
  event.waitUntil(
    (async () => {
      let payload;
      try {
        payload = event.data?.json();
      } catch {
        return;
      }
      const data = payload?.data;
      if (!data) return;
      const windows = await self.clients.matchAll({
        type: "window",
        includeUncontrolled: true,
      });
      windows.forEach((client) => client.postMessage({ type: "notification" }));
      await self.registration.showNotification(
        data.title || "ScanToForms update",
        {
          body: data.body || "You have a new update.",
          icon: "/icon-192.png",
          badge: "/icon-192.png",
          tag: data.notification_id || "scanforms",
          data: { url: "/notifications" },
        },
      );
    })(),
  );
});
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    (async () => {
      const target = new URL("/notifications", self.location.origin).href;
      const windows = await self.clients.matchAll({
        type: "window",
        includeUncontrolled: true,
      });
      for (const client of windows) {
        if (
          new URL(client.url).origin === self.location.origin &&
          "focus" in client
        ) {
          await client.navigate(target);
          return client.focus();
        }
      }
      return self.clients.openWindow(target);
    })(),
  );
});
