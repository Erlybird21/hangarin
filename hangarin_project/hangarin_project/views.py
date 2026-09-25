"""Site-level views: PWA manifest, service worker, offline fallback.

These are deliberately separate from the `tasks` app: they describe the
whole Hangarin site, not user task data. None of these views require
authentication and none expose private data.
"""

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.templatetags.static import static

CACHE_VERSION = "hangarin-v1"


def manifest(request):
    """Serve the Web App Manifest as JSON."""
    return JsonResponse(
        {
            "name": "Hangarin",
            "short_name": "Hangarin",
            "description": "Hangarin is a task and todo management "
            "application for tracking tasks, subtasks, and notes.",
            "start_url": "/tasks/",
            "display": "standalone",
            "orientation": "portrait-primary",
            "background_color": "#F8FAFC",
            "theme_color": "#1E40AF",
            "icons": [
                {
                    "src": static("icons/icon-192.png"),
                    "sizes": "192x192",
                    "type": "image/png",
                },
                {
                    "src": static("icons/icon-512.png"),
                    "sizes": "512x512",
                    "type": "image/png",
                },
            ],
        },
        content_type="application/manifest+json",
    )


def service_worker(request):
    """Serve the service worker as JavaScript.

    Served from the site root (`/service-worker.js`) so its scope covers
    the Hangarin application routes. Caching policy, by design:

    * precached: offline page, stylesheet, icons, manifest (all public)
    * navigations: network first, offline fallback on failure
    * /static/* + manifest: cache first, network fallback
    * everything else (tasks, accounts, admin HTML, POSTs,
      third-party): untouched, network only — private task data is
      never written to the cache.
    """
    offline_url = "/offline/"
    css_url = static("css/hangarin.css")
    icon_192 = static("icons/icon-192.png")
    icon_512 = static("icons/icon-512.png")
    manifest_url = "/manifest.json"
    js = """\
const CACHE_NAME = '%(cache)s';
const OFFLINE_URL = '%(offline)s';
const APP_SHELL = [
  OFFLINE_URL,
  '%(css)s',
  '%(icon192)s',
  '%(icon512)s',
  '%(manifest)s',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(
        names.filter((name) => name !== CACHE_NAME).map((name) => caches.delete(name))
      )
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') {
    return;
  }
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) {
    return;
  }
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request).catch(() => caches.match(OFFLINE_URL))
    );
    return;
  }
  if (url.pathname.startsWith('/static/') || url.pathname === '%(manifest)s') {
    event.respondWith(
      caches.match(event.request).then((cached) => cached || fetch(event.request))
    );
    return;
  }
  // All other same-origin requests (tasks, accounts, admin): network only.
});
""" % {
        "cache": CACHE_VERSION,
        "offline": offline_url,
        "css": css_url,
        "icon192": icon_192,
        "icon512": icon_512,
        "manifest": manifest_url,
    }
    return HttpResponse(js, content_type="application/javascript")


def offline(request):
    """Render the offline fallback page (public, no private data)."""
    return render(request, "offline.html")
