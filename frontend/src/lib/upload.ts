// Attachment model + the "send to backend" upload function.
// STUB: the backend upload endpoint doesn't exist yet — uploadAttachment returns a
// local object URL so the demo works. The REAL multipart shape is kept below so M5
// is a one-line swap once the backend adds POST /api/chat/upload.

export type AttachmentKind = "image" | "document";

export interface Attachment {
  id: string;
  file: File;
  name: string;
  kind: AttachmentKind;
  size: number;
  previewUrl?: string; // object URL for images
  remoteUrl?: string; // set after upload
}

export function isImage(file: File): boolean {
  return file.type.startsWith("image/");
}

let _seq = 0;
export function toAttachment(file: File): Attachment {
  const kind: AttachmentKind = isImage(file) ? "image" : "document";
  return {
    id: `att-${++_seq}-${file.size}`,
    file,
    name: file.name,
    kind,
    size: file.size,
    previewUrl: kind === "image" ? URL.createObjectURL(file) : undefined,
  };
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Send an attachment to the backend and return its stored URL.
 * STUB: no backend endpoint yet → resolves to the local object URL.
 */
export async function uploadAttachment(att: Attachment): Promise<string> {
  // REAL SHAPE (M5 — wire when the backend adds the endpoint):
  //   const fd = new FormData();
  //   fd.append("file", att.file);
  //   const res = await apiFetch("/api/chat/upload", { method: "POST", body: fd, headers: {} });
  //   if (!res.ok) throw new ApiError(res.status, "Upload failed");
  //   return (await res.json()).url as string;
  await new Promise((r) => setTimeout(r, 400)); // simulate the round-trip
  return att.previewUrl ?? "stub://uploaded/" + att.id;
}
