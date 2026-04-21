// ADAC proxy Edge Function
//
// Fetches pages from adac.de on behalf of the Daytona-hosted backend, which
// can't reach adac.de directly due to an outbound allowlist. Deno runtime
// on Supabase's edge has no such restriction.
//
// Usage:
//   GET {FN_URL}?url=https://www.adac.de/rund-ums-fahrzeug/autokatalog/marken-modelle/bmw/x5/
//
// Auth:
//   Requires `Authorization: Bearer <SUPABASE_ANON_OR_SERVICE_KEY>` header
//   (enforced automatically by Supabase's function gateway).

const ADAC_HOST = "www.adac.de";

const BROWSER_HEADERS: Record<string, string> = {
  "User-Agent":
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " +
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
  "Accept-Language": "de-DE,de;q=0.9",
  "Accept":
    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
};

const CORS_HEADERS: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "authorization, content-type",
};

Deno.serve(async (req: Request): Promise<Response> => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: CORS_HEADERS });
  }

  const params = new URL(req.url).searchParams;
  const target = params.get("url");

  if (!target) {
    return new Response(JSON.stringify({ error: "missing url param" }), {
      status: 400,
      headers: { "content-type": "application/json", ...CORS_HEADERS },
    });
  }

  let parsed: URL;
  try {
    parsed = new URL(target);
  } catch {
    return new Response(JSON.stringify({ error: "invalid url" }), {
      status: 400,
      headers: { "content-type": "application/json", ...CORS_HEADERS },
    });
  }

  if (parsed.host !== ADAC_HOST) {
    return new Response(
      JSON.stringify({ error: `host not allowed: ${parsed.host}` }),
      {
        status: 403,
        headers: { "content-type": "application/json", ...CORS_HEADERS },
      },
    );
  }

  const upstream = await fetch(parsed.toString(), {
    headers: BROWSER_HEADERS,
    redirect: "follow",
  });

  const body = await upstream.text();
  return new Response(body, {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") ?? "text/html; charset=utf-8",
      "cache-control": "public, max-age=3600",
      ...CORS_HEADERS,
    },
  });
});
