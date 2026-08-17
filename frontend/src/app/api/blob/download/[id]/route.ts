import { issueSignedToken, presignUrl } from "@vercel/blob";

export const runtime = "nodejs";

/** Authorize an attachment, then redirect to a five-minute private Blob URL. */
export async function GET(
  request: Request,
  { params }: { params: { id: string } },
): Promise<Response> {
  const authorization = request.headers.get("authorization");
  const backend = process.env.NEXT_PUBLIC_API_URL;
  if (!authorization) {
    return Response.json({ detail: "authentication required" }, { status: 401 });
  }
  if (!backend || !process.env.BLOB_READ_WRITE_TOKEN) {
    return Response.json(
      { detail: "Vercel Blob downloads are not configured" },
      { status: 503 },
    );
  }
  if (!/^\d+$/.test(params.id)) {
    return Response.json({ detail: "invalid attachment id" }, { status: 400 });
  }

  try {
    const access = await fetch(
      `${backend}/api/uploads/${params.id}/blob-access`,
      {
        headers: { Authorization: authorization },
        cache: "no-store",
      },
    );
    if (access.status === 401) {
      return Response.json({ detail: "authentication required" }, { status: 401 });
    }
    if (!access.ok) {
      return Response.json({ detail: "attachment not found" }, { status: 404 });
    }
    const { url } = (await access.json()) as { url: string };
    const pathname = new URL(url).pathname.replace(/^\//, "");
    const validUntil = Date.now() + 5 * 60 * 1000;
    const signed = await issueSignedToken({
      pathname,
      operations: ["get"],
      validUntil,
    });
    const { presignedUrl } = await presignUrl(signed, {
      operation: "get",
      pathname,
      access: "private",
      validUntil,
    });
    return Response.redirect(presignedUrl, 307);
  } catch (error) {
    console.error("Blob download signing error", error);
    return Response.json({ detail: "attachment unavailable" }, { status: 503 });
  }
}
