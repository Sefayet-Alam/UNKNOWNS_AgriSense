import { handleUpload, type HandleUploadBody } from "@vercel/blob/client";

export const runtime = "nodejs";

const ALLOWED_CONTENT_TYPES = [
  "image/jpeg",
  "image/jpg",
  "image/png",
  "image/webp",
  "audio/mpeg",
  "audio/mp3",
  "audio/mp4",
  "audio/ogg",
  "audio/wav",
  "audio/x-wav",
  "audio/webm",
];

/** Issue a tightly scoped Vercel Blob client-upload token after API auth. */
export async function POST(request: Request): Promise<Response> {
  const authorization = request.headers.get("authorization");
  const backend = process.env.NEXT_PUBLIC_API_URL;
  if (!authorization) {
    return Response.json({ detail: "authentication required" }, { status: 401 });
  }
  if (!backend || !process.env.BLOB_READ_WRITE_TOKEN) {
    return Response.json(
      { detail: "Vercel Blob uploads are not configured" },
      { status: 503 },
    );
  }

  try {
    const body = (await request.json()) as HandleUploadBody;
    const result = await handleUpload({
      body,
      request,
      onBeforeGenerateToken: async (pathname) => {
        // Validate the AgriSense access token against the backend rather than
        // sharing JWT_SECRET_KEY with the frontend project.
        const me = await fetch(`${backend}/api/auth/me`, {
          headers: { Authorization: authorization },
          cache: "no-store",
        });
        if (!me.ok) throw new Error("invalid AgriSense access token");
        const user = (await me.json()) as { id: number };
        if (!pathname.startsWith(`uploads/${user.id}/`)) {
          throw new Error("upload path does not belong to this user");
        }
        return {
          allowedContentTypes: ALLOWED_CONTENT_TYPES,
          maximumSizeInBytes: 10 * 1024 * 1024,
          addRandomSuffix: false,
          allowOverwrite: false,
          tokenPayload: String(user.id),
        };
      },
    });
    return Response.json(result);
  } catch (error) {
    console.error("Blob upload token error", error);
    return Response.json({ detail: "upload authorization failed" }, { status: 400 });
  }
}
