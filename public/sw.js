// Educa Já — service worker: o app abre sem internet com os últimos dados vistos.
// Rede primeiro (com cache: "no-cache" para conferir versão nova a cada abertura); cache se offline.
const VERSAO = "educaja-v12";
const BASE = ["./", "index.html", "manifest.webmanifest", "icon.svg", "icon-192.png", "icon-512.png", "apple-touch-icon.png",
  "data/municipios.json", "data/escolas/meta.json"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(VERSAO).then(c => c.addAll(BASE).catch(() => {})).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== VERSAO).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

async function redePrimeiro(req){
  const c = await caches.open(VERSAO);
  try {
    const r = await fetch(req, {cache: "no-cache"});
    if (r.ok) c.put(req, r.clone());
    return r;
  } catch {
    const r = await c.match(req, {ignoreSearch: true});
    if (r) return r;
    throw new Error("offline");
  }
}

self.addEventListener("fetch", e => {
  if (e.request.method !== "GET") return;
  const url = new URL(e.request.url);
  if (url.origin === location.origin || url.hostname.endsWith("gstatic.com") || url.hostname.endsWith("googleapis.com")
      || url.hostname.endsWith("cloudflare.com"))
    e.respondWith(redePrimeiro(e.request));
});
