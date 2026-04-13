const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8003/api";

const INTERNAL_MEDIA_HOSTS = new Set(["localhost", "127.0.0.1", "backend"]);

function getApiOrigin(): string {
  try {
    return new URL(API_BASE_URL).origin;
  } catch {
    return "";
  }
}

export function normalizeMediaUrl(url?: string | null): string {
  const value = url?.trim();
  if (!value) {
    return "";
  }

  const apiOrigin = getApiOrigin();
  if (!apiOrigin) {
    return value;
  }

  if (value.startsWith("/")) {
    return new URL(value, apiOrigin).toString();
  }

  try {
    const parsedUrl = new URL(value);
    const apiUrl = new URL(apiOrigin);
    const isMediaPath = parsedUrl.pathname.startsWith("/media/");
    const usesInternalMediaHost = INTERNAL_MEDIA_HOSTS.has(parsedUrl.hostname);
    const usesWrongScheme = parsedUrl.hostname === apiUrl.hostname && parsedUrl.protocol !== apiUrl.protocol;

    if (isMediaPath && (usesInternalMediaHost || usesWrongScheme)) {
      return new URL(
        `${parsedUrl.pathname}${parsedUrl.search}${parsedUrl.hash}`,
        apiOrigin
      ).toString();
    }

    return parsedUrl.toString();
  } catch {
    return value;
  }
}
