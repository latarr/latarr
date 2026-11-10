// Stremio Protocol v3 Router para Cloudflare Pages Functions
// LATARR PRO: Películas, Series y Anime con Subtítulos en Español y múltiples calidades

const MANIFEST = {
  id: "org.latarr.pro",
  version: "2.0.0",
  name: "LATARR PRO",
  description: "Películas, Series y Anime con Subtítulos en Español y Audio Dual",
  logo: "https://latarr-pro.pages.dev/icon.png",
  background: "https://latarr-pro.pages.dev/hero.jpg",
  resources: ["catalog", "meta", "stream"],
  types: ["movie", "series"],
  idPrefixes: ["tmdb", "tt"],
  catalogs: [
    {
      type: "movie",
      id: "latarr_movies",
      name: "🎬 Películas LATARR",
      extra: [
        {
          name: "genre",
          options: [
            "Accion",
            "Aventura",
            "Ciencia Ficcion",
            "Comedia",
            "Crimen",
            "Drama",
            "Familia",
            "Fantasia",
            "Terror",
            "Suspenso",
            "Romance",
            "Animacion",
            "Documental",
            "Belica",
            "Historia",
            "Musica",
            "Western"
          ]
        },
        { name: "skip", isRequired: false },
        { name: "search", isRequired: false }
      ]
    },
    {
      type: "series",
      id: "latarr_series",
      name: "📺 Series LATARR",
      extra: [
        {
          name: "genre",
          options: [
            "Accion",
            "Animacion",
            "Ciencia Ficcion",
            "Comedia",
            "Crimen",
            "Drama",
            "Documental",
            "Otros"
          ]
        },
        { name: "skip", isRequired: false },
        { name: "search", isRequired: false }
      ]
    },
    {
      type: "series",
      id: "latarr_anime",
      name: "⛩️ Anime LATARR",
      extra: [
        { name: "skip", isRequired: false },
        { name: "search", isRequired: false }
      ]
    }
  ]
};

const DEFAULT_TRACKERS = [
  "tracker:udp://tracker.opentrackr.org:1337/announce",
  "tracker:udp://open.stealth.si:80/announce",
  "tracker:udp://tracker.openbittorrent.com:6969/announce",
  "tracker:udp://tracker.openbittorrent.com:80/announce",
  "tracker:udp://exodus.desync.com:6969/announce",
  "tracker:udp://tracker.torrent.eu.org:451/announce",
  "tracker:udp://explodie.org:6969/announce",
  "tracker:udp://tracker.cyberia.is:6969/announce",
  "tracker:udp://p4p.arenabg.com:1337/announce",
  "tracker:udp://tracker.tiny-vps.com:6969/announce"
];

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Headers": "*",
      "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
      "Cache-Control": "public, max-age=1800"
    }
  });
}

function normalizeText(text) {
  if (!text) return "";
  return text
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function parseMagnet(magnet) {
  if (!magnet || typeof magnet !== "string") return null;
  const hashMatch = magnet.match(/urn:btih:([a-zA-Z0-9]{40})/i);
  if (!hashMatch) return null;
  const infoHash = hashMatch[1].toLowerCase();

  const trackers = new Set(DEFAULT_TRACKERS);
  const trMatches = magnet.matchAll(/[?&]tr=([^&]+)/gi);
  for (const match of trMatches) {
    try {
      const decoded = decodeURIComponent(match[1]);
      if (decoded.startsWith("http://") || decoded.startsWith("https://") || decoded.startsWith("udp://")) {
        trackers.add("tracker:" + decoded);
      }
    } catch (e) {}
  }

  return {
    infoHash,
    sources: Array.from(trackers)
  };
}

function determineAudio(audioStr, titleStr) {
  const text = (audioStr + " " + titleStr).toLowerCase();
  if (text.includes("latino") && (text.includes("dual") || text.includes("multi") || text.includes("eng"))) {
    return "Dual (Latino / VO)";
  }
  if (text.includes("latino")) {
    return "Audio Latino";
  }
  if (text.includes("castellano") || text.includes("spanish")) {
    return "Castellano";
  }
  return "Sub Español";
}

function normalizeQuality(q) {
  const norm = (q || "").toUpperCase();
  if (norm.includes("4K") || norm.includes("2160")) return "4K UHD";
  if (norm.includes("1080")) return "1080p FHD";
  if (norm.includes("720")) return "720p HD";
  return "HD";
}

function getQualityRank(q) {
  if (q.includes("4K")) return 3;
  if (q.includes("1080")) return 2;
  if (q.includes("720")) return 1;
  return 0;
}

async function fetchAssetJson(context, path) {
  try {
    const assetUrl = new URL(path, context.request.url);
    const res = context.env.ASSETS
      ? await context.env.ASSETS.fetch(assetUrl)
      : await fetch(assetUrl);
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    return null;
  }
}

export async function onRequest(context) {
  const { request } = context;
  const url = new URL(request.url);

  // 1. Manejo de preflight CORS (OPTIONS)
  if (request.method === "OPTIONS") {
    return new Response(null, {
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "*",
        "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS"
      }
    });
  }

  let pathname = decodeURIComponent(url.pathname);
  if (pathname.startsWith("/prueba/")) {
    pathname = pathname.substring(7);
  } else if (pathname === "/prueba") {
    pathname = "/manifest.json";
  }
  if (!pathname.startsWith("/")) pathname = "/" + pathname;

  // 2. MANIFEST
  if (pathname === "/manifest.json" || pathname === "/") {
    return jsonResponse(MANIFEST);
  }

  // 3. CATALOG
  const catalogMatch = pathname.match(/^\/catalog\/([^\/]+)\/([^\/]+)(?:\/(.+))?$/);
  if (catalogMatch) {
    const catType = catalogMatch[1];
    const catId = catalogMatch[2].replace(/\.json$/, "");
    const extraRaw = catalogMatch[3] ? catalogMatch[3].replace(/\.json$/, "") : "";

    const extra = {};
    if (extraRaw) {
      const pairs = extraRaw.split("&");
      for (const pair of pairs) {
        const idx = pair.indexOf("=");
        if (idx !== -1) {
          const k = pair.substring(0, idx);
          const v = decodeURIComponent(pair.substring(idx + 1));
          extra[k] = v;
        }
      }
    }

    let items = [];
    if (catId === "latarr_movies") {
      if (!extra.genre && !extra.search && (!extra.skip || parseInt(extra.skip) === 0)) {
        items = (await fetchAssetJson(context, "/top_movies.json")) || [];
      } else {
        items = (await fetchAssetJson(context, "/peliculas.json")) || [];
      }
    } else if (catId === "latarr_series") {
      if (!extra.genre && !extra.search && (!extra.skip || parseInt(extra.skip) === 0)) {
        items = (await fetchAssetJson(context, "/top_series.json")) || [];
      } else {
        items = (await fetchAssetJson(context, "/series.json")) || [];
      }
    } else if (catId === "latarr_anime") {
      if (!extra.search && (!extra.skip || parseInt(extra.skip) === 0)) {
        items = (await fetchAssetJson(context, "/top_anime.json")) || [];
      } else {
        items = (await fetchAssetJson(context, "/anime.json")) || [];
      }
    } else {
      return jsonResponse({ metas: [] });
    }

    // Filtrar por género
    if (extra.genre && extra.genre !== "Todos") {
      const targetGenre = normalizeText(extra.genre);
      items = items.filter(i => normalizeText(i.genre) === targetGenre);
    }

    // Filtrar por búsqueda
    if (extra.search) {
      const q = normalizeText(extra.search);
      items = items.filter(i => {
        const title = normalizeText(i.clean_title || i.title || "");
        return title.includes(q);
      });
    }

    // Paginación
    const skip = parseInt(extra.skip) || 0;
    const page = items.slice(skip, skip + 50);

    const metas = page.map(i => ({
      id: "tmdb:" + i.tmdb_id,
      type: catId === "latarr_movies" ? "movie" : "series",
      name: (i.clean_title || i.title || "Sin título") + (i.year ? ` (${i.year})` : ""),
      poster: i.poster_path ? `https://image.tmdb.org/t/p/w500${i.poster_path}` : undefined,
      background: i.poster_path ? `https://image.tmdb.org/t/p/original${i.poster_path}` : undefined,
      description: i.overview || "",
      genres: i.genre ? [i.genre] : [],
      releaseInfo: i.year ? String(i.year) : undefined,
      imdbRating: i.rating ? String(Number(i.rating).toFixed(1)) : undefined
    }));

    return jsonResponse({ metas });
  }

  // 4. META
  const metaMatch = pathname.match(/^\/meta\/([^\/]+)\/([^\/]+)\.json$/);
  if (metaMatch) {
    const type = metaMatch[1];
    const rawId = metaMatch[2];

    let tmdbId = null;
    if (rawId.startsWith("tmdb:")) {
      tmdbId = rawId.substring(5);
    } else if (rawId.startsWith("tt")) {
      try {
        const cRes = await fetch(`https://v3-cinemeta.strem.io/meta/${type}/${rawId}.json`);
        if (cRes.ok) {
          const cData = await cRes.json();
          const targetTitle = cData.meta && cData.meta.name;
          const targetYear = cData.meta && cData.meta.year;
          if (targetTitle) {
            const norm = normalizeText(targetTitle);
            const listFile = type === "movie" ? "/peliculas.json" : "/series.json";
            let catalogList = (await fetchAssetJson(context, listFile)) || [];
            let match = catalogList.find(m => normalizeText(m.clean_title || m.title) === norm && (!targetYear || String(m.year) === String(targetYear)));
            if (!match) match = catalogList.find(m => normalizeText(m.clean_title || m.title) === norm);
            if (!match && type === "series") {
              const animeList = (await fetchAssetJson(context, "/anime.json")) || [];
              match = animeList.find(m => normalizeText(m.clean_title || m.title) === norm);
            }
            if (match) tmdbId = String(match.tmdb_id);
          }
        }
      } catch (e) {}
    }

    if (!tmdbId) {
      return jsonResponse({ meta: null });
    }

    if (type === "movie") {
      const data = await fetchAssetJson(context, `/links/movies/${tmdbId}.json`);
      if (data && data.metadata) {
        const m = data.metadata;
        return jsonResponse({
          meta: {
            id: "tmdb:" + tmdbId,
            type: "movie",
            name: (m.clean_title || m.title || "Película") + (m.year ? ` (${m.year})` : ""),
            poster: m.poster_path ? `https://image.tmdb.org/t/p/w500${m.poster_path}` : undefined,
            background: m.poster_path ? `https://image.tmdb.org/t/p/original${m.poster_path}` : undefined,
            description: m.overview || "",
            genres: m.genre ? [m.genre] : [],
            releaseInfo: m.year ? String(m.year) : undefined,
            imdbRating: m.rating ? String(Number(m.rating).toFixed(1)) : undefined
          }
        });
      }
    } else if (type === "series") {
      let data = await fetchAssetJson(context, `/links/series/${tmdbId}.json`);
      if (!data) {
        data = await fetchAssetJson(context, `/links/anime/${tmdbId}.json`);
      }
      if (data && data.metadata) {
        const m = data.metadata;
        const seen = new Set();
        const videos = [];
        for (const ep of (data.episodes || [])) {
          const s = parseInt(ep.season) || 1;
          const e = parseInt(ep.episode) || 1;
          const key = `${s}:${e}`;
          if (!seen.has(key)) {
            seen.add(key);
            videos.push({
              id: `tmdb:${tmdbId}:${s}:${e}`,
              title: `Temporada ${s} · Episodio ${e}`,
              season: s,
              episode: e
            });
          }
        }
        videos.sort((a, b) => a.season !== b.season ? a.season - b.season : a.episode - b.episode);
        return jsonResponse({
          meta: {
            id: "tmdb:" + tmdbId,
            type: "series",
            name: (m.clean_title || m.title || "Serie") + (m.year ? ` (${m.year})` : ""),
            poster: m.poster_path ? `https://image.tmdb.org/t/p/w500${m.poster_path}` : undefined,
            background: m.poster_path ? `https://image.tmdb.org/t/p/original${m.poster_path}` : undefined,
            description: m.overview || "",
            genres: m.genre ? [m.genre] : [],
            releaseInfo: m.year ? String(m.year) : undefined,
            imdbRating: m.rating ? String(Number(m.rating).toFixed(1)) : undefined,
            videos
          }
        });
      }
    }

    return jsonResponse({ meta: null });
  }

  // 5. STREAM
  const streamMatch = pathname.match(/^\/stream\/([^\/]+)\/([^\/]+)\.json$/);
  if (streamMatch) {
    const type = streamMatch[1];
    const rawId = streamMatch[2];

    let tmdbId = null;
    let targetSeason = 1;
    let targetEpisode = 1;

    if (rawId.startsWith("tmdb:")) {
      const parts = rawId.split(":");
      tmdbId = parts[1];
      if (parts.length >= 4) {
        targetSeason = parseInt(parts[2]) || 1;
        targetEpisode = parseInt(parts[3]) || 1;
      }
    } else if (rawId.startsWith("tt")) {
      const parts = rawId.split(":");
      const imdbId = parts[0];
      if (parts.length >= 3) {
        targetSeason = parseInt(parts[1]) || 1;
        targetEpisode = parseInt(parts[2]) || 1;
      }
      try {
        const cRes = await fetch(`https://v3-cinemeta.strem.io/meta/${type}/${imdbId}.json`);
        if (cRes.ok) {
          const cData = await cRes.json();
          const targetTitle = cData.meta && cData.meta.name;
          const targetYear = cData.meta && cData.meta.year;
          if (targetTitle) {
            const norm = normalizeText(targetTitle);
            const listFile = type === "movie" ? "/peliculas.json" : "/series.json";
            let catalogList = (await fetchAssetJson(context, listFile)) || [];
            let match = catalogList.find(m => normalizeText(m.clean_title || m.title) === norm && (!targetYear || String(m.year) === String(targetYear)));
            if (!match) match = catalogList.find(m => normalizeText(m.clean_title || m.title) === norm);
            if (!match && type === "series") {
              const animeList = (await fetchAssetJson(context, "/anime.json")) || [];
              match = animeList.find(m => normalizeText(m.clean_title || m.title) === norm);
            }
            if (match) tmdbId = String(match.tmdb_id);
          }
        }
      } catch (e) {}
    }

    if (!tmdbId) {
      return jsonResponse({ streams: [] });
    }

    let links = [];
    if (type === "movie") {
      const data = await fetchAssetJson(context, `/links/movies/${tmdbId}.json`);
      if (data && data.links) {
        links = data.links;
      }
    } else if (type === "series") {
      let data = await fetchAssetJson(context, `/links/series/${tmdbId}.json`);
      if (!data) {
        data = await fetchAssetJson(context, `/links/anime/${tmdbId}.json`);
      }
      if (data && data.episodes) {
        links = data.episodes.filter(
          ep => (parseInt(ep.season) || 1) === targetSeason && (parseInt(ep.episode) || 1) === targetEpisode
        );
      }
    }

    const streams = [];
    for (const link of links) {
      const parsed = parseMagnet(link.magnet);
      if (!parsed || !parsed.infoHash) continue;

      const quality = normalizeQuality(link.quality || "");
      const audio = determineAudio(link.audio || "", link.title || "");
      const sizeStr = link.size ? ` · 💾 ${link.size}` : "";
      const seedsStr = link.seeds !== undefined ? `\n👤 ${link.seeds} semillas` : "";
      const cleanTitle = link.clean_title || link.title || "";

      streams.push({
        name: `LATARR PRO\n${quality}`,
        title: `⚡ ${quality} | ${audio}${sizeStr}${seedsStr}\n📄 ${link.title || cleanTitle}`,
        infoHash: parsed.infoHash,
        sources: parsed.sources,
        _seeds: parseInt(link.seeds) || 0,
        _qualityRank: getQualityRank(quality)
      });
    }

    // Ordenar: Calidad (4K > 1080p > 720p) y luego por Semillas desc
    streams.sort((a, b) => {
      if (b._qualityRank !== a._qualityRank) {
        return b._qualityRank - a._qualityRank;
      }
      return b._seeds - a._seeds;
    });

    const cleanedStreams = streams.slice(0, 10).map(s => {
      const { _seeds, _qualityRank, ...rest } = s;
      return rest;
    });

    return jsonResponse({ streams: cleanedStreams });
  }

  // 6. Si no es una ruta de Stremio, pasar la petición al servidor de estáticos de Cloudflare Pages
  return context.next();
}
