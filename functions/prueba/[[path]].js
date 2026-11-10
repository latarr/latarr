// Router de Stremio Protocol v3 para Cloudflare Pages
// Responde a: manifest.json, catalog, meta, stream con CORS abierto

const DATA = {
  "movies": [
    {
      "id": "tt15239678",
      "name": "Dune: Parte Dos (2024)",
      "poster": "https://image.tmdb.org/t/p/w500/8b8R8l88Qje9dn9OE8PY05Nxl1X.jpg",
      "background": "https://image.tmdb.org/t/p/w1280/xOMo8BRK7PfcJv9JCnx7s520b22.jpg",
      "description": "Paul Atreides se une a Chani y a los Fremen mientras busca venganza contra los conspiradores que destruyeron a su familia. Ante la disyuntiva de elegir entre el amor de su vida y el destino del universo conocido, emprende una misión para evitar un futuro terrible que solo él puede prever.",
      "genres": [
        "Ciencia Ficción",
        "Aventura"
      ],
      "releaseInfo": "2024",
      "imdbRating": "8.5",
      "stream": {
        "name": "LATARR Latino",
        "title": "⚡ 1080p FHD | Dual Latino/Inglés | 2.8 GB",
        "infoHash": "70d6a2f7c0a6b7e09641772648be167d4ecb3f46"
      }
    },
    {
      "id": "tt6263850",
      "name": "Deadpool & Wolverine (2024)",
      "poster": "https://image.tmdb.org/t/p/w500/8cdWjvZQUExUUTzyp4t6EDMubfO.jpg",
      "background": "https://image.tmdb.org/t/p/w1280/yDHYTjA3R0jFYba16jBB1jv82E9.jpg",
      "description": "Un apático Wade Wilson se afana en la vida civil dejando atrás sus días como Deadpool. Pero cuando su mundo se enfrenta a una amenaza existencial, Wade se ve obligado a regañadientes a ponerse el traje de nuevo junto a un aún más reticente Wolverine.",
      "genres": [
        "Acción",
        "Comedia"
      ],
      "releaseInfo": "2024",
      "imdbRating": "7.8",
      "stream": {
        "name": "LATARR Latino",
        "title": "⚡ 1080p FHD | Audio Latino | 2.5 GB",
        "infoHash": "281f6236b3b5e40e6cbb731a550eb608ca4288b3"
      }
    }
  ],
  "series": [
    {
      "id": "tt3581920",
      "name": "The Last of Us (2023)",
      "poster": "https://image.tmdb.org/t/p/w500/uKvVjK19uKnQ08a9kF3Q0qFzS4S.jpg",
      "background": "https://image.tmdb.org/t/p/w1280/2OMG0DqFvB9N284yN0vCgWz7M2u.jpg",
      "description": "Veinte años después de que la civilización moderna fuera destruida por un hongo parásito, Joel, un curtido superviviente, recibe el encargo de sacar clandestinamente a Ellie, una niña de 14 años, de una opresiva zona de cuarentena.",
      "genres": [
        "Drama",
        "Acción"
      ],
      "releaseInfo": "2023",
      "imdbRating": "8.8",
      "episodes": [
        {
          "id": "tt3581920:1:1",
          "title": "Episodio 1: Cuando te pierdes en la oscuridad",
          "season": 1,
          "episode": 1,
          "stream": {
            "name": "LATARR Latino",
            "title": "⚡ 1080p | S01E01 | Audio Latino | 1.8 GB",
            "infoHash": "9b7d8fa8f9e68b3f2db06e9871c4c1a5b4c48972"
          }
        }
      ]
    },
    {
      "id": "tt11198330",
      "name": "House of the Dragon (2022)",
      "poster": "https://image.tmdb.org/t/p/w500/7QMsOTMUswlwxJP0rTTZfmz2tX2.jpg",
      "background": "https://image.tmdb.org/t/p/w1280/etj5CuMuamBvRTA4ghGcCwhq5Qj.jpg",
      "description": "Ambientada 200 años antes de los acontecimientos de Juego de Tronos, la serie narra el principio del fin de la Casa Targaryen y los acontecimientos que condujeron a la guerra civil conocida como la 'Danza de Dragones'.",
      "genres": [
        "Fantasía",
        "Drama"
      ],
      "releaseInfo": "2022",
      "imdbRating": "8.4",
      "episodes": [
        {
          "id": "tt11198330:1:1",
          "title": "Episodio 1: Los herederos del dragón",
          "season": 1,
          "episode": 1,
          "stream": {
            "name": "LATARR Latino",
            "title": "⚡ 1080p | S01E01 | Audio Latino | 2.1 GB",
            "infoHash": "5a4f7831d3f572834b6706e23ec3665780a1c1d8"
          }
        }
      ]
    }
  ]
};

const MANIFEST = {
  "id": "org.latarr.prueba",
  "version": "1.0.0",
  "name": "LATARR PRO (Prueba)",
  "description": "Prueba de concepto de LATARR en Stremio con Películas y Series en Español Latino",
  "logo": "https://latarr-pro.pages.dev/icon.png",
  "background": "https://latarr-pro.pages.dev/hero.jpg",
  "resources": [
    "catalog",
    "meta",
    "stream"
  ],
  "types": [
    "movie",
    "series"
  ],
  "idPrefixes": [
    "tt"
  ],
  "catalogs": [
    {
      "type": "movie",
      "id": "latarr_movies",
      "name": "LATARR Películas (Prueba)"
    },
    {
      "type": "series",
      "id": "latarr_series",
      "name": "LATARR Series (Prueba)"
    }
  ]
};

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Headers": "*",
      "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
      "Cache-Control": "public, max-age=3600"
    }
  });
}

export async function onRequest(context) {
  const { request } = context;
  const url = new URL(request.url);

  // Manejo de preflight CORS (OPTIONS)
  if (request.method === "OPTIONS") {
    return new Response(null, {
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "*",
        "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS"
      }
    });
  }

  // Decodificar la ruta limpia
  let pathname = decodeURIComponent(url.pathname);
  // Quitar el prefijo /prueba si viene incluido
  if (pathname.startsWith("/prueba/")) {
    pathname = pathname.substring(7);
  } else if (pathname.startsWith("/prueba")) {
    pathname = pathname.substring(6);
  }
  if (!pathname.startsWith("/")) pathname = "/" + pathname;

  // 1. MANIFEST
  if (pathname === "/manifest.json" || pathname === "/") {
    return jsonResponse(MANIFEST);
  }

  // 2. CATALOG: /catalog/{type}/{id}.json
  const catalogMatch = pathname.match(/^\/catalog\/([^\/]+)\/([^\/\.]+)(?:\.json)?$/);
  if (catalogMatch) {
    const type = catalogMatch[1];
    const catId = catalogMatch[2];

    if (type === "movie" && catId === "latarr_movies") {
      const metas = DATA.movies.map(m => ({
        id: m.id,
        type: "movie",
        name: m.name,
        poster: m.poster,
        background: m.background,
        description: m.description,
        genres: m.genres,
        releaseInfo: m.releaseInfo,
        imdbRating: m.imdbRating
      }));
      return jsonResponse({ metas });
    }

    if (type === "series" && catId === "latarr_series") {
      const metas = DATA.series.map(s => ({
        id: s.id,
        type: "series",
        name: s.name,
        poster: s.poster,
        background: s.background,
        description: s.description,
        genres: s.genres,
        releaseInfo: s.releaseInfo,
        imdbRating: s.imdbRating
      }));
      return jsonResponse({ metas });
    }

    return jsonResponse({ metas: [] });
  }

  // 3. META: /meta/{type}/{id}.json
  const metaMatch = pathname.match(/^\/meta\/([^\/]+)\/([^\/\.]+)(?:\.json)?$/);
  if (metaMatch) {
    const type = metaMatch[1];
    const id = metaMatch[2];

    if (type === "movie") {
      const item = DATA.movies.find(m => m.id === id);
      if (item) {
        return jsonResponse({
          meta: {
            id: item.id,
            type: "movie",
            name: item.name,
            poster: item.poster,
            background: item.background,
            description: item.description,
            genres: item.genres,
            releaseInfo: item.releaseInfo,
            imdbRating: item.imdbRating
          }
        });
      }
    }

    if (type === "series") {
      const item = DATA.series.find(s => s.id === id);
      if (item) {
        return jsonResponse({
          meta: {
            id: item.id,
            type: "series",
            name: item.name,
            poster: item.poster,
            background: item.background,
            description: item.description,
            genres: item.genres,
            releaseInfo: item.releaseInfo,
            imdbRating: item.imdbRating,
            videos: item.episodes.map(ep => ({
              id: ep.id,
              title: ep.title,
              season: ep.season,
              episode: ep.episode,
              released: new Date().toISOString()
            }))
          }
        });
      }
    }

    return jsonResponse({ meta: null });
  }

  // 4. STREAM: /stream/{type}/{id}.json
  const streamMatch = pathname.match(/^\/stream\/([^\/]+)\/([^\/\.]+)(?:\.json)?$/);
  if (streamMatch) {
    const type = streamMatch[1];
    const id = streamMatch[2];

    if (type === "movie") {
      const item = DATA.movies.find(m => m.id === id);
      if (item && item.stream) {
        return jsonResponse({ streams: [item.stream] });
      }
    }

    if (type === "series") {
      // Buscar en los episodios de todas las series
      for (const s of DATA.series) {
        const ep = s.episodes.find(e => e.id === id);
        if (ep && ep.stream) {
          return jsonResponse({ streams: [ep.stream] });
        }
      }
    }

    return jsonResponse({ streams: [] });
  }

  return new Response("Not Found", { status: 404 });
}
